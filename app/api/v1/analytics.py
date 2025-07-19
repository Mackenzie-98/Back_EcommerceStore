"""Analytics API endpoints"""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from uuid import UUID
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, or_, text

from app.models import (
    Order, OrderItem, Product, ProductVariant, User, Cart, CartItem,
    UserEvent, Category, Review
)
from app.extensions import db

# Create namespace
ns = Namespace('analytics', description='Analytics and reporting operations')

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
dashboard_model = ns.model('Dashboard', {
    'revenue': fields.Float(description='Total revenue'),
    'orders': fields.Integer(description='Total orders'),
    'customers': fields.Integer(description='Total customers'),
    'avg_order_value': fields.Float(description='Average order value'),
    'conversion_rate': fields.Float(description='Conversion rate'),
    'growth_rate': fields.Float(description='Growth rate'),
    'period': fields.Raw(description='Date period')
})

sales_analytics_model = ns.model('SalesAnalytics', {
    'period': fields.String(description='Time period'),
    'revenue': fields.Float(description='Revenue for period'),
    'orders': fields.Integer(description='Orders for period'),
    'avg_order_value': fields.Float(description='Average order value')
})

@ns.route('/dashboard')
class AnalyticsDashboard(Resource):
    @jwt_required()
    @ns.doc('get_dashboard_metrics')
    @ns.param('start_date', 'Start date (YYYY-MM-DD)')
    @ns.param('end_date', 'End date (YYYY-MM-DD)')
    @ns.marshal_with(dashboard_model)
    def get(self):
        """Get dashboard analytics metrics"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            # Parse date range
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                # Default to last 30 days
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
            
            # Total revenue
            revenue_query = db.session.query(func.sum(Order.total)).filter(
                Order.created_at >= start_date,
                Order.created_at <= end_date + timedelta(days=1),
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            )
            total_revenue = revenue_query.scalar() or 0
            
            # Total orders
            orders_query = db.session.query(func.count(Order.id)).filter(
                Order.created_at >= start_date,
                Order.created_at <= end_date + timedelta(days=1)
            )
            total_orders = orders_query.scalar() or 0
            
            # Total customers (new registrations)
            customers_query = db.session.query(func.count(User.id)).filter(
                User.created_at >= start_date,
                User.created_at <= end_date + timedelta(days=1)
            )
            new_customers = customers_query.scalar() or 0
            
            # Average order value
            avg_order_value = float(total_revenue / total_orders) if total_orders > 0 else 0
            
            # Conversion rate (orders vs cart creations)
            carts_created = db.session.query(func.count(Cart.id)).filter(
                Cart.created_at >= start_date,
                Cart.created_at <= end_date + timedelta(days=1)
            ).scalar() or 0
            
            conversion_rate = (total_orders / carts_created * 100) if carts_created > 0 else 0
            
            # Growth rate (comparing to previous period)
            prev_start = start_date - (end_date - start_date)
            prev_end = start_date - timedelta(days=1)
            
            prev_revenue = db.session.query(func.sum(Order.total)).filter(
                Order.created_at >= prev_start,
                Order.created_at <= prev_end + timedelta(days=1),
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).scalar() or 0
            
            growth_rate = ((float(total_revenue) - float(prev_revenue)) / float(prev_revenue) * 100) if prev_revenue > 0 else 0
            
            return {
                'revenue': float(total_revenue),
                'orders': total_orders,
                'customers': new_customers,
                'avg_order_value': avg_order_value,
                'conversion_rate': conversion_rate,
                'growth_rate': growth_rate,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }, 200
            
        except ValueError:
            return {'error': 'Invalid date format. Use YYYY-MM-DD'}, 400
        except Exception as e:
            return {'error': 'Failed to retrieve dashboard metrics'}, 500

@ns.route('/sales')
class SalesAnalytics(Resource):
    @jwt_required()
    @ns.doc('get_sales_analytics')
    @ns.param('start_date', 'Start date (YYYY-MM-DD)')
    @ns.param('end_date', 'End date (YYYY-MM-DD)')
    @ns.param('group_by', 'Group by period', enum=['day', 'week', 'month'], default='day')
    def get(self):
        """Get sales analytics over time"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            group_by = request.args.get('group_by', 'day')
            
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
            
            # Group by period
            if group_by == 'day':
                date_trunc = func.date(Order.created_at)
            elif group_by == 'week':
                date_trunc = func.strftime('%Y-W%W', Order.created_at)
            else:  # month
                date_trunc = func.strftime('%Y-%m', Order.created_at)
            
            sales_data = db.session.query(
                date_trunc.label('period'),
                func.count(Order.id).label('orders'),
                func.sum(Order.total).label('revenue'),
                func.avg(Order.total).label('avg_order_value')
            ).filter(
                Order.created_at >= start_date,
                Order.created_at <= end_date + timedelta(days=1),
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).group_by(date_trunc).order_by(date_trunc).all()
            
            result = []
            for row in sales_data:
                result.append({
                    'period': str(row.period),
                    'orders': row.orders,
                    'revenue': float(row.revenue) if row.revenue else 0,
                    'avg_order_value': float(row.avg_order_value) if row.avg_order_value else 0
                })
            
            return result, 200
            
        except ValueError:
            return {'error': 'Invalid date format. Use YYYY-MM-DD'}, 400
        except Exception as e:
            return {'error': 'Failed to retrieve sales analytics'}, 500

