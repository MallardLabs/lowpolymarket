"""
Example Discord cog using dependency injection.

This shows how to create Discord cogs that use the DI container
for clean separation of concerns and better testability.
"""

import logging
from typing import List

import discord
from discord import app_commands
from discord.ext import commands

from core.container import get_container
from examples.di_container_integration import PredictionService, BettingService


class EnhancedPredictionCog(commands.Cog):
    """Enhanced prediction cog using dependency injection."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        
        # Services will be injected during cog load
        self.prediction_service: PredictionService = None
        self.betting_service: BettingService = None
    
    async def cog_load(self) -> None:
        """Initialize the cog with dependency injection."""
        container = get_container()
        
        # Resolve services from the DI container
        self.prediction_service = await container.get_service(PredictionService)
        self.betting_service = await container.get_service(BettingService)
        
        self.logger.info("Enhanced prediction cog loaded with DI")
    
    @app_commands.command(name="create_prediction_enhanced", description="Create a prediction using DI services")
    @app_commands.describe(
        question="The prediction question",
        options="Comma-separated options",
        duration_hours="Duration in hours"
    )
    async def create_prediction_enhanced(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        duration_hours: int
    ):
        """Create a prediction using the injected service."""
        await interaction.response.defer()
        
        try:
            # Parse options
            option_list = [opt.strip() for opt in options.split(",")]
            
            # Calculate end time
            import datetime
            end_time = datetime.datetime.utcnow() + datetime.timedelta(hours=duration_hours)
            
            # Use the injected service
            prediction_id = await self.prediction_service.create_prediction(
                guild_id=interaction.guild.id,
                question=question,
                options=option_list,
                creator_id=interaction.user.id,
                end_time=end_time
            )
            
            await interaction.followup.send(
                f"✅ Prediction created successfully!\n"
                f"**ID:** {prediction_id}\n"
                f"**Question:** {question}\n"
                f"**Options:** {', '.join(option_list)}\n"
                f"**Duration:** {duration_hours} hours"
            )
            
        except ValueError as e:
            await interaction.followup.send(f"❌ Validation error: {e}", ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error creating prediction: {e}")
            await interaction.followup.send("❌ An error occurred while creating the prediction.", ephemeral=True)
    
    @app_commands.command(name="place_bet_enhanced", description="Place a bet using DI services")
    @app_commands.describe(
        prediction_id="The prediction ID",
        option="The option to bet on",
        amount="Amount to bet"
    )
    async def place_bet_enhanced(
        self,
        interaction: discord.Interaction,
        prediction_id: str,
        option: str,
        amount: int
    ):
        """Place a bet using the injected service."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Use the injected service
            success = await self.betting_service.place_bet(
                user_id=interaction.user.id,
                prediction_id=prediction_id,
                option=option,
                amount=amount
            )
            
            if success:
                await interaction.followup.send(
                    f"✅ Bet placed successfully!\n"
                    f"**Amount:** {amount:,} points\n"
                    f"**Option:** {option}\n"
                    f"**Prediction:** {prediction_id}"
                )
            else:
                await interaction.followup.send("❌ Failed to place bet. Please try again.")
                
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}")
        except Exception as e:
            self.logger.error(f"Error placing bet: {e}")
            await interaction.followup.send("❌ An error occurred while placing your bet.")
    
    @app_commands.command(name="list_predictions_enhanced", description="List predictions using DI services")
    async def list_predictions_enhanced(self, interaction: discord.Interaction):
        """List active predictions using the injected service."""
        await interaction.response.defer()
        
        try:
            # Use the injected service
            predictions = await self.prediction_service.get_active_predictions(interaction.guild.id)
            
            if not predictions:
                await interaction.followup.send("No active predictions found.")
                return
            
            # Create embed
            embed = discord.Embed(
                title="🎲 Active Predictions",
                description=f"Found {len(predictions)} active prediction(s)",
                color=discord.Color.blue()
            )
            
            for pred in predictions[:5]:  # Limit to 5 for display
                embed.add_field(
                    name=f"ID: {pred.get('id', 'Unknown')}",
                    value=f"**Question:** {pred.get('question', 'Unknown')}\n"
                          f"**Options:** {', '.join(pred.get('options', []))}\n"
                          f"**Ends:** <t:{int(pred.get('end_time', 0).timestamp())}:R>",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error listing predictions: {e}")
            await interaction.followup.send("❌ An error occurred while fetching predictions.")


async def setup(bot: commands.Bot):
    """Set up the cog."""
    await bot.add_cog(EnhancedPredictionCog(bot))