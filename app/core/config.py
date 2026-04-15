from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Core App Settings
    PROJECT_NAME: str = "E-Commerce Platform"
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "e_commerce"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email OTP Configuration
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@ecommerce.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    @model_validator(mode="after")
    def validate_security_settings(self):
        if not self.SECRET_KEY.strip():
            raise ValueError("SECRET_KEY must be set in .env")
        return self
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",    
        case_sensitive=False 
    )

settings = Settings()


