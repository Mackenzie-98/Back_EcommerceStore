"""Order API endpoints"""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields as ma_fields, validate, ValidationError
from uuid import UUID
from datetime import datetime

from app.models import Order, OrderItem, Cart, CartItem, ProductVariant, Address, User
from app.services import CartService
from app.extensions import db

# Create namespace
ns = Namespace('orders', description='Order operations')

# Initialize services
cart_service = CartService()

# Flask-RESTX models for documentation
checkout_model = ns.model('Checkout', {
    'shipping_address_id': fields.String(required=True, description='Shipping address ID'),
    'billing_address_id': fields.String(required=True, description='Billing address ID'),
    'payment_method': fields.String(required=True, description='Payment method'),
    'notes': fields.String(description='Order notes'),
    'coupon_code': fields.String(description='Coupon code')
})

order_item_model = ns.model('OrderItem', {
    'id': fields.String(description='Order item ID'),
    'variant_id': fields.String(description='Product variant ID'),
    'product_name': fields.String(description='Product name'),
    'variant_name': fields.String(description='Variant name'),
    'variant_sku': fields.String(description='Variant SKU'),
    'quantity': fields.Integer(description='Quantity'),
    'price': fields.Float(description='Unit price'),
    'total': fields.Float(description='Item total')
})

order_model = ns.model('Order', {
    'id': fields.String(description='Order ID'),
    'order_number': fields.String(description='Order number'),
    'status': fields.String(description='Order status'),
    'payment_status': fields.String(description='Payment status'),
    'subtotal': fields.Float(description='Subtotal'),
    'tax_amount': fields.Float(description='Tax amount'),
    'shipping_amount': fields.Float(description='Shipping amount'),
    'discount_amount': fields.Float(description='Discount amount'),
    'total': fields.Float(description='Total amount'),
    'currency': fields.String(description='Currency'),
    'shipping_address': fields.Raw(description='Shipping address'),
    'billing_address': fields.Raw(description='Billing address'),
    'items': fields.List(fields.Nested(order_item_model)),
    'tracking_number': fields.String(description='Tracking number'),
    'shipped_at': fields.String(description='Shipped date'),
    'delivered_at': fields.String(description='Delivered date'),
    'created_at': fields.String(description='Created date'),
    'updated_at': fields.String(description='Updated date')
})

@ns.route('')
class OrderList(Resource):
    @jwt_required()
    @ns.doc('create_order')
    @ns.expect(checkout_model)
    @ns.marshal_with(order_model)
    def post(self):
        """Create order (checkout)"""
        try:
            user_id = UUID(get_jwt_identity())
            data = request.json
            
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Validate required fields
            required_fields = ['shipping_address_id', 'billing_address_id', 'payment_method']
            for field in required_fields:
                if not data.get(field):
                    return {'error': f'{field} is required'}, 400
            
            # Get user cart
            cart = cart_service.get_or_create_cart(user_id, None)
            if not cart or cart.is_empty():
                return {'error': 'Cart is empty'}, 400
            
            # Validate cart items
            validation_result = cart_service.validate_cart(user_id, None)
            if not validation_result['valid']:
                return {
                    'error': 'Cart validation failed',
                    'details': validation_result['errors']
                }, 400
            
            # Validate addresses
            shipping_address = db.session.query(Address).filter(
                Address.id == UUID(data['shipping_address_id']),
                Address.user_id == user_id
            ).first()
            
            billing_address = db.session.query(Address).filter(
                Address.id == UUID(data['billing_address_id']),
                Address.user_id == user_id
            ).first()
            
            if not shipping_address or not billing_address:
                return {'error': 'Invalid address'}, 400
            
            try:
                # Calculate totals
                totals_result = cart_service.calculate_totals(user_id, None, UUID(data['shipping_address_id']))
                if not totals_result['success']:
                    return {'error': 'Failed to calculate totals'}, 500
                
                totals = totals_result['totals']
                
                # Create order
                order = Order(
                    user_id=user_id,
                    status='pending',
                    payment_status='pending',
                    subtotal=totals['subtotal'],
                    tax_amount=totals['tax'],
                    shipping_amount=totals['shipping'],
                    discount_amount=totals['discount'],
                    total=totals['total'],
                    currency='USD',
                    shipping_address={
                        'line1': shipping_address.line1,
                        'line2': shipping_address.line2,
                        'city': shipping_address.city,
                        'state': shipping_address.state,
                        'postal_code': shipping_address.postal_code,
                        'country': shipping_address.country
                    },
                    billing_address={
                        'line1': billing_address.line1,
                        'line2': billing_address.line2,
                        'city': billing_address.city,
                        'state': billing_address.state,
                        'postal_code': billing_address.postal_code,
                        'country': billing_address.country
                    },
                    payment_method=data['payment_method'],
                    notes=data.get('notes')
                )
                
                db.session.add(order)
                db.session.flush()  # Get order ID
                
                # Create order items from cart
                for cart_item in cart.items:
                    order_item = OrderItem(
                        order_id=order.id,
                        variant_id=cart_item.variant_id,
                        quantity=cart_item.quantity,
                        price=cart_item.price,
                        total=cart_item.price * cart_item.quantity,
                        product_name=cart_item.variant.product.name if cart_item.variant.product else '',
                        product_sku=cart_item.variant.product.sku if cart_item.variant.product else '',
                        variant_name=cart_item.variant.name,
                        variant_sku=cart_item.variant.sku,
                        variant_attributes=cart_item.variant.attributes or {}
                    )
                    db.session.add(order_item)
                    
                    # Update stock
                    cart_item.variant.stock -= cart_item.quantity
                
                # Clear cart
                cart.status = 'converted'
                cart.converted_at = datetime.utcnow()
                
                # Process payment (simplified)
                if data['payment_method'] in ['credit_card', 'paypal']:
                    order.payment_status = 'captured'
                    order.status = 'confirmed'
                
                db.session.commit()
                
                # Track order creation event
                self._track_order_event(user_id, order.id, 'order_created')
                
                return order.to_dict(), 201
                
            except Exception as e:
                db.session.rollback()
                return {'error': 'Failed to create order'}, 500
                
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            return {'error': 'Failed to process checkout'}, 500
    
    @jwt_required()
    @ns.doc('get_orders')
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
    
    def _track_order_event(self, user_id: UUID, order_id: UUID, event_type: str):
        """Track order-related events"""
        try:
            from app.models import UserEvent
            event = UserEvent(
                user_id=user_id,
                event_type=event_type,
                entity_type='order',
                entity_id=order_id,
                metadata={}
            )
            db.session.add(event)
            db.session.commit()
        except Exception:
            db.session.rollback()

