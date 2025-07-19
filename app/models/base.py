"""Base model with common fields and functionality"""

import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class BaseModel(Base):
    """Base model class with common fields"""
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self, exclude_fields=None):
        """Convert model instance to dictionary"""
        if exclude_fields is None:
            exclude_fields = []
        
        result = {}
        for column in self.__table__.columns:
            if column.name not in exclude_fields:
                value = getattr(self, column.name)
                # Handle datetime objects
                if isinstance(value, datetime):
                    value = value.isoformat()
                # Handle UUID objects
                elif isinstance(value, uuid.UUID):
                    value = str(value)
                result[column.name] = value
        return result
    
    def update_from_dict(self, data, exclude_fields=None):
        """Update model instance from dictionary"""
        if exclude_fields is None:
            exclude_fields = ['id', 'created_at', 'updated_at']
        
        for key, value in data.items():
            if key not in exclude_fields and hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def create(cls, **kwargs):
        """Create new instance with given kwargs"""
        instance = cls(**kwargs)
        return instance
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>" 