@ns.route('/products')
class ProductAnalytics(Resource):
    @jwt_required()
    @ns.doc('get_product_analytics')
    @ns.param('limit', 'Number of top products', type=int, default=10)
    @ns.param('period_days', 'Analysis period in days', type=int, default=30)
    @ns.param('sort_by', 'Sort by metric', enum=['revenue', 'units', 'views'], default='revenue')
    def get(self):
        """Get product performance analytics"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            limit = request.args.get('limit', 10, type=int)
            period_days = request.args.get('period_days', 30, type=int)
            sort_by = request.args.get('sort_by', 'revenue')
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Base query for product performance
            product_query = db.session.query(
                Product.id,
                Product.name,
                Product.brand,
                func.sum(OrderItem.quantity).label('units_sold'),
                func.sum(OrderItem.total).label('revenue'),
                func.count(func.distinct(Order.user_id)).label('unique_buyers')
            ).join(
                ProductVariant, Product.id == ProductVariant.product_id
            ).join(
                OrderItem, ProductVariant.id == OrderItem.variant_id
            ).join(
                Order, OrderItem.order_id == Order.id
            ).filter(
                Order.created_at >= start_date,
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).group_by(Product.id, Product.name, Product.brand)
            
            # Sort by requested metric
            if sort_by == 'revenue':
                product_query = product_query.order_by(func.sum(OrderItem.total).desc())
            elif sort_by == 'units':
                product_query = product_query.order_by(func.sum(OrderItem.quantity).desc())
            
            products = product_query.limit(limit).all()
            
            # Get product views from events
            view_events = db.session.query(
                UserEvent.entity_id,
                func.count(UserEvent.id).label('views')
            ).filter(
                UserEvent.event_type == 'product_view',
                UserEvent.entity_type == 'product',
                UserEvent.created_at >= start_date
            ).group_by(UserEvent.entity_id).all()
            
            view_dict = {str(event.entity_id): event.views for event in view_events}
            
            result = []
            for product in products:
                result.append({
                    'product_id': str(product.id),
                    'name': product.name,
                    'brand': product.brand,
                    'units_sold': product.units_sold or 0,
                    'revenue': float(product.revenue) if product.revenue else 0,
                    'unique_buyers': product.unique_buyers or 0,
                    'views': view_dict.get(str(product.id), 0),
                    'conversion_rate': (product.unique_buyers / view_dict.get(str(product.id), 1)) * 100 if view_dict.get(str(product.id)) else 0
                })
            
            return result, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve product analytics'}, 500

@ns.route('/categories')
class CategoryAnalytics(Resource):
    @jwt_required()
    @ns.doc('get_category_analytics')
    @ns.param('period_days', 'Analysis period in days', type=int, default=30)
    def get(self):
        """Get category performance analytics"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            period_days = request.args.get('period_days', 30, type=int)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Category performance query
            category_stats = db.session.query(
                Category.id,
                Category.name,
                func.count(func.distinct(Product.id)).label('product_count'),
                func.sum(OrderItem.quantity).label('units_sold'),
                func.sum(OrderItem.total).label('revenue')
            ).join(
                Product, Category.id == Product.category_id
            ).join(
                ProductVariant, Product.id == ProductVariant.product_id
            ).join(
                OrderItem, ProductVariant.id == OrderItem.variant_id
            ).join(
                Order, OrderItem.order_id == Order.id
            ).filter(
                Order.created_at >= start_date,
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).group_by(Category.id, Category.name).all()
            
            result = []
            for category in category_stats:
                result.append({
                    'category_id': str(category.id),
                    'name': category.name,
                    'product_count': category.product_count or 0,
                    'units_sold': category.units_sold or 0,
                    'revenue': float(category.revenue) if category.revenue else 0
                })
            
            return result, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve category analytics'}, 500