@ns.route('/<string:order_id>')
class OrderDetail(Resource):
    @jwt_required()
    @ns.doc('get_order_details')
    @ns.marshal_with(order_model)
    def get(self, order_id):
        """Get order details"""
        try:
            user_id = UUID(get_jwt_identity())
            order_uuid = UUID(order_id)
            
            order = db.session.query(Order).filter(
                Order.id == order_uuid,
                Order.user_id == user_id
            ).first()
            
            if not order:
                return {'error': 'Order not found'}, 404
            
            return order.to_dict(), 200
            
        except ValueError:
            return {'error': 'Invalid order ID'}, 400
        except Exception as e:
            return {'error': 'Failed to retrieve order'}, 500

@ns.route('/<string:order_id>/cancel')
class CancelOrder(Resource):
    @jwt_required()
    @ns.doc('cancel_order')
    def post(self, order_id):
        """Cancel order"""
        try:
            user_id = UUID(get_jwt_identity())
            order_uuid = UUID(order_id)
            
            order = db.session.query(Order).filter(
                Order.id == order_uuid,
                Order.user_id == user_id
            ).first()
            
            if not order:
                return {'error': 'Order not found'}, 404
            
            if not order.can_be_cancelled():
                return {'error': 'Order cannot be cancelled'}, 400
            
            try:
                # Cancel order
                reason = request.json.get('reason', 'Customer requested cancellation') if request.json else 'Customer requested cancellation'
                order.cancel_order(reason)
                
                # Restore stock
                for item in order.items:
                    if item.variant:
                        item.variant.stock += item.quantity
                
                db.session.commit()
                
                # Track cancellation event
                self._track_order_event(user_id, order.id, 'order_cancelled')
                
                return {'message': 'Order cancelled successfully'}, 200
                
            except Exception as e:
                db.session.rollback()
                return {'error': 'Failed to cancel order'}, 500
                
        except ValueError:
            return {'error': 'Invalid order ID'}, 400
        except Exception as e:
            return {'error': 'Failed to cancel order'}, 500
    
    def _track_order_event(self, user_id: UUID, order_id: UUID, event_type: str):
        """Track order-related events"""
        try:
            from app.models import UserEvent
            event = UserEvent(
                user_id=user_id,
                event_type=event_type,
                entity_type='order',
                entity_id=order_id,
                metadata={}
            )
            db.session.add(event)
            db.session.commit()
        except Exception:
            db.session.rollback()

