"""Product models for catalog management"""

import enum
from decimal import Decimal
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Numeric, ForeignKey, 
    Index, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from .base import BaseModel


class Category(BaseModel):
    """Product category with hierarchical structure"""
    __tablename__ = 'categories'
    
    # Category Information
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    
    # Hierarchy
    parent_id = Column(UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    
    # Status and Ordering
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    
    # SEO Fields
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    
    # Relationships
    parent = relationship("Category", remote_side="Category.id", backref="children")
    products = relationship("Product", back_populates="category")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_category_parent_active', 'parent_id', 'is_active'),
        Index('idx_category_slug', 'slug'),
        Index('idx_category_sort', 'sort_order'),
    )
    
    def get_full_path(self) -> str:
        """Get full category path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)
    
    def get_all_children(self) -> list:
        """Get all child categories recursively"""
        children = []
        for child in self.children:
            children.append(child)
            children.extend(child.get_all_children())
        return children


class Product(BaseModel):
    """Product model with basic information"""
    __tablename__ = 'products'
    
    # Basic Information
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)
    
    # Categorization
    category_id = Column(UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    brand = Column(String(100), nullable=True, index=True)
    tags = Column(JSON, default=list, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    
    # Physical Properties
    weight = Column(Numeric(10, 3), nullable=True)  # kg
    dimensions = Column(JSON, nullable=True)  # {length, width, height} in cm
    
    # SEO
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(Text, nullable=True)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product", cascade="all, delete-orphan")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_product_category_active', 'category_id', 'is_active'),
        Index('idx_product_brand_active', 'brand', 'is_active'),
        Index('idx_product_featured', 'is_featured'),
        # Note: PostgreSQL text search index commented out for SQLite compatibility
        # Index('idx_product_name_search', func.to_tsvector('english', name)),
    )
    
    def get_price_range(self) -> dict:
        """Get min and max price from variants"""
        if not self.variants:
            return {"min": 0, "max": 0}
        
        prices = [v.price for v in self.variants if v.is_active]
        if not prices:
            return {"min": 0, "max": 0}
        
        return {
            "min": min(prices),
            "max": max(prices)
        }
    
    def get_total_stock(self) -> int:
        """Get total stock across all variants"""
        return sum(v.stock for v in self.variants if v.is_active)
    
    def get_primary_image(self):
        """Get primary product image"""
        primary_images = [img for img in self.images if img.is_primary]
        if primary_images:
            return primary_images[0]
        elif self.images:
            return self.images[0]
        return None
    
    def get_average_rating(self) -> float:
        """Calculate average rating from reviews"""
        if not self.reviews:
            return 0.0
        
        active_reviews = [r for r in self.reviews if r.rating is not None]
        if not active_reviews:
            return 0.0
        
        return sum(r.rating for r in active_reviews) / len(active_reviews)
    
    def get_review_count(self) -> int:
        """Get count of reviews"""
        return len([r for r in self.reviews if r.rating is not None])


class ProductVariant(BaseModel):
    """Product variant with pricing and inventory"""
    __tablename__ = 'product_variants'
    
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    
    # Variant Information
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    
    # Pricing
    price = Column(Numeric(10, 2), nullable=False)
    compare_at_price = Column(Numeric(10, 2), nullable=True)  # Original price for sales
    cost = Column(Numeric(10, 2), nullable=True)  # Internal cost
    
    # Inventory
    stock = Column(Integer, nullable=False, default=0)
    low_stock_threshold = Column(Integer, default=10, nullable=False)
    
    # Variant Attributes (color, size, etc.)
    attributes = Column(JSON, default=dict, nullable=False)
    
    # Images specific to this variant
    images = Column(JSON, default=list, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="variants")
    order_items = relationship("OrderItem", back_populates="variant")
    cart_items = relationship("CartItem", back_populates="variant")
    wishlists = relationship("Wishlist", back_populates="variant")
    
    # Database Constraints
    __table_args__ = (
        CheckConstraint('price >= 0', name='check_positive_price'),
        CheckConstraint('stock >= 0', name='check_non_negative_stock'),
        Index('idx_variant_product_active', 'product_id', 'is_active'),
        Index('idx_variant_price', 'price'),
        Index('idx_variant_stock', 'stock'),
    )
    
    def is_low_stock(self) -> bool:
        """Check if variant is low on stock"""
        return self.stock <= self.low_stock_threshold
    
    def is_in_stock(self) -> bool:
        """Check if variant is in stock"""
        return self.stock > 0
    
    def get_discount_percentage(self) -> float:
        """Calculate discount percentage if compare_at_price is set"""
        if not self.compare_at_price or self.compare_at_price <= self.price:
            return 0.0
        
        return ((self.compare_at_price - self.price) / self.compare_at_price) * 100
    
    def reserve_stock(self, quantity: int) -> bool:
        """Reserve stock for an order"""
        if self.stock >= quantity:
            self.stock -= quantity
            return True
        return False
    
    def release_stock(self, quantity: int):
        """Release reserved stock back to inventory"""
        self.stock += quantity


class ProductImage(BaseModel):
    """Product image management"""
    __tablename__ = 'product_images'
    
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey('product_variants.id'), nullable=True)
    
    # Image Information
    url = Column(String(500), nullable=False)
    alt_text = Column(String(255), nullable=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="images")
    variant = relationship("ProductVariant")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_image_product_primary', 'product_id', 'is_primary'),
        Index('idx_image_sort', 'sort_order'),
    )


class Review(BaseModel):
    """Product review and rating system"""
    __tablename__ = 'reviews'
    
    product_id = Column(UUID(as_uuid=True), ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Review Content
    rating = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    
    # Verification
    is_verified_purchase = Column(Boolean, default=False, nullable=False)
    
    # Engagement
    helpful_count = Column(Integer, default=0, nullable=False)
    
    # Additional Media
    images = Column(JSON, default=list, nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="reviews")
    user = relationship("User", back_populates="reviews")
    
    # Database Constraints
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
        Index('idx_review_product_rating', 'product_id', 'rating'),
        Index('idx_review_user', 'user_id'),
        Index('idx_review_verified', 'is_verified_purchase'),
    )
    
    def mark_helpful(self):
        """Increment helpful count"""
        self.helpful_count += 1 