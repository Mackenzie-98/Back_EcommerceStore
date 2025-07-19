"""Admin API endpoints"""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields as ma_fields, validate, ValidationError
from uuid import UUID
from datetime import datetime, timedelta

from app.models import (
    User, Product, ProductVariant, Category, Order, OrderItem, 
    Coupon, DiscountRule, Address, Review, Cart, CartItem
)
from app.extensions import db

# Create namespace
ns = Namespace('admin', description='Administrative operations')

# Utility function to check admin permissions
def require_admin():
    """Check if current user is admin"""
    try:
        user_id = UUID(get_jwt_identity())
        user = db.session.query(User).filter(User.id == user_id).first()
        if not user or not user.is_staff:
            return False
        return True
    except:
        return False

# Flask-RESTX models for documentation
product_create_model = ns.model('ProductCreate', {
    'name': fields.String(required=True, description='Product name'),
    'slug': fields.String(required=True, description='Product slug'),
    'sku': fields.String(required=True, description='Product SKU'),
    'description': fields.String(description='Product description'),
    'short_description': fields.String(description='Short description'),
    'category_id': fields.String(description='Category ID'),
    'brand': fields.String(description='Brand name'),
    'tags': fields.List(fields.String, description='Product tags'),
    'is_active': fields.Boolean(description='Is product active', default=True),
    'is_featured': fields.Boolean(description='Is product featured', default=False),
    'weight': fields.Float(description='Product weight'),
    'dimensions': fields.Raw(description='Product dimensions'),
    'meta_title': fields.String(description='SEO meta title'),
    'meta_description': fields.String(description='SEO meta description')
})

variant_create_model = ns.model('VariantCreate', {
    'name': fields.String(description='Variant name'),
    'sku': fields.String(required=True, description='Variant SKU'),
    'price': fields.Float(required=True, description='Variant price'),
    'compare_at_price': fields.Float(description='Compare at price'),
    'cost': fields.Float(description='Cost price'),
    'stock': fields.Integer(required=True, description='Stock quantity'),
    'low_stock_threshold': fields.Integer(description='Low stock threshold', default=10),
    'attributes': fields.Raw(description='Variant attributes'),
    'is_active': fields.Boolean(description='Is variant active', default=True)
})

order_update_model = ns.model('OrderUpdate', {
    'status': fields.String(required=True, description='Order status', 
                          enum=['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']),
    'tracking_number': fields.String(description='Tracking number'),
    'shipping_carrier': fields.String(description='Shipping carrier'),
    'notes': fields.String(description='Internal notes')
})

user_update_model = ns.model('UserUpdate', {
    'is_active': fields.Boolean(description='User active status'),
    'is_verified': fields.Boolean(description='Email verified status'),
    'is_staff': fields.Boolean(description='Staff status'),
    'first_name': fields.String(description='First name'),
    'last_name': fields.String(description='Last name'),
    'phone': fields.String(description='Phone number')
})

coupon_model = ns.model('Coupon', {
    'code': fields.String(required=True, description='Coupon code'),
    'description': fields.String(description='Coupon description'),
    'discount_type': fields.String(required=True, description='Discount type', enum=['percentage', 'fixed']),
    'discount_value': fields.Float(required=True, description='Discount value'),
    'minimum_amount': fields.Float(description='Minimum order amount'),
    'usage_limit': fields.Integer(description='Total usage limit'),
    'user_limit': fields.Integer(description='Per-user usage limit', default=1),
    'valid_from': fields.String(description='Valid from date (ISO format)'),
    'valid_until': fields.String(description='Valid until date (ISO format)'),
    'is_active': fields.Boolean(description='Is coupon active', default=True)
})

# ============= PRODUCT MANAGEMENT =============

