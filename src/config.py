"""
Configuration Settings

This module defines the variables for the app.
"""

import os
import json


class Settings:
    DB_USER: str = os.getenv("DB_USER", "admin")

    @property
    def DB_PASSWORD(self) -> str:
        password_file = os.getenv("DB_PASSWORD_FILE")
        if password_file and os.path.exists(password_file):
            with open(password_file, "r") as f:
                return f.read().strip()
        return os.getenv("DB_PASSWORD", "admin")

    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "candig_api")
    CANDIG_SCHEMA: str = os.getenv("CANDIG_SCHEMA", "candig")
    CDM_SCHEMA: str = os.getenv("CDM_SCHEMA", "omop")
    TO_INGEST_DIR = "upload/to_ingest"
    RESULTS_DIR = "upload/results"
    with open("src/concept_mappings.json", "r") as f:
        MAPPING_JSON = json.load(f)

    @property
    def DATABASE_URI(self) -> str:
        return os.getenv(
            "DATABASE_URI",
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}",
        )


settings = Settings()
