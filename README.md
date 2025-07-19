# E-commerce API Backend

A comprehensive, production-ready e-commerce API backend built with Flask Python. This system provides a complete foundation for modern e-commerce applications with advanced features including analytics, recommendations, and scalable architecture.

## Features

### ✨ Core E-commerce Features
- **User Management**: Registration, authentication, profiles, addresses
- **Product Catalog**: Products with variants, categories, inventory tracking
- **Shopping Cart**: Persistent cart, guest checkout, discount system
- **Order Processing**: Complete checkout flow, payment integration, order management
- **Review System**: Product reviews with verification
- **Wishlist**: Save products for later

### 🚀 Advanced Features  
- **Analytics Dashboard**: Sales metrics, conversion tracking
- **Search Engine**: ElasticSearch integration for products
- **Recommendations**: Collaborative filtering algorithms
- **Admin Panel**: Backend management interface
- **Inventory Management**: Stock tracking, low stock alerts
- **Email System**: Transactional emails via Celery

### 🔧 Technical Features
- **API Documentation**: Auto-generated Swagger docs
- **Rate Limiting**: Protection against abuse
- **Caching**: Multi-level caching strategy with Redis
- **Error Handling**: Comprehensive error responses
- **Logging**: Structured logging for monitoring
- **Security**: JWT authentication, input validation, CORS

## Technology Stack

- **Backend Framework**: Flask with extensions
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis for sessions, cart, and performance
- **Search**: ElasticSearch for product search
- **Queue**: Celery for background tasks
- **Authentication**: JWT with refresh tokens
- **API Documentation**: Swagger/OpenAPI via Flask-RESTX
- **Testing**: Pytest with factory patterns

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- ElasticSearch 8+ (optional for development)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ecommerce-api
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your database and service configurations
```

5. **Initialize database**
```bash
# Create PostgreSQL database first
createdb ecommerce_db

# Run migrations
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. **Start services**
```bash
# Option 1: Using Docker Compose (recommended)
docker-compose up -d postgres redis elasticsearch

# Option 2: Start services manually
# Start PostgreSQL, Redis, and ElasticSearch on your system
```

7. **Run the application**
```bash
python app.py
```

The API will be available at `http://localhost:5000`

### API Documentation

Once the application is running, visit:
- **Swagger UI**: `http://localhost:5000/api/v1/docs/`
- **Health Check**: `http://localhost:5000/health`

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/profile` - Get user profile
- `PUT /api/v1/auth/profile` - Update user profile

### Products
- `GET /api/v1/products` - List products with filtering
- `GET /api/v1/products/{id}` - Get product details
- `GET /api/v1/products/featured` - Get featured products
- `GET /api/v1/products/recommendations` - Get personalized recommendations
- `GET /api/v1/products/categories` - Get product categories
- `GET /api/v1/products/{id}/reviews` - Get product reviews
- `POST /api/v1/products/{id}/reviews` - Add product review

### Shopping Cart
- `GET /api/v1/cart` - Get cart contents
- `POST /api/v1/cart/items` - Add item to cart
- `PUT /api/v1/cart/items/{id}` - Update cart item
- `DELETE /api/v1/cart/items/{id}` - Remove cart item
- `POST /api/v1/cart/clear` - Clear cart
- `POST /api/v1/cart/coupon` - Apply coupon
- `DELETE /api/v1/cart/coupon` - Remove coupon
- `GET /api/v1/cart/totals` - Calculate cart totals

## Configuration

Key environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/ecommerce_db

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Business Settings
TAX_RATE=0.08
DEFAULT_CURRENCY=USD
```

## Development

### Running Tests
```bash
pytest -v --cov=app
```

### Database Migrations
```bash
# Create new migration
flask db migrate -m "Description of changes"

# Apply migrations
flask db upgrade

# Downgrade migrations
flask db downgrade
```

### Background Tasks
```bash
# Start Celery worker
celery -A app.tasks worker --loglevel=info

# Start Flower monitoring
celery -A app.tasks flower
```

## Project Structure

```
ecommerce-api/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration management
│   ├── extensions.py            # Flask extensions
│   ├── models/                  # SQLAlchemy models
│   ├── repositories/            # Data access layer
│   ├── services/                # Business logic layer
│   ├── api/                     # API routes
│   │   └── v1/                  # API version 1
│   └── tasks/                   # Celery tasks
├── memory-bank/                 # Project documentation
├── migrations/                  # Database migrations
├── tests/                       # Test suite
├── requirements.txt             # Dependencies
├── app.py                       # Application entry point
└── README.md                    # This file
```

## Deployment

### Production Checklist

1. **Environment Configuration**
   - Set `FLASK_ENV=production`
   - Use strong `SECRET_KEY` and `JWT_SECRET_KEY`
   - Configure production database
   - Set up email service

2. **Security**
   - Enable HTTPS
   - Configure CORS properly
   - Set up rate limiting
   - Review security headers

3. **Performance**
   - Configure Redis for caching
   - Set up ElasticSearch for search
   - Enable database connection pooling
   - Configure Celery for background tasks

4. **Monitoring**
   - Set up logging
   - Configure health checks
   - Monitor API performance
   - Set up error tracking

### Docker Deployment

```bash
# Build Docker image
docker build -t ecommerce-api .

# Run with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Check the [API documentation](http://localhost:5000/api/v1/docs/)
- Review the [project documentation](memory-bank/)
- Open an issue on GitHub

---

Built with ❤️ using Flask Python