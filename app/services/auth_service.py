"""Authentication service for user management and JWT handling"""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, get_jwt

from app.models import User, Address
from app.repositories import UserRepository
from app.extensions import redis_client


class AuthService:
    """Service for authentication and user management"""
    
    def __init__(self):
        self.user_repo = UserRepository()
    
    def register_user(self, email: str, password: str, **kwargs) -> Dict[str, Any]:
        """Register a new user"""
        # Check if user already exists
        if self.user_repo.find_one_by({'email': email}):
            return {
                'success': False,
                'error': 'User with this email already exists'
            }
        
        # Check username if provided
        username = kwargs.get('username')
        if username and self.user_repo.find_one_by({'username': username}):
            return {
                'success': False,
                'error': 'Username already taken'
            }
        
        # Create user
        user_data = {
            'email': email,
            'username': username,
            'first_name': kwargs.get('first_name'),
            'last_name': kwargs.get('last_name'),
            'phone': kwargs.get('phone')
        }
        
        user = self.user_repo.create(user_data)
        user.set_password(password)
        
        try:
            self.user_repo.commit()
            
            # Generate tokens
            tokens = user.generate_tokens()
            
            return {
                'success': True,
                'user': user.to_dict(),
                'tokens': tokens
            }
        except Exception as e:
            self.user_repo.rollback()
            return {
                'success': False,
                'error': 'Failed to create user'
            }
    
    def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return tokens"""
        user = self.user_repo.find_one_by({'email': email})
        
        if not user:
            return {
                'success': False,
                'error': 'Invalid email or password'
            }
        
        if not user.is_active:
            return {
                'success': False,
                'error': 'Account is deactivated'
            }
        
        if not user.check_password(password):
            return {
                'success': False,
                'error': 'Invalid email or password'
            }
        
        # Update last login
        user.update_last_login()
        self.user_repo.commit()
        
        # Generate tokens
        tokens = user.generate_tokens()
        
        return {
            'success': True,
            'user': user.to_dict(),
            'tokens': tokens
        }
    
    def refresh_token(self, refresh_token_jti: str) -> Dict[str, Any]:
        """Refresh access token"""
        try:
            # Check if refresh token is blacklisted
            if redis_client.get(f"blacklist:{refresh_token_jti}"):
                return {
                    'success': False,
                    'error': 'Token has been revoked'
                }
            
            user_id = get_jwt_identity()
            user = self.user_repo.get_by_id(UUID(user_id))
            
            if not user or not user.is_active:
                return {
                    'success': False,
                    'error': 'User not found or inactive'
                }
            
            # Generate new access token
            additional_claims = {
                "role": user.role.value,
                "is_staff": user.is_staff,
                "is_verified": user.is_verified
            }
            
            access_token = create_access_token(
                identity=str(user.id),
                additional_claims=additional_claims
            )
            
            return {
                'success': True,
                'access_token': access_token,
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': 'Invalid refresh token'
            }
    
    def logout_user(self, access_jti: str, refresh_jti: str) -> Dict[str, Any]:
        """Logout user by blacklisting tokens"""
        try:
            # Blacklist both tokens
            redis_client.setex(f"blacklist:{access_jti}", 3600, "true")  # 1 hour
            redis_client.setex(f"blacklist:{refresh_jti}", 604800, "true")  # 7 days
            
            return {
                'success': True,
                'message': 'Logged out successfully'
            }
        except Exception:
            return {
                'success': False,
                'error': 'Failed to logout'
            }
    
    def get_current_user(self, user_id: str) -> Optional[User]:
        """Get current user from JWT identity"""
        try:
            return self.user_repo.get_by_id(UUID(user_id))
        except Exception:
            return None
    
    def update_profile(self, user_id: UUID, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        # Don't allow updating sensitive fields
        sensitive_fields = ['id', 'password_hash', 'is_staff', 'role', 'created_at']
        filtered_data = {k: v for k, v in data.items() if k not in sensitive_fields}
        
        try:
            user = self.user_repo.update(user, filtered_data)
            self.user_repo.commit()
            
            return {
                'success': True,
                'user': user.to_dict()
            }
        except Exception:
            self.user_repo.rollback()
            return {
                'success': False,
                'error': 'Failed to update profile'
            }
    
    def change_password(self, user_id: UUID, current_password: str, 
                       new_password: str) -> Dict[str, Any]:
        """Change user password"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        if not user.check_password(current_password):
            return {
                'success': False,
                'error': 'Current password is incorrect'
            }
        
        try:
            user.set_password(new_password)
            self.user_repo.commit()
            
            return {
                'success': True,
                'message': 'Password changed successfully'
            }
        except Exception:
            self.user_repo.rollback()
            return {
                'success': False,
                'error': 'Failed to change password'
            }
    
    def verify_email(self, user_id: UUID) -> Dict[str, Any]:
        """Mark user email as verified"""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        try:
            user.mark_email_verified()
            self.user_repo.commit()
            
            return {
                'success': True,
                'message': 'Email verified successfully'
            }
        except Exception:
            self.user_repo.rollback()
            return {
                'success': False,
                'error': 'Failed to verify email'
            }
    
    def is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        return redis_client.get(f"blacklist:{jti}") is not None


# Removed duplicate UserRepository class - now using the one from repositories package 