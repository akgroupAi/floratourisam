"""Application constants."""

# API Version
API_V1_PREFIX = "/api/v1"

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_PAGE = 1

# Token constants
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# File upload
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx"}
MAX_FILE_SIZE_MB = 10

# Cache TTL (in seconds)
CACHE_TTL_SHORT = 60  # 1 minute
CACHE_TTL_MEDIUM = 300  # 5 minutes
CACHE_TTL_LONG = 3600  # 1 hour
CACHE_TTL_DAY = 86400  # 24 hours

# Rate limiting
RATE_LIMIT_DEFAULT = 100  # requests per minute
RATE_LIMIT_AUTH = 20  # auth endpoints per minute
RATE_LIMIT_UPLOAD = 10  # uploads per minute

# WebSocket
WS_HEARTBEAT_INTERVAL = 30  # seconds
WS_MAX_MESSAGE_SIZE = 65536  # 64KB

# Consultation
CONSULTATION_DURATION_MINUTES = 30
CONSULTATION_BUFFER_MINUTES = 10

# Booking
BOOKING_CANCELLATION_HOURS = 24
BOOKING_REMINDER_HOURS = 2

# Password requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = True

# OTP
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10

# Session
SESSION_EXPIRY_HOURS = 24

# Error codes
ERROR_CODES = {
    "AUTH_001": "Invalid credentials",
    "AUTH_002": "Token expired",
    "AUTH_003": "Token invalid",
    "AUTH_004": "User not found",
    "AUTH_005": "User disabled",
    "AUTH_006": "Insufficient permissions",
    "USER_001": "User already exists",
    "USER_002": "Invalid user data",
    "BOOKING_001": "Booking not available",
    "BOOKING_002": "Booking cancelled",
    "PAYMENT_001": "Payment failed",
    "PAYMENT_002": "Insufficient funds",
    "VALIDATION_001": "Invalid input",
    "SERVER_001": "Internal server error",
}

# Success messages
SUCCESS_MESSAGES = {
    "auth_login": "Login successful",
    "auth_logout": "Logout successful",
    "auth_register": "Registration successful",
    "booking_created": "Booking created successfully",
    "booking_cancelled": "Booking cancelled successfully",
    "payment_success": "Payment processed successfully",
}
