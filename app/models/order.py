"""Order models for e-commerce order processing"""

import enum
from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Column, String, Numeric, Integer, ForeignKey, DateTime, 
    Boolean, Text, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from .base import BaseModel


class OrderStatus(enum.Enum):
    """Order status enumeration"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentStatus(enum.Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Order(BaseModel):
    """Order model for managing customer orders"""
    __tablename__ = 'orders'
    
    # Order Identification
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Order Status
    status = Column(String(20), default=OrderStatus.PENDING.value, nullable=False)
    payment_status = Column(String(20), default=PaymentStatus.PENDING.value, nullable=False)
    
    # Financial Information
    subtotal = Column(Numeric(10, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(10, 2), nullable=False, default=0)
    shipping_amount = Column(Numeric(10, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(10, 2), nullable=False, default=0)
    total = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    
    # Address Information (stored as JSON for historical preservation)
    shipping_address = Column(JSON, nullable=True)
    billing_address = Column(JSON, nullable=True)
    
    # Additional Information
    notes = Column(Text, nullable=True)
    order_metadata = Column(JSON, default=dict, nullable=False)
    
    # Tracking Information
    shipping_carrier = Column(String(100), nullable=True)
    tracking_number = Column(String(255), nullable=True)
    shipped_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Payment Information
    payment_method = Column(String(50), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_order_user_status', 'user_id', 'status'),
        Index('idx_order_status', 'status'),
        Index('idx_order_number', 'order_number'),
        Index('idx_order_created', 'created_at'),
        Index('idx_order_total', 'total'),
        CheckConstraint('total >= 0', name='check_positive_total'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.order_number:
            self.order_number = self.generate_order_number()
    
    @staticmethod
    def generate_order_number() -> str:
        """Generate unique order number"""
        from datetime import datetime
        import random
        timestamp = datetime.now().strftime('%Y%m%d')
        random_part = str(random.randint(1000, 9999))
        return f"ORD-{timestamp}-{random_part}"
    
    def calculate_totals(self):
        """Calculate order totals from items"""
        self.subtotal = sum(item.total for item in self.items)
        # Tax calculation can be customized based on business rules
        tax_rate = Decimal('0.08')  # 8% tax rate example
        self.tax_amount = self.subtotal * tax_rate
        
        # Shipping calculation can be customized
        if self.subtotal > 50:  # Free shipping over $50
            self.shipping_amount = Decimal('0.00')
        else:
            self.shipping_amount = Decimal('9.99')
        
        self.total = self.subtotal + self.tax_amount + self.shipping_amount - self.discount_amount
    
    def can_be_cancelled(self) -> bool:
        """Check if order can be cancelled"""
        return self.status in [OrderStatus.PENDING.value, OrderStatus.CONFIRMED.value]
    
    def can_be_refunded(self) -> bool:
        """Check if order can be refunded"""
        return self.status in [
            OrderStatus.DELIVERED.value,
            OrderStatus.SHIPPED.value
        ] and self.payment_status == PaymentStatus.CAPTURED.value
    
    def mark_as_shipped(self, carrier: str = None, tracking_number: str = None):
        """Mark order as shipped"""
        self.status = OrderStatus.SHIPPED.value
        self.shipped_at = datetime.utcnow()
        if carrier:
            self.shipping_carrier = carrier
        if tracking_number:
            self.tracking_number = tracking_number
    
    def mark_as_delivered(self):
        """Mark order as delivered"""
        self.status = OrderStatus.DELIVERED.value
        self.delivered_at = datetime.utcnow()
    
    def cancel_order(self, reason: str = None):
        """Cancel the order"""
        if not self.can_be_cancelled():
            raise ValueError("Order cannot be cancelled in current status")
        
        self.status = OrderStatus.CANCELLED.value
        if reason:
            if not self.order_metadata:
                self.order_metadata = {}
            self.order_metadata['cancellation_reason'] = reason
            self.order_metadata['cancelled_at'] = datetime.utcnow().isoformat()
    
    def get_item_count(self) -> int:
        """Get total number of items in order"""
        return sum(item.quantity for item in self.items)
    
    def get_weight(self) -> Decimal:
        """Calculate total weight of order"""
        total_weight = Decimal('0.00')
        for item in self.items:
            if item.variant and item.variant.product and item.variant.product.weight:
                total_weight += item.variant.product.weight * item.quantity
        return total_weight
    
    def to_dict(self):
        """Convert order to dictionary with complete details"""
        data = super().to_dict()
        
        # Add computed fields
        data['item_count'] = self.get_item_count()
        data['weight'] = float(self.get_weight())
        data['can_cancel'] = self.can_be_cancelled()
        data['can_refund'] = self.can_be_refunded()
        
        # Include order items
        data['items'] = [item.to_dict() for item in self.items]
        
        return data


class OrderItem(BaseModel):
    """Order item model for individual products in an order"""
    __tablename__ = 'order_items'
    
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey('product_variants.id'), nullable=False)
    
    # Item Details (preserved at time of order)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)  # Price at time of order
    discount_amount = Column(Numeric(10, 2), default=0, nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    
    # Product Information (preserved for historical record)
    product_name = Column(String(255), nullable=False)
    product_sku = Column(String(100), nullable=False)
    variant_name = Column(String(255), nullable=True)
    variant_sku = Column(String(100), nullable=False)
    variant_attributes = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="items")
    variant = relationship("ProductVariant", back_populates="order_items")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_order_item_order', 'order_id'),
        Index('idx_order_item_variant', 'variant_id'),
        Index('idx_order_item_sku', 'variant_sku'),
        CheckConstraint('quantity > 0', name='check_positive_quantity'),
        CheckConstraint('price >= 0', name='check_non_negative_price'),
    )
    
    def __init__(self, **kwargs):
        # Auto-populate product information from variant if available
        if 'variant' in kwargs and kwargs['variant']:
            variant = kwargs['variant']
            kwargs.setdefault('product_name', variant.product.name if variant.product else '')
            kwargs.setdefault('product_sku', variant.product.sku if variant.product else '')
            kwargs.setdefault('variant_name', variant.name)
            kwargs.setdefault('variant_sku', variant.sku)
            kwargs.setdefault('variant_attributes', variant.attributes or {})
            kwargs.setdefault('price', variant.price)
        
        super().__init__(**kwargs)
        
        # Calculate total if not provided
        if not hasattr(self, 'total') or self.total is None:
            self.calculate_total()
    
    def calculate_total(self):
        """Calculate item total"""
        subtotal = self.price * self.quantity
        self.total = subtotal + self.tax_amount - self.discount_amount
    
    def get_discount_percentage(self) -> float:
        """Calculate discount percentage for this item"""
        if self.discount_amount <= 0:
            return 0.0
        
        item_subtotal = self.price * self.quantity
        return (self.discount_amount / item_subtotal) * 100 if item_subtotal > 0 else 0.0
    
    def to_dict(self):
        """Convert order item to dictionary"""
        data = super().to_dict()
        
        # Add computed fields
        data['subtotal'] = float(self.price * self.quantity)
        data['discount_percentage'] = self.get_discount_percentage()
        
        # Add current variant information if still available
        if self.variant:
            data['current_variant'] = {
                'id': str(self.variant.id),
                'current_price': float(self.variant.price),
                'stock': self.variant.stock,
                'is_active': self.variant.is_active
            }
        
        return data 