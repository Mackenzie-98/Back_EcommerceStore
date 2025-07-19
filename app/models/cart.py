"""Cart models for shopping cart functionality"""

import enum
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class CartStatus(enum.Enum):
    """Cart status enumeration"""
    ACTIVE = "active"
    ABANDONED = "abandoned"
    CONVERTED = "converted"
    EXPIRED = "expired"


class Cart(BaseModel):
    """Shopping cart model"""
    __tablename__ = 'carts'
    
    # User Association
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    session_id = Column(String(255), nullable=True, index=True)  # For guest users
    
    # Cart Status
    status = Column(String(20), default=CartStatus.ACTIVE.value, nullable=False)
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_cart_user', 'user_id'),
        Index('idx_cart_session', 'session_id'),
        Index('idx_cart_status', 'status'),
        Index('idx_cart_expires', 'expires_at'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set default expiration to 30 days from creation
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=30)
    
    def add_item(self, variant, quantity=1):
        """Add item to cart or update quantity if exists"""
        existing_item = self.get_item_by_variant(variant.id)
        
        if existing_item:
            existing_item.quantity += quantity
            return existing_item
        else:
            new_item = CartItem(
                cart=self,
                variant=variant,
                quantity=quantity,
                price=variant.price
            )
            self.items.append(new_item)
            return new_item
    
    def remove_item(self, variant_id):
        """Remove item from cart"""
        item = self.get_item_by_variant(variant_id)
        if item:
            self.items.remove(item)
            return True
        return False
    
    def update_item_quantity(self, variant_id, quantity):
        """Update item quantity"""
        item = self.get_item_by_variant(variant_id)
        if item:
            if quantity <= 0:
                self.items.remove(item)
            else:
                item.quantity = quantity
            return True
        return False
    
    def get_item_by_variant(self, variant_id):
        """Get cart item by variant ID"""
        for item in self.items:
            if item.variant_id == variant_id:
                return item
        return None
    
    def clear(self):
        """Remove all items from cart"""
        self.items.clear()
    
    def get_subtotal(self) -> Decimal:
        """Calculate cart subtotal"""
        return sum(item.get_total() for item in self.items)
    
    def get_total_quantity(self) -> int:
        """Get total quantity of items in cart"""
        return sum(item.quantity for item in self.items)
    
    def is_empty(self) -> bool:
        """Check if cart is empty"""
        return len(self.items) == 0
    
    def is_expired(self) -> bool:
        """Check if cart has expired"""
        return self.expires_at and datetime.utcnow() > self.expires_at
    
    def extend_expiration(self, days=30):
        """Extend cart expiration"""
        self.expires_at = datetime.utcnow() + timedelta(days=days)
    
    def mark_abandoned(self):
        """Mark cart as abandoned"""
        self.status = CartStatus.ABANDONED.value
    
    def mark_converted(self):
        """Mark cart as converted to order"""
        self.status = CartStatus.CONVERTED.value
    
    def validate_items(self) -> dict:
        """Validate all cart items for stock and pricing"""
        errors = []
        updated_items = []
        
        for item in self.items:
            # Check if variant is still active
            if not item.variant.is_active:
                errors.append(f"Product '{item.variant.name}' is no longer available")
                continue
            
            # Check stock availability
            if not item.variant.is_in_stock():
                errors.append(f"Product '{item.variant.name}' is out of stock")
                continue
            
            if item.variant.stock < item.quantity:
                errors.append(
                    f"Only {item.variant.stock} units of '{item.variant.name}' available, "
                    f"but {item.quantity} requested"
                )
                continue
            
            # Check for price changes
            if item.price != item.variant.price:
                item.price = item.variant.price
                updated_items.append(item)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "updated_items": updated_items
        }


class CartItem(BaseModel):
    """Cart item model"""
    __tablename__ = 'cart_items'
    
    cart_id = Column(UUID(as_uuid=True), ForeignKey('carts.id', ondelete='CASCADE'), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey('product_variants.id'), nullable=False)
    
    # Item Details
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Numeric(10, 2), nullable=False)  # Price at time of adding to cart
    
    # Relationships
    cart = relationship("Cart", back_populates="items")
    variant = relationship("ProductVariant", back_populates="cart_items")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_cart_item_cart', 'cart_id'),
        Index('idx_cart_item_variant', 'variant_id'),
        Index('idx_cart_item_unique', 'cart_id', 'variant_id', unique=True),
    )
    
    def get_total(self) -> Decimal:
        """Calculate total price for this cart item"""
        return self.price * self.quantity
    
    def update_price(self):
        """Update price to current variant price"""
        self.price = self.variant.price
    
    def get_savings(self) -> Decimal:
        """Calculate savings if variant has compare_at_price"""
        if self.variant.compare_at_price and self.variant.compare_at_price > self.price:
            return (self.variant.compare_at_price - self.price) * self.quantity
        return Decimal('0.00')
    
    def to_dict(self):
        """Convert cart item to dictionary with product details"""
        data = super().to_dict()
        
        # Add variant and product information
        if self.variant:
            data['variant'] = {
                'id': str(self.variant.id),
                'sku': self.variant.sku,
                'name': self.variant.name,
                'current_price': float(self.variant.price),
                'compare_at_price': float(self.variant.compare_at_price) if self.variant.compare_at_price else None,
                'stock': self.variant.stock,
                'is_in_stock': self.variant.is_in_stock(),
                'attributes': self.variant.attributes,
                'images': self.variant.images
            }
            
            if self.variant.product:
                data['product'] = {
                    'id': str(self.variant.product.id),
                    'name': self.variant.product.name,
                    'slug': self.variant.product.slug,
                    'brand': self.variant.product.brand
                }
        
        # Add calculated fields
        data['total'] = float(self.get_total())
        data['savings'] = float(self.get_savings())
        
        return data 