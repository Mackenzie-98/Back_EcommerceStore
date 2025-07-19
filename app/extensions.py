"""Flask extensions initialization module"""

from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate
# from flask_mail import Mail
from flask_caching import Cache
import redis
# from elasticsearch import Elasticsearch
# from celery import Celery


# Database
db = SQLAlchemy()

# Serialization
ma = Marshmallow()

# Database migrations
migrate = Migrate()

# Email
# mail = Mail()

# Caching
cache = Cache()


class RedisClient:
    """Redis client wrapper"""
    
    def __init__(self):
        self._client = None
    
    def init_app(self, app):
        """Initialize Redis client with Flask app"""
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        self._client = redis.from_url(redis_url, decode_responses=True)
    
    def __getattr__(self, name):
        """Proxy attribute access to Redis client"""
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call init_app() first.")
        return getattr(self._client, name)


# Commented out for now to get basic app running
# class ElasticsearchClient:
#     """ElasticSearch client wrapper"""
#     
#     def __init__(self):
#         self._client = None
#     
#     def init_app(self, app):
#         """Initialize ElasticSearch client with Flask app"""
#         es_url = app.config.get('ELASTICSEARCH_URL', 'http://localhost:9200')
#         self._client = Elasticsearch([es_url])
#     
#     def __getattr__(self, name):
#         """Proxy attribute access to ElasticSearch client"""
#         if self._client is None:
#             raise RuntimeError("ElasticSearch client not initialized. Call init_app() first.")
#         return getattr(self._client, name)


# class CeleryExtension:
#     """Celery extension for Flask"""
#     
#     def __init__(self):
#         self._celery = None
#     
#     def init_app(self, app):
#         """Initialize Celery with Flask app"""
#         self._celery = Celery(
#             app.import_name,
#             broker=app.config.get('CELERY_BROKER_URL'),
#             backend=app.config.get('CELERY_RESULT_BACKEND')
#         )
#         
#         # Update configuration
#         self._celery.conf.update(
#             task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
#             result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
#             accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
#             timezone=app.config.get('CELERY_TIMEZONE', 'UTC'),
#             enable_utc=app.config.get('CELERY_ENABLE_UTC', True),
#         )
#         
#         # Context task for Flask app context
#         class ContextTask(self._celery.Task):
#             def __call__(self, *args, **kwargs):
#                 with app.app_context():
#                     return self.run(*args, **kwargs)
#         
#         self._celery.Task = ContextTask
#     
#     def __getattr__(self, name):
#         """Proxy attribute access to Celery instance"""
#         if self._celery is None:
#             raise RuntimeError("Celery not initialized. Call init_app() first.")
#         return getattr(self._celery, name)


# Initialize extension instances
redis_client = RedisClient()
# es_client = ElasticsearchClient()
# celery = CeleryExtension() 