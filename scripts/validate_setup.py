#!/usr/bin/env python3
"""
Setup validation script to check if everything is configured correctly.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a file exists."""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} (missing)")
        return False


def check_env_variable(var_name: str, required: bool = True) -> bool:
    """Check if environment variable is set."""
    value = os.getenv(var_name)
    if value:
        # Hide sensitive values
        if 'token' in var_name.lower() or 'key' in var_name.lower() or 'secret' in var_name.lower():
            display_value = f"{value[:8]}..." if len(value) > 8 else "***"
        else:
            display_value = value
        print(f"✅ {var_name}: {display_value}")
        return True
    else:
        status = "❌" if required else "⚠️"
        req_text = "required" if required else "optional"
        print(f"{status} {var_name}: not set ({req_text})")
        return not required


def main():
    """Validate the setup."""
    print("🔍 Discord Bot Setup Validation")
    print("=" * 50)
    
    all_good = True
    
    # Check Python version
    print(f"\n🐍 Python Version: {sys.version}")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        all_good = False
    else:
        print("✅ Python version OK")
    
    # Check required files
    print(f"\n📁 File Structure:")
    required_files = [
        ("main.py", "Main entry point"),
        ("requirements.txt", "Dependencies"),
        (".env", "Environment configuration"),
        ("config/settings.py", "Settings module"),
        ("core/container.py", "DI Container"),
        ("core/logging_manager.py", "Logging system"),
        ("core/error_handler.py", "Error handler"),
        ("cogs/economy/test_commands.py", "Test commands"),
    ]
    
    for file_path, description in required_files:
        if not check_file_exists(file_path, description):
            all_good = False
    
    # Check directories
    print(f"\n📂 Directories:")
    required_dirs = [
        ("logs", "Log directory"),
        ("cogs", "Commands directory"),
        ("core", "Core modules"),
        ("config", "Configuration"),
    ]
    
    for dir_path, description in required_dirs:
        if os.path.isdir(dir_path):
            print(f"✅ {description}: {dir_path}/")
        else:
            print(f"❌ {description}: {dir_path}/ (missing)")
            all_good = False
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print(f"\n✅ Environment variables loaded from .env")
    except ImportError:
        print(f"\n❌ python-dotenv not installed")
        all_good = False
    except Exception as e:
        print(f"\n❌ Error loading .env: {e}")
        all_good = False
    
    # Check environment variables
    print(f"\n🔧 Environment Variables:")
    
    # Required variables
    required_vars = [
        "DISCORD_TOKEN",
        "ENVIRONMENT",
    ]
    
    for var in required_vars:
        if not check_env_variable(var, required=True):
            all_good = False
    
    # Optional but recommended variables
    optional_vars = [
        "DATABASE_URL",
        "DATABASE_SUPABASE_URL",
        "DATABASE_SUPABASE_PUBLISHABLE_KEY",
        "LOG_LEVEL",
        "DEBUG",
    ]
    
    for var in optional_vars:
        check_env_variable(var, required=False)
    
    # Check dependencies
    print(f"\n📦 Dependencies:")
    try:
        import discord
        print(f"✅ discord.py: {discord.__version__}")
    except ImportError:
        print(f"❌ discord.py: not installed")
        all_good = False
    
    try:
        import pydantic
        print(f"✅ pydantic: {pydantic.__version__}")
    except ImportError:
        print(f"❌ pydantic: not installed")
        all_good = False
    
    try:
        from dotenv import load_dotenv
        print(f"✅ python-dotenv: installed")
    except ImportError:
        print(f"❌ python-dotenv: not installed")
        all_good = False
    
    # Test configuration loading
    print(f"\n⚙️ Configuration Test:")
    try:
        from config import validate_configuration
        settings = validate_configuration()
        print(f"✅ Configuration validation passed")
        print(f"   Environment: {settings.environment}")
        print(f"   Debug: {settings.debug}")
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        all_good = False
    
    # Summary
    print(f"\n" + "=" * 50)
    if all_good:
        print("🎉 Setup validation passed!")
        print("\nYou can now run your bot:")
        print("   python main.py")
        print("\nOr test the architecture:")
        print("   python scripts/test_setup.py")
    else:
        print("❌ Setup validation failed!")
        print("\nPlease fix the issues above before running the bot.")
        print("\nCommon fixes:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Copy .env.example to .env and fill in your values")
        print("3. Set your Discord bot token in .env")
    
    return all_good


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Validation error: {e}")
        sys.exit(1)