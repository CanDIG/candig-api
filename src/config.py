"""
Configuration Settings

This module defines the variables for the app.
"""
import os

class Settings:
    _DB_USER: str = os.getenv("DB_USER", "admin")
    @property
    def _DB_PASSWORD(self) -> str:
        password_file = os.getenv("DB_PASSWORD_FILE")
        if password_file and os.path.exists(password_file):
            with open(password_file, 'r') as f:
                return f.read().strip()
        return os.getenv("DB_PASSWORD", "admin")
    _DB_HOST: str = os.getenv("DB_HOST", "localhost")
    _DB_PORT: str = os.getenv("DB_PORT", "5432")
    _DB_NAME: str = os.getenv("DB_NAME", "candig_api")

    OMOP_SCHEMA = "omop"
    CANDIG_SCHEMA = "candig"

    @property
    def DATABASE_URI(self) -> str:
        return os.getenv(
            "DATABASE_URI",
            f"postgresql://{self._DB_USER}:{self._DB_PASSWORD}@{self._DB_HOST}:{self._DB_PORT}/{self._DB_NAME}",
        )


settings = Settings()