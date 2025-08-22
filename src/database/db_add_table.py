"""
Database Extensions

This module defines additional tables that extend 
the standard OMOP Common Data Model to support DHDP requirements.

Tables added:
- dataset: Stores dataset info
- person_in_dataset: Mapping persons to datasets

"""

from sqlalchemy import Column, Integer, String, JSON, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base, relationship
from ..config import settings

Base = declarative_base()

class Dataset(Base):
    __tablename__ = 'dataset'
    __table_args__ = {'schema': settings.CANDIG_SCHEMA}

    dataset_id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_source_value = Column(String(64), unique=True, nullable=False)
    dataset_info = Column(String, nullable=False)

    person_mappings = relationship("PersonInDataset", back_populates="dataset", cascade="all, delete-orphan")

class PersonInDataset(Base):
    __tablename__ = 'person_in_dataset'

    dataset_id = Column(Integer, ForeignKey(f'{settings.CANDIG_SCHEMA}.dataset.dataset_id'), nullable=False)
    person_id = Column(Integer, unique=True, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('dataset_id', 'person_id'),
        {'schema': settings.CANDIG_SCHEMA}
    )

    dataset = relationship("Dataset", back_populates="person_mappings")