@ns.route('/<string:order_id>/track')
class TrackOrder(Resource):
    @jwt_required()
    @ns.doc('track_order')
    def get(self, order_id):
        """Track order status"""
        try:
            user_id = UUID(get_jwt_identity())
            order_uuid = UUID(order_id)
            
            order = db.session.query(Order).filter(
                Order.id == order_uuid,
                Order.user_id == user_id
            ).first()
            
            if not order:
                return {'error': 'Order not found'}, 404
            
            # Generate tracking information
            tracking_info = {
                'order_id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'payment_status': order.payment_status,
                'tracking_number': order.tracking_number,
                'shipping_carrier': order.shipping_carrier,
                'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None,
                'delivered_at': order.delivered_at.isoformat() if order.delivered_at else None,
                'estimated_delivery': self._calculate_estimated_delivery(order),
                'timeline': self._generate_order_timeline(order)
            }
            
            return tracking_info, 200
            
        except ValueError:
            return {'error': 'Invalid order ID'}, 400
        except Exception as e:
            return {'error': 'Failed to track order'}, 500
    
    def _calculate_estimated_delivery(self, order):
        """Calculate estimated delivery date"""
        from datetime import timedelta
        
        if order.delivered_at:
            return order.delivered_at.isoformat()
        
        if order.shipped_at:
            # Estimate 3-5 business days from ship date
            estimated = order.shipped_at + timedelta(days=5)
            return estimated.isoformat()
        
        # Estimate based on order date
        if order.status in ['pending', 'confirmed']:
            estimated = order.created_at + timedelta(days=7)
            return estimated.isoformat()
        
        return None
    
    def _generate_order_timeline(self, order):
        """Generate order status timeline"""
        timeline = []
        
        # Order placed
        timeline.append({
            'status': 'placed',
            'title': 'Order Placed',
            'description': f'Order {order.order_number} was placed',
            'date': order.created_at.isoformat(),
            'completed': True
        })
        
        # Order confirmed
        if order.status != 'pending':
            timeline.append({
                'status': 'confirmed',
                'title': 'Order Confirmed',
                'description': 'Payment confirmed and order is being processed',
                'date': order.updated_at.isoformat(),
                'completed': True
            })
        
        # Order shipped
        if order.shipped_at:
            timeline.append({
                'status': 'shipped',
                'title': 'Order Shipped',
                'description': f'Order shipped via {order.shipping_carrier or "carrier"}',
                'date': order.shipped_at.isoformat(),
                'completed': True
            })
        elif order.status in ['processing', 'shipped', 'delivered']:
            timeline.append({
                'status': 'shipped',
                'title': 'Order Shipped',
                'description': 'Order is being prepared for shipment',
                'date': None,
                'completed': False
            })
        
        # Order delivered
        if order.delivered_at:
            timeline.append({
                'status': 'delivered',
                'title': 'Order Delivered',
                'description': 'Order has been delivered',
                'date': order.delivered_at.isoformat(),
                'completed': True
            })
        elif order.status == 'delivered':
            timeline.append({
                'status': 'delivered',
                'title': 'Order Delivered',
                'description': 'Order has been delivered',
                'date': None,
                'completed': True
            })
        else:
            timeline.append({
                'status': 'delivered',
                'title': 'Order Delivered',
                'description': 'Order will be delivered soon',
                'date': None,
                'completed': False
            })
        
        return timeline

@ns.route('/<string:order_id>/invoice')
class OrderInvoice(Resource):
    @jwt_required()
    @ns.doc('get_order_invoice')
    def get(self, order_id):
        """Get order invoice"""
        try:
            user_id = UUID(get_jwt_identity())
            order_uuid = UUID(order_id)
            
            order = db.session.query(Order).filter(
                Order.id == order_uuid,
                Order.user_id == user_id
            ).first()
            
            if not order:
                return {'error': 'Order not found'}, 404
            
            # Generate invoice data
            invoice_data = {
                'order': order.to_dict(),
                'invoice_number': f'INV-{order.order_number}',
                'invoice_date': datetime.utcnow().isoformat(),
                'due_date': datetime.utcnow().isoformat(),  # Paid order
                'status': 'paid' if order.payment_status == 'captured' else 'pending'
            }
            
            return invoice_data, 200
            
        except ValueError:
            return {'error': 'Invalid order ID'}, 400
        except Exception as e:
            return {'error': 'Failed to generate invoice'}, 500 