from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    DATABASE_URL: str
    SECRET_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY:   str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    SUPER_ADMIN_EMAIL: str = ""
    SUPER_ADMIN_PASSWORD: str = ""

    # Email (Gmail SMTP)
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM:     str = ""
    MAIL_SERVER:   str = "smtp.gmail.com"
    MAIL_PORT:     int = 587

    # Frontend URL
    FRONTEND_URL:  str = "http://localhost:5173"

    class Config:
        env_file = ".env"

settings = Settings()
