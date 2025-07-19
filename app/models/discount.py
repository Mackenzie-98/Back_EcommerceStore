"""Discount and coupon models for promotional features"""

import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, String, Numeric, Integer, Boolean, ForeignKey, 
    DateTime, Text, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from .base import BaseModel


class DiscountType(enum.Enum):
    """Discount type enumeration"""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    FREE_SHIPPING = "free_shipping"
    BUY_X_GET_Y = "buy_x_get_y"


class CouponStatus(enum.Enum):
    """Coupon status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"


class Coupon(BaseModel):
    """Coupon model for discount codes"""
    __tablename__ = 'coupons'
    
    # Coupon Information
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Discount Configuration
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Numeric(10, 2), nullable=False)
    
    # Usage Restrictions
    minimum_amount = Column(Numeric(10, 2), nullable=True)
    maximum_discount = Column(Numeric(10, 2), nullable=True)
    usage_limit = Column(Integer, nullable=True)  # Total usage limit
    usage_limit_per_user = Column(Integer, default=1, nullable=False)
    
    # Usage Tracking
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Validity Period
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Conditions (JSON for flexible rule definition)
    conditions = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_coupon_code', 'code'),
        Index('idx_coupon_active_valid', 'is_active', 'valid_from', 'valid_until'),
        Index('idx_coupon_type', 'discount_type'),
        CheckConstraint('discount_value >= 0', name='check_non_negative_discount'),
        CheckConstraint('usage_count >= 0', name='check_non_negative_usage'),
    )
    
    def is_valid(self, cart_total: Decimal = None, user_id: UUID = None) -> dict:
        """Check if coupon is valid for use"""
        errors = []
        
        # Check if coupon is active
        if not self.is_active:
            errors.append("Coupon is not active")
        
        # Check validity period
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from:
            errors.append("Coupon is not yet valid")
        
        if self.valid_until and now > self.valid_until:
            errors.append("Coupon has expired")
        
        # Check usage limits
        if self.usage_limit and self.usage_count >= self.usage_limit:
            errors.append("Coupon usage limit exceeded")
        
        # Check minimum amount
        if self.minimum_amount and cart_total and cart_total < self.minimum_amount:
            errors.append(f"Minimum order amount of ${self.minimum_amount} required")
        
        # Check per-user usage limit
        if user_id and self.usage_limit_per_user:
            user_usage_count = len([u for u in self.usages if u.user_id == user_id])
            if user_usage_count >= self.usage_limit_per_user:
                errors.append("You have already used this coupon the maximum number of times")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def calculate_discount(self, cart_total: Decimal, items: list = None) -> Decimal:
        """Calculate discount amount for given cart total"""
        if self.discount_type == DiscountType.PERCENTAGE.value:
            discount = cart_total * (self.discount_value / 100)
        elif self.discount_type == DiscountType.FIXED.value:
            discount = self.discount_value
        elif self.discount_type == DiscountType.FREE_SHIPPING.value:
            # This would need shipping amount from context
            discount = Decimal('0.00')  # Handled separately
        else:
            discount = Decimal('0.00')
        
        # Apply maximum discount limit
        if self.maximum_discount and discount > self.maximum_discount:
            discount = self.maximum_discount
        
        # Ensure discount doesn't exceed cart total
        if discount > cart_total:
            discount = cart_total
        
        return discount
    
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1
    
    def get_status(self) -> str:
        """Get current coupon status"""
        if not self.is_active:
            return CouponStatus.INACTIVE.value
        
        now = datetime.utcnow()
        if self.valid_until and now > self.valid_until:
            return CouponStatus.EXPIRED.value
        
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return CouponStatus.EXHAUSTED.value
        
        return CouponStatus.ACTIVE.value


class DiscountRule(BaseModel):
    """Automatic discount rule model"""
    __tablename__ = 'discount_rules'
    
    # Rule Information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Rule Type
    rule_type = Column(String(50), nullable=False)  # 'cart_total', 'quantity', 'category', etc.
    
    # Conditions (JSON for flexible rule definition)
    conditions = Column(JSON, nullable=False)
    
    # Actions (JSON for flexible action definition)
    actions = Column(JSON, nullable=False)
    
    # Priority and Status
    priority = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Validity Period
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    
    # Usage Tracking
    usage_count = Column(Integer, default=0, nullable=False)
    usage_limit = Column(Integer, nullable=True)
    
    # Database Indexes
    __table_args__ = (
        Index('idx_discount_rule_active', 'is_active'),
        Index('idx_discount_rule_priority', 'priority'),
        Index('idx_discount_rule_type', 'rule_type'),
        Index('idx_discount_rule_valid', 'valid_from', 'valid_until'),
    )
    
    def is_applicable(self, context: dict) -> bool:
        """Check if discount rule applies to given context"""
        if not self.is_active:
            return False
        
        # Check validity period
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from:
            return False
        
        if self.valid_until and now > self.valid_until:
            return False
        
        # Check usage limit
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False
        
        # Check rule-specific conditions
        cart_total = context.get('cart_total', 0)
        cart_items = context.get('cart_items', [])
        user = context.get('user')
        
        if self.rule_type == 'cart_total':
            min_amount = self.conditions.get('min_amount', 0)
            return cart_total >= min_amount
        
        elif self.rule_type == 'quantity':
            min_quantity = self.conditions.get('min_quantity', 0)
            total_quantity = sum(item.get('quantity', 0) for item in cart_items)
            return total_quantity >= min_quantity
        
        elif self.rule_type == 'category':
            required_categories = self.conditions.get('category_ids', [])
            item_categories = [item.get('category_id') for item in cart_items]
            return any(cat in item_categories for cat in required_categories)
        
        elif self.rule_type == 'first_order':
            return user and user.get('order_count', 0) == 0
        
        return False
    
    def apply_discount(self, context: dict) -> dict:
        """Apply discount rule and return discount details"""
        if not self.is_applicable(context):
            return {"applicable": False, "discount": 0}
        
        cart_total = context.get('cart_total', 0)
        action = self.actions
        
        if action.get('type') == 'percentage':
            discount = cart_total * (action.get('value', 0) / 100)
        elif action.get('type') == 'fixed':
            discount = action.get('value', 0)
        else:
            discount = 0
        
        # Apply maximum discount limit
        max_discount = action.get('max_discount')
        if max_discount and discount > max_discount:
            discount = max_discount
        
        return {
            "applicable": True,
            "discount": discount,
            "rule_name": self.name,
            "rule_id": str(self.id)
        }


class CouponUsage(BaseModel):
    """Track coupon usage by users"""
    __tablename__ = 'coupon_usages'
    
    coupon_id = Column(UUID(as_uuid=True), ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id'), nullable=True)
    
    # Usage Details
    discount_amount = Column(Numeric(10, 2), nullable=False)
    cart_total = Column(Numeric(10, 2), nullable=False)
    
    # Relationships
    coupon = relationship("Coupon", back_populates="usages")
    user = relationship("User")
    order = relationship("Order")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_coupon_usage_coupon', 'coupon_id'),
        Index('idx_coupon_usage_user', 'user_id'),
        Index('idx_coupon_usage_order', 'order_id'),
    ) 