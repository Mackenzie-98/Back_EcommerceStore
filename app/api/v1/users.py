"""User API endpoints"""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields as ma_fields, validate, ValidationError
from uuid import UUID

from app.models import User, Address, Order, Wishlist, ProductVariant
from app.extensions import db

# Create namespace
ns = Namespace('users', description='User profile and management operations')

# Flask-RESTX models for documentation
address_model = ns.model('Address', {
    'id': fields.String(description='Address ID'),
    'type': fields.String(description='Address type', enum=['billing', 'shipping']),
    'line1': fields.String(required=True, description='Address line 1'),
    'line2': fields.String(description='Address line 2'),
    'city': fields.String(required=True, description='City'),
    'state': fields.String(description='State/Province'),
    'postal_code': fields.String(required=True, description='Postal code'),
    'country': fields.String(required=True, description='Country code (ISO 2-letter)'),
    'is_default': fields.Boolean(description='Is default address'),
    'created_at': fields.String(description='Creation date')
})

address_create_model = ns.model('AddressCreate', {
    'type': fields.String(required=True, description='Address type', enum=['billing', 'shipping']),
    'line1': fields.String(required=True, description='Address line 1'),
    'line2': fields.String(description='Address line 2'),
    'city': fields.String(required=True, description='City'),
    'state': fields.String(description='State/Province'),
    'postal_code': fields.String(required=True, description='Postal code'),
    'country': fields.String(required=True, description='Country code (ISO 2-letter)'),
    'is_default': fields.Boolean(description='Is default address', default=False)
})

user_profile_model = ns.model('UserProfile', {
    'id': fields.String(description='User ID'),
    'email': fields.String(description='Email address'),
    'username': fields.String(description='Username'),
    'first_name': fields.String(description='First name'),
    'last_name': fields.String(description='Last name'),
    'phone': fields.String(description='Phone number'),
    'is_verified': fields.Boolean(description='Email verified'),
    'created_at': fields.String(description='Account creation date'),
    'last_login': fields.String(description='Last login date')
})

wishlist_item_model = ns.model('WishlistItem', {
    'id': fields.String(description='Wishlist item ID'),
    'variant_id': fields.String(description='Product variant ID'),
    'variant': fields.Raw(description='Product variant details'),
    'added_at': fields.String(description='Date added to wishlist')
})

