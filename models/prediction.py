import datetime
from typing import Dict, List, Set, Optional
from decimal import Decimal
import asyncio

class DatabasePrediction:
    """Database-backed Prediction class that replaces the in-memory version"""
    
    def __init__(self, prediction_data: Dict, db_manager, cog):
        # Core prediction data from database
        self.id = str(prediction_data['id'])
        self.guild_id = prediction_data['guild_id']
        self.question = prediction_data['question']
        self.options = prediction_data['options']
        self.creator_id = prediction_data['creator_id']
        self.category = prediction_data.get('category')
        self.end_time = prediction_data['end_time']
        self.created_at = prediction_data['created_at']
        
        # Status fields
        self.status = prediction_data['status']
        self.resolved = prediction_data['resolved']
        self.result = prediction_data.get('result')
        self.refunded = prediction_data['refunded']
        
        # AMM parameters
        self.initial_liquidity = prediction_data['initial_liquidity']
        self.k_constant = prediction_data['k_constant']
        self.total_bets = prediction_data['total_bets']
        
        # Database and cog references
        self.db = db_manager
        self.cog = cog
        
        # Cache for liquidity pools (refreshed from DB as needed)
        self._liquidity_cache = {}
        self._cache_timestamp = None
        self._cache_ttl = 5  # seconds
    
    async def _refresh_liquidity_cache(self):
        """Refresh liquidity pool cache from database"""
        now = datetime.datetime.now()
        if (self._cache_timestamp is None or 
            (now - self._cache_timestamp).total_seconds() > self._cache_ttl):
            
            self._liquidity_cache = await self.db.get_liquidity_pools(self.id)
            self._cache_timestamp = now
    
    async def get_liquidity_pool(self) -> Dict[str, int]:
        """Get current liquidity pools"""
        await self._refresh_liquidity_cache()
        return self._liquidity_cache.copy()
    
    def get_opposite_option(self, option: str) -> str:
        """Get the opposite option in a binary market"""
        return [opt for opt in self.options if opt != option][0]
    
    def calculate_shares_for_points(self, option: str, points: int) -> float:
        """Calculate how many shares user gets for their points using AMM formula"""
        if option not in self._liquidity_cache:
            return 0.0
            
        current_shares = self._liquidity_cache[option]
        other_option = self.get_opposite_option(option)
        other_shares = self._liquidity_cache[other_option]
        
        # Using constant product formula: x * y = k
        new_other_shares = other_shares + points
        new_shares = self.k_constant / new_other_shares
        shares_received = current_shares - new_shares
        
        return max(0.0, shares_received)
    
    def get_price(self, option: str, shares_to_buy: float) -> float:
        """Calculate price for buying shares using constant product formula"""
        if option not in self._liquidity_cache:
            return 0.0
        
        current_shares = self._liquidity_cache[option]
        other_option = self.get_opposite_option(option)
        other_shares = self._liquidity_cache[other_option]
        
        # Using constant product formula: x * y = k
        new_shares = current_shares - shares_to_buy
        if new_shares <= 0:
            return float('inf')
        
        new_other_shares = self.k_constant / new_shares
        cost = new_other_shares - other_shares
        return max(0.0, cost)
    
    async def place_bet(self, user_id: int, option: str, amount: int) -> bool:
        """Place a bet using AMM pricing with database persistence"""
        await self._refresh_liquidity_cache()
        
        if option not in self._liquidity_cache:
            return False
        
        # Calculate shares based on the amount
        shares = self.calculate_shares_for_points(option, amount)
        if shares <= 0:
            return False
        
        price_per_share = amount / shares
        
        # Update liquidity pools
        new_option_liquidity = self._liquidity_cache[option] - shares
        opposite_option = self.get_opposite_option(option)
        new_opposite_liquidity = self._liquidity_cache[opposite_option] + amount
        
        # Persist to database atomically
        try:
            # Place bet in database
            success = await self.db.place_bet(
                self.id, user_id, self.guild_id, option,
                amount, shares, price_per_share
            )
            
            if success:
                # Update liquidity pools
                await self.db.update_liquidity_pool(self.id, option, int(new_option_liquidity))
                await self.db.update_liquidity_pool(self.id, opposite_option, int(new_opposite_liquidity))
                
                # Update local cache
                self._liquidity_cache[option] = int(new_option_liquidity)
                self._liquidity_cache[opposite_option] = int(new_opposite_liquidity)
                
                # Deduct points from user's balance
                await self.cog.points_manager.remove_points(user_id, amount)
                
                return True
            
        except Exception as e:
            print(f"Error placing bet: {e}")
            return False
        
        return False
    
    async def get_odds(self) -> Dict[str, float]:
        """Calculate odds based on total bets from database"""
        option_totals = {}
        
        for option in self.options:
            bets = await self.db.get_option_bets(self.id, option)
            option_totals[option] = sum(bet['total_amount'] for bet in bets)
        
        total_all_bets = sum(option_totals.values())
        
        if total_all_bets == 0:
            return {option: 1/len(self.options) for option in self.options}
        
        return {
            option: option_totals[option] / total_all_bets
            for option in self.options
        }
    
    async def get_current_prices(self, points_to_spend: int = 100) -> Dict[str, Dict]:
        """Calculate current prices and potential shares for a given point amount"""
        await self._refresh_liquidity_cache()
        prices = {}
        
        # Get odds from database
        odds = await self.get_odds()
        
        for option in self.options:
            # Calculate actual shares user would get for their points
            shares = self.calculate_shares_for_points(option, points_to_spend)
            
            # Calculate actual price per share based on points spent and shares received
            price_per_share = points_to_spend / shares if shares > 0 else float('inf')
            
            # Get total bets for this option
            option_bets = await self.db.get_option_bets(self.id, option)
            total_bets = sum(bet['total_amount'] for bet in option_bets)
            
            prices[option] = {
                'price_per_share': price_per_share,
                'potential_shares': shares,
                'potential_payout': points_to_spend if shares > 0 else 0,
                'probability': odds[option] * 100,
                'total_bets': total_bets
            }
        
        return prices
    
    async def has_voted(self, user_id: int) -> bool:
        """Check if user has voted on resolution"""
        return await self.db.has_user_voted(self.id, user_id)
    
    async def vote(self, user_id: int, option: str) -> bool:
        """Add a resolution vote"""
        return await self.db.add_resolution_vote(self.id, user_id, self.guild_id, option)
    
    async def get_vote_counts(self) -> Dict[str, int]:
        """Get current vote counts for resolution"""
        return await self.db.get_resolution_votes(self.id)
    
    async def async_resolve(self, winning_option: str, resolved_by: int) -> bool:
        """Resolve the prediction and distribute payouts"""
        try:
            # Get all winning bets
            winning_bets = await self.db.get_option_bets(self.id, winning_option)
            
            if not winning_bets:
                print("No winning bets found.")
                return False
            
            # Calculate totals
            total_pool = self.total_bets
            total_winning_bets = sum(bet['total_amount'] for bet in winning_bets)
            
            if total_winning_bets <= 0:
                print("No valid winning bets to distribute points.")
                return False
            
            # Get vote count
            vote_counts = await self.get_vote_counts()
            vote_count = vote_counts.get(winning_option, 0)
            
            # Resolve in database
            success = await self.db.resolve_prediction(
                self.id, winning_option, resolved_by,
                total_pool, total_winning_bets, vote_count
            )
            
            if not success:
                return False
            
            # Distribute payouts
            for bet in winning_bets:
                user_id = bet['user_id']
                bet_amount = bet['total_amount']
                shares_owned = bet['total_shares']
                
                # Calculate proportional payout
                payout = int((bet_amount / total_winning_bets) * total_pool)
                
                # Add points to user's balance
                await self.cog.points_manager.add_points(user_id, payout)
                
                # Record payout
                await self.db.record_payout(
                    self.id, user_id, self.guild_id,
                    bet_amount, shares_owned, payout
                )
                
                # Notify user
                try:
                    user = await self.cog.bot.fetch_user(user_id)
                    await user.send(
                        f"🎉 You won {payout:,} Points on '{self.question}'!\n"
                        f"Your Bet: {bet_amount:,} → Payout: {payout:,}"
                    )
                except Exception as e:
                    print(f"Error notifying winner {user_id}: {e}")
            
            # Notify losers
            for option in self.options:
                if option != winning_option:
                    losing_bets = await self.db.get_option_bets(self.id, option)
                    for bet in losing_bets:
                        user_id = bet['user_id']
                        amount = bet['total_amount']
                        
                        try:
                            user = await self.cog.bot.fetch_user(user_id)
                            await user.send(
                                f"💔 You lost your bet of {amount:,} Points on '{self.question}'.\n"
                                f"The winning option was: '{winning_option}'."
                            )
                        except Exception as e:
                            print(f"Error notifying loser {user_id}: {e}")
            
            # Update local state
            self.resolved = True
            self.result = winning_option
            self.status = 'resolved'
            
            return True
            
        except Exception as e:
            print(f"Error resolving prediction: {e}")
            return False
    
    async def mark_as_refunded(self) -> List[Dict]:
        """Mark prediction as refunded and return refund data"""
        refund_data = await self.db.refund_prediction(self.id)
        
        # Update local state
        self.refunded = True
        self.resolved = True
        self.status = 'refunded'
        
        return refund_data
    
    def get_total_bets(self) -> int:
        """Get total bets amount"""
        return self.total_bets
    
    async def get_option_total_bets(self, option: str) -> int:
        """Get total bets for a specific option"""
        option_bets = await self.db.get_option_bets(self.id, option)
        return sum(bet['total_amount'] for bet in option_bets)
    
    async def get_bet_history(self) -> List[tuple]:
        """Get bet history for this prediction"""
        history = []
        for option in self.options:
            option_bets = await self.db.get_option_bets(self.id, option)
            for bet in option_bets:
                history.append((bet['user_id'], option, bet['total_amount']))
        return history
    
    def is_resolved(self) -> bool:
        """Check if prediction is resolved"""
        return self.resolved