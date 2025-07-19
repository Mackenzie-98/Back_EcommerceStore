"""Product API endpoints"""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import Schema, fields as ma_fields, validate, ValidationError
from uuid import UUID

from app.services import ProductService

# Create namespace
ns = Namespace('products', description='Product operations')

# Initialize services
product_service = ProductService()

# Flask-RESTX models for documentation
product_model = ns.model('Product', {
    'id': fields.String(description='Product ID'),
    'name': fields.String(description='Product name'),
    'slug': fields.String(description='Product slug'),
    'description': fields.String(description='Product description'),
    'brand': fields.String(description='Product brand'),
    'category_id': fields.String(description='Category ID'),
    'is_active': fields.Boolean(description='Is product active'),
    'is_featured': fields.Boolean(description='Is product featured'),
    'created_at': fields.String(description='Creation date'),
    'updated_at': fields.String(description='Update date')
})

@ns.route('')
class ProductList(Resource):
    @ns.doc('list_products')
    @ns.param('q', 'Search query')
    @ns.param('category', 'Category ID filter')
    @ns.param('brand', 'Brand filter')
    @ns.param('min_price', 'Minimum price filter')
    @ns.param('max_price', 'Maximum price filter')
    @ns.param('in_stock', 'Only show in-stock products')
    @ns.param('sort', 'Sort order (name, price, created_at)')
    @ns.param('page', 'Page number')
    @ns.param('limit', 'Items per page')
    def get(self):
        """Get products with filtering and search"""
        try:
            # Get query parameters
            query = request.args.get('q', '')
            category_id = request.args.get('category')
            brand = request.args.get('brand')
            min_price = request.args.get('min_price', type=float)
            max_price = request.args.get('max_price', type=float)
            in_stock = request.args.get('in_stock', 'true').lower() == 'true'
            sort = request.args.get('sort', 'created_at')
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            
            # Build filters
            filters = {}
            if category_id:
                try:
                    filters['category_ids'] = [UUID(category_id)]
                except ValueError:
                    return {'error': 'Invalid category ID'}, 400
            
            if brand:
                filters['brands'] = [brand]
            
            if min_price is not None:
                filters['min_price'] = min_price
                
            if max_price is not None:
                filters['max_price'] = max_price
            
            filters['in_stock'] = in_stock
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Search products
            result = product_service.search_products(
                query=query if query else None,
                filters=filters,
                sort=sort,
                limit=limit,
                offset=offset
            )
            
            return {
                'products': [product.to_dict() for product in result['products']],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': result['total'],
                    'pages': (result['total'] + limit - 1) // limit
                }
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to fetch products'}, 500

@ns.route('/<string:product_id>')
class ProductDetail(Resource):
    @ns.doc('get_product')
    def get(self, product_id):
        """Get product details by ID"""
        try:
            product_uuid = UUID(product_id)
            product = product_service.get_product_with_variants(product_uuid)
            
            if not product:
                return {'error': 'Product not found'}, 404
            
            # Track product view
            user_id = None
            try:
                user_id = get_jwt_identity() if get_jwt_identity() else None
            except:
                pass
            
            product_service.track_product_view(product_uuid, user_id)
            
            return {'product': product.to_dict()}, 200
            
        except ValueError:
            return {'error': 'Invalid product ID'}, 400
        except Exception as e:
            return {'error': 'Failed to fetch product'}, 500

