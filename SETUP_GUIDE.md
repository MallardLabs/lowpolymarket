# Discord Prediction Market Bot - Setup Guide

This guide will help you set up the Discord Prediction Market Bot with Supabase database integration.

## Prerequisites

- Python 3.8+
- Discord Bot Token
- Supabase Project
- DRIP API Access (for points system)

## Step 1: Clone and Install Dependencies

```bash
# Install Python dependencies
pip3 install -r requirements.txt
```

## Step 2: Get Your Supabase Configuration

### 2.1 Database Connection String
1. Go to your **Supabase Dashboard**
2. Navigate to **Settings → Database**
3. Copy the **Connection string** 
4. **Choose "Transaction pooler"** (port 6543) - this is optimal for Discord bots

Example:
```
postgresql://postgres.zxytvcfgyyzvlhpjffkm:[YOUR-PASSWORD]@aws-0-us-east-2.pooler.supabase.com:6543/postgres
```

### 2.2 Supabase Project URL
1. In your **Supabase Dashboard**
2. Navigate to **Settings → API**
3. Copy the **Project URL**

Example:
```
https://zxytvcfgyyzvlhpjffkm.supabase.co
```

### 2.3 New Supabase API Keys (June 2025+ Format)
1. In **Settings → API**
2. Look for the **new API keys section**
3. Copy both keys:
   - **Publishable Key**: `sb_publishable_...`
   - **Secret Key**: `sb_secret_...`

> **Note**: These are the new format keys. The bot only supports the new keys, not the legacy JWT format.

## Step 3: Configure Environment Variables

### 3.1 Create Your .env File
```bash
cp .env.template .env
```

### 3.2 Edit .env with Your Values
```bash
# Environment
ENVIRONMENT=development
DEBUG=true

# Discord Bot
DISCORD_TOKEN=your_actual_discord_bot_token_here
DISCORD_COMMAND_PREFIX=!
DISCORD_SYNC_COMMANDS=true

# Database Configuration
DATABASE_URL=postgresql://postgres.your-ref:your-password@aws-0-us-east-2.pooler.supabase.com:6543/postgres
DATABASE_SUPABASE_URL=https://your-project-ref.supabase.co
DATABASE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_your_actual_key_here
DATABASE_SUPABASE_SECRET_KEY=sb_secret_your_actual_key_here

# DRIP API (your existing points system)
API_API_KEY=your_drip_api_key_here
API_REALM_ID=your_drip_realm_id_here
```

## Step 4: Validate Configuration

Test your configuration before proceeding:

```bash
# Check for missing environment variables
python3 scripts/validate_config.py --check-env-vars

# Validate full configuration
python3 scripts/validate_config.py --show-summary
```

You should see:
```
✅ All required environment variables are set
✅ Configuration validation successful!
```

## Step 5: Set Up Database Schema

### 5.1 Test Database Connection
```bash
python3 scripts/setup_database.py --test-only
```

You should see:
```
✅ PostgreSQL connection successful
✅ Supabase API connection successful
```

### 5.2 Create Database Schema
```bash
python3 scripts/setup_database.py
```

This will:
- Create all necessary tables (guilds, predictions, bets, etc.)
- Set up indexes for performance
- Configure triggers and functions
- Enable real-time subscriptions

## Step 6: Test the Bot

### 6.1 Run Configuration Test
```bash
python3 test_config.py
```

### 6.2 Start the Bot
```bash
python3 bot.py
```

You should see:
```
============================================================
CONFIGURATION SUMMARY
============================================================
Environment: development
Debug Mode: True
...
✅ Configuration is ready for use!

Bot is ready! YourBotName
```

## Step 7: Test Prediction Markets

Once your bot is running, test it in Discord:

1. **Create a prediction**: `/predict "Will it rain tomorrow?" "Yes" "No" 24h`
2. **Place a bet**: `/bet 1 Yes 100`
3. **Check markets**: `/markets`
4. **Resolve prediction**: `/resolve 1 Yes` (admin only)

## Troubleshooting

### Common Issues

#### ❌ "Missing required environment variables"
- Check your `.env` file exists and has all required variables
- Make sure variable names match exactly (case-sensitive)

#### ❌ "Database connection failed"
- Verify your `DATABASE_URL` is correct
- Check your Supabase project is active
- Ensure you're using the Transaction Pooler URL (port 6543)

#### ❌ "Supabase API connection failed"
- Verify your `DATABASE_SUPABASE_URL` is correct
- Check your API keys are the new format (`sb_publishable_...`, `sb_secret_...`)
- Make sure your Supabase project has the new API keys enabled

#### ❌ "Discord token validation failed"
- Ensure your Discord token is at least 50 characters
- Check the token is from the correct bot application

### Debug Mode

Enable debug mode for detailed logging:

```bash
# In your .env file
DEBUG=true
LOG_LEVEL=DEBUG
```

### Getting Help

1. **Check logs**: Look at `logs/discord.log` for detailed error messages
2. **Validate config**: Run `python3 scripts/validate_config.py --show-summary`
3. **Test database**: Run `python3 scripts/setup_database.py --test-only`

## Environment-Specific Configuration

### Development
- Debug mode enabled
- Detailed console logging
- Lenient rate limits
- Memory-only caching

### Production
- Debug mode disabled
- JSON logging with rotation
- Strict rate limits
- Redis caching recommended

Switch environments by changing:
```bash
ENVIRONMENT=production  # or development, staging
```

## Next Steps

Once your bot is running:

1. **Configure Discord permissions** for your bot
2. **Set up admin roles** for prediction resolution
3. **Configure rate limits** based on your server size
4. **Set up monitoring** and logging
5. **Consider Redis caching** for production use

## Security Notes

- **Never commit your `.env` file** to version control
- **Use environment-specific configurations** for different deployments
- **Rotate your API keys regularly**
- **Use the secret key only in secure backend operations**
- **Enable Row Level Security** in Supabase for production

## Support

If you encounter issues:
1. Check this setup guide
2. Review the configuration documentation in `config/README.md`
3. Run the validation scripts to identify specific problems
4. Check the logs for detailed error messages