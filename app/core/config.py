from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb+srv://infozodex_db_user:absolutions@data.yycywiw.mongodb.net"
    DATABASE_NAME: str = "videocall_app"
    SECRET_KEY: str = "videocall-super-secret-key-2024-min-32-chars-safe"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "Admin@123"
    UPLOAD_DIR: str = "static/uploads"
    MAX_FILE_SIZE: int = 10485760

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Debug — startup pe confirm karega
print(f"🔗 MongoDB: {settings.MONGODB_URL[:45]}...")
