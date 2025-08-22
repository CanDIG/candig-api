"""
Configuration Settings

This module defines the variables for the app.
"""
import os

class Settings:
    _DB_USER: str = os.getenv("DB_USER", "admin")
    _DB_PASSWORD: str = os.getenv("DB_PASSWORD", "admin")
    _DB_HOST: str = os.getenv("DB_HOST", "localhost")
    _DB_PORT: str = os.getenv("DB_PORT", "5432")
    _DB_NAME: str = os.getenv("DB_NAME", "candig_api")

    OMOP_SCHEMA = "omop"
    CANDIG_SCHEMA = "candig"

    DATABASE_URI: str = os.getenv(
        "DATABASE_URI",
        f"postgresql://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}",
    )


settings = Settings()