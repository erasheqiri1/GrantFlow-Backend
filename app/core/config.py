from pydantic_settings import BaseSettings
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    JWT_SECRET: str = SECRET_KEY if False else ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    class Config:
        env_file = ".env"

settings = Settings()