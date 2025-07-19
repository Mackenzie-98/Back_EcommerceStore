"""Cart API endpoints"""

from flask import request, session
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields as ma_fields, validate, ValidationError
from uuid import UUID

from app.services import CartService

# Create namespace
ns = Namespace('cart', description='Shopping cart operations')

# Initialize services
cart_service = CartService()

# Flask-RESTX models for documentation
cart_item_model = ns.model('CartItem', {
    'id': fields.String(description='Cart item ID'),
    'variant_id': fields.String(description='Product variant ID'),
    'quantity': fields.Integer(description='Item quantity'),
    'price': fields.Float(description='Item price'),
    'total': fields.Float(description='Item total')
})

cart_model = ns.model('Cart', {
    'id': fields.String(description='Cart ID'),
    'items': fields.List(fields.Nested(cart_item_model)),
    'subtotal': fields.Float(description='Subtotal'),
    'tax': fields.Float(description='Tax amount'),
    'shipping': fields.Float(description='Shipping cost'),
    'discount': fields.Float(description='Discount amount'),
    'total': fields.Float(description='Total amount'),
    'items_count': fields.Integer(description='Total items count')
})

add_item_model = ns.model('AddCartItem', {
    'variant_id': fields.String(required=True, description='Product variant ID'),
    'quantity': fields.Integer(required=True, description='Quantity', min=1)
})

update_item_model = ns.model('UpdateCartItem', {
    'quantity': fields.Integer(required=True, description='New quantity', min=0)
})

coupon_model = ns.model('ApplyCoupon', {
    'code': fields.String(required=True, description='Coupon code')
})

def get_user_or_session():
    """Get current user ID or session ID"""
    user_id = None
    session_id = None
    
    try:
        if get_jwt_identity():
            user_id = UUID(get_jwt_identity())
    except:
        pass
    
    if not user_id:
        session_id = session.get('session_id')
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
    
    return user_id, session_id

@ns.route('')
class CartResource(Resource):
    @ns.doc('get_cart')
    @ns.marshal_with(cart_model)
    def get(self):
        """Get current cart contents"""
        try:
            user_id, session_id = get_user_or_session()
            
            cart = cart_service.get_or_create_cart(user_id, session_id)
            if not cart:
                return {'error': 'Unable to access cart'}, 400
            
            # Calculate totals
            totals_result = cart_service.calculate_totals(user_id, session_id)
            if not totals_result['success']:
                return {'error': totals_result['error']}, 500
            
            # Format response
            cart_data = {
                'id': str(cart.id),
                'items': [
                    {
                        'id': str(item.id),
                        'variant_id': str(item.variant_id),
                        'quantity': item.quantity,
                        'price': float(item.price),
                        'total': float(item.price * item.quantity),
                        'variant': {
                            'id': str(item.variant.id),
                            'name': item.variant.name,
                            'sku': item.variant.sku,
                            'product_name': item.variant.product.name if item.variant.product else None,
                            'attributes': item.variant.attributes,
                            'stock': item.variant.stock
                        }
                    }
                    for item in cart.items
                ],
                **totals_result['totals']
            }
            
            return cart_data, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve cart'}, 500

@ns.route('/items')
class CartItems(Resource):
    @ns.doc('add_to_cart')
    @ns.expect(add_item_model)
    def post(self):
        """Add item to cart"""
        try:
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            variant_id = UUID(data['variant_id'])
            quantity = data['quantity']
            
            if quantity <= 0:
                return {'error': 'Quantity must be greater than 0'}, 400
            
            user_id, session_id = get_user_or_session()
            
            result = cart_service.add_to_cart(user_id, session_id, variant_id, quantity)
            
            if result['success']:
                return {'message': 'Item added to cart successfully'}, 201
            else:
                return {'error': result['error']}, 400
                
        except ValueError:
            return {'error': 'Invalid variant ID'}, 400
        except Exception as e:
            return {'error': 'Failed to add item to cart'}, 500

