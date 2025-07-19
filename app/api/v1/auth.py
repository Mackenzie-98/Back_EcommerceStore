"""Authentication API endpoints"""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields as ma_fields, validate, ValidationError

from app.services import AuthService

# Create namespace
ns = Namespace('auth', description='Authentication operations')

# Marshmallow schemas for validation
class RegisterSchema(Schema):
    email = ma_fields.Email(required=True)
    password = ma_fields.Str(required=True, validate=validate.Length(min=8))
    username = ma_fields.Str(allow_none=True, validate=validate.Length(min=3, max=50))
    first_name = ma_fields.Str(allow_none=True, validate=validate.Length(max=100))
    last_name = ma_fields.Str(allow_none=True, validate=validate.Length(max=100))
    phone = ma_fields.Str(allow_none=True)

class LoginSchema(Schema):
    email = ma_fields.Email(required=True)
    password = ma_fields.Str(required=True)

class ChangePasswordSchema(Schema):
    current_password = ma_fields.Str(required=True)
    new_password = ma_fields.Str(required=True, validate=validate.Length(min=8))

# Flask-RESTX models for documentation
register_model = ns.model('Register', {
    'email': fields.String(required=True, description='User email'),
    'password': fields.String(required=True, description='User password (min 8 chars)'),
    'username': fields.String(description='Username'),
    'first_name': fields.String(description='First name'),
    'last_name': fields.String(description='Last name'),
    'phone': fields.String(description='Phone number')
})

login_model = ns.model('Login', {
    'email': fields.String(required=True, description='User email'),
    'password': fields.String(required=True, description='User password')
})

# Initialize services
auth_service = AuthService()

@ns.route('/register')
class Register(Resource):
    @ns.expect(register_model)
    @ns.doc('register_user')
    def post(self):
        """Register a new user"""
        try:
            # Validate input
            schema = RegisterSchema()
            data = schema.load(request.json)
            
            # Register user
            result = auth_service.register_user(**data)
            
            if result['success']:
                return {
                    'message': 'User registered successfully',
                    'user': result['user'],
                    'tokens': result['tokens']
                }, 201
            else:
                return {'error': result['error']}, 400
                
        except ValidationError as e:
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Registration failed'}, 500

@ns.route('/login')
class Login(Resource):
    @ns.expect(login_model)
    @ns.doc('login_user')
    def post(self):
        """User login"""
        try:
            # Validate input
            schema = LoginSchema()
            data = schema.load(request.json)
            
            # Login user
            result = auth_service.login_user(data['email'], data['password'])
            
            if result['success']:
                return {
                    'message': 'Login successful',
                    'user': result['user'],
                    'tokens': result['tokens']
                }, 200
            else:
                return {'error': result['error']}, 401
                
        except ValidationError as e:
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Login failed'}, 500

@ns.route('/refresh')
class RefreshToken(Resource):
    @jwt_required(refresh=True)
    @ns.doc('refresh_token')
    def post(self):
        """Refresh access token"""
        try:
            jwt_data = get_jwt()
            result = auth_service.refresh_token(jwt_data['jti'])
            
            if result['success']:
                return {
                    'access_token': result['access_token'],
                    'token_type': result['token_type']
                }, 200
            else:
                return {'error': result['error']}, 401
                
        except Exception as e:
            return {'error': 'Token refresh failed'}, 500

@ns.route('/logout')
class Logout(Resource):
    @jwt_required()
    @ns.doc('logout_user')
    def post(self):
        """User logout"""
        try:
            # Get JWT data from both access and refresh tokens
            jwt_data = get_jwt()
            access_jti = jwt_data['jti']
            
            # Note: In a real implementation, you'd need to get the refresh token JTI
            # from the request or store it when logging in
            refresh_jti = request.json.get('refresh_jti', '')
            
            result = auth_service.logout_user(access_jti, refresh_jti)
            
            if result['success']:
                return {'message': result['message']}, 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Logout failed'}, 500

@ns.route('/profile')
class Profile(Resource):
    @jwt_required()
    @ns.doc('get_profile')
    def get(self):
        """Get current user profile"""
        try:
            user_id = get_jwt_identity()
            user = auth_service.get_current_user(user_id)
            
            if user:
                return {'user': user.to_dict()}, 200
            else:
                return {'error': 'User not found'}, 404
                
        except Exception as e:
            return {'error': 'Failed to get profile'}, 500
    
    @jwt_required()
    @ns.doc('update_profile')
    def put(self):
        """Update user profile"""
        try:
            from uuid import UUID
            user_id = UUID(get_jwt_identity())
            
            result = auth_service.update_profile(user_id, request.json)
            
            if result['success']:
                return {
                    'message': 'Profile updated successfully',
                    'user': result['user']
                }, 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Failed to update profile'}, 500

@ns.route('/change-password')
class ChangePassword(Resource):
    @jwt_required()
    @ns.doc('change_password')
    def post(self):
        """Change user password"""
        try:
            from uuid import UUID
            
            # Validate input
            schema = ChangePasswordSchema()
            data = schema.load(request.json)
            
            user_id = UUID(get_jwt_identity())
            result = auth_service.change_password(
                user_id, 
                data['current_password'], 
                data['new_password']
            )
            
            if result['success']:
                return {'message': result['message']}, 200
            else:
                return {'error': result['error']}, 400
                
        except ValidationError as e:
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            return {'error': 'Failed to change password'}, 500

@ns.route('/verify-email')
class VerifyEmail(Resource):
    @jwt_required()
    @ns.doc('verify_email')
    def post(self):
        """Verify user email"""
        try:
            from uuid import UUID
            user_id = UUID(get_jwt_identity())
            
            result = auth_service.verify_email(user_id)
            
            if result['success']:
                return {'message': result['message']}, 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Failed to verify email'}, 500 