@ns.route('/products')
class AdminProducts(Resource):
    @jwt_required()
    @ns.doc('admin_list_products')
    @ns.param('page', 'Page number', type=int, default=1)
    @ns.param('limit', 'Items per page', type=int, default=20)
    @ns.param('search', 'Search query')
    @ns.param('category', 'Category filter')
    @ns.param('status', 'Status filter', enum=['active', 'inactive', 'all'])
    def get(self):
        """Get all products (admin view)"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            search = request.args.get('search', '')
            category_id = request.args.get('category')
            status = request.args.get('status', 'all')
            
            # Validate pagination
            if page < 1 or limit < 1 or limit > 100:
                return {'error': 'Invalid pagination parameters'}, 400
            
            offset = (page - 1) * limit
            
            # Build query
            query = db.session.query(Product)
            
            if search:
                query = query.filter(
                    db.or_(
                        Product.name.ilike(f'%{search}%'),
                        Product.sku.ilike(f'%{search}%'),
                        Product.brand.ilike(f'%{search}%')
                    )
                )
            
            if category_id:
                try:
                    query = query.filter(Product.category_id == UUID(category_id))
                except ValueError:
                    return {'error': 'Invalid category ID'}, 400
            
            if status == 'active':
                query = query.filter(Product.is_active == True)
            elif status == 'inactive':
                query = query.filter(Product.is_active == False)
            
            # Get total count
            total = query.count()
            
            # Get products
            products = query.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()
            
            result = []
            for product in products:
                product_data = product.to_dict()
                # Add admin-specific information
                product_data['variants_count'] = len(product.variants)
                product_data['total_stock'] = sum(v.stock for v in product.variants)
                product_data['avg_rating'] = 0  # Calculate if needed
                product_data['reviews_count'] = len(product.reviews)
                result.append(product_data)
            
            return {
                'products': result,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve products'}, 500
    
    @jwt_required()
    @ns.doc('admin_create_product')
    @ns.expect(product_create_model)
    def post(self):
        """Create new product"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Validate required fields
            required_fields = ['name', 'slug', 'sku']
            for field in required_fields:
                if not data.get(field):
                    return {'error': f'{field} is required'}, 400
            
            # Check if SKU is unique
            existing_product = db.session.query(Product).filter(Product.sku == data['sku']).first()
            if existing_product:
                return {'error': 'SKU already exists'}, 400
            
            # Check if slug is unique
            existing_slug = db.session.query(Product).filter(Product.slug == data['slug']).first()
            if existing_slug:
                return {'error': 'Slug already exists'}, 400
            
            # Create product
            product = Product(
                name=data['name'],
                slug=data['slug'],
                sku=data['sku'],
                description=data.get('description'),
                short_description=data.get('short_description'),
                category_id=UUID(data['category_id']) if data.get('category_id') else None,
                brand=data.get('brand'),
                tags=data.get('tags', []),
                is_active=data.get('is_active', True),
                is_featured=data.get('is_featured', False),
                weight=data.get('weight'),
                dimensions=data.get('dimensions'),
                meta_title=data.get('meta_title'),
                meta_description=data.get('meta_description')
            )
            
            db.session.add(product)
            db.session.commit()
            db.session.refresh(product)
            
            return product.to_dict(), 201
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to create product'}, 500

@ns.route('/products/<string:product_id>')
class AdminProduct(Resource):
    @jwt_required()
    @ns.doc('admin_update_product')
    @ns.expect(product_create_model)
    def put(self, product_id):
        """Update product"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            product_uuid = UUID(product_id)
            product = db.session.query(Product).filter(Product.id == product_uuid).first()
            
            if not product:
                return {'error': 'Product not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Update fields
            updatable_fields = [
                'name', 'slug', 'description', 'short_description', 'brand', 'tags',
                'is_active', 'is_featured', 'weight', 'dimensions', 'meta_title', 'meta_description'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(product, field, data[field])
            
            if 'category_id' in data and data['category_id']:
                product.category_id = UUID(data['category_id'])
            
            product.updated_at = datetime.utcnow()
            db.session.commit()
            db.session.refresh(product)
            
            return product.to_dict(), 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to update product'}, 500
    
    @jwt_required()
    @ns.doc('admin_delete_product')
    def delete(self, product_id):
        """Delete (deactivate) product"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            product_uuid = UUID(product_id)
            product = db.session.query(Product).filter(Product.id == product_uuid).first()
            
            if not product:
                return {'error': 'Product not found'}, 404
            
            # Soft delete by deactivating
            product.is_active = False
            product.updated_at = datetime.utcnow()
            
            # Deactivate all variants
            for variant in product.variants:
                variant.is_active = False
            
            db.session.commit()
            
            return {'message': 'Product deactivated successfully'}, 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to delete product'}, 500