@ns.route('/featured')
class FeaturedProducts(Resource):
    @ns.doc('get_featured_products')
    @ns.param('limit', 'Number of featured products to return')
    def get(self):
        """Get featured products"""
        try:
            limit = request.args.get('limit', 10, type=int)
            products = product_service.get_featured_products(limit)
            
            return {
                'products': [product.to_dict() for product in products]
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to fetch featured products'}, 500

@ns.route('/categories')
class Categories(Resource):
    @ns.doc('get_categories')
    def get(self):
        """Get product categories"""
        try:
            categories = product_service.get_categories()
            return {'categories': categories}, 200
        except Exception as e:
            return {'error': 'Failed to fetch categories'}, 500

@ns.route('/categories/<string:category_id>/products')
class CategoryProducts(Resource):
    @ns.doc('get_category_products')
    @ns.param('page', 'Page number')
    @ns.param('limit', 'Items per page')
    def get(self, category_id):
        """Get products in a specific category"""
        try:
            category_uuid = UUID(category_id)
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            offset = (page - 1) * limit
            
            result = product_service.get_products_by_category(
                category_uuid, limit, offset
            )
            
            return {
                'products': [product.to_dict() for product in result['products']],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': result['total'],
                    'pages': (result['total'] + limit - 1) // limit
                }
            }, 200
            
        except ValueError:
            return {'error': 'Invalid category ID'}, 400
        except Exception as e:
            return {'error': 'Failed to fetch category products'}, 500

@ns.route('/<string:product_id>/related')
class RelatedProducts(Resource):
    @ns.doc('get_related_products')
    @ns.param('limit', 'Number of related products to return')
    def get(self, product_id):
        """Get related products"""
        try:
            product_uuid = UUID(product_id)
            limit = request.args.get('limit', 5, type=int)
            
            products = product_service.get_related_products(product_uuid, limit)
            
            return {
                'products': [product.to_dict() for product in products]
            }, 200
            
        except ValueError:
            return {'error': 'Invalid product ID'}, 400
        except Exception as e:
            return {'error': 'Failed to fetch related products'}, 500

@ns.route('/recommendations')
class Recommendations(Resource):
    @ns.doc('get_recommendations')
    @ns.param('limit', 'Number of recommendations to return')
    def get(self):
        """Get personalized product recommendations"""
        try:
            limit = request.args.get('limit', 10, type=int)
            user_id = None
            
            try:
                user_id = UUID(get_jwt_identity()) if get_jwt_identity() else None
            except:
                pass
            
            products = product_service.get_recommendations(user_id, limit)
            
            return {
                'products': [product.to_dict() for product in products]
            }, 200
            
        except Exception as e:
            return {'error': 'Failed to fetch recommendations'}, 500

@ns.route('/<string:product_id>/reviews')
class ProductReviews(Resource):
    @ns.doc('get_product_reviews')
    @ns.param('page', 'Page number')
    @ns.param('limit', 'Items per page')
    def get(self, product_id):
        """Get product reviews"""
        try:
            product_uuid = UUID(product_id)
            page = request.args.get('page', 1, type=int)
            limit = request.args.get('limit', 20, type=int)
            
            result = product_service.get_product_reviews(
                product_uuid, page, limit
            )
            
            return {
                'reviews': result['reviews'],
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': result['total'],
                    'pages': (result['total'] + limit - 1) // limit
                },
                'summary': result['summary']
            }, 200
            
        except ValueError:
            return {'error': 'Invalid product ID'}, 400
        except Exception as e:
            return {'error': 'Failed to fetch reviews'}, 500
    
    @jwt_required()
    @ns.doc('add_product_review')
    def post(self, product_id):
        """Add a product review"""
        try:
            product_uuid = UUID(product_id)
            user_id = UUID(get_jwt_identity())
            
            data = request.json
            if not data or 'rating' not in data:
                return {'error': 'Rating is required'}, 400
            
            if not 1 <= data['rating'] <= 5:
                return {'error': 'Rating must be between 1 and 5'}, 400
            
            result = product_service.add_review(
                product_uuid,
                user_id,
                data['rating'],
                data.get('title'),
                data.get('comment'),
                data.get('images', [])
            )
            
            if result['success']:
                return {
                    'message': 'Review added successfully',
                    'review': result['review']
                }, 201
            else:
                return {'error': result['error']}, 400
                
        except ValueError:
            return {'error': 'Invalid product ID'}, 400
        except Exception as e:
            return {'error': 'Failed to add review'}, 500 