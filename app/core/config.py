from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    class Config:
        env_file = ".env"

settings = Settings()