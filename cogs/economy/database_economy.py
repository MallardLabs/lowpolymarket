from discord.ext import commands
import discord
from discord import app_commands
import datetime
import asyncio
import math
import os
from typing import Dict, List, Optional

from database.supabase_client import SupabaseManager, PredictionDatabase
from models.prediction import DatabasePrediction

def is_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

class DatabaseEconomy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.points_manager = bot.points_manager
        self.active_views = set()
        
        # Initialize Supabase connection
        self.supabase_manager = SupabaseManager(
            url=os.getenv("SUPABASE_URL"),
            key=os.getenv("SUPABASE_ANON_KEY"),
            db_url=os.getenv("DATABASE_URL")
        )
        self.db = PredictionDatabase(self.supabase_manager)
        
        # Start background tasks
        self.cleanup_task = None
        self.auto_refund_task = None
    
    async def cog_load(self):
        """Initialize database connection when cog loads"""
        await self.supabase_manager.initialize()
        
        # Start background tasks
        self.cleanup_task = asyncio.create_task(self.cleanup_expired_predictions())
        self.auto_refund_task = asyncio.create_task(self.auto_refund_expired_predictions())
    
    async def cog_unload(self):
        """Cleanup when cog unloads"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.auto_refund_task:
            self.auto_refund_task.cancel()
        
        # Stop all active views
        for view in list(self.active_views):
            if hasattr(view, 'stop_auto_update'):
                view.stop_auto_update()
        
        await self.supabase_manager.cleanup()
    
    async def cleanup_expired_predictions(self):
        """Background task to update expired predictions"""
        while True:
            try:
                expired = await self.db.get_expired_predictions()
                for pred_data in expired:
                    # Update status to 'ended'
                    await self.supabase_manager.pool.execute("""
                        UPDATE predictions SET status = 'ended' WHERE id = $1
                    """, pred_data['id'])
                    
                    # Notify creator
                    try:
                        creator = await self.bot.fetch_user(pred_data['creator_id'])
                        await creator.send(
                            f"🎲 Betting has ended for your prediction: '{pred_data['question']}'\n"
                            f"Please use `/resolve_prediction` to resolve the market.\n"
                            f"If not resolved within 5 days, all bets will be automatically refunded."
                        )
                    except Exception as e:
                        print(f"Error notifying creator {pred_data['creator_id']}: {e}")
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                print(f"Error in cleanup task: {e}")
                await asyncio.sleep(300)
    
    async def auto_refund_expired_predictions(self):
        """Background task to auto-refund predictions after 120 hours"""
        while True:
            try:
                to_refund = await self.db.get_predictions_for_auto_refund(120)
                
                for pred_data in to_refund:
                    # Create prediction object for refunding
                    prediction = DatabasePrediction(pred_data, self.db, self)
                    refund_data = await prediction.mark_as_refunded()
                    
                    # Process refunds
                    for refund in refund_data:
                        user_id = refund['user_id']
                        amount = refund['total_amount']
                        
                        await self.points_manager.add_points(user_id, amount)
                        
                        try:
                            user = await self.bot.fetch_user(user_id)
                            await user.send(
                                f"💰 Your bet of {amount:,} Points has been refunded for the expired market:\n"
                                f"'{pred_data['question']}'"
                            )
                        except Exception as e:
                            print(f"Error sending refund notification to {user_id}: {e}")
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                print(f"Error in auto-refund task: {e}")
                await asyncio.sleep(3600)

    @app_commands.guild_only()
    @app_commands.command(name="create_prediction", description="Create a new prediction market")
    @app_commands.describe(
        question="The question for the prediction",
        duration="Duration format: days,hours,minutes (e.g., 1,2,30 or ,,30 or 1,,)",
        options="Comma-separated list of prediction options",
        category="Category for the prediction (optional)"
    )
    async def create_prediction(
        self, 
        interaction: discord.Interaction, 
        question: str, 
        options: str, 
        duration: str,
        category: str = None
    ):
        await interaction.response.defer(ephemeral=False)
        
        # Check permissions
        creator_role_ids = {1301958999092236389}
        user_roles = {role.id for role in interaction.user.roles}

        if not user_roles.intersection(creator_role_ids):
            await interaction.followup.send("You do not have permission to create prediction markets.", ephemeral=True)
            return
        
        try:
            # Ensure guild exists in database
            await self.supabase_manager.ensure_guild_exists(
                interaction.guild.id, 
                interaction.guild.name
            )
            
            # Process options
            options_list = [opt.strip() for opt in options.split(",")]
            
            if len(options_list) < 2:
                await interaction.followup.send("You need at least two options for a prediction!", ephemeral=True)
                return
            
            # Process duration
            duration_parts = duration.split(",")
            if len(duration_parts) != 3:
                await interaction.followup.send("Duration must be in format: days,hours,minutes", ephemeral=True)
                return
            
            days = int(duration_parts[0]) if duration_parts[0].strip() else 0
            hours = int(duration_parts[1]) if duration_parts[1].strip() else 0
            minutes = int(duration_parts[2]) if duration_parts[2].strip() else 0
            
            total_minutes = (days * 24 * 60) + (hours * 60) + minutes
            if total_minutes <= 0:
                await interaction.followup.send("Duration must be greater than 0!", ephemeral=True)
                return
            
            # Create prediction in database
            end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=total_minutes)
            prediction_id = await self.db.create_prediction(
                guild_id=interaction.guild.id,
                question=question,
                options=options_list,
                creator_id=interaction.user.id,
                end_time=end_time,
                category=category
            )
            
            # Format duration string
            duration_parts = []
            if days > 0:
                duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                duration_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            duration_str = ", ".join(duration_parts)
            
            await interaction.followup.send(
                f"Prediction created successfully!\n"
                f"ID: {prediction_id}\n"
                f"Question: {question}\n"
                f"Options: {', '.join(options_list)}\n"
                f"Duration: {duration_str}\n"
                f"Category: {category if category else 'None'}",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.followup.send("Invalid duration format!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error creating prediction: {str(e)}", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="bet", description="Place a bet on a prediction")
    async def bet(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Get active predictions from database
        active_predictions_data = await self.db.get_active_predictions(interaction.guild.id)
        
        if not active_predictions_data:
            await interaction.followup.send("No active predictions at the moment.", ephemeral=True)
            return

        # Convert to DatabasePrediction objects
        active_predictions = [
            DatabasePrediction(pred_data, self.db, self) 
            for pred_data in active_predictions_data
        ]

        # Get categories
        categories = list(set(pred.category for pred in active_predictions if pred.category))
        categories.append("All")

        # Create category selection interface
        class CategoryButton(discord.ui.Button):
            def __init__(self, label, cog):
                super().__init__(label=label, style=discord.ButtonStyle.primary)
                self.cog = cog
                self.category = label

            async def callback(self, button_interaction: discord.Interaction):
                await button_interaction.response.defer(ephemeral=True)

                if self.category == "All":
                    filtered_predictions = active_predictions
                else:
                    filtered_predictions = [p for p in active_predictions if p.category == self.category]

                if not filtered_predictions:
                    await button_interaction.followup.send("No predictions available for this category.", ephemeral=True)
                    return

                # Create prediction selection menu
                class PredictionSelect(discord.ui.Select):
                    def __init__(self, predictions, cog):
                        self.cog = cog
                        options = [
                            discord.SelectOption(
                                label=pred.question[:100], 
                                description=f"Ends at {pred.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}", 
                                value=pred.id
                            )
                            for pred in predictions
                        ]
                        super().__init__(placeholder="Select a prediction to bet on...", options=options)

                    async def callback(self, interaction: discord.Interaction):
                        await interaction.response.defer(ephemeral=True)
                        
                        selected_id = self.values[0]
                        selected_prediction = next(p for p in filtered_predictions if p.id == selected_id)

                        # Check if prediction has ended
                        if selected_prediction.end_time <= datetime.datetime.utcnow():
                            await interaction.followup.send("This prediction has already ended!", ephemeral=True)
                            return

                        # Create betting interface
                        view = DatabaseOptionButtonView(selected_prediction, self.cog)
                        prices = await selected_prediction.get_current_prices(100)
                        
                        market_info = "**Current Market Prices**\n\n"
                        for option in selected_prediction.options:
                            price = prices[option]['price_per_share']
                            market_info += f"{option}: {price:.2f} Points/Share\n"
                        
                        message = await interaction.followup.send(
                            content=market_info,
                            view=view, 
                            ephemeral=True,
                            wait=True
                        )
                        view.stored_interaction = message

                class PredictionSelectView(discord.ui.View):
                    def __init__(self, predictions, cog):
                        super().__init__()
                        self.add_item(PredictionSelect(predictions, cog))

                await button_interaction.followup.send(
                    content="Please select a prediction to bet on:", 
                    view=PredictionSelectView(filtered_predictions, self.cog),
                    ephemeral=True
                )

        class CategoryButtonView(discord.ui.View):
            def __init__(self, categories, cog):
                super().__init__()
                for category in categories:
                    self.add_item(CategoryButton(category, cog))

        await interaction.followup.send("Please select a category:", view=CategoryButtonView(categories, self))

    @app_commands.guild_only()
    @app_commands.command(name="list_predictions", description="List all predictions")
    async def list_predictions(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get all predictions from database
            all_predictions_data = await self.db.get_predictions_by_status(interaction.guild.id)
            
            if not all_predictions_data:
                await interaction.followup.send("No predictions found for this server.", ephemeral=True)
                return
            
            # Create list view
            view = DatabaseListPredictionsView(self, all_predictions_data)
            self.active_views.add(view)

            embed = await view.create_current_page_embed()
            message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.stored_interaction = message
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.guild_only()
    @app_commands.command(name="resolve_prediction", description="Vote to resolve a prediction")
    async def resolve_prediction_command(self, interaction: discord.Interaction):
        # Check permissions
        resolver_role_ids = {1301959367536672838, 1301958999092236389}
        user_roles = {role.id for role in interaction.user.roles}

        if not user_roles.intersection(resolver_role_ids):
            await interaction.response.send_message("You do not have permission to resolve predictions.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get unresolved predictions that have ended
        ended_predictions_data = await self.db.get_predictions_by_status(interaction.guild.id, 'ended')
        
        if not ended_predictions_data:
            await interaction.followup.send("There are no predictions ready to be resolved.", ephemeral=True)
            return

        # Create selection interface
        class PredictionSelect(discord.ui.Select):
            def __init__(self, predictions_data, cog):
                self.cog = cog
                self.predictions_data = predictions_data
                options = [
                    discord.SelectOption(
                        label=pred['question'][:100], 
                        description=f"Ended {pred['end_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}", 
                        value=str(pred['id'])
                    )
                    for pred in predictions_data
                ]
                super().__init__(placeholder="Select a prediction to resolve...", options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_id = self.values[0]
                pred_data = next(p for p in self.predictions_data if str(p['id']) == selected_id)
                selected_prediction = DatabasePrediction(pred_data, self.cog.db, self.cog)
                
                # Check if user has already voted
                if await selected_prediction.has_voted(interaction.user.id):
                    await interaction.response.send_message("You have already voted on this prediction!", ephemeral=True)
                    return

                # Create voting interface
                embed = discord.Embed(
                    title=f"Vote to Resolve: {selected_prediction.question}",
                    description="Please vote for the winning option:",
                    color=discord.Color.blue()
                )

                view = discord.ui.View()
                for option in selected_prediction.options:
                    button = discord.ui.Button(label=option, style=discord.ButtonStyle.primary)

                    async def button_callback(btn_interaction: discord.Interaction, option=option):
                        # Check permissions again
                        user_roles = {role.id for role in btn_interaction.user.roles}
                        if not user_roles.intersection(resolver_role_ids):
                            await btn_interaction.response.send_message("You do not have permission to vote.", ephemeral=True)
                            return

                        if await selected_prediction.has_voted(btn_interaction.user.id):
                            await btn_interaction.response.send_message("You have already voted!", ephemeral=True)
                            return

                        # Add vote
                        await selected_prediction.vote(btn_interaction.user.id, option)
                        await btn_interaction.response.send_message(f"You voted for {option}.", ephemeral=True)

                        # Check if threshold is met (2 votes)
                        vote_counts = await selected_prediction.get_vote_counts()
                        if vote_counts.get(option, 0) >= 2:
                            success = await selected_prediction.async_resolve(option, btn_interaction.user.id)
                            if success:
                                await btn_interaction.channel.send(f"Market resolved! The winning option is: {option}")
                                # Disable all buttons
                                for item in view.children:
                                    item.disabled = True
                                await btn_interaction.message.edit(view=view)

                    button.callback = button_callback
                    view.add_item(button)

                await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

        view = discord.ui.View()
        view.add_item(PredictionSelect(ended_predictions_data, self))
        await interaction.followup.send("Select a prediction to resolve:", view=view, ephemeral=True)

# UI Components for database-backed predictions
class DatabaseOptionButton(discord.ui.Button):
    def __init__(self, label, prediction, cog, view):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"bet_{label}"
        )
        self.prediction = prediction
        self.cog = cog
        self.option = label
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.send_modal(DatabaseAmountInput(self.prediction, self.option, self.cog))
        except Exception as e:
            print(f"Error in button callback: {e}")
            await interaction.response.send_message("An error occurred.", ephemeral=True)

class DatabaseAmountInput(discord.ui.Modal, title="Place Your Bet"):
    def __init__(self, prediction, option, cog):
        super().__init__()
        self.prediction = prediction
        self.option = option
        self.cog = cog
        
        self.amount = discord.ui.TextInput(
            label=f"Enter amount to bet on {option}",
            style=discord.TextStyle.short,
            placeholder="Enter bet amount",
            required=True,
            default="100"
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                await interaction.response.send_message("Amount must be positive!", ephemeral=True)
                return

            # Check if prediction is still active
            if self.prediction.end_time <= datetime.datetime.utcnow():
                await interaction.response.send_message("This prediction has already ended!", ephemeral=True)
                return

            # Check user's balance
            balance = await self.cog.points_manager.get_balance(interaction.user.id)
            if balance < amount:
                await interaction.response.send_message(f"You don't have enough Points! Your balance: {balance:,} Points", ephemeral=True)
                return

            # Calculate potential shares
            shares = self.prediction.calculate_shares_for_points(self.option, amount)
            if shares <= 0:
                await interaction.response.send_message("Cannot calculate shares for this bet amount.", ephemeral=True)
                return

            actual_price_per_share = amount / shares

            # Place bet
            success = await self.prediction.place_bet(interaction.user.id, self.option, amount)
            
            if success:
                await interaction.response.send_message(
                    f"Bet placed successfully!\n"
                    f"Amount: {amount:,} Points\n"
                    f"Shares received: {shares:.2f}\n"
                    f"Price per share: {actual_price_per_share:.2f} Points",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message("Failed to place bet. Please try again.", ephemeral=True)
                
        except ValueError:
            await interaction.response.send_message("Invalid amount entered!", ephemeral=True)
        except Exception as e:
            print(f"Error in modal submit: {e}")
            await interaction.response.send_message("An error occurred while placing your bet.", ephemeral=True)

class DatabaseOptionButtonView(discord.ui.View):
    def __init__(self, prediction, cog):
        super().__init__(timeout=None)
        self.prediction = prediction
        self.cog = cog
        self.stored_interaction = None
        self.update_task = None
        
        self.update_buttons()
        self.cog.active_views.add(self)
        self.start_auto_update()

    def update_buttons(self):
        self.clear_items()
        for option in self.prediction.options:
            button = DatabaseOptionButton(option, self.prediction, self.cog, self)
            self.add_item(button)

    def start_auto_update(self):
        if not self.update_task:
            self.update_task = asyncio.create_task(self.auto_update_prices())

    def stop_auto_update(self):
        if self.update_task:
            self.update_task.cancel()
            self.update_task = None

    async def auto_update_prices(self):
        try:
            while True:
                await self.refresh_view()
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in auto_update_prices: {e}")

    async def refresh_view(self):
        if self.stored_interaction:
            try:
                if self.prediction.end_time <= datetime.datetime.utcnow():
                    self.stop_auto_update()
                    await self.stored_interaction.edit(content="This prediction has ended!", view=None)
                    return

                prices = await self.prediction.get_current_prices(10)
                market_info = "**Current Market Status**\n\n"
                
                for option in self.prediction.options:
                    price_info = prices[option]
                    market_info += f"**{option}**\n"
                    market_info += f"• Total Bets: {price_info['total_bets']:,} Points\n"
                    market_info += f"• Probability: {price_info['probability']:.1f}%\n"
                    market_info += f"• Current Price: {price_info['price_per_share']:.2f} Points/Share\n\n"
                
                total_volume = self.prediction.get_total_bets()
                market_info += f"\n**Total Volume**: {total_volume:,} Points"
                
                await self.stored_interaction.edit(content=market_info, view=self)
                
            except discord.NotFound:
                self.stop_auto_update()
                self.cog.active_views.discard(self)
            except Exception as e:
                print(f"Error refreshing view: {e}")

    def __del__(self):
        self.stop_auto_update()
        self.cog.active_views.discard(self)

class DatabaseListPredictionsView(discord.ui.View):
    def __init__(self, cog, predictions_data, markets_per_page=1):
        super().__init__(timeout=None)
        self.cog = cog
        self.predictions_data = predictions_data
        self.stored_interaction = None
        self.current_page = 0
        self.markets_per_page = markets_per_page
        
        # Add pagination buttons
        self.add_item(discord.ui.Button(label="◀", custom_id="prev_page", style=discord.ButtonStyle.secondary))
        self.add_item(discord.ui.Button(label="▶", custom_id="next_page", style=discord.ButtonStyle.secondary))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "prev_page":
            await self.previous_page(interaction)
        elif interaction.data["custom_id"] == "next_page":
            await self.next_page(interaction)
        return True

    async def previous_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_page(interaction)
        else:
            await interaction.response.defer()

    async def next_page(self, interaction: discord.Interaction):
        if (self.current_page + 1) * self.markets_per_page < len(self.predictions_data):
            self.current_page += 1
            await self.update_page(interaction)
        else:
            await interaction.response.defer()

    async def update_page(self, interaction: discord.Interaction):
        embed = await self.create_current_page_embed()
        await interaction.response.edit_message(embed=embed)

    async def create_current_page_embed(self):
        start_idx = self.current_page * self.markets_per_page
        end_idx = start_idx + self.markets_per_page
        current_markets = self.predictions_data[start_idx:end_idx]

        embed = discord.Embed(
            title="🎲 Prediction Markets",
            description=f"Page {self.current_page + 1}/{math.ceil(len(self.predictions_data)/self.markets_per_page)}",
            color=discord.Color.blue()
        )

        for pred_data in current_markets:
            # Create DatabasePrediction object for display
            prediction = DatabasePrediction(pred_data, self.cog.db, self.cog)
            
            # Get status emoji
            status_emoji = {
                'active': '🟢 ACTIVE',
                'ended': '🟡 PENDING',
                'resolved': '✅ RESOLVED',
                'refunded': '💰 REFUNDED'
            }.get(pred_data['status'], '❓ UNKNOWN')
            
            # Get creator name
            try:
                creator = await self.cog.bot.fetch_user(pred_data['creator_id'])
                creator_name = creator.name
            except:
                creator_name = "Unknown"
            
            # Create market display
            market_text = await self.create_market_display(prediction, pred_data)
            
            embed.add_field(
                name=f"{status_emoji} {pred_data['question']} (Created by: {creator_name})",
                value=market_text,
                inline=False
            )

        embed.set_footer(text="Use /bet to place bets on active markets")
        return embed

    async def create_market_display(self, prediction: DatabasePrediction, pred_data: Dict):
        """Create market display for a prediction"""
        market_text = (
            f"**Category:** {pred_data.get('category') or 'None'}\n"
            f"**Total Volume:** {pred_data['total_bets']:,} Points\n"
            f"**Ends:** <t:{int(pred_data['end_time'].timestamp())}:R>\n\n"
        )
        
        if pred_data['status'] == 'active':
            prices = await prediction.get_current_prices(100)
            market_text += "**Current Market Status:**\n"
            
            for option in prediction.options:
                if option in prices:
                    price_info = prices[option]
                    market_text += (
                        f"```\n"
                        f"{option}\n"
                        f"Price: {price_info['price_per_share']:.2f} Points/Share\n"
                        f"Prob:  {price_info['probability']:.1f}%\n"
                        f"Volume: {price_info['total_bets']:,} Points\n"
                        f"```\n"
                    )
        elif pred_data['status'] == 'resolved':
            market_text += f"**Winner:** {pred_data['result']}\n"
        elif pred_data['status'] == 'ended':
            vote_counts = await prediction.get_vote_counts()
            market_text += "**Resolution Votes:**\n"
            for option in prediction.options:
                votes = vote_counts.get(option, 0)
                market_text += f"• {option}: {votes} votes\n"
        
        return market_text

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DatabaseEconomy(bot))