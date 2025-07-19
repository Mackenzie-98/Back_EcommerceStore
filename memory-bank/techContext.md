# E-commerce API - Technical Context

## Technology Stack

### Core Framework
- **Flask 3.0+**: Lightweight, flexible web framework
- **Flask-RESTful**: RESTful API support with resource classes
- **Flask-JWT-Extended**: JWT authentication with refresh tokens
- **Flask-RESTX**: Swagger/OpenAPI documentation
- **Flask-Migrate**: Database migrations via Alembic
- **Flask-CORS**: Cross-origin resource sharing
- **Flask-Limiter**: Rate limiting and throttling

### Database & ORM
- **PostgreSQL 15+**: Primary database with JSON support
- **SQLAlchemy 2.0+**: Modern ORM with async support
- **Alembic**: Database schema migrations
- **psycopg2-binary**: PostgreSQL adapter

### Caching & Search
- **Redis 7.0+**: Session storage, caching, and message broker
- **ElasticSearch 8.0+**: Full-text search and analytics
- **redis-py**: Redis client for Python

### Background Tasks
- **Celery 5.3+**: Distributed task queue
- **Redis**: Message broker for Celery
- **Flower**: Celery monitoring

### Data Validation & Serialization
- **Marshmallow 3.20+**: Object serialization/deserialization
- **marshmallow-sqlalchemy**: SQLAlchemy integration
- **Pydantic**: Type validation for configuration

### Development & Testing
- **Pytest**: Testing framework
- **Factory Boy**: Test data generation
- **Faker**: Fake data generation
- **pytest-asyncio**: Async test support
- **coverage**: Code coverage reporting

### Production & Deployment
- **Gunicorn**: WSGI HTTP server
- **Nginx**: Reverse proxy and static files
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration

## Development Environment Setup

### Prerequisites
```bash
# Required system dependencies
Python 3.11+
PostgreSQL 15+
Redis 7+
ElasticSearch 8+ (optional for development)
Docker & Docker Compose (recommended)
```

### Project Structure
```
ecommerce-api/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration management
│   ├── extensions.py            # Flask extensions initialization
│   ├── models/                  # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── order.py
│   │   └── analytics.py
│   ├── schemas/                 # Marshmallow schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── product.py
│   │   └── order.py
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── cart_service.py
│   │   ├── order_service.py
│   │   └── analytics_service.py
│   ├── repositories/            # Data access layer
│   │   ├── __init__.py
│   │   ├── base_repository.py
│   │   ├── user_repository.py
│   │   ├── product_repository.py
│   │   └── order_repository.py
│   ├── api/                     # API routes
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── products.py
│   │   │   ├── cart.py
│   │   │   ├── orders.py
│   │   │   ├── users.py
│   │   │   ├── admin.py
│   │   │   └── analytics.py
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── error_handler.py
│   │       └── rate_limiter.py
│   ├── utils/                   # Utility functions
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   ├── helpers.py
│   │   └── decorators.py
│   └── tasks/                   # Celery tasks
│       ├── __init__.py
│       ├── email_tasks.py
│       ├── analytics_tasks.py
│       └── inventory_tasks.py
├── migrations/                  # Alembic migrations
├── tests/                       # Test suite
│   ├── conftest.py
│   ├── factories/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docker/                      # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── scripts/                     # Utility scripts
│   ├── seed_data.py
│   ├── run_tests.py
│   └── deploy.py
├── requirements/                # Dependencies
│   ├── base.txt
│   ├── development.txt
│   ├── production.txt
│   └── testing.txt
├── .env.example                 # Environment variables template
├── .gitignore
├── README.md
├── Makefile                     # Common commands
└── pyproject.toml              # Project configuration
```

### Installation Steps
```bash
# 1. Clone and setup virtual environment
git clone <repository>
cd ecommerce-api
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements/development.txt

# 3. Setup environment variables
cp .env.example .env
# Edit .env with your database and service configurations

# 4. Start services with Docker Compose
docker-compose up -d postgres redis elasticsearch

# 5. Initialize database
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 6. Seed development data
python scripts/seed_data.py

# 7. Run development server
flask run --debug

# 8. Run tests
pytest

# 9. Start Celery worker (separate terminal)
celery -A app.tasks worker --loglevel=info
```

## Configuration Management

### Environment-Based Configuration
```python
# config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    
    # Redis Configuration
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    # ElasticSearch Configuration
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or 'http://localhost:9200'
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    
    # Celery Configuration
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

### Environment Variables
```bash
# .env.example
# Flask
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://username:password@localhost/ecommerce_db

# Redis
REDIS_URL=redis://localhost:6379/0

# ElasticSearch
ELASTICSEARCH_URL=http://localhost:9200

# JWT
JWT_SECRET_KEY=your-jwt-secret-key

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Payment Gateway
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# AWS (for file uploads)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name

# External APIs
GOOGLE_ANALYTICS_ID=GA_MEASUREMENT_ID
```

## Database Configuration

### PostgreSQL Setup
```sql
-- Create database and user
CREATE DATABASE ecommerce_db;
CREATE USER ecommerce_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO ecommerce_user;

-- Enable UUID extension
\c ecommerce_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search
```

### Redis Configuration
```bash
# redis.conf optimizations for production
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Development Workflow

### Common Commands (Makefile)
```makefile
# Development
.PHONY: install dev test clean

install:
	pip install -r requirements/development.txt

dev:
	flask run --debug

test:
	pytest -v --cov=app

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Database
.PHONY: db-init db-migrate db-upgrade db-seed

db-init:
	flask db init

db-migrate:
	flask db migrate -m "$(message)"

db-upgrade:
	flask db upgrade

db-seed:
	python scripts/seed_data.py

# Services
.PHONY: services-up services-down

services-up:
	docker-compose up -d postgres redis elasticsearch

services-down:
	docker-compose down

# Production
.PHONY: build deploy

build:
	docker build -t ecommerce-api .

deploy:
	./scripts/deploy.sh
```

### Git Workflow
```bash
# Feature development
git checkout -b feature/product-search
# ... make changes ...
git add .
git commit -m "feat: implement product search with ElasticSearch"
git push origin feature/product-search
# Create pull request

# Database migrations
git checkout main
git pull origin main
flask db migrate -m "Add product search fields"
git add migrations/
git commit -m "db: add product search fields migration"
git push origin main
```

## Performance Considerations

### Database Optimization
- Connection pooling with SQLAlchemy
- Query optimization with indexes
- Read replicas for analytics queries
- Partitioning for large tables (orders, events)

### Caching Strategy
- Redis for session storage and frequent queries
- Application-level caching for product catalog
- CDN for static assets and API responses

### Background Processing
- Celery for email sending and heavy computations
- Separate queues for different task priorities
- Monitoring with Flower

### Monitoring & Logging
- Structured logging with JSON format
- Application metrics with custom decorators
- Health check endpoints for monitoring systems

This technical foundation provides a robust, scalable platform for the e-commerce API with clear development workflows and production readiness. 