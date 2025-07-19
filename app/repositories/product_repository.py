"""Product repository with specialized product queries"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import joinedload

from app.models import Product, ProductVariant, Category, Review
from .base_repository import BaseRepository


class ProductRepository(BaseRepository):
    """Repository for product-related database operations"""
    
    def __init__(self):
        super().__init__(Product)
    
    def get_with_variants(self, product_id: UUID) -> Optional[Product]:
        """Get product with all variants loaded"""
        return self.db.query(Product).options(
            joinedload(Product.variants),
            joinedload(Product.images),
            joinedload(Product.category)
        ).filter(Product.id == product_id).first()
    
    def search_products(self, query: str = None, category_ids: List[UUID] = None,
                       min_price: float = None, max_price: float = None,
                       brands: List[str] = None, in_stock: bool = True,
                       limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Advanced product search with filters"""
        
        # Base query with joins
        base_query = self.db.query(Product).options(
            joinedload(Product.variants),
            joinedload(Product.images),
            joinedload(Product.category)
        ).filter(Product.is_active == True)
        
        # Text search
        if query:
            search_filter = or_(
                Product.name.ilike(f'%{query}%'),
                Product.description.ilike(f'%{query}%'),
                Product.brand.ilike(f'%{query}%')
            )
            base_query = base_query.filter(search_filter)
        
        # Category filter
        if category_ids:
            base_query = base_query.filter(Product.category_id.in_(category_ids))
        
        # Brand filter
        if brands:
            base_query = base_query.filter(Product.brand.in_(brands))
        
        # Price filter (check variants)
        if min_price is not None or max_price is not None:
            variant_subquery = self.db.query(ProductVariant.product_id).filter(
                ProductVariant.is_active == True
            )
            
            if min_price is not None:
                variant_subquery = variant_subquery.filter(ProductVariant.price >= min_price)
            if max_price is not None:
                variant_subquery = variant_subquery.filter(ProductVariant.price <= max_price)
            
            base_query = base_query.filter(Product.id.in_(variant_subquery.subquery()))
        
        # Stock filter
        if in_stock:
            in_stock_subquery = self.db.query(ProductVariant.product_id).filter(
                and_(
                    ProductVariant.is_active == True,
                    ProductVariant.stock > 0
                )
            )
            base_query = base_query.filter(Product.id.in_(in_stock_subquery.subquery()))
        
        # Get total count
        total_count = base_query.count()
        
        # Apply pagination and get results
        products = base_query.offset(offset).limit(limit).all()
        
        return {
            'products': products,
            'total': total_count,
            'limit': limit,
            'offset': offset
        }
    
    def get_featured_products(self, limit: int = 10) -> List[Product]:
        """Get featured products"""
        # Simplified query without joins for now - tables may not exist yet
        return self.db.query(Product).filter(
            and_(Product.is_active == True, Product.is_featured == True)
        ).limit(limit).all()
    
    def get_products_by_category(self, category_id: UUID, limit: int = 20, 
                                offset: int = 0) -> List[Product]:
        """Get products in a specific category"""
        return self.db.query(Product).options(
            joinedload(Product.variants),
            joinedload(Product.images)
        ).filter(
            and_(Product.is_active == True, Product.category_id == category_id)
        ).offset(offset).limit(limit).all()
    
    def get_related_products(self, product_id: UUID, limit: int = 5) -> List[Product]:
        """Get related products based on category and brand"""
        product = self.get_by_id(product_id)
        if not product:
            return []
        
        return self.db.query(Product).options(
            joinedload(Product.variants),
            joinedload(Product.images)
        ).filter(
            and_(
                Product.is_active == True,
                Product.id != product_id,
                or_(
                    Product.category_id == product.category_id,
                    Product.brand == product.brand
                )
            )
        ).limit(limit).all()
    
    def get_top_rated_products(self, limit: int = 10) -> List[Product]:
        """Get top-rated products"""
        # Subquery for average ratings
        rating_subquery = self.db.query(
            Review.product_id,
            func.avg(Review.rating).label('avg_rating'),
            func.count(Review.id).label('review_count')
        ).filter(Review.rating.isnot(None)).group_by(Review.product_id).subquery()
        
        return self.db.query(Product).options(
            joinedload(Product.variants),
            joinedload(Product.images)
        ).join(
            rating_subquery, Product.id == rating_subquery.c.product_id
        ).filter(
            and_(
                Product.is_active == True,
                rating_subquery.c.review_count >= 5,  # Minimum 5 reviews
                rating_subquery.c.avg_rating >= 4.0   # Minimum 4.0 rating
            )
        ).order_by(desc(rating_subquery.c.avg_rating)).limit(limit).all()
    
    def get_low_stock_products(self, threshold: int = 10) -> List[Dict[str, Any]]:
        """Get products with low stock"""
        low_stock_variants = self.db.query(ProductVariant).options(
            joinedload(ProductVariant.product)
        ).filter(
            and_(
                ProductVariant.is_active == True,
                ProductVariant.stock <= threshold
            )
        ).all()
        
        return [
            {
                'product': variant.product,
                'variant': variant,
                'stock': variant.stock
            }
            for variant in low_stock_variants
        ]
    
    def get_product_analytics(self, product_id: UUID, days: int = 30) -> Dict[str, Any]:
        """Get product analytics for specified period"""
        from datetime import datetime, timedelta
        from app.models import ProductMetric, UserEvent
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get aggregated metrics
        metrics = self.db.query(ProductMetric).filter(
            and_(
                ProductMetric.product_id == product_id,
                ProductMetric.date >= start_date,
                ProductMetric.date <= end_date
            )
        ).all()
        
        # Calculate totals
        total_views = sum(m.views for m in metrics)
        total_purchases = sum(m.purchases for m in metrics)
        total_revenue = sum(m.revenue for m in metrics)
        total_cart_adds = sum(m.adds_to_cart for m in metrics)
        
        # Calculate conversion rates
        conversion_rate = (total_purchases / total_views * 100) if total_views > 0 else 0
        cart_conversion = (total_purchases / total_cart_adds * 100) if total_cart_adds > 0 else 0
        
        return {
            'period_days': days,
            'total_views': total_views,
            'total_purchases': total_purchases,
            'total_revenue': float(total_revenue),
            'total_cart_adds': total_cart_adds,
            'conversion_rate': round(conversion_rate, 2),
            'cart_conversion_rate': round(cart_conversion, 2),
            'daily_metrics': [
                {
                    'date': m.date.isoformat(),
                    'views': m.views,
                    'purchases': m.purchases,
                    'revenue': float(m.revenue),
                    'cart_adds': m.adds_to_cart
                }
                for m in metrics
            ]
        }


