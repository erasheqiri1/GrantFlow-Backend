from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    SUPER_ADMIN_EMAIL: str = ""
    SUPER_ADMIN_PASSWORD: str = ""

<<<<<<< Updated upstream
    # Email (Gmail SMTP)
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""   # Gmail App Password
    MAIL_FROM:     str = ""
    MAIL_SERVER:   str = "smtp.gmail.com"
    MAIL_PORT:     int = 587

    # Frontend URL (për invitation links)
    FRONTEND_URL:  str = "http://localhost:5173"
=======
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587

    FRONTEND_URL: str = "http://localhost:5173"
>>>>>>> Stashed changes

    class Config:
        env_file = ".env"

settings = Settings()