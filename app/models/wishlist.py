"""Wishlist model for saved products functionality"""

from sqlalchemy import Column, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class Wishlist(BaseModel):
    """Wishlist model for users to save products"""
    __tablename__ = 'wishlists'
    
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="wishlists")
    variant = relationship("ProductVariant", back_populates="wishlists")
    
    # Database Indexes
    __table_args__ = (
        Index('idx_wishlist_user', 'user_id'),
        Index('idx_wishlist_variant', 'variant_id'),
        Index('idx_wishlist_unique', 'user_id', 'variant_id', unique=True),
    )
    
    def to_dict(self):
        """Convert wishlist item to dictionary with product details"""
        data = super().to_dict()
        
        # Add variant and product information
        if self.variant:
            data['variant'] = {
                'id': str(self.variant.id),
                'sku': self.variant.sku,
                'name': self.variant.name,
                'price': float(self.variant.price),
                'compare_at_price': float(self.variant.compare_at_price) if self.variant.compare_at_price else None,
                'stock': self.variant.stock,
                'is_in_stock': self.variant.is_in_stock(),
                'is_active': self.variant.is_active,
                'attributes': self.variant.attributes,
                'images': self.variant.images
            }
            
            if self.variant.product:
                data['product'] = {
                    'id': str(self.variant.product.id),
                    'name': self.variant.product.name,
                    'slug': self.variant.product.slug,
                    'brand': self.variant.product.brand,
                    'is_active': self.variant.product.is_active,
                    'average_rating': self.variant.product.get_average_rating(),
                    'review_count': self.variant.product.get_review_count()
                }
                
                # Add primary image
                primary_image = self.variant.product.get_primary_image()
                if primary_image:
                    data['product']['primary_image'] = {
                        'url': primary_image.url,
                        'alt_text': primary_image.alt_text
                    }
        
        return data 