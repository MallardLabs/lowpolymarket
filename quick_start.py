#!/usr/bin/env python3
"""
Quick start script for the Discord Prediction Market Bot.

This script will:
1. Validate your setup
2. Run basic tests
3. Start the bot if everything is working
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path


def run_command(command: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✅ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ {description} failed: Command not found")
        return False


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print(f"❌ Python 3.8+ required, you have {sys.version}")
        return False
    print(f"✅ Python {sys.version.split()[0]} is compatible")
    return True


def check_env_file() -> bool:
    """Check if .env file exists."""
    if not os.path.exists('.env'):
        print("❌ .env file not found")
        print("   Please copy .env.example to .env and fill in your values:")
        print("   cp .env.example .env")
        return False
    print("✅ .env file found")
    return True


def check_discord_token() -> bool:
    """Check if Discord token is set."""
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token or token == 'your_discord_bot_token_here':
        print("❌ Discord token not set in .env file")
        print("   Please set DISCORD_TOKEN in your .env file")
        return False
    print("✅ Discord token is configured")
    return True


async def main():
    """Main quick start process."""
    print("🚀 Discord Bot Quick Start")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Check .env file
    if not check_env_file():
        return False
    
    # Check Discord token
    try:
        if not check_discord_token():
            return False
    except ImportError:
        print("❌ python-dotenv not installed")
        print("   Installing dependencies...")
        if not run_command("pip install -r requirements.txt", "Installing dependencies"):
            return False
        if not check_discord_token():
            return False
    
    # Validate setup
    print(f"\n🔍 Validating setup...")
    if not run_command("python scripts/validate_setup.py", "Setup validation"):
        print("\n❌ Setup validation failed. Please fix the issues above.")
        return False
    
    # Run architecture tests
    print(f"\n🧪 Testing architecture...")
    if not run_command("python scripts/test_setup.py", "Architecture tests"):
        print("\n❌ Architecture tests failed. Please check the errors above.")
        return False
    
    # All checks passed
    print(f"\n" + "=" * 50)
    print("🎉 All checks passed! Your bot is ready to run.")
    print("\nStarting the bot...")
    print("Press Ctrl+C to stop the bot")
    print("=" * 50)
    
    # Start the bot
    try:
        import main
        await main.main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Bot failed to start: {e}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Quick start error: {e}")
        sys.exit(1)