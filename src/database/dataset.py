"""
Database Extensions

This module defines additional tables that extend
the standard OMOP Common Data Model to support DHDP requirements.

Tables added:
- dataset: Stores dataset info

"""

from typing import Any, Dict, Optional

from sqlalchemy import JSON, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

from ..config import settings

Base = declarative_base()


class Dataset(Base):
    __tablename__ = "dataset"
    __table_args__ = {"schema": settings.CANDIG_SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_value: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True, default={}
    )

    person_mappings = relationship(
        "PersonInDataset", back_populates="dataset", cascade="all, delete-orphan"
    )