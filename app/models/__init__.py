"""Models package - SQLAlchemy models for the e-commerce API"""

from .base import BaseModel
from .user import User, Address, UserRole
from .product import Category, Product, ProductVariant, ProductImage, Review
from .cart import Cart, CartItem
from .order import Order, OrderItem, OrderStatus
from .discount import Coupon, DiscountRule, CouponUsage
from .analytics import UserEvent, ProductMetric, CartAbandonment
from .wishlist import Wishlist

# Export all models for easy importing
__all__ = [
    'BaseModel',
    'User', 'Address', 'UserRole',
    'Category', 'Product', 'ProductVariant', 'ProductImage', 'Review',
    'Cart', 'CartItem',
    'Order', 'OrderItem', 'OrderStatus',
    'Coupon', 'DiscountRule', 'CouponUsage',
    'UserEvent', 'ProductMetric', 'CartAbandonment',
    'Wishlist'
] 