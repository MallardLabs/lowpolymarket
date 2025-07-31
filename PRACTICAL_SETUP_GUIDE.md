# 🚀 Practical Discord Bot Setup Guide

This guide will get your Discord Prediction Market Bot running with the complete architecture we've built, including dependency injection, logging, error handling, validation, security, and rate limiting.

## 📋 Prerequisites

- Python 3.8+ installed
- Discord Developer Account
- Supabase Account (for database)
- Basic terminal/command line knowledge

## 🔧 Step 1: Install Dependencies

First, let's install all required packages:

```bash
# Install Python dependencies
pip install -r requirements.txt

# If you don't have pip, install it first:
# python -m ensurepip --upgrade
```

## 📁 Step 2: Project Structure Overview

Your project should have this structure:
```
discord-bot/
├── bot.py                    # Main bot entry point
├── main.py                   # New main entry point (we'll create this)
├── requirements.txt          # Dependencies
├── .env                      # Your environment variables
├── config/                   # Configuration management
│   ├── __init__.py
│   ├── settings.py          # Settings classes
│   └── validation.py        # Config validation
├── core/                     # Core architecture components
│   ├── __init__.py
│   ├── container.py         # Dependency injection
│   ├── logging_manager.py   # Structured logging
│   ├── error_handler.py     # Error handling
│   ├── exceptions.py        # Custom exceptions
│   ├── validation.py        # Input validation
│   ├── rate_limiter.py      # Rate limiting
│   └── security.py          # Security middleware
├── cogs/                     # Discord command modules
│   ├── __init__.py
│   └── economy/             # Economy commands
├── database/                 # Database layer
├── models/                   # Data models
├── helpers/                  # Utility functions
└── logs/                     # Log files (auto-created)
```

## ⚙️ Step 3: Environment Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```env
# Discord Bot Token (get from Discord Developer Portal)
DISCORD_TOKEN=your_actual_discord_bot_token_here

# Database (get from Supabase Dashboard)
DATABASE_URL=postgresql://postgres.your-ref:your-password@aws-0-us-east-2.pooler.supabase.com:6543/postgres
DATABASE_SUPABASE_URL=https://your-project-ref.supabase.co
DATABASE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_your_key_here
DATABASE_SUPABASE_SECRET_KEY=sb_secret_your_key_here

# Environment
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
```

## 🏗️ Step 4: Create Main Entry Point

Let's create a new main entry point that properly initializes our architecture:
## 
🎯 Step 5: Create a Simple Test Command

Let's create a simple economy command that demonstrates all our architecture features:
## 🗄️ Step 6: Set Up Database (Optional for Testing)

For now, let's create a simple database setup script:#
# 🧪 Step 7: Test Your Setup

Before running the bot, let's test that everything is working:

```bash
# Run the test setup script
python scripts/test_setup.py
```

This will test:
- ✅ Configuration loading
- ✅ Logging system with correlation IDs
- ✅ Dependency injection container
- ✅ Rate limiting
- ✅ Error handling
- ✅ Security manager

## 🚀 Step 8: Run Your Bot

Now let's run the bot with our new architecture:

```bash
# Run the bot
python main.py
```

You should see output like:
```
🎯 Discord Prediction Market Bot
==================================================
📋 Loading configuration...
✅ Configuration loaded and validated
📝 Initializing logging system...
🏗️ Setting up dependency injection container...
🤖 Creating bot instance...
🚀 Starting bot...
[2024-01-20 10:30:15] [INFO    ] [MAIN_STARTUP] Main:main:45 - 🚀 Starting application
[2024-01-20 10:30:15] [INFO    ] [STARTUP] PredictionMarketBot:setup_hook:67 - 🚀 Starting bot setup...
✅ All services initialized
✅ All cogs loaded
✅ Slash commands synced
🎉 Bot setup completed successfully!
🤖 YourBotName is ready!
```

## 🎮 Step 9: Test Discord Commands

Once your bot is running, test these slash commands in Discord:

### `/test-balance`
- Tests the complete architecture
- Shows correlation ID tracking
- Demonstrates rate limiting
- Shows structured logging
- Tests error handling

### `/test-error`
- Intentionally triggers errors
- Tests error handling system
- Shows user-friendly error messages
- Demonstrates error logging

### `/test-logs`
- Generates different log levels
- Shows structured logging
- Demonstrates correlation IDs

### `/system-status`
- Shows health of all systems
- Displays service status
- Shows error statistics

## 📊 Step 10: Monitor Logs and Errors

### View Logs
```bash
# View real-time logs
tail -f logs/discord.log