@ns.route('/items/<string:item_id>')
class CartItem(Resource):
    @ns.doc('update_cart_item')
    @ns.expect(update_item_model)
    def put(self, item_id):
        """Update cart item quantity"""
        try:
            item_uuid = UUID(item_id)
            data = request.json
            
            if not data or 'quantity' not in data:
                return {'error': 'Quantity is required'}, 400
            
            quantity = data['quantity']
            
            if quantity < 0:
                return {'error': 'Quantity cannot be negative'}, 400
            
            user_id, session_id = get_user_or_session()
            
            result = cart_service.update_cart_item(user_id, session_id, item_uuid, quantity)
            
            if result['success']:
                message = 'Item removed from cart' if quantity == 0 else 'Cart item updated successfully'
                return {'message': message}, 200
            else:
                return {'error': result['error']}, 400
                
        except ValueError:
            return {'error': 'Invalid item ID'}, 400
        except Exception as e:
            return {'error': 'Failed to update cart item'}, 500
    
    @ns.doc('remove_cart_item')
    def delete(self, item_id):
        """Remove item from cart"""
        try:
            item_uuid = UUID(item_id)
            user_id, session_id = get_user_or_session()
            
            result = cart_service.remove_from_cart(user_id, session_id, item_uuid)
            
            if result['success']:
                return {'message': 'Item removed from cart'}, 200
            else:
                return {'error': result['error']}, 400
                
        except ValueError:
            return {'error': 'Invalid item ID'}, 400
        except Exception as e:
            return {'error': 'Failed to remove cart item'}, 500

@ns.route('/clear')
class ClearCart(Resource):
    @ns.doc('clear_cart')
    def post(self):
        """Clear all items from cart"""
        try:
            user_id, session_id = get_user_or_session()
            
            result = cart_service.clear_cart(user_id, session_id)
            
            if result['success']:
                return {'message': 'Cart cleared successfully'}, 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Failed to clear cart'}, 500

@ns.route('/coupon')
class CartCoupon(Resource):
    @ns.doc('apply_coupon')
    @ns.expect(coupon_model)
    def post(self):
        """Apply coupon to cart"""
        try:
            data = request.json
            if not data or 'code' not in data:
                return {'error': 'Coupon code is required'}, 400
            
            code = data['code'].strip()
            if not code:
                return {'error': 'Coupon code cannot be empty'}, 400
            
            user_id, session_id = get_user_or_session()
            
            result = cart_service.apply_coupon(user_id, session_id, code)
            
            if result['success']:
                return {
                    'message': 'Coupon applied successfully',
                    'discount': result['discount']
                }, 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Failed to apply coupon'}, 500
    
    @ns.doc('remove_coupon')
    def delete(self):
        """Remove coupon from cart"""
        try:
            user_id, session_id = get_user_or_session()
            
            result = cart_service.remove_coupon(user_id, session_id)
            
            if result['success']:
                return {'message': 'Coupon removed successfully'}, 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Failed to remove coupon'}, 500

@ns.route('/validate')
class ValidateCart(Resource):
    @ns.doc('validate_cart')
    def post(self):
        """Validate cart items for stock and pricing"""
        try:
            user_id, session_id = get_user_or_session()
            
            result = cart_service.validate_cart(user_id, session_id)
            
            return {
                'valid': result['valid'],
                'errors': result.get('errors', []),
                'warnings': result.get('warnings', [])
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to validate cart'}, 500

@ns.route('/totals')
class CartTotals(Resource):
    @ns.doc('calculate_totals')
    @ns.param('shipping_address_id', 'Shipping address ID for shipping calculation')
    def get(self):
        """Calculate cart totals"""
        try:
            shipping_address_id = request.args.get('shipping_address_id')
            shipping_uuid = None
            if shipping_address_id:
                try:
                    shipping_uuid = UUID(shipping_address_id)
                except ValueError:
                    return {'error': 'Invalid shipping address ID'}, 400
            
            user_id, session_id = get_user_or_session()
            
            result = cart_service.calculate_totals(user_id, session_id, shipping_uuid)
            
            if result['success']:
                return result['totals'], 200
            else:
                return {'error': result['error']}, 400
                
        except Exception as e:
            return {'error': 'Failed to calculate totals'}, 500

@ns.route('/shipping-options')
class ShippingOptions(Resource):
    @ns.doc('get_shipping_options')
    def get(self):
        """Get available shipping options"""
        # This is a simplified implementation
        # In a real application, you would integrate with shipping providers
        options = [
            {
                'id': 'standard',
                'name': 'Standard Shipping',
                'description': '5-7 business days',
                'price': 9.99
            },
            {
                'id': 'express',
                'name': 'Express Shipping',
                'description': '2-3 business days',
                'price': 19.99
            },
            {
                'id': 'overnight',
                'name': 'Overnight Shipping',
                'description': '1 business day',
                'price': 39.99
            }
        ]
        
        return {'shipping_options': options}, 200 