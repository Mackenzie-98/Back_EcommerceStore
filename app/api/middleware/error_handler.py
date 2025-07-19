"""Error handler middleware for consistent error responses"""

from flask import jsonify, request
from flask_jwt_extended.exceptions import JWTExtendedException
from werkzeug.exceptions import HTTPException
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register error handlers for the Flask application"""
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        """Handle Marshmallow validation errors"""
        return jsonify({
            'error': 'Validation failed',
            'details': e.messages,
            'request_id': getattr(request, 'id', None)
        }), 400
    
    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        """Handle database integrity errors"""
        logger.error(f"Database integrity error: {str(e)}")
        return jsonify({
            'error': 'Data integrity error',
            'message': 'The request conflicts with existing data',
            'request_id': getattr(request, 'id', None)
        }), 409
    
    @app.errorhandler(JWTExtendedException)
    def handle_jwt_error(e):
        """Handle JWT-related errors"""
        return jsonify({
            'error': 'Authentication error',
            'message': str(e),
            'request_id': getattr(request, 'id', None)
        }), 401
    
    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        """Handle HTTP exceptions"""
        return jsonify({
            'error': e.name,
            'message': e.description,
            'status_code': e.code,
            'request_id': getattr(request, 'id', None)
        }), e.code
    
    @app.errorhandler(404)
    def handle_not_found(e):
        """Handle 404 errors"""
        return jsonify({
            'error': 'Not found',
            'message': 'The requested resource was not found',
            'request_id': getattr(request, 'id', None)
        }), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        """Handle method not allowed errors"""
        return jsonify({
            'error': 'Method not allowed',
            'message': f'Method {request.method} not allowed for this endpoint',
            'request_id': getattr(request, 'id', None)
        }), 405
    
    @app.errorhandler(500)
    def handle_internal_error(e):
        """Handle internal server errors"""
        logger.error(f"Internal server error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'request_id': getattr(request, 'id', None)
        }), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        """Handle any unexpected errors"""
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Unexpected error',
            'message': 'An unexpected error occurred',
            'request_id': getattr(request, 'id', None)
        }), 500 