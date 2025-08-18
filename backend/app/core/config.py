from pydantic import BaseModel
import os

class Settings(BaseModel):
    APP_NAME: str = os.getenv("APP_NAME", "Oraculum")
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    BACKEND_CORS_ORIGINS: str = os.getenv(
        "BACKEND_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
settings = Settings()
