# E-commerce API - System Architecture & Patterns

## Overall Architecture

### Layered Architecture
```
┌─────────────────────────────────────┐
│          API Layer (Flask)          │  <- Routes, Authentication, Validation
├─────────────────────────────────────┤
│        Service Layer               │  <- Business Logic, Orchestration
├─────────────────────────────────────┤
│        Repository Layer            │  <- Data Access, ORM Abstractions
├─────────────────────────────────────┤
│         Model Layer                │  <- SQLAlchemy Models, Schemas
└─────────────────────────────────────┘
```

### Technology Stack
- **API Framework**: Flask + Flask-RESTful + Flask-JWT-Extended
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis for sessions, cart persistence, rate limiting
- **Search**: ElasticSearch for product search and analytics
- **Queue**: Celery + Redis for background tasks
- **Documentation**: Flask-RESTX (Swagger UI)
- **Testing**: Pytest with factory patterns

## Design Patterns

### Repository Pattern
```python
# Abstract repository interface
class BaseRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[Model]:
        pass
    
    @abstractmethod
    async def create(self, data: dict) -> Model:
        pass

# Concrete implementation
class ProductRepository(BaseRepository):
    def __init__(self, db_session):
        self.db = db_session
    
    async def get_by_id(self, id: UUID) -> Optional[Product]:
        return await self.db.query(Product).filter_by(id=id).first()
```

### Service Layer Pattern
```python
class ProductService:
    def __init__(self, product_repo: ProductRepository, search_service: SearchService):
        self.product_repo = product_repo
        self.search_service = search_service
    
    async def search_products(self, query: str, filters: dict) -> SearchResult:
        # Orchestrate between repository and search service
        # Apply business rules
        # Return formatted results
```

### Factory Pattern for Tests
```python
class ProductFactory:
    @staticmethod
    def create_product(**kwargs) -> Product:
        defaults = {
            'name': 'Test Product',
            'price': 29.99,
            'stock': 100
        }
        defaults.update(kwargs)
        return Product(**defaults)
```

## Data Architecture

### Database Design Principles
1. **Normalization**: 3NF for transactional data
2. **Denormalization**: Strategic for read-heavy operations
3. **Partitioning**: By date for analytics tables
4. **Indexing**: Query-optimized indexes
5. **Constraints**: Database-level business rule enforcement

### Key Entities & Relationships
```
User 1:N Orders
User 1:N Addresses
User 1:N CartItems (via Cart)

Product 1:N ProductVariants
Product 1:N Reviews
Product N:1 Category

Order 1:N OrderItems
OrderItem N:1 ProductVariant

Cart 1:N CartItems
CartItem N:1 ProductVariant
```

### Audit Trail Pattern
```sql
-- All core tables include audit fields
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
created_by UUID REFERENCES users(id)
updated_by UUID REFERENCES users(id)
version INTEGER DEFAULT 1  -- Optimistic locking
```

## API Design Patterns

### RESTful Resource Design
```
GET    /api/v1/products          # List with filtering
POST   /api/v1/products          # Create new
GET    /api/v1/products/{id}     # Get specific
PUT    /api/v1/products/{id}     # Update full
PATCH  /api/v1/products/{id}     # Partial update
DELETE /api/v1/products/{id}     # Delete
```

### Nested Resources
```
GET    /api/v1/products/{id}/variants
POST   /api/v1/products/{id}/variants
GET    /api/v1/products/{id}/reviews
POST   /api/v1/products/{id}/reviews
```

### Response Format Standardization
```json
{
  "data": { ... },           // Main response data
  "meta": {                  // Metadata
    "page": 1,
    "total": 100,
    "has_next": true
  },
  "links": {                 // HATEOAS links
    "self": "/api/v1/products?page=1",
    "next": "/api/v1/products?page=2"
  }
}
```

## Caching Strategy

### Multi-Level Caching
1. **Application Cache**: Redis for frequently accessed data
2. **Query Cache**: Database query result caching
3. **CDN Cache**: Static assets and API responses
4. **Browser Cache**: HTTP headers for client caching

### Cache Patterns
```python
# Cache-Aside Pattern
async def get_product(product_id: UUID) -> Product:
    # Try cache first
    cached = await redis_client.get(f"product:{product_id}")
    if cached:
        return Product.parse_raw(cached)
    
    # Fallback to database
    product = await product_repo.get_by_id(product_id)
    
    # Update cache
    await redis_client.setex(
        f"product:{product_id}", 
        300,  # 5 minutes TTL
        product.json()
    )
    return product
```

## Security Patterns

### Authentication Flow
```
1. User login -> JWT access token (15 min) + refresh token (7 days)
2. API requests include access token in Authorization header
3. Token validation on each request
4. Refresh token rotation on renewal
5. Logout invalidates both tokens
```

### Authorization Middleware
```python
@require_auth
@require_permission('products:write')
async def create_product():
    # Route handler
    pass
```

### Input Validation
```python
# Marshmallow schemas for validation
class ProductCreateSchema(Schema):
    name = fields.Str(required=True, validate=Length(min=1, max=255))
    price = fields.Decimal(required=True, validate=Range(min=0))
    category_id = fields.UUID(required=True)
```

## Error Handling Patterns

### Structured Error Responses
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "name": ["This field is required"],
      "price": ["Must be greater than 0"]
    },
    "timestamp": "2024-01-15T10:30:00Z",
    "request_id": "uuid-here"
  }
}
```

### Exception Hierarchy
```python
class EcommerceException(Exception):
    """Base exception for all e-commerce errors"""
    
class ValidationError(EcommerceException):
    """Data validation errors"""
    
class BusinessLogicError(EcommerceException):
    """Business rule violations"""
    
class ResourceNotFoundError(EcommerceException):
    """Resource not found errors"""
```

## Background Job Patterns

### Celery Task Organization
```python
# Email tasks
@celery.task
def send_order_confirmation(order_id: UUID):
    pass

@celery.task  
def send_abandoned_cart_email(cart_id: UUID):
    pass

# Analytics tasks
@celery.task
def update_product_metrics(product_id: UUID, event_type: str):
    pass

# Inventory tasks
@celery.task
def check_low_stock_alerts():
    pass
```

## Monitoring & Observability

### Logging Strategy
```python
# Structured logging with context
logger.info("Order created", extra={
    'order_id': str(order.id),
    'user_id': str(order.user_id),
    'total': float(order.total),
    'event': 'order_created'
})
```

### Health Check Endpoints
```python
@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'database': check_database_connection(),
        'redis': check_redis_connection(),
        'elasticsearch': check_elasticsearch_connection()
    }
```

This architecture provides a solid foundation for building a scalable, maintainable e-commerce API that can grow with business needs while maintaining code quality and performance. 