class CategoryRepository(BaseRepository):
    """Repository for category operations"""
    
    def __init__(self):
        super().__init__(Category)
    
    def get_active_categories(self) -> List[Category]:
        """Get all active categories"""
        return self.db.query(Category).filter(
            Category.is_active == True
        ).order_by(Category.sort_order, Category.name).all()
    
    def get_root_categories(self) -> List[Category]:
        """Get root level categories"""
        return self.db.query(Category).filter(
            and_(
                Category.is_active == True,
                Category.parent_id.is_(None)
            )
        ).order_by(Category.sort_order, Category.name).all()
    
    def get_category_tree(self) -> List[Dict[str, Any]]:
        """Get hierarchical category tree"""
        def build_tree(parent_id=None):
            categories = self.db.query(Category).filter(
                and_(
                    Category.is_active == True,
                    Category.parent_id == parent_id
                )
            ).order_by(Category.sort_order, Category.name).all()
            
            result = []
            for category in categories:
                cat_dict = category.to_dict()
                cat_dict['children'] = build_tree(category.id)
                result.append(cat_dict)
            
            return result
        
        return build_tree()


class ProductVariantRepository(BaseRepository):
    """Repository for product variant operations"""
    
    def __init__(self):
        super().__init__(ProductVariant)
    
    def get_by_sku(self, sku: str) -> Optional[ProductVariant]:
        """Get variant by SKU"""
        return self.db.query(ProductVariant).filter(
            ProductVariant.sku == sku
        ).first()
    
    def get_variants_by_product(self, product_id: UUID) -> List[ProductVariant]:
        """Get all variants for a product"""
        return self.db.query(ProductVariant).filter(
            and_(
                ProductVariant.product_id == product_id,
                ProductVariant.is_active == True
            )
        ).all()
    
    def check_stock_availability(self, variant_id: UUID, quantity: int) -> bool:
        """Check if variant has enough stock"""
        variant = self.get_by_id(variant_id)
        return variant and variant.is_active and variant.stock >= quantity 