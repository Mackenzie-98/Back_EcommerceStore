"""Base repository with common database operations"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.extensions import db


class BaseRepository(ABC):
    """Abstract base repository class"""
    
    def __init__(self, model_class):
        self.model_class = model_class
        self.db: Session = db.session
    
    def get_by_id(self, id: UUID) -> Optional[Any]:
        """Get entity by ID"""
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()
    
    def get_all(self, limit: int = None, offset: int = None) -> List[Any]:
        """Get all entities with optional pagination"""
        query = self.db.query(self.model_class)
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def create(self, data: Dict[str, Any]) -> Any:
        """Create new entity"""
        entity = self.model_class(**data)
        self.db.add(entity)
        self.db.flush()  # Get ID without committing
        return entity
    
    def update(self, entity: Any, data: Dict[str, Any]) -> Any:
        """Update existing entity"""
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        
        self.db.flush()
        return entity
    
    def delete(self, entity: Any) -> bool:
        """Delete entity"""
        try:
            self.db.delete(entity)
            self.db.flush()
            return True
        except Exception:
            return False
    
    def delete_by_id(self, id: UUID) -> bool:
        """Delete entity by ID"""
        entity = self.get_by_id(id)
        if entity:
            return self.delete(entity)
        return False
    
    def count(self, filters: Dict[str, Any] = None) -> int:
        """Count entities with optional filters"""
        query = self.db.query(func.count(self.model_class.id))
        
        if filters:
            query = self._apply_filters(query, filters)
        
        return query.scalar()
    
    def filter_by(self, filters: Dict[str, Any], limit: int = None, 
                  offset: int = None, order_by: str = None) -> List[Any]:
        """Filter entities by criteria"""
        query = self.db.query(self.model_class)
        
        # Apply filters
        query = self._apply_filters(query, filters)
        
        # Apply ordering
        if order_by:
            if order_by.startswith('-'):
                # Descending order
                field = order_by[1:]
                if hasattr(self.model_class, field):
                    query = query.order_by(getattr(self.model_class, field).desc())
            else:
                # Ascending order
                if hasattr(self.model_class, order_by):
                    query = query.order_by(getattr(self.model_class, order_by))
        
        # Apply pagination
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def find_one_by(self, filters: Dict[str, Any]) -> Optional[Any]:
        """Find single entity by criteria"""
        query = self.db.query(self.model_class)
        query = self._apply_filters(query, filters)
        return query.first()
    
    def exists(self, filters: Dict[str, Any]) -> bool:
        """Check if entity exists with given criteria"""
        query = self.db.query(self.model_class.id)
        query = self._apply_filters(query, filters)
        return query.first() is not None
    
    def bulk_create(self, items: List[Dict[str, Any]]) -> List[Any]:
        """Create multiple entities"""
        entities = [self.model_class(**item) for item in items]
        self.db.bulk_save_objects(entities, return_defaults=True)
        return entities
    
    def bulk_update(self, updates: List[Dict[str, Any]]) -> bool:
        """Update multiple entities"""
        try:
            self.db.bulk_update_mappings(self.model_class, updates)
            return True
        except Exception:
            return False
    
    def commit(self):
        """Commit transaction"""
        self.db.commit()
    
    def rollback(self):
        """Rollback transaction"""
        self.db.rollback()
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query"""
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                if isinstance(value, list):
                    # IN clause for lists
                    query = query.filter(getattr(self.model_class, key).in_(value))
                elif isinstance(value, dict):
                    # Range filters
                    if 'gte' in value:
                        query = query.filter(getattr(self.model_class, key) >= value['gte'])
                    if 'lte' in value:
                        query = query.filter(getattr(self.model_class, key) <= value['lte'])
                    if 'gt' in value:
                        query = query.filter(getattr(self.model_class, key) > value['gt'])
                    if 'lt' in value:
                        query = query.filter(getattr(self.model_class, key) < value['lt'])
                else:
                    # Exact match
                    query = query.filter(getattr(self.model_class, key) == value)
        
        return query 