@ns.route('/customers')
class CustomerAnalytics(Resource):
    @jwt_required()
    @ns.doc('get_customer_analytics')
    def get(self):
        """Get customer analytics and insights"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            # Total customers
            total_customers = db.session.query(func.count(User.id)).scalar()
            
            # Active customers (ordered in last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            active_customers = db.session.query(func.count(func.distinct(Order.user_id))).filter(
                Order.created_at >= thirty_days_ago
            ).scalar()
            
            # Customer lifetime value
            clv_data = db.session.query(
                func.avg(func.sum(Order.total)).label('avg_lifetime_value'),
                func.avg(func.count(Order.id)).label('avg_orders_per_customer')
            ).filter(
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).group_by(Order.user_id).first()
            
            # New customers this month
            start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            new_customers_month = db.session.query(func.count(User.id)).filter(
                User.created_at >= start_of_month
            ).scalar()
            
            # Customer segments
            segments = self._get_customer_segments()
            
            return {
                'total_customers': total_customers,
                'active_customers': active_customers,
                'new_customers_this_month': new_customers_month,
                'avg_lifetime_value': float(clv_data.avg_lifetime_value) if clv_data and clv_data.avg_lifetime_value else 0,
                'avg_orders_per_customer': float(clv_data.avg_orders_per_customer) if clv_data and clv_data.avg_orders_per_customer else 0,
                'customer_retention_rate': (active_customers / total_customers * 100) if total_customers > 0 else 0,
                'segments': segments
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve customer analytics'}, 500
    
    def _get_customer_segments(self):
        """Get customer segmentation data"""
        try:
            # Segment customers by order frequency and value
            segments_query = db.session.query(
                func.case(
                    (func.sum(Order.total) >= 1000, 'High Value'),
                    (func.sum(Order.total) >= 500, 'Medium Value'),
                    else_='Low Value'
                ).label('segment'),
                func.count(func.distinct(Order.user_id)).label('customer_count'),
                func.sum(Order.total).label('total_revenue')
            ).filter(
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).group_by(
                func.case(
                    (func.sum(Order.total) >= 1000, 'High Value'),
                    (func.sum(Order.total) >= 500, 'Medium Value'),
                    else_='Low Value'
                )
            ).all()
            
            return [{
                'segment': segment.segment,
                'customer_count': segment.customer_count,
                'total_revenue': float(segment.total_revenue)
            } for segment in segments_query]
            
        except:
            return []

@ns.route('/cart-abandonment')
class CartAbandonmentAnalytics(Resource):
    @jwt_required()
    @ns.doc('get_cart_abandonment')
    @ns.param('period_days', 'Analysis period in days', type=int, default=30)
    def get(self):
        """Get cart abandonment analytics"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            period_days = request.args.get('period_days', 30, type=int)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Abandoned carts (not converted and older than 24 hours)
            abandoned_threshold = datetime.now() - timedelta(hours=24)
            
            abandoned_carts = db.session.query(
                func.count(Cart.id).label('count'),
                func.sum(
                    db.session.query(func.sum(CartItem.price * CartItem.quantity))
                    .filter(CartItem.cart_id == Cart.id)
                    .correlate(Cart)
                    .scalar_subquery()
                ).label('total_value')
            ).filter(
                Cart.status == 'active',
                Cart.updated_at < abandoned_threshold,
                Cart.created_at >= start_date
            ).first()
            
            # Total carts created
            total_carts = db.session.query(func.count(Cart.id)).filter(
                Cart.created_at >= start_date
            ).scalar()
            
            # Converted carts
            converted_carts = db.session.query(func.count(Cart.id)).filter(
                Cart.status == 'converted',
                Cart.created_at >= start_date
            ).scalar()
            
            abandonment_rate = ((abandoned_carts.count / total_carts) * 100) if total_carts > 0 else 0
            
            return {
                'abandoned_carts': abandoned_carts.count or 0,
                'total_value_abandoned': float(abandoned_carts.total_value) if abandoned_carts.total_value else 0,
                'total_carts': total_carts,
                'converted_carts': converted_carts,
                'abandonment_rate': abandonment_rate,
                'conversion_rate': ((converted_carts / total_carts) * 100) if total_carts > 0 else 0
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve cart abandonment analytics'}, 500

@ns.route('/conversion-funnel')
class ConversionFunnel(Resource):
    @jwt_required()
    @ns.doc('get_conversion_funnel')
    @ns.param('period_days', 'Analysis period in days', type=int, default=30)
    def get(self):
        """Get conversion funnel analytics"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            period_days = request.args.get('period_days', 30, type=int)
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Product views
            product_views = db.session.query(func.count(UserEvent.id)).filter(
                UserEvent.event_type == 'product_view',
                UserEvent.created_at >= start_date
            ).scalar()
            
            # Add to cart events
            add_to_cart = db.session.query(func.count(UserEvent.id)).filter(
                UserEvent.event_type == 'add_to_cart',
                UserEvent.created_at >= start_date
            ).scalar()
            
            # Checkout started (carts with items)
            checkout_started = db.session.query(func.count(Cart.id)).filter(
                Cart.created_at >= start_date,
                Cart.id.in_(
                    db.session.query(CartItem.cart_id).distinct()
                )
            ).scalar()
            
            # Orders completed
            orders_completed = db.session.query(func.count(Order.id)).filter(
                Order.created_at >= start_date,
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).scalar()
            
            # Calculate conversion rates
            funnel = {
                'product_views': product_views,
                'add_to_cart': add_to_cart,
                'checkout_started': checkout_started,
                'orders_completed': orders_completed,
                'conversion_rates': {
                    'view_to_cart': (add_to_cart / product_views * 100) if product_views > 0 else 0,
                    'cart_to_checkout': (checkout_started / add_to_cart * 100) if add_to_cart > 0 else 0,
                    'checkout_to_order': (orders_completed / checkout_started * 100) if checkout_started > 0 else 0,
                    'overall': (orders_completed / product_views * 100) if product_views > 0 else 0
                }
            }
            
            return funnel, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve conversion funnel'}, 500

@ns.route('/revenue-forecast')
class RevenueForecast(Resource):
    @jwt_required()
    @ns.doc('get_revenue_forecast')
    def get(self):
        """Get revenue forecast based on historical data"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            # Get last 12 months of revenue data
            twelve_months_ago = datetime.now() - timedelta(days=365)
            
            monthly_revenue = db.session.query(
                func.strftime('%Y-%m', Order.created_at).label('month'),
                func.sum(Order.total).label('revenue')
            ).filter(
                Order.created_at >= twelve_months_ago,
                Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
            ).group_by(
                func.strftime('%Y-%m', Order.created_at)
            ).order_by(
                func.strftime('%Y-%m', Order.created_at)
            ).all()
            
            if len(monthly_revenue) < 2:
                return {
                    'forecast': 0,
                    'confidence': 'low',
                    'historical_data': [],
                    'trend': 'insufficient_data'
                }, 200
            
            # Simple linear trend calculation
            revenues = [float(row.revenue) for row in monthly_revenue]
            avg_growth = sum(revenues[i] - revenues[i-1] for i in range(1, len(revenues))) / (len(revenues) - 1)
            
            # Forecast next month
            last_month_revenue = revenues[-1]
            forecast = last_month_revenue + avg_growth
            
            # Calculate trend
            if avg_growth > 0:
                trend = 'growing'
            elif avg_growth < 0:
                trend = 'declining'
            else:
                trend = 'stable'
            
            # Confidence based on data consistency
            variance = sum((rev - sum(revenues)/len(revenues))**2 for rev in revenues) / len(revenues)
            confidence = 'high' if variance < 100000 else 'medium' if variance < 500000 else 'low'
            
            return {
                'forecast': max(0, forecast),  # Don't predict negative revenue
                'confidence': confidence,
                'avg_monthly_growth': avg_growth,
                'trend': trend,
                'historical_data': [{
                    'month': row.month,
                    'revenue': float(row.revenue)
                } for row in monthly_revenue]
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to generate revenue forecast'}, 500

@ns.route('/reviews')
class ReviewAnalytics(Resource):
    @jwt_required()
    @ns.doc('get_review_analytics')
    def get(self):
        """Get review and rating analytics"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            # Overall review statistics
            review_stats = db.session.query(
                func.count(Review.id).label('total_reviews'),
                func.avg(Review.rating).label('avg_rating'),
                func.sum(func.case((Review.rating >= 4, 1), else_=0)).label('positive_reviews'),
                func.sum(func.case((Review.rating <= 2, 1), else_=0)).label('negative_reviews')
            ).first()
            
            # Rating distribution
            rating_distribution = db.session.query(
                Review.rating,
                func.count(Review.id).label('count')
            ).group_by(Review.rating).order_by(Review.rating).all()
            
            # Recent reviews trend (last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_reviews = db.session.query(func.count(Review.id)).filter(
                Review.created_at >= thirty_days_ago
            ).scalar()
            
            return {
                'total_reviews': review_stats.total_reviews or 0,
                'average_rating': float(review_stats.avg_rating) if review_stats.avg_rating else 0,
                'positive_reviews': review_stats.positive_reviews or 0,
                'negative_reviews': review_stats.negative_reviews or 0,
                'recent_reviews_30d': recent_reviews,
                'rating_distribution': [{
                    'rating': rating.rating,
                    'count': rating.count
                } for rating in rating_distribution]
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to retrieve review analytics'}, 500

@ns.route('/export')
class ExportAnalytics(Resource):
    @jwt_required()
    @ns.doc('export_analytics_data')
    @ns.param('type', 'Export type', enum=['orders', 'products', 'customers', 'analytics'], required=True)
    @ns.param('format', 'Export format', enum=['csv', 'json'], default='csv')
    @ns.param('start_date', 'Start date (YYYY-MM-DD)')
    @ns.param('end_date', 'End date (YYYY-MM-DD)')
    def post(self):
        """Export analytics data"""
        if not require_admin():
            return {'error': 'Admin access required'}, 403
        
        try:
            export_type = request.args.get('type')
            export_format = request.args.get('format', 'csv')
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            
            if not export_type:
                return {'error': 'Export type is required'}, 400
            
            # Generate export filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{export_type}_export_{timestamp}.{export_format}"
            
            # In a real implementation, you would:
            # 1. Generate the actual export file
            # 2. Store it in cloud storage (S3, etc.)
            # 3. Return a download URL
            
            return {
                'message': f'{export_type.title()} export initiated',
                'filename': filename,
                'format': export_format,
                'download_url': f'/downloads/{filename}',
                'expires_at': (datetime.now() + timedelta(hours=24)).isoformat()
            }, 202
            
        except Exception as e:
            return {'error': 'Failed to initiate export'}, 500 