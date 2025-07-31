"""
Example usage of security enhancements for the Discord Prediction Market Bot.

This file demonstrates how to use:
- Input sanitization and validation
- Audit logging for critical operations
- Secure token handling
- Data encryption for sensitive information
- Security middleware for Discord commands
"""

import asyncio
import discord
from discord.ext import commands
from datetime import datetime

# Import security components
from core.security import (
    InputSanitizer, TokenManager, DataEncryption, AuditLogger,
    AuditEventType, SecurityLevel, sanitize_user_input, audit_user_action,
    encrypt_sensitive_data, decrypt_sensitive_data
)
from core.security_middleware import (
    SecurityMiddleware, secure_prediction_command, secure_betting_command,
    secure_admin_command, secure_user_command
)
from core.exceptions import SecurityError


class SecurityExampleCog(commands.Cog):
    """Example cog demonstrating security features."""
    
    def __init__(self, bot):
        self.bot = bot
        self.security_middleware = SecurityMiddleware()
        self.token_manager = TokenManager()
        self.data_encryption = DataEncryption("example_password")
        self.audit_logger = AuditLogger()
    
    # Example 1: Basic input sanitization
    @discord.app_commands.command(name="sanitize_example")
    async def sanitize_example(self, interaction: discord.Interaction, user_input: str):
        """Example of input sanitization."""
        try:
            # Sanitize user input
            sanitized_input = sanitize_user_input(user_input, max_length=500)
            
            await interaction.response.send_message(
                f"**Original:** {user_input[:100]}...\n"
                f"**Sanitized:** {sanitized_input[:100]}...",
                ephemeral=True
            )
            
        except SecurityError as e:
            await interaction.response.send_message(
                f"🔒 Security violation detected: {e.user_message}",
                ephemeral=True
            )
    
    # Example 2: Secure prediction creation with comprehensive security
    @secure_prediction_command(
        audit_event_type=AuditEventType.PREDICTION_CREATED,
        security_level=SecurityLevel.HIGH
    )
    @discord.app_commands.command(name="create_secure_prediction")
    async def create_secure_prediction(
        self, 
        interaction: discord.Interaction, 
        question: str,
        option1: str,
        option2: str,
        duration: str = "1d"
    ):
        """Create a prediction with comprehensive security."""
        
        # The security middleware automatically:
        # - Sanitizes all string inputs
        # - Logs the audit event
        # - Monitors for anomalies
        # - Applies rate limiting
        
        prediction_data = {
            "question": question,
            "options": [option1, option2],
            "duration": duration,
            "creator_id": interaction.user.id,
            "guild_id": interaction.guild.id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Encrypt sensitive prediction data if needed
        encrypted_data = encrypt_sensitive_data(prediction_data)
        
        await interaction.response.send_message(
            f"✅ **Secure Prediction Created**\n"
            f"**Question:** {question}\n"
            f"**Options:** {option1} vs {option2}\n"
            f"**Duration:** {duration}\n"
            f"*All inputs have been sanitized and logged for security.*",
            ephemeral=False
        )
    
    # Example 3: Secure betting with sensitive data handling
    @secure_betting_command(
        audit_event_type=AuditEventType.BET_PLACED,
        security_level=SecurityLevel.HIGH,
        sensitive_params=['amount']  # Mark amount as sensitive
    )
    @discord.app_commands.command(name="place_secure_bet")
    async def place_secure_bet(
        self,
        interaction: discord.Interaction,
        prediction_id: str,
        option: str,
        amount: int
    ):
        """Place a bet with security enhancements."""
        
        # Security middleware handles:
        # - Input sanitization
        # - Audit logging (with sensitive data masking)
        # - Rate limiting
        # - Anomaly detection
        
        bet_data = {
            "prediction_id": prediction_id,
            "user_id": interaction.user.id,
            "option": option,
            "amount": amount,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Encrypt sensitive bet information
        encrypted_bet = encrypt_sensitive_data(bet_data)
        
        await interaction.response.send_message(
            f"💰 **Secure Bet Placed**\n"
            f"**Prediction:** {prediction_id}\n"
            f"**Option:** {option}\n"
            f"**Amount:** {amount:,} points\n"
            f"*Your bet has been securely processed and logged.*"
        )
    
    # Example 4: Admin command with maximum security
    @secure_admin_command(
        audit_event_type=AuditEventType.ADMIN_ACTION,
        security_level=SecurityLevel.CRITICAL
    )
    @discord.app_commands.command(name="admin_resolve")
    async def admin_resolve_prediction(
        self,
        interaction: discord.Interaction,
        prediction_id: str,
        winning_option: str,
        reason: str = "Admin resolution"
    ):
        """Admin command to resolve predictions with maximum security."""
        
        # This command has:
        # - Admin-only permissions
        # - Critical security level
        # - Strict rate limiting (5 per 5 minutes)
        # - Comprehensive audit logging
        # - Input sanitization with strict mode
        
        resolution_data = {
            "prediction_id": prediction_id,
            "winning_option": winning_option,
            "reason": reason,
            "resolved_by": interaction.user.id,
            "resolved_at": datetime.utcnow().isoformat()
        }
        
        # Log additional audit event for resolution
        audit_user_action(
            event_type=AuditEventType.PREDICTION_RESOLVED,
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            details=resolution_data,
            security_level=SecurityLevel.CRITICAL
        )
        
        await interaction.response.send_message(
            f"⚖️ **Prediction Resolved (Admin)**\n"
            f"**Prediction:** {prediction_id}\n"
            f"**Winner:** {winning_option}\n"
            f"**Reason:** {reason}\n"
            f"*Resolution has been logged with maximum security.*"
        )
    
    # Example 5: Token management demonstration
    @discord.app_commands.command(name="token_example")
    async def token_example(self, interaction: discord.Interaction):
        """Demonstrate secure token handling."""
        
        # Generate a secure token
        secure_token = self.token_manager.generate_secure_token()
        
        # Encrypt the token for storage
        encrypted_token = self.token_manager.encrypt_token(secure_token)
        
        # Hash the token for verification
        token_hash, salt = self.token_manager.hash_token(secure_token)
        
        await interaction.response.send_message(
            f"🔐 **Token Security Example**\n"
            f"**Generated Token:** `{secure_token[:8]}...` (truncated)\n"
            f"**Encrypted Length:** {len(encrypted_token)} characters\n"
            f"**Hash Length:** {len(token_hash)} characters\n"
            f"*Tokens are securely generated, encrypted, and hashed.*",
            ephemeral=True
        )
    
    # Example 6: Data encryption demonstration
    @discord.app_commands.command(name="encryption_example")
    async def encryption_example(self, interaction: discord.Interaction):
        """Demonstrate data encryption capabilities."""
        
        # Example sensitive data
        sensitive_data = {
            "user_id": interaction.user.id,
            "api_key": "secret_key_12345",
            "personal_info": "sensitive information",
            "balance": 50000
        }
        
        # Encrypt the entire data structure
        encrypted_data = self.data_encryption.encrypt_data(sensitive_data)
        
        # Encrypt only specific fields
        sensitive_fields = ["api_key", "personal_info"]
        field_encrypted = self.data_encryption.encrypt_sensitive_fields(
            sensitive_data.copy(), 
            sensitive_fields
        )
        
        await interaction.response.send_message(
            f"🔒 **Data Encryption Example**\n"
            f"**Original Data Size:** {len(str(sensitive_data))} characters\n"
            f"**Encrypted Data Size:** {len(encrypted_data)} characters\n"
            f"**Field Encryption:** {len(sensitive_fields)} fields encrypted\n"
            f"*Sensitive data is securely encrypted for storage.*",
            ephemeral=True
        )
    
    # Example 7: Manual audit logging
    @discord.app_commands.command(name="audit_example")
    async def audit_example(self, interaction: discord.Interaction, action: str):
        """Demonstrate manual audit logging."""
        
        # Log a custom audit event
        audit_user_action(
            event_type=AuditEventType.USER_LOGIN,  # Example event type
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            details={
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "ip_address": "192.168.1.1",  # Would be real IP in production
                "user_agent": "Discord Bot"
            },
            success=True,
            security_level=SecurityLevel.MEDIUM
        )
        
        await interaction.response.send_message(
            f"📝 **Audit Event Logged**\n"
            f"**Action:** {action}\n"
            f"**User:** {interaction.user.mention}\n"
            f"**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"*Event has been logged to the audit trail.*"
        )
    
    # Example 8: Security monitoring demonstration
    @secure_user_command()
    @discord.app_commands.command(name="monitor_example")
    async def monitor_example(self, interaction: discord.Interaction, test_input: str):
        """Demonstrate security monitoring features."""
        
        # The security middleware automatically monitors for:
        # - Input anomalies (length, entropy, patterns)
        # - Rate limit abuse
        # - Suspicious patterns
        # - Failed attempts
        
        # Simulate some monitoring checks
        input_length = len(test_input)
        has_special_chars = any(c in test_input for c in "<>\"'&;")
        
        monitoring_results = {
            "input_length": input_length,
            "has_special_chars": has_special_chars,
            "monitoring_active": True,
            "anomalies_detected": input_length > 1000 or has_special_chars
        }
        
        await interaction.response.send_message(
            f"🔍 **Security Monitoring Results**\n"
            f"**Input Length:** {input_length} characters\n"
            f"**Special Characters:** {'Yes' if has_special_chars else 'No'}\n"
            f"**Anomalies Detected:** {'Yes' if monitoring_results['anomalies_detected'] else 'No'}\n"
            f"*All inputs are continuously monitored for security threats.*"
        )


# Example of using security features in a service class
class SecurePredictionService:
    """Example service class with security enhancements."""
    
    def __init__(self):
        self.sanitizer = InputSanitizer()
        self.audit_logger = AuditLogger()
        self.data_encryption = DataEncryption("service_password")
    
    async def create_prediction_securely(
        self, 
        user_id: int, 
        guild_id: int, 
        question: str, 
        options: list
    ):
        """Create a prediction with comprehensive security."""
        
        try:
            # 1. Sanitize inputs
            sanitized_question = self.sanitizer.sanitize_text(
                question, 
                max_length=500, 
                strict_mode=True
            )
            
            sanitized_options = []
            for option in options:
                sanitized_option = self.sanitizer.sanitize_text(
                    option, 
                    max_length=100, 
                    strict_mode=True
                )
                sanitized_options.append(sanitized_option)
            
            # 2. Create prediction data
            prediction_data = {
                "question": sanitized_question,
                "options": sanitized_options,
                "creator_id": user_id,
                "guild_id": guild_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # 3. Encrypt sensitive data
            encrypted_data = self.data_encryption.encrypt_data(prediction_data)
            
            # 4. Log audit event
            self.audit_logger.log_user_action(
                event_type=AuditEventType.PREDICTION_CREATED,
                user_id=user_id,
                guild_id=guild_id,
                details={
                    "question_length": len(sanitized_question),
                    "options_count": len(sanitized_options),
                    "encrypted": True
                },
                success=True,
                security_level=SecurityLevel.HIGH
            )
            
            return {
                "success": True,
                "prediction_id": "pred_12345",  # Would be generated
                "encrypted_data": encrypted_data
            }
            
        except SecurityError as e:
            # Log security violation
            self.audit_logger.log_security_violation(
                violation_type="prediction_creation_blocked",
                user_id=user_id,
                guild_id=guild_id,
                details={
                    "error": str(e),
                    "question_length": len(question),
                    "options_count": len(options)
                }
            )
            
            return {
                "success": False,
                "error": "Security violation detected",
                "error_details": str(e)
            }


# Example of environment-specific security configuration
class SecurityConfig:
    """Security configuration for different environments."""
    
    @staticmethod
    def get_production_config():
        """Get production security configuration."""
        return {
            "strict_sanitization": True,
            "audit_all_events": True,
            "encrypt_sensitive_data": True,
            "max_input_length": 1000,
            "rate_limit_strict": True,
            "security_monitoring": True,
            "log_security_events": True
        }
    
    @staticmethod
    def get_development_config():
        """Get development security configuration."""
        return {
            "strict_sanitization": False,
            "audit_all_events": True,
            "encrypt_sensitive_data": False,
            "max_input_length": 5000,
            "rate_limit_strict": False,
            "security_monitoring": True,
            "log_security_events": True
        }
    
    @staticmethod
    def get_testing_config():
        """Get testing security configuration."""
        return {
            "strict_sanitization": False,
            "audit_all_events": False,
            "encrypt_sensitive_data": False,
            "max_input_length": 10000,
            "rate_limit_strict": False,
            "security_monitoring": False,
            "log_security_events": False
        }


# Example usage in a bot setup
async def setup_secure_bot():
    """Example of setting up a bot with security enhancements."""
    
    # Initialize security components
    token_manager = TokenManager()
    data_encryption = DataEncryption("bot_encryption_password")
    audit_logger = AuditLogger()
    
    # Create bot with security middleware
    intents = discord.Intents.default()
    intents.message_content = True
    
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    # Add security cog
    await bot.add_cog(SecurityExampleCog(bot))
    
    # Log bot startup
    audit_logger.log_user_action(
        event_type=AuditEventType.USER_LOGIN,
        user_id=0,  # Bot user ID
        details={
            "event": "bot_startup",
            "security_enabled": True,
            "timestamp": datetime.utcnow().isoformat()
        },
        success=True,
        security_level=SecurityLevel.HIGH
    )
    
    print("🔒 Bot initialized with comprehensive security enhancements!")
    return bot


if __name__ == "__main__":
    # Example of running security tests
    async def run_security_examples():
        """Run security enhancement examples."""
        
        print("🔒 Security Enhancement Examples")
        print("=" * 50)
        
        # Example 1: Input sanitization
        sanitizer = InputSanitizer()
        malicious_input = "<script>alert('xss')</script>Hello World"
        sanitized = sanitizer.sanitize_text(malicious_input)
        print(f"Original: {malicious_input}")
        print(f"Sanitized: {sanitized}")
        print()
        
        # Example 2: Token management
        token_manager = TokenManager()
        token = token_manager.generate_secure_token()
        encrypted = token_manager.encrypt_token(token)
        decrypted = token_manager.decrypt_token(encrypted)
        print(f"Token: {token}")
        print(f"Encrypted: {encrypted[:50]}...")
        print(f"Decrypted: {decrypted}")
        print()
        
        # Example 3: Data encryption
        encryption = DataEncryption("example_password")
        data = {"secret": "sensitive_information", "public": "normal_data"}
        encrypted_data = encryption.encrypt_data(data)
        decrypted_data = encryption.decrypt_data(encrypted_data)
        print(f"Original: {data}")
        print(f"Encrypted: {encrypted_data[:50]}...")
        print(f"Decrypted: {decrypted_data}")
        print()
        
        print("✅ Security examples completed successfully!")
    
    # Run the examples
    asyncio.run(run_security_examples())