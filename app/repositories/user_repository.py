"""User repository for data access operations"""

from typing import Optional, List
from sqlalchemy.orm import joinedload
from app.models import User, Address
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    """Repository for user-related database operations"""
    
    def __init__(self, db=None):
        super().__init__(User)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Find user by email address"""
        return self.db.session.query(User).filter(
            User.email == email.lower()
        ).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        return self.db.session.query(User).filter(
            User.username == username
        ).first()
    
    def get_with_addresses(self, user_id) -> Optional[User]:
        """Get user with their addresses loaded"""
        return self.db.session.query(User).options(
            joinedload(User.addresses)
        ).filter(User.id == user_id).first()
    
    def create_user(self, user_data: dict) -> User:
        """Create a new user"""
        # Ensure email is lowercase
        if 'email' in user_data:
            user_data['email'] = user_data['email'].lower()
        
        user = User(**user_data)
        return self.create(user)
    
    def update_user(self, user_id, update_data: dict) -> Optional[User]:
        """Update user information"""
        # Ensure email is lowercase if being updated
        if 'email' in update_data:
            update_data['email'] = update_data['email'].lower()
        
        return self.update(user_id, update_data)
    
    def get_active_users(self) -> List[User]:
        """Get all active users"""
        return self.db.session.query(User).filter(
            User.is_active == True
        ).all()
    
    def search_users(self, query: str, limit: int = 50) -> List[User]:
        """Search users by name, email, or username"""
        search_term = f"%{query.lower()}%"
        return self.db.session.query(User).filter(
            (User.first_name.ilike(search_term)) |
            (User.last_name.ilike(search_term)) |
            (User.email.ilike(search_term)) |
            (User.username.ilike(search_term))
        ).limit(limit).all()
    
    def get_user_addresses(self, user_id) -> List[Address]:
        """Get all addresses for a user"""
        return self.db.session.query(Address).filter(
            Address.user_id == user_id
        ).all()
    
    def add_address(self, user_id, address_data: dict) -> Address:
        """Add a new address for a user"""
        address_data['user_id'] = user_id
        address = Address(**address_data)
        self.db.session.add(address)
        self.db.session.commit()
        return address
    
    def update_address(self, address_id, address_data: dict) -> Optional[Address]:
        """Update an address"""
        address = self.db.session.query(Address).filter(
            Address.id == address_id
        ).first()
        
        if not address:
            return None
        
        for key, value in address_data.items():
            if hasattr(address, key):
                setattr(address, key, value)
        
        self.db.session.commit()
        return address
    
    def delete_address(self, address_id) -> bool:
        """Delete an address"""
        address = self.db.session.query(Address).filter(
            Address.id == address_id
        ).first()
        
        if not address:
            return False
        
        self.db.session.delete(address)
        self.db.session.commit()
        return True
    
    def email_exists(self, email: str, exclude_user_id=None) -> bool:
        """Check if email already exists"""
        query = self.db.session.query(User).filter(
            User.email == email.lower()
        )
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        
        return query.first() is not None
    
    def username_exists(self, username: str, exclude_user_id=None) -> bool:
        """Check if username already exists"""
        query = self.db.session.query(User).filter(
            User.username == username
        )
        
        if exclude_user_id:
            query = query.filter(User.id != exclude_user_id)
        
        return query.first() is not None 