# View structured JSON logs
cat logs/discord.log | jq '.'
```

### Check Error Statistics
Use the `/system-status` command in Discord to see:
- Service health
- Error counts
- System status

## 🔧 Step 11: Configuration Examples

### Development Environment (.env)
```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LOG_CONSOLE_COLORS=true
DISCORD_SYNC_COMMANDS=true

# Rate limiting (relaxed for development)
RATE_LIMIT_USER_REQUESTS_PER_MINUTE=30
RATE_LIMIT_USER_BETS_PER_MINUTE=10
```

### Production Environment (.env)
```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_JSON_FORMAT=true
LOG_FILE_ENABLED=true

# Rate limiting (strict for production)
RATE_LIMIT_USER_REQUESTS_PER_MINUTE=10
RATE_LIMIT_USER_BETS_PER_MINUTE=5
```

## 🛠️ Step 12: Troubleshooting

### Common Issues

#### "Configuration Error"
- Check your `.env` file exists
- Verify all required variables are set
- Run `python scripts/validate_config.py`

#### "Discord Token Invalid"
- Check your Discord bot token in `.env`
- Ensure the token is correct and not expired
- Verify bot permissions in Discord Developer Portal

#### "Import Errors"
- Run `pip install -r requirements.txt`
- Check Python version (3.8+ required)
- Verify project structure matches the guide

#### "Database Connection Failed"
- Check Supabase credentials in `.env`
- Verify database URL format
- Test connection with `python test_db_connection.py`

### Debug Mode
Enable debug mode for detailed logging:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Correlation ID Tracking
Every operation gets a unique correlation ID. Use this to track issues:
1. Find the correlation ID in error messages
2. Search logs for that ID: `grep "CORRELATION_ID" logs/discord.log`
3. See the complete flow of that operation

## 🎯 Step 13: Next Steps

Now that your bot is running with the complete architecture:

1. **Add More Commands**: Create new cogs in `cogs/` directory
2. **Database Integration**: Set up Supabase and add database operations
3. **Custom Validation**: Add business logic validation rules
4. **Monitoring**: Set up log aggregation and monitoring
5. **Testing**: Add unit tests for your commands
6. **Deployment**: Deploy to a cloud service

## 📚 Architecture Features You Now Have

✅ **Dependency Injection**: Clean service management  
✅ **Structured Logging**: JSON logs with correlation IDs  
✅ **Error Handling**: User-friendly error messages  
✅ **Input Validation**: Pydantic models and custom rules  
✅ **Rate Limiting**: Prevent abuse and spam  
✅ **Security**: Input sanitization and validation  
✅ **Configuration**: Environment-based settings  
✅ **Monitoring**: Health checks and error statistics  

## 🚀 Quick Start (All-in-One)

If you want to skip the individual steps, use the quick start script:

```bash
# This will validate everything and start the bot
python quick_start.py
```

This script will:
1. ✅ Check Python version
2. ✅ Verify .env file exists
3. ✅ Validate Discord token
4. ✅ Install dependencies if needed
5. ✅ Run setup validation
6. ✅ Test architecture components
7. ✅ Start the bot

## 📋 Manual Validation

To check your setup manually:

```bash
# Validate your setup
python scripts/validate_setup.py

# Test the architecture
python scripts/test_setup.py

# Start the bot
python main.py
```

## 🎉 Congratulations!

Your Discord bot now has enterprise-grade architecture with:

✅ **Dependency Injection**: Clean service management and testability  
✅ **Structured Logging**: JSON logs with correlation ID tracking  
✅ **Error Handling**: User-friendly messages with unique error IDs  
✅ **Input Validation**: Pydantic models with custom validation rules  
✅ **Rate Limiting**: Prevent abuse with configurable limits  
✅ **Security**: Input sanitization and injection protection  
✅ **Configuration**: Environment-based settings with validation  
✅ **Monitoring**: Health checks and comprehensive error statistics  

## 🔄 Development Workflow

1. **Make Changes**: Edit code in your IDE
2. **Test Locally**: Use test commands to verify functionality
3. **Check Logs**: Monitor `logs/discord.log` for issues
4. **Debug**: Use correlation IDs to trace problems
5. **Deploy**: Your architecture is production-ready

## 📊 Monitoring in Production

- **Logs**: Structured JSON logs with correlation IDs
- **Errors**: Unique error IDs for tracking issues
- **Health**: `/system-status` command shows system health
- **Rate Limits**: Built-in protection against abuse
- **Security**: Automatic input sanitization

The bot is ready for real-world use and can be easily extended with new features!