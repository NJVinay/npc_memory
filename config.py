# Configuration file for NPC Memory Dialogue System
# This file centralizes all configuration values

import os
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Main configuration class for the application."""
    
    # Application Settings
    APP_NAME: str = "NPC Memory API"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = "development"
    
    # Server Settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8001"))
    RELOAD: bool = os.getenv("RELOAD", "True").lower() == "true"
    
    # Database Settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    # AI Model Settings
    USE_EXTERNAL_LLM: bool = os.getenv("USE_EXTERNAL_LLM", "false").lower() == "true"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
    
    MODEL_PATH: str = os.getenv("MODEL_PATH", "./models/mistral-7b-instruct-v0.1.Q2_K.gguf")
    MODEL_N_THREADS: int = int(os.getenv("MODEL_N_THREADS", "2"))
    MODEL_N_CTX: int = int(os.getenv("MODEL_N_CTX", "4096"))  # Optimized for 16GB RAM
    MODEL_N_BATCH: int = int(os.getenv("MODEL_N_BATCH", "128"))
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.4"))
    MODEL_MAX_TOKENS: int = int(os.getenv("MODEL_MAX_TOKENS", "150"))
    
    # Sentiment Analysis Settings
    SENTIMENT_MODEL: str = os.getenv(
        "SENTIMENT_MODEL",
        "cardiffnlp/twitter-roberta-base-sentiment"
    )
    SENTIMENT_CACHE_SIZE: int = int(os.getenv("SENTIMENT_CACHE_SIZE", "1000"))
    
    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALLOWED_ORIGINS: list = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    SERVICE_API_KEY: str = os.getenv("SERVICE_API_KEY", "")
    REQUIRE_SERVICE_API_KEY: bool = os.getenv("REQUIRE_SERVICE_API_KEY", "true").lower() == "true"
    ALLOWED_EMAIL_DOMAINS: list = [
        domain.strip().lower()
        for domain in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",")
        if domain.strip()
    ]
    ALLOWED_EMAILS: list = [
        email.strip().lower()
        for email in os.getenv("ALLOWED_EMAILS", "").split(",")
        if email.strip()
    ]
    
    # Chat Settings
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "20"))  # Fetch more from DB
    CONTEXT_WINDOW: int = int(os.getenv("CONTEXT_WINDOW", "15"))  # Send more to LLM for better memory
    
    # NPC Settings
    DEFAULT_NPC_ID: int = int(os.getenv("DEFAULT_NPC_ID", "1"))
    
    # Pagination Settings
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "50"))
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "100"))
    
    # Logging Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Rate Limiting (from security_config.py)
    RATE_LIMITS: Dict[str, str] = {
        "chat_api": "30/minute",  # Groq free tier limit
        "login": "5/minute",  # Prevent brute force
        "register": "3/minute",  # Prevent spam
        "general": "100/minute"  # General API rate limit
    }
    
    # Security Headers (from security_config.py)
    SECURITY_HEADERS: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains" if os.getenv("ENVIRONMENT") == "production" else "",
    }
    
    # Validation Rules
    MAX_REQUEST_SIZE: int = 1024 * 1024  # 1MB
    MAX_DIALOGUE_LENGTH: int = 500  # characters
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration values."""
        print(f"🔍 Validating configuration for environment: {os.getenv('ENVIRONMENT', 'development')}")
        
        if not cls.DATABASE_URL:
            print("❌ Error: DATABASE_URL is missing")
            raise ValueError("DATABASE_URL must be set in environment variables")
        print("✅ DATABASE_URL is set")
        
        # Only check for model file if using local LLM
        if not cls.USE_EXTERNAL_LLM:
            if not os.path.exists(cls.MODEL_PATH):
                print(f"❌ Error: Local model not found at {cls.MODEL_PATH}")
                raise FileNotFoundError(f"Model file not found: {cls.MODEL_PATH}")
            print(f"✅ Local model found at {cls.MODEL_PATH}")
        else:
            # Validate external LLM configuration
            if not cls.LLM_API_KEY:
                print("❌ Error: LLM_API_KEY is missing while USE_EXTERNAL_LLM=true")
                raise ValueError(f"LLM_API_KEY must be set when USE_EXTERNAL_LLM=true. Get free key at: https://console.groq.com/keys")
            print("✅ LLM_API_KEY is set")
        
        if cls.REQUIRE_SERVICE_API_KEY and not cls.SERVICE_API_KEY:
            print("❌ Error: SERVICE_API_KEY is missing while REQUIRE_SERVICE_API_KEY=true")
            raise ValueError("SERVICE_API_KEY must be set when REQUIRE_SERVICE_API_KEY=true")
        
        if cls.REQUIRE_SERVICE_API_KEY:
            print("✅ SERVICE_API_KEY is set")

        print("✨ Configuration validation successful")
        return True
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Get all configuration as a dictionary."""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith("_") and not callable(getattr(cls, key))
        }


class DevelopmentConfig(Config):
    """Development-specific configuration."""
    DEBUG = True
    RELOAD = True
    LOG_LEVEL = "DEBUG"
    ENVIRONMENT = "development"


class ProductionConfig(Config):
    """Production-specific configuration."""
    DEBUG = False
    RELOAD = False
    LOG_LEVEL = "WARNING"
    ENVIRONMENT = "production"
    
    # Override with production security
    SECRET_KEY = os.getenv("SECRET_KEY")  # Must be set in production
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
    
    @classmethod
    def validate(cls) -> bool:
        """Additional production validation."""
        super().validate()
        
        if cls.SECRET_KEY == "your-secret-key-change-in-production":
            raise ValueError("SECRET_KEY must be changed in production")
        
        if "*" in cls.ALLOWED_ORIGINS:
            raise ValueError("CORS origins must be restricted in production")
        
        return True


class TestConfig(Config):
    """Test-specific configuration."""
    DEBUG = True
    DATABASE_URL = "sqlite:///./test.db"
    SENTIMENT_CACHE_SIZE = 100
    ENVIRONMENT = "test"


# Factory function to get the right config
def get_config() -> Config:
    """Get configuration based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "test": TestConfig
    }
    
    config_class = configs.get(env, DevelopmentConfig)
    config_class.validate()
    
    return config_class


# Export the active configuration
config = get_config()