@ns.route('/products/<string:product_id>/variants')
class AdminProductVariants(Resource):
    @jwt_required()
    @ns.doc('admin_create_variant')
    @ns.expect(variant_create_model)
    def post(self, product_id):
        """Create product variant"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            product_uuid = UUID(product_id)
            product = db.session.query(Product).filter(Product.id == product_uuid).first()
            
            if not product:
                return {'error': 'Product not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Check if SKU is unique
            existing_variant = db.session.query(ProductVariant).filter(
                ProductVariant.sku == data['sku']
            ).first()
            if existing_variant:
                return {'error': 'Variant SKU already exists'}, 400
            
            # Create variant
            variant = ProductVariant(
                product_id=product_uuid,
                name=data.get('name'),
                sku=data['sku'],
                price=data['price'],
                compare_at_price=data.get('compare_at_price'),
                cost=data.get('cost'),
                stock=data['stock'],
                low_stock_threshold=data.get('low_stock_threshold', 10),
                attributes=data.get('attributes', {}),
                is_active=data.get('is_active', True)
            )
            
            db.session.add(variant)
            db.session.commit()
            db.session.refresh(variant)
            
            return variant.to_dict(), 201
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to create variant'}, 500

# ============= ORDER MANAGEMENT =============

@ns.route('/orders')
class AdminOrders(Resource):
    @jwt_required()
    @ns.doc('admin_list_orders')
    @ns.param('page', 'Page number', type=int, default=1)
    @ns.param('limit', 'Items per page', type=int, default=20)
    @ns.param('status', 'Order status filter')
    @ns.param('search', 'Search by order number or customer email')
    def get(self):
        """Get all orders (admin view)"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            status = request.args.get('status')
            search = request.args.get('search', '')
            
            offset = (page - 1) * limit
            
            # Build query
            query = db.session.query(Order)
            
            if status:
                query = query.filter(Order.status == status)
            
            if search:
                query = query.join(User).filter(
                    db.or_(
                        Order.order_number.ilike(f'%{search}%'),
                        User.email.ilike(f'%{search}%')
                    )
                )
            
            # Get total count
            total = query.count()
            
            # Get orders
            orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
            
            result = []
            for order in orders:
                order_data = order.to_dict()
                # Add customer info
                if order.user:
                    order_data['customer'] = {
                        'id': str(order.user.id),
                        'email': order.user.email,
                        'name': f"{order.user.first_name or ''} {order.user.last_name or ''}".strip()
                    }
                result.append(order_data)
            
            return {
                'orders': result,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve orders'}, 500

@ns.route('/orders/<string:order_id>')
class AdminOrder(Resource):
    @jwt_required()
    @ns.doc('admin_update_order')
    @ns.expect(order_update_model)
    def put(self, order_id):
        """Update order status and details"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            order_uuid = UUID(order_id)
            order = db.session.query(Order).filter(Order.id == order_uuid).first()
            
            if not order:
                return {'error': 'Order not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Update order status
            if 'status' in data:
                old_status = order.status
                new_status = data['status']
                
                # Validate status transition
                valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
                if new_status not in valid_statuses:
                    return {'error': 'Invalid order status'}, 400
                
                order.status = new_status
                
                # Handle status-specific logic
                if new_status == 'shipped' and old_status != 'shipped':
                    order.shipped_at = datetime.utcnow()
                    if 'tracking_number' in data:
                        order.tracking_number = data['tracking_number']
                    if 'shipping_carrier' in data:
                        order.shipping_carrier = data['shipping_carrier']
                
                elif new_status == 'delivered' and old_status != 'delivered':
                    order.delivered_at = datetime.utcnow()
                
                elif new_status == 'cancelled':
                    # Restore stock for cancelled orders
                    for item in order.items:
                        if item.variant:
                            item.variant.stock += item.quantity
            
            # Update tracking information
            if 'tracking_number' in data:
                order.tracking_number = data['tracking_number']
            
            if 'shipping_carrier' in data:
                order.shipping_carrier = data['shipping_carrier']
            
            # Update internal notes
            if 'notes' in data:
                if not order.order_metadata:
                    order.order_metadata = {}
                order.order_metadata['admin_notes'] = data['notes']
            
            order.updated_at = datetime.utcnow()
            db.session.commit()
            db.session.refresh(order)
            
            return order.to_dict(), 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to update order'}, 500

@ns.route('/orders/<string:order_id>/refund')
class AdminOrderRefund(Resource):
    @jwt_required()
    @ns.doc('admin_refund_order')
    def post(self, order_id):
        """Process order refund"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            order_uuid = UUID(order_id)
            order = db.session.query(Order).filter(Order.id == order_uuid).first()
            
            if not order:
                return {'error': 'Order not found'}, 404
            
            if not order.can_be_refunded():
                return {'error': 'Order cannot be refunded'}, 400
            
            data = request.json or {}
            refund_amount = data.get('amount', float(order.total))
            reason = data.get('reason', 'Admin refund')
            
            # Process refund
            order.status = 'refunded'
            order.payment_status = 'refunded'
            
            # Store refund information
            if not order.order_metadata:
                order.order_metadata = {}
            
            order.order_metadata['refund'] = {
                'amount': refund_amount,
                'reason': reason,
                'processed_by': str(get_jwt_identity()),
                'processed_at': datetime.utcnow().isoformat()
            }
            
            # Restore stock
            for item in order.items:
                if item.variant:
                    item.variant.stock += item.quantity
            
            db.session.commit()
            
            return {
                'message': 'Refund processed successfully',
                'refund_amount': refund_amount,
                'order_status': order.status
            }, 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to process refund'}, 500

# ============= USER MANAGEMENT =============

@ns.route('/users')
class AdminUsers(Resource):
    @jwt_required()
    @ns.doc('admin_list_users')
    @ns.param('page', 'Page number', type=int, default=1)
    @ns.param('limit', 'Items per page', type=int, default=20)
    @ns.param('search', 'Search by email or name')
    @ns.param('status', 'User status filter', enum=['active', 'inactive', 'all'])
    def get(self):
        """Get all users (admin view)"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            search = request.args.get('search', '')
            status = request.args.get('status', 'all')
            
            offset = (page - 1) * limit
            
            # Build query
            query = db.session.query(User)
            
            if search:
                query = query.filter(
                    db.or_(
                        User.email.ilike(f'%{search}%'),
                        User.first_name.ilike(f'%{search}%'),
                        User.last_name.ilike(f'%{search}%')
                    )
                )
            
            if status == 'active':
                query = query.filter(User.is_active == True)
            elif status == 'inactive':
                query = query.filter(User.is_active == False)
            
            # Get total count
            total = query.count()
            
            # Get users
            users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()
            
            result = []
            for user in users:
                # Calculate user statistics
                total_orders = len(user.orders)
                total_spent = sum(order.total for order in user.orders if order.status in ['delivered', 'completed'])
                
                user_data = {
                    'id': str(user.id),
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'is_active': user.is_active,
                    'is_verified': user.is_verified,
                    'is_staff': user.is_staff,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'total_orders': total_orders,
                    'total_spent': float(total_spent)
                }
                result.append(user_data)
            
            return {
                'users': result,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve users'}, 500

@ns.route('/users/<string:user_id>')
class AdminUser(Resource):
    @jwt_required()
    @ns.doc('admin_update_user')
    @ns.expect(user_update_model)
    def put(self, user_id):
        """Update user details"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            user_uuid = UUID(user_id)
            user = db.session.query(User).filter(User.id == user_uuid).first()
            
            if not user:
                return {'error': 'User not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Update allowed fields
            updatable_fields = ['is_active', 'is_verified', 'is_staff', 'first_name', 'last_name', 'phone']
            
            for field in updatable_fields:
                if field in data:
                    setattr(user, field, data[field])
            
            db.session.commit()
            db.session.refresh(user)
            
            return {
                'id': str(user.id),
                'email': user.email,
                'is_active': user.is_active,
                'is_verified': user.is_verified,
                'is_staff': user.is_staff,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone
            }, 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to update user'}, 500

# ============= INVENTORY MANAGEMENT =============

@ns.route('/inventory')
class AdminInventory(Resource):
    @jwt_required()
    @ns.doc('admin_get_inventory')
    @ns.param('low_stock_only', 'Show only low stock items', type=bool, default=False)
    @ns.param('page', 'Page number', type=int, default=1)
    @ns.param('limit', 'Items per page', type=int, default=50)
    def get(self):
        """Get inventory status"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            low_stock_only = request.args.get('low_stock_only', False, type=bool)
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 50, type=int)
            
            offset = (page - 1) * limit
            
            # Build query
            query = db.session.query(ProductVariant).join(Product)
            
            if low_stock_only:
                query = query.filter(ProductVariant.stock <= ProductVariant.low_stock_threshold)
            
            # Get total count
            total = query.count()
            
            # Get variants
            variants = query.order_by(ProductVariant.stock.asc()).offset(offset).limit(limit).all()
            
            result = []
            for variant in variants:
                result.append({
                    'variant_id': str(variant.id),
                    'product_name': variant.product.name if variant.product else '',
                    'variant_name': variant.name,
                    'sku': variant.sku,
                    'stock': variant.stock,
                    'low_stock_threshold': variant.low_stock_threshold,
                    'is_low_stock': variant.stock <= variant.low_stock_threshold,
                    'price': float(variant.price),
                    'is_active': variant.is_active
                })
            
            return {
                'inventory': result,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'pages': (total + limit - 1) // limit
                }
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve inventory'}, 500

@ns.route('/inventory/adjust')
class AdminInventoryAdjust(Resource):
    @jwt_required()
    @ns.doc('admin_adjust_inventory')
    def post(self):
        """Adjust inventory stock"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            variant_id = data.get('variant_id')
            adjustment = data.get('adjustment')
            reason = data.get('reason', 'Admin adjustment')
            
            if not variant_id or adjustment is None:
                return {'error': 'variant_id and adjustment are required'}, 400
            
            variant = db.session.query(ProductVariant).filter(
                ProductVariant.id == UUID(variant_id)
            ).first()
            
            if not variant:
                return {'error': 'Product variant not found'}, 404
            
            old_stock = variant.stock
            new_stock = old_stock + adjustment
            
            if new_stock < 0:
                return {'error': 'Stock cannot be negative'}, 400
            
            variant.stock = new_stock
            db.session.commit()
            
            return {
                'variant_id': str(variant.id),
                'previous_stock': old_stock,
                'adjustment': adjustment,
                'new_stock': new_stock,
                'reason': reason
            }, 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to adjust inventory'}, 500

# ============= COUPON MANAGEMENT =============

@ns.route('/coupons')
class AdminCoupons(Resource):
    @jwt_required()
    @ns.doc('admin_list_coupons')
    def get(self):
        """Get all coupons"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            coupons = db.session.query(Coupon).order_by(Coupon.created_at.desc()).all()
            
            result = []
            for coupon in coupons:
                result.append({
                    'id': str(coupon.id),
                    'code': coupon.code,
                    'description': coupon.description,
                    'discount_type': coupon.discount_type,
                    'discount_value': float(coupon.discount_value),
                    'minimum_amount': float(coupon.minimum_amount) if coupon.minimum_amount else None,
                    'usage_limit': coupon.usage_limit,
                    'usage_count': coupon.usage_count,
                    'user_limit': coupon.user_limit,
                    'valid_from': coupon.valid_from.isoformat() if coupon.valid_from else None,
                    'valid_until': coupon.valid_until.isoformat() if coupon.valid_until else None,
                    'is_active': coupon.is_active,
                    'created_at': coupon.created_at.isoformat() if coupon.created_at else None
                })
            
            return result, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve coupons'}, 500
    
    @jwt_required()
    @ns.doc('admin_create_coupon')
    @ns.expect(coupon_model)
    def post(self):
        """Create new coupon"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Check if code already exists
            existing_coupon = db.session.query(Coupon).filter(
                Coupon.code == data['code'].upper()
            ).first()
            
            if existing_coupon:
                return {'error': 'Coupon code already exists'}, 400
            
            # Parse dates
            valid_from = None
            valid_until = None
            
            if data.get('valid_from'):
                valid_from = datetime.fromisoformat(data['valid_from'].replace('Z', '+00:00'))
            
            if data.get('valid_until'):
                valid_until = datetime.fromisoformat(data['valid_until'].replace('Z', '+00:00'))
            
            # Create coupon
            coupon = Coupon(
                code=data['code'].upper(),
                description=data.get('description'),
                discount_type=data['discount_type'],
                discount_value=data['discount_value'],
                minimum_amount=data.get('minimum_amount'),
                usage_limit=data.get('usage_limit'),
                user_limit=data.get('user_limit', 1),
                valid_from=valid_from,
                valid_until=valid_until,
                is_active=data.get('is_active', True)
            )
            
            db.session.add(coupon)
            db.session.commit()
            db.session.refresh(coupon)
            
            return {
                'id': str(coupon.id),
                'code': coupon.code,
                'description': coupon.description,
                'discount_type': coupon.discount_type,
                'discount_value': float(coupon.discount_value),
                'is_active': coupon.is_active
            }, 201
            
        except ValueError as e:
            return {'error': 'Invalid date format. Use ISO format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to create coupon'}, 500

@ns.route('/coupons/<string:coupon_id>')
class AdminCoupon(Resource):
    @jwt_required()
    @ns.doc('admin_update_coupon')
    @ns.expect(coupon_model)
    def put(self, coupon_id):
        """Update coupon"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            coupon_uuid = UUID(coupon_id)
            coupon = db.session.query(Coupon).filter(Coupon.id == coupon_uuid).first()
            
            if not coupon:
                return {'error': 'Coupon not found'}, 404
            
            data = request.json
            if not data:
                return {'error': 'Request body required'}, 400
            
            # Update fields
            updatable_fields = [
                'description', 'discount_value', 'minimum_amount', 'usage_limit',
                'user_limit', 'is_active'
            ]
            
            for field in updatable_fields:
                if field in data:
                    setattr(coupon, field, data[field])
            
            # Update dates
            if 'valid_from' in data and data['valid_from']:
                coupon.valid_from = datetime.fromisoformat(data['valid_from'].replace('Z', '+00:00'))
            
            if 'valid_until' in data and data['valid_until']:
                coupon.valid_until = datetime.fromisoformat(data['valid_until'].replace('Z', '+00:00'))
            
            db.session.commit()
            db.session.refresh(coupon)
            
            return {
                'id': str(coupon.id),
                'code': coupon.code,
                'description': coupon.description,
                'discount_type': coupon.discount_type,
                'discount_value': float(coupon.discount_value),
                'is_active': coupon.is_active
            }, 200
            
        except ValueError:
            return {'error': 'Invalid UUID or date format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to update coupon'}, 500
    
    @jwt_required()
    @ns.doc('admin_delete_coupon')
    def delete(self, coupon_id):
        """Deactivate coupon"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            coupon_uuid = UUID(coupon_id)
            coupon = db.session.query(Coupon).filter(Coupon.id == coupon_uuid).first()
            
            if not coupon:
                return {'error': 'Coupon not found'}, 404
            
            coupon.is_active = False
            db.session.commit()
            
            return {'message': 'Coupon deactivated successfully'}, 200
            
        except ValueError:
            return {'error': 'Invalid UUID format'}, 400
        except Exception as e:
            db.session.rollback()
            return {'error': 'Failed to deactivate coupon'}, 500 