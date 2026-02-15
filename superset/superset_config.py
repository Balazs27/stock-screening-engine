# Superset configuration file
# Mounted to /app/superset_home/superset_config.py

import os

# Secret key for session management
SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'your-secret-key-change-in-production')

# Allow Snowflake connections
PREVENT_UNSAFE_DB_CONNECTIONS = False

# Session configuration
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_NAME = 'superset_session'
PERMANENT_SESSION_LIFETIME = 86400

# CSRF Protection
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None

# =============================================================================
# MCP Service Configuration (Native Superset MCP)
# =============================================================================
# Username for MCP authentication (must exist in Superset)
MCP_DEV_USERNAME = 'admin'

# Internal Superset URL for MCP service to connect to
SUPERSET_WEBSERVER_ADDRESS = 'http://localhost:8088'

# WebDriver configuration for screenshots (optional)
WEBDRIVER_BASEURL = 'http://localhost:8088/'
WEBDRIVER_BASEURL_USER_FRIENDLY = WEBDRIVER_BASEURL
