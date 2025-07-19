"""Analytics models for tracking user behavior and business metrics"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, JSON, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import BaseModel


class UserEvent(BaseModel):
    """Model for tracking user events and behavior"""
    __tablename__ = 'user_events'
    
    # Event Details
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)  # Null for anonymous users
    event_type = Column(String(100), nullable=False)  # e.g., 'page_view', 'product_view', 'add_to_cart'
    event_name = Column(String(255), nullable=False)
    
    # Context Information
    session_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    referrer = Column(Text, nullable=True)
    
    # Event Data
    properties = Column(JSON, default=dict, nullable=False)  # Event-specific data
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="events")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_user_event_user_id', 'user_id'),
        Index('idx_user_event_type', 'event_type'),
        Index('idx_user_event_timestamp', 'timestamp'),
        Index('idx_user_event_session', 'session_id'),
    )
    
    @staticmethod
    def create_event(event_type: str, event_name: str, user_id=None, session_id=None, properties=None):
        """Factory method for creating events"""
        return UserEvent(
            event_type=event_type,
            event_name=event_name,
            user_id=user_id,
            session_id=session_id,
            properties=properties or {}
        )


class ProductMetric(BaseModel):
    """Model for tracking product-specific metrics"""
    __tablename__ = 'product_metrics'
    
    # Product Reference
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id'), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    
    # View Metrics
    views = Column(Integer, default=0, nullable=False)
    unique_views = Column(Integer, default=0, nullable=False)
    
    # Engagement Metrics
    add_to_cart = Column(Integer, default=0, nullable=False)
    add_to_wishlist = Column(Integer, default=0, nullable=False)
    
    # Purchase Metrics
    purchases = Column(Integer, default=0, nullable=False)
    revenue = Column(Float, default=0.0, nullable=False)
    
    # Conversion Metrics
    conversion_rate = Column(Float, default=0.0, nullable=False)  # purchases / views
    cart_conversion_rate = Column(Float, default=0.0, nullable=False)  # purchases / add_to_cart
    
    # Additional Metrics
    average_time_on_page = Column(Float, default=0.0, nullable=False)  # seconds
    bounce_rate = Column(Float, default=0.0, nullable=False)
    
    # Relationships
    product = relationship("Product")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_product_metric_product_date', 'product_id', 'date'),
        Index('idx_product_metric_date', 'date'),
        Index('idx_product_metric_views', 'views'),
        Index('idx_product_metric_purchases', 'purchases'),
    )
    
    def calculate_conversion_rates(self):
        """Calculate conversion rates"""
        if self.views > 0:
            self.conversion_rate = self.purchases / self.views
        
        if self.add_to_cart > 0:
            self.cart_conversion_rate = self.purchases / self.add_to_cart


class CartAbandonment(BaseModel):
    """Model for tracking cart abandonment events"""
    __tablename__ = 'cart_abandonments'
    
    # Cart Reference
    cart_id = Column(UUID(as_uuid=True), ForeignKey('carts.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    
    # Abandonment Details
    abandoned_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    abandonment_stage = Column(String(50), nullable=False)  # 'cart', 'checkout', 'payment'
    
    # Cart State at Abandonment
    items_count = Column(Integer, nullable=False)
    cart_value = Column(Float, nullable=False)
    
    # Context Information
    session_id = Column(String(255), nullable=True)
    last_activity = Column(DateTime(timezone=True), nullable=False)
    time_in_cart = Column(Integer, nullable=False)  # minutes
    
    # Recovery Information
    recovered = Column(Boolean, default=False, nullable=False)
    recovered_at = Column(DateTime(timezone=True), nullable=True)
    recovery_channel = Column(String(50), nullable=True)  # 'email', 'push', 'direct'
    
    # Additional Data
    abandonment_reason = Column(String(255), nullable=True)
    recovery_data = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    cart = relationship("Cart")
    user = relationship("User")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_cart_abandonment_user', 'user_id'),
        Index('idx_cart_abandonment_date', 'abandoned_at'),
        Index('idx_cart_abandonment_stage', 'abandonment_stage'),
        Index('idx_cart_abandonment_recovered', 'recovered'),
        Index('idx_cart_abandonment_value', 'cart_value'),
    )
    
    def mark_as_recovered(self, channel: str = None):
        """Mark cart abandonment as recovered"""
        self.recovered = True
        self.recovered_at = datetime.utcnow()
        if channel:
            self.recovery_channel = channel
    
    @staticmethod
    def create_abandonment(cart, stage: str, reason: str = None):
        """Factory method for creating cart abandonment records"""
        time_diff = datetime.utcnow() - cart.updated_at
        time_in_cart = int(time_diff.total_seconds() / 60)  # Convert to minutes
        
        return CartAbandonment(
            cart_id=cart.id,
            user_id=cart.user_id,
            abandonment_stage=stage,
            items_count=len(cart.items),
            cart_value=float(cart.total),
            session_id=getattr(cart, 'session_id', None),
            last_activity=cart.updated_at,
            time_in_cart=time_in_cart,
            abandonment_reason=reason
        ) 