@ns.route('/me')
class UserProfile(Resource):
    @jwt_required()
    @ns.doc('get_user_profile')
    @ns.marshal_with(user_profile_model)
    def get(self):
        """Get current user profile"""
        try:
            user_id = UUID(get_jwt_identity())
            user = db.session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {'error': 'User not found'}, 404
            
            return {
                'id': str(user.id),
                'email': user.email,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'is_verified': user.is_verified,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve user profile'}, 500
    
    @jwt_required()
    @ns.doc('update_user_profile')
    def put(self):
        """Update user profile"""
        try:
            user_id = UUID(get_jwt_identity())
            user = db.session.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {'error': 'User not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Update allowed fields
            allowed_fields = ['first_name', 'last_name', 'phone', 'username']
            updated_fields = []
            
            for field in allowed_fields:
                if field in data:
                    # Validate username uniqueness
                    if field == 'username' and data[field]:
                        existing_user = db.session.query(User).filter(
                            User.username == data[field],
                            User.id != user_id
                        ).first()
                        if existing_user:
                            return {'error': 'Username already taken'}, 400
                    
                    setattr(user, field, data[field])
                    updated_fields.append(field)
            
            if updated_fields:
                db.session.commit()
                return {
                    'message': 'Profile updated successfully',
                    'updated_fields': updated_fields
                }, 200
            else:
                return {'message': 'No changes made'}, 200
                
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to update profile'}, 500

@ns.route('/me/addresses')
class UserAddresses(Resource):
    @jwt_required()
    @ns.doc('get_user_addresses')
    @ns.marshal_list_with(address_model)
    def get(self):
        """Get user's addresses"""
        try:
            user_id = UUID(get_jwt_identity())
            addresses = db.session.query(Address).filter(
                Address.user_id == user_id
            ).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
            
            return [{
                'id': str(addr.id),
                'type': addr.type,
                'line1': addr.line1,
                'line2': addr.line2,
                'city': addr.city,
                'state': addr.state,
                'postal_code': addr.postal_code,
                'country': addr.country,
                'is_default': addr.is_default,
                'created_at': addr.created_at.isoformat() if addr.created_at else None
            } for addr in addresses], 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve addresses'}, 500
    
    @jwt_required()
    @ns.doc('create_user_address')
    @ns.expect(address_create_model)
    @ns.marshal_with(address_model)
    def post(self):
        """Create new address"""
        try:
            user_id = UUID(get_jwt_identity())
            data = request.json
            
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Validate required fields
            required_fields = ['type', 'line1', 'city', 'postal_code', 'country']
            for field in required_fields:
                if not data.get(field):
                    return {'error': f'{field} is required'}, 400
            
            # Validate address type
            if data['type'] not in ['billing', 'shipping']:
                return {'error': 'Invalid address type'}, 400
            
            # If this is set as default, unset other defaults of the same type
            if data.get('is_default', False):
                db.session.query(Address).filter(
                    Address.user_id == user_id,
                    Address.type == data['type']
                ).update({'is_default': False})
            
            # Create address
            address = Address(
                user_id=user_id,
                type=data['type'],
                line1=data['line1'],
                line2=data.get('line2'),
                city=data['city'],
                state=data.get('state'),
                postal_code=data['postal_code'],
                country=data['country'],
                is_default=data.get('is_default', False)
            )
            
            db.session.add(address)
            db.session.commit()
            db.session.refresh(address)
            
            return {
                'id': str(address.id),
                'type': address.type,
                'line1': address.line1,
                'line2': address.line2,
                'city': address.city,
                'state': address.state,
                'postal_code': address.postal_code,
                'country': address.country,
                'is_default': address.is_default,
                'created_at': address.created_at.isoformat()
            }, 201
            
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to create address'}, 500

@ns.route('/me/addresses/<string:address_id>')
class UserAddress(Resource):
    @jwt_required()
    @ns.doc('get_user_address')
    @ns.marshal_with(address_model)
    def get(self, address_id):
        """Get specific address"""
        try:
            user_id = UUID(get_jwt_identity())
            address_uuid = UUID(address_id)
            
            address = db.session.query(Address).filter(
                Address.id == address_uuid,
                Address.user_id == user_id
            ).first()
            
            if not address:
                return {'error': 'Address not found'}, 404
            
            return {
                'id': str(address.id),
                'type': address.type,
                'line1': address.line1,
                'line2': address.line2,
                'city': address.city,
                'state': address.state,
                'postal_code': address.postal_code,
                'country': address.country,
                'is_default': address.is_default,
                'created_at': address.created_at.isoformat()
            }, 200
            
        except ValueError:
            return {'error': 'Invalid address ID'}, 400
        except Exception as e:
            return {'error': 'Failed to retrieve address'}, 500
    
    @jwt_required()
    @ns.doc('update_user_address')
    @ns.expect(address_create_model)
    @ns.marshal_with(address_model)
    def put(self, address_id):
        """Update address"""
        try:
            user_id = UUID(get_jwt_identity())
            address_uuid = UUID(address_id)
            
            address = db.session.query(Address).filter(
                Address.id == address_uuid,
                Address.user_id == user_id
            ).first()
            
            if not address:
                return {'error': 'Address not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # If setting as default, unset other defaults of the same type
            if data.get('is_default', False) and not address.is_default:
                db.session.query(Address).filter(
                    Address.user_id == user_id,
                    Address.type == address.type,
                    Address.id != address_uuid
                ).update({'is_default': False})
            
            # Update fields
            updatable_fields = ['type', 'line1', 'line2', 'city', 'state', 'postal_code', 'country', 'is_default']
            for field in updatable_fields:
                if field in data:
                    setattr(address, field, data[field])
            
            db.session.commit()
            db.session.refresh(address)
            
            return {
                'id': str(address.id),
                'type': address.type,
                'line1': address.line1,
                'line2': address.line2,
                'city': address.city,
                'state': address.state,
                'postal_code': address.postal_code,
                'country': address.country,
                'is_default': address.is_default,
                'created_at': address.created_at.isoformat()
            }, 200
            
        except ValueError:
            return {'error': 'Invalid address ID'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to update address'}, 500
    
    @jwt_required()
    @ns.doc('delete_user_address')
    def delete(self, address_id):
        """Delete address"""
        try:
            user_id = UUID(get_jwt_identity())
            address_uuid = UUID(address_id)
            
            address = db.session.query(Address).filter(
                Address.id == address_uuid,
                Address.user_id == user_id
            ).first()
            
            if not address:
                return {'error': 'Address not found'}, 404
            
            db.session.delete(address)
            db.session.commit()
            
            return {'message': 'Address deleted successfully'}, 200
            
        except ValueError:
            return {'error': 'Invalid address ID'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to delete address'}, 500

@ns.route('/me/orders')
class UserOrders(Resource):
    @jwt_required()
    @ns.doc('get_user_orders')
    @ns.param('page', 'Page number', type=int, default=1)
    @ns.param('limit', 'Items per page', type=int, default=20)
    @ns.param('status', 'Filter by order status')
    def get(self):
        """Get user's order history"""
        try:
            user_id = UUID(get_jwt_identity())
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            status_filter = request.args.get('status')
            
            # Validate pagination
            if page < 1 or limit < 1 or limit > 100:
                return {'error': 'Invalid pagination parameters'}, 400
            
            offset = (page - 1) * limit
            
            # Build query
            query = db.session.query(Order).filter(Order.user_id == user_id)
            
            if status_filter:
                query = query.filter(Order.status == status_filter)
            
            # Get total count
            total = query.count()
            
            # Get orders
            orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
            
            return {
                'orders': [order.to_dict() for order in orders],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve orders'}, 500

@ns.route('/me/wishlist')
class UserWishlist(Resource):
    @jwt_required()
    @ns.doc('get_user_wishlist')
    @ns.marshal_list_with(wishlist_item_model)
    def get(self):
        """Get user's wishlist"""
        try:
            user_id = UUID(get_jwt_identity())
            
            wishlist_items = db.session.query(Wishlist).filter(
                Wishlist.user_id == user_id
            ).order_by(Wishlist.created_at.desc()).all()
            
            result = []
            for item in wishlist_items:
                result.append({
                    'id': str(item.id),
                    'variant_id': str(item.variant_id),
                    'variant': {
                        'id': str(item.variant.id),
                        'name': item.variant.name,
                        'sku': item.variant.sku,
                        'price': float(item.variant.price),
                        'stock': item.variant.stock,
                        'attributes': item.variant.attributes,
                        'product': {
                            'id': str(item.variant.product.id),
                            'name': item.variant.product.name,
                            'slug': item.variant.product.slug,
                            'brand': item.variant.product.brand
                        } if item.variant.product else None
                    } if item.variant else None,
                    'added_at': item.created_at.isoformat() if item.created_at else None
                })
            
            return result, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve wishlist'}, 500
    
    @jwt_required()
    @ns.doc('add_to_wishlist')
    def post(self):
        """Add item to wishlist"""
        try:
            user_id = UUID(get_jwt_identity())
            data = request.json
            
            if not data or 'variant_id' not in data:
                return {'error': 'variant_id is required'}, 400
            
            variant_id = UUID(data['variant_id'])
            
            # Check if variant exists
            variant = db.session.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.is_active == True
            ).first()
            
            if not variant:
                return {'error': 'Product variant not found'}, 404
            
            # Check if already in wishlist
            existing = db.session.query(Wishlist).filter(
                Wishlist.user_id == user_id,
                Wishlist.variant_id == variant_id
            ).first()
            
            if existing:
                return {'error': 'Item already in wishlist'}, 400
            
            # Add to wishlist
            wishlist_item = Wishlist(
                user_id=user_id,
                variant_id=variant_id
            )
            
            db.session.add(wishlist_item)
            db.session.commit()
            
            return {'message': 'Item added to wishlist'}, 201
            
        except ValueError:
            return {'error': 'Invalid variant ID'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to add item to wishlist'}, 500

@ns.route('/me/wishlist/<string:variant_id>')
class WishlistItem(Resource):
    @jwt_required()
    @ns.doc('remove_from_wishlist')
    def delete(self, variant_id):
        """Remove item from wishlist"""
        try:
            user_id = UUID(get_jwt_identity())
            variant_uuid = UUID(variant_id)
            
            wishlist_item = db.session.query(Wishlist).filter(
                Wishlist.user_id == user_id,
                Wishlist.variant_id == variant_uuid
            ).first()
            
            if not wishlist_item:
                return {'error': 'Item not in wishlist'}, 404
            
            db.session.delete(wishlist_item)
            db.session.commit()
            
            return {'message': 'Item removed from wishlist'}, 200
            
        except ValueError:
            return {'error': 'Invalid variant ID'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to remove item from wishlist'}, 500

@ns.route('/me/wishlist/<string:variant_id>/move-to-cart')
class MoveToCart(Resource):
    @jwt_required()
    @ns.doc('move_wishlist_to_cart')
    def post(self, variant_id):
        """Move wishlist item to cart"""
        try:
            user_id = UUID(get_jwt_identity())
            variant_uuid = UUID(variant_id)
            
            # Check if item is in wishlist
            wishlist_item = db.session.query(Wishlist).filter(
                Wishlist.user_id == user_id,
                Wishlist.variant_id == variant_uuid
            ).first()
            
            if not wishlist_item:
                return {'error': 'Item not in wishlist'}, 404
            
            # Check stock availability
            variant = wishlist_item.variant
            if not variant or not variant.is_active or variant.stock < 1:
                return {'error': 'Product is not available'}, 400
            
            # Add to cart using cart service
            from app.services import CartService
            cart_service = CartService()
            
            result = cart_service.add_to_cart(user_id, None, variant_uuid, 1)
            
            if result['success']:
                # Remove from wishlist
                db.session.delete(wishlist_item)
                db.session.commit()
                
                return {'message': 'Item moved to cart successfully'}, 200
            else:
                return {'error': result['error']}, 400
                
        except ValueError:
            return {'error': 'Invalid variant ID'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to move item to cart'}, 500

@ns.route('/me/stats')
class UserStats(Resource):
    @jwt_required()
    @ns.doc('get_user_stats')
    def get(self):
        """Get user statistics"""
        try:
            user_id = UUID(get_jwt_identity())
            
            # Calculate user statistics
            total_orders = db.session.query(Order).filter(Order.user_id == user_id).count()
            
            completed_orders = db.session.query(Order).filter(
                Order.user_id == user_id,
                Order.status.in_(['delivered', 'completed'])
            ).count()
            
            total_spent = db.session.query(db.func.sum(Order.total)).filter(
                Order.user_id == user_id,
                Order.status.in_(['delivered', 'completed', 'shipped'])
            ).scalar() or 0
            
            wishlist_count = db.session.query(Wishlist).filter(
                Wishlist.user_id == user_id
            ).count()
            
            # Get last order
            last_order = db.session.query(Order).filter(
                Order.user_id == user_id
            ).order_by(Order.created_at.desc()).first()
            
            stats = {
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'total_spent': float(total_spent),
                'wishlist_items': wishlist_count,
                'last_order': {
                    'id': str(last_order.id),
                    'order_number': last_order.order_number,
                    'status': last_order.status,
                    'total': float(last_order.total),
                    'date': last_order.created_at.isoformat()
                } if last_order else None
            }
            
            return stats, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve user statistics'}, 500 