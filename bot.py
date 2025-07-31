import logging
import os
import platform
import webserver

import discord
from discord.ext import commands
from dotenv import load_dotenv

from helpers.SimplePointsManager import PointsManagerSingleton
from cogs import EXTENSIONS
from config import validate_configuration, print_configuration_summary, ConfigurationError
from core.logging_manager import get_logging_manager, get_logger, set_correlation_id

intents = discord.Intents.default()


class LoggingFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


# Initialize configuration first
try:
    settings = validate_configuration()
    print_configuration_summary(settings)
except ConfigurationError as e:
    print(f"❌ Configuration Error: {e}")
    exit(1)

logger = logging.getLogger("discord_bot")
logger.setLevel(getattr(logging, settings.logging.level))

# Console handler
if settings.logging.console_enabled:
    console_handler = logging.StreamHandler()
    if settings.logging.console_colors:
        console_handler.setFormatter(LoggingFormatter())
    else:
        console_formatter = logging.Formatter(
            settings.logging.format, settings.logging.date_format, style="{"
        )
        console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

# File handler
if settings.logging.file_enabled:
    # Ensure log directory exists
    os.makedirs(os.path.dirname(settings.logging.file_path), exist_ok=True)
    
    file_handler = logging.FileHandler(
        filename=settings.logging.file_path, 
        encoding="utf-8", 
        mode="w"
    )
    file_handler_formatter = logging.Formatter(
        settings.logging.format, settings.logging.date_format, style="{"
    )
    file_handler.setFormatter(file_handler_formatter)
    logger.addHandler(file_handler)


class DiscordBot(commands.Bot):
    def __init__(self, settings) -> None:
        super().__init__(
            command_prefix=settings.discord.command_prefix,
            intents=intents
        )
        self.logger = logger
        self._connected = False
        self.settings = settings

        self.points_manager = PointsManagerSingleton(
            base_url=settings.drip_api.base_url,
            api_key=settings.drip_api.api_key,
            realm_id=settings.drip_api.realm_id
        )

    async def load_cogs(self) -> None:
        """
        The code in this function is executed whenever the bot will start.
        """
        for file in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if file.endswith(".py"):
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                    self.logger.info(f"Loaded extension '{extension}'")
                except Exception as e:
                    exception = f"{type(e).__name__}: {e}"
                    self.logger.error(
                        f"Failed to load extension {extension}\n{exception}"
                    )

    async def setup_hook(self) -> None:
        """
        This will just be executed when the bot starts the first time.
        """
        self.logger.info(f"Logged in as {self.user.name}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("-------------------")
        for cog in EXTENSIONS:
            await self.load_extension(cog)

    async def on_ready(self) -> None:
        """|coro|

        Overriding :meth:`~discord.Client.on_ready`, to do some basic connect/reconnect info
        """
        await self.wait_until_ready()
        if self.settings.discord.sync_commands:
            await self.tree.sync()
        if not self._connected:
            self.logger.info("Bot is ready!" + self.user.name)
            if self.settings.discord.sync_commands:
                self.logger.info("synced!")
        else:
            self.logger.info("Bot reconnected.")

    async def close(self) -> None:
        """
        This is called when the bot is shutting down.
        Clean up the points manager session.
        """
        await self.points_manager.cleanup()
        await super().close()


load_dotenv(override=True)

bot = DiscordBot(settings)
webserver.keep_alive()
bot.run(settings.discord.token)