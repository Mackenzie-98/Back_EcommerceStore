"""Product service with business logic for product operations"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from app.repositories import ProductRepository
from app.models import Product, ProductVariant, Category, Review, UserEvent
from app.extensions import db, redis_client


class ProductService:
    """Service for product-related business logic"""
    
    def __init__(self):
        self.product_repo = ProductRepository()
        self.category_repo = CategoryRepository()
        self.variant_repo = ProductVariantRepository()
    
    def search_products(self, query: str = None, filters: Dict[str, Any] = None,
                       sort: str = 'created_at', limit: int = 20, 
                       offset: int = 0) -> Dict[str, Any]:
        """Search products with filters and sorting"""
        if filters is None:
            filters = {}
        
        # Extract filter parameters
        category_ids = filters.get('category_ids', [])
        min_price = filters.get('min_price')
        max_price = filters.get('max_price')
        brands = filters.get('brands', [])
        in_stock = filters.get('in_stock', True)
        
        result = self.product_repo.search_products(
            query=query,
            category_ids=category_ids,
            min_price=min_price,
            max_price=max_price,
            brands=brands,
            in_stock=in_stock,
            limit=limit,
            offset=offset
        )
        
        return result
    
    def get_product_with_variants(self, product_id: UUID) -> Optional[Product]:
        """Get product with all variants and related data"""
        return self.product_repo.get_with_variants(product_id)
    
    def get_featured_products(self, limit: int = 10) -> List[Product]:
        """Get featured products"""
        return self.product_repo.get_featured_products(limit)
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get product categories as tree structure"""
        return self.category_repo.get_category_tree()
    
    def get_products_by_category(self, category_id: UUID, limit: int = 20, 
                                offset: int = 0) -> Dict[str, Any]:
        """Get products in a specific category"""
        products = self.product_repo.get_products_by_category(
            category_id, limit, offset
        )
        
        # Get total count for pagination
        total = self.product_repo.count({
            'category_id': category_id,
            'is_active': True
        })
        
        return {
            'products': products,
            'total': total,
            'limit': limit,
            'offset': offset
        }
    
    def get_related_products(self, product_id: UUID, limit: int = 5) -> List[Product]:
        """Get related products based on category and brand"""
        return self.product_repo.get_related_products(product_id, limit)
    
    def get_recommendations(self, user_id: Optional[UUID] = None, 
                          limit: int = 10) -> List[Product]:
        """Get personalized product recommendations"""
        cache_key = f"recommendations:{user_id}:{limit}"
        
        # Try to get from cache first
        try:
            cached = redis_client.get(cache_key)
            if cached:
                import json
                product_ids = json.loads(cached)
                products = []
                for pid in product_ids:
                    product = self.product_repo.get_by_id(UUID(pid))
                    if product:
                        products.append(product)
                return products
        except:
            pass
        
        if user_id:
            # User-based recommendations (simplified)
            # In a real system, this would use collaborative filtering
            recommendations = self._get_user_based_recommendations(user_id, limit)
        else:
            # For anonymous users, return popular/featured products
            recommendations = self.product_repo.get_featured_products(limit)
        
        # Cache the recommendations
        try:
            import json
            product_ids = [str(p.id) for p in recommendations]
            redis_client.setex(cache_key, 300, json.dumps(product_ids))  # 5 min cache
        except:
            pass
        
        return recommendations
    
    def track_product_view(self, product_id: UUID, user_id: Optional[UUID] = None,
                          session_id: Optional[str] = None):
        """Track product view event"""
        try:
            event = UserEvent(
                user_id=user_id,
                session_id=session_id,
                event_type='product_view',
                entity_type='product',
                entity_id=product_id,
                metadata={}
            )
            db.session.add(event)
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    def get_product_reviews(self, product_id: UUID, page: int = 1, 
                           limit: int = 20) -> Dict[str, Any]:
        """Get product reviews with pagination and summary"""
        offset = (page - 1) * limit
        
        # Get reviews
        reviews = db.session.query(Review).filter(
            Review.product_id == product_id
        ).order_by(Review.created_at.desc()).offset(offset).limit(limit).all()
        
        # Get total count
        total = db.session.query(Review).filter(
            Review.product_id == product_id
        ).count()
        
        # Get rating summary
        from sqlalchemy import func
        rating_summary = db.session.query(
            func.avg(Review.rating).label('average'),
            func.count(Review.id).label('total'),
            func.sum(func.case([(Review.rating == 5, 1)], else_=0)).label('five_star'),
            func.sum(func.case([(Review.rating == 4, 1)], else_=0)).label('four_star'),
            func.sum(func.case([(Review.rating == 3, 1)], else_=0)).label('three_star'),
            func.sum(func.case([(Review.rating == 2, 1)], else_=0)).label('two_star'),
            func.sum(func.case([(Review.rating == 1, 1)], else_=0)).label('one_star'),
        ).filter(Review.product_id == product_id).first()
        
        return {
            'reviews': [review.to_dict() for review in reviews],
            'total': total,
            'summary': {
                'average_rating': float(rating_summary.average) if rating_summary.average else 0,
                'total_reviews': rating_summary.total or 0,
                'rating_distribution': {
                    '5': rating_summary.five_star or 0,
                    '4': rating_summary.four_star or 0,
                    '3': rating_summary.three_star or 0,
                    '2': rating_summary.two_star or 0,
                    '1': rating_summary.one_star or 0,
                }
            }
        }
    
    def add_review(self, product_id: UUID, user_id: UUID, rating: int,
                   title: str = None, comment: str = None, 
                   images: List[str] = None) -> Dict[str, Any]:
        """Add a product review"""
        # Check if product exists
        product = self.product_repo.get_by_id(product_id)
        if not product:
            return {
                'success': False,
                'error': 'Product not found'
            }
        
        # Check if user already reviewed this product
        existing_review = db.session.query(Review).filter(
            Review.product_id == product_id,
            Review.user_id == user_id
        ).first()
        
        if existing_review:
            return {
                'success': False,
                'error': 'You have already reviewed this product'
            }
        
        try:
            # Create review
            review = Review(
                product_id=product_id,
                user_id=user_id,
                rating=rating,
                title=title,
                comment=comment,
                images=images or []
            )
            
            # Check if this is a verified purchase
            from app.models import Order, OrderItem, ProductVariant
            verified_purchase = db.session.query(Order).join(OrderItem).join(ProductVariant).filter(
                Order.user_id == user_id,
                ProductVariant.product_id == product_id,
                Order.status.in_(['delivered', 'completed'])
            ).first()
            
            if verified_purchase:
                review.is_verified_purchase = True
            
            db.session.add(review)
            db.session.commit()
            
            # Track review event
            self._track_review_event(product_id, user_id, rating)
            
            return {
                'success': True,
                'review': review.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            return {
                'success': False,
                'error': 'Failed to add review'
            }
    
    def _get_user_based_recommendations(self, user_id: UUID, limit: int) -> List[Product]:
        """Get user-based recommendations (simplified algorithm)"""
        # Get user's purchase history
        from app.models import Order, OrderItem, ProductVariant
        
        purchased_products = db.session.query(Product).join(ProductVariant).join(
            OrderItem
        ).join(Order).filter(
            Order.user_id == user_id,
            Order.status.in_(['delivered', 'completed'])
        ).distinct().all()
        
        if not purchased_products:
            # No purchase history, return featured products
            return self.product_repo.get_featured_products(limit)
        
        # Get products in same categories as purchased products
        category_ids = [p.category_id for p in purchased_products if p.category_id]
        
        if category_ids:
            recommendations = db.session.query(Product).filter(
                Product.category_id.in_(category_ids),
                Product.is_active == True,
                ~Product.id.in_([p.id for p in purchased_products])  # Exclude already purchased
            ).limit(limit).all()
            
            if len(recommendations) < limit:
                # Fill remaining with featured products
                additional = self.product_repo.get_featured_products(limit - len(recommendations))
                recommendations.extend([p for p in additional if p not in recommendations])
            
            return recommendations[:limit]
        
        return self.product_repo.get_featured_products(limit)
    
    def _track_review_event(self, product_id: UUID, user_id: UUID, rating: int):
        """Track review submission event"""
        try:
            event = UserEvent(
                user_id=user_id,
                event_type='review_submit',
                entity_type='product',
                entity_id=product_id,
                metadata={'rating': rating}
            )
            db.session.add(event)
            db.session.commit()
        except Exception:
            db.session.rollback()


# Import repositories
from app.repositories.product_repository import CategoryRepository, ProductVariantRepository 