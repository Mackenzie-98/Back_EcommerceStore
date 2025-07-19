"""API v1 blueprint with all route registrations"""

from flask import Blueprint
from flask_restx import Api

from .auth import ns as auth_ns
from .products import ns as products_ns
from .cart import ns as cart_ns
from .orders import ns as orders_ns
from .users import ns as users_ns
from .analytics import ns as analytics_ns
from .admin import ns as admin_ns

# Create v1 API blueprint
api_v1_bp = Blueprint('api_v1', __name__)

# Create Flask-RESTX API instance
api = Api(
    api_v1_bp,
    title='E-commerce API',
    version='1.0',
    description='Comprehensive e-commerce backend API',
    doc='/docs/'
)

# Register namespaces
api.add_namespace(auth_ns, path='/auth')
api.add_namespace(products_ns, path='/products')
api.add_namespace(cart_ns, path='/cart')
api.add_namespace(orders_ns, path='/orders')
api.add_namespace(users_ns, path='/users')
api.add_namespace(analytics_ns, path='/analytics')
api.add_namespace(admin_ns, path='/admin') 