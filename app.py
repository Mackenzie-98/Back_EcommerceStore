"""Flask application entry point"""

import os
from app import create_app
from app.config import get_config

# Get configuration based on environment
config_name = os.environ.get('FLASK_ENV', 'development')
config_class = get_config(config_name)

# Create Flask application
app = create_app(config_class)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=config_class.DEBUG
    ) 