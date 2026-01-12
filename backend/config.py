from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    db_host: str = Field(..., alias="DB_HOST")
    db_port: int = Field(3306, alias="DB_PORT")
    db_user: str = Field(..., alias="DB_USER")
    db_password: str = Field(..., alias="DB_PASSWORD")
    db_name: str = Field(..., alias="DB_NAME")
    
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    api_debug: bool = Field(False, alias="API_DEBUG")
    
    class Config:
        env_file = str(Path(__file__).parent / ".env.local")
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()