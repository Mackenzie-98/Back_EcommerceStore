"""User models for authentication and profiles"""

import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, create_refresh_token

from .base import BaseModel


class UserRole(enum.Enum):
    """User role enumeration"""
    CUSTOMER = "customer"
    ADMIN = "admin"
    STAFF = "staff"
    MANAGER = "manager"


class User(BaseModel):
    """User model for authentication and profile data"""
    __tablename__ = 'users'
    
    # Basic Information
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Profile Information
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Status Fields
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_staff = Column(Boolean, default=False, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    
    # Authentication Tracking
    last_login = Column(DateTime(timezone=True), nullable=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    addresses = relationship("Address", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    cart = relationship("Cart", back_populates="user", uselist=False)
    wishlists = relationship("Wishlist", back_populates="user", cascade="all, delete-orphan")
    events = relationship("UserEvent", back_populates="user")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
        Index('idx_user_role', 'role'),
    )
    
    def set_password(self, password: str):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password: str) -> bool:
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_tokens(self):
        """Generate JWT access and refresh tokens"""
        additional_claims = {
            "role": self.role.value,
            "is_staff": self.is_staff,
            "is_verified": self.is_verified
        }
        
        access_token = create_access_token(
            identity=str(self.id),
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(identity=str(self.id))
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer"
        }
    
    def get_full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username or self.email
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        # Admin has all permissions
        if self.role == UserRole.ADMIN:
            return True
        
        # Staff permissions
        if self.role == UserRole.STAFF and permission in [
            'orders:read', 'products:read', 'users:read'
        ]:
            return True
        
        # Manager permissions
        if self.role == UserRole.MANAGER and permission in [
            'orders:read', 'orders:write', 'products:read', 'products:write',
            'users:read', 'analytics:read'
        ]:
            return True
        
        # Customer permissions
        if self.role == UserRole.CUSTOMER and permission in [
            'profile:read', 'profile:write', 'orders:read_own', 'cart:write',
            'wishlist:write', 'reviews:write'
        ]:
            return True
        
        return False
    
    def mark_email_verified(self):
        """Mark email as verified"""
        self.is_verified = True
        self.email_verified_at = datetime.utcnow()
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary, optionally excluding sensitive data"""
        exclude_fields = ['password_hash'] if not include_sensitive else []
        data = super().to_dict(exclude_fields=exclude_fields)
        
        # Add computed fields
        data['full_name'] = self.get_full_name()
        data['role'] = self.role.value if self.role else None
        
        return data


class Address(BaseModel):
    """Address model for shipping and billing"""
    __tablename__ = 'addresses'
    
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Address Type
    type = Column(String(20), nullable=False)  # 'billing', 'shipping'
    
    # Address Fields
    line1 = Column(String(255), nullable=False)
    line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False)  # ISO country code
    
    # Status
    is_default = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="addresses")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_address_user_type', 'user_id', 'type'),
        Index('idx_address_user_default', 'user_id', 'is_default'),
    )
    
    def get_formatted_address(self) -> str:
        """Get formatted address string"""
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        parts.append(self.country.upper())
        return "\n".join(parts)
    
    def to_dict(self):
        """Convert address to dictionary with formatted version"""
        data = super().to_dict()
        data['formatted_address'] = self.get_formatted_address()
        return data 