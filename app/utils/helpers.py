"""Utility helper functions."""

import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar
from uuid import UUID

from app.utils.constants import PASSWORD_MIN_LENGTH

T = TypeVar("T")


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP.

    Args:
        length: Length of OTP (default 6).

    Returns:
        Numeric OTP string.
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_token(length: int = 32) -> str:
    """Generate a secure random token.

    Args:
        length: Length of token (default 32).

    Returns:
        Random token string.
    """
    return secrets.token_urlsafe(length)


def generate_reference_id(prefix: str = "REF") -> str:
    """Generate a unique reference ID.

    Args:
        prefix: Prefix for the reference ID.

    Returns:
        Reference ID string like 'REF-20240123-ABC123'.
    """
    date_part = datetime.now().strftime("%Y%m%d")
    random_part = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix}-{date_part}-{random_part}"


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug.

    Args:
        text: Text to convert.

    Returns:
        Slugified string.
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special characters with hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    # Remove leading/trailing hyphens
    return text.strip("-")


def validate_password(password: str) -> tuple[bool, List[str]]:
    """Validate password against requirements.

    Args:
        password: Password to validate.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    errors = []

    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Password must contain at least one special character")

    return len(errors) == 0, errors


def validate_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: Email to validate.

    Returns:
        True if valid email format.
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format.

    Args:
        phone: Phone number to validate.

    Returns:
        True if valid phone format.
    """
    # Remove common separators
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    # Check if it's a valid phone number (10-15 digits, optionally starting with +)
    pattern = r"^\+?[1-9]\d{9,14}$"
    return bool(re.match(pattern, cleaned))


def mask_email(email: str) -> str:
    """Mask email address for display.

    Args:
        email: Email to mask.

    Returns:
        Masked email like 'j***@example.com'.
    """
    if "@" not in email:
        return email

    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(phone: str) -> str:
    """Mask phone number for display.

    Args:
        phone: Phone number to mask.

    Returns:
        Masked phone like '****1234'.
    """
    if len(phone) <= 4:
        return "*" * len(phone)
    return "*" * (len(phone) - 4) + phone[-4:]


def paginate_list(
    items: List[T],
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[T], int]:
    """Paginate a list of items.

    Args:
        items: List to paginate.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Tuple of (paginated items, total count).
    """
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


def is_valid_uuid(value: str) -> bool:
    """Check if string is a valid UUID.

    Args:
        value: String to check.

    Returns:
        True if valid UUID.
    """
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def safe_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value.

    Args:
        data: Dictionary to search.
        *keys: Nested keys to traverse.
        default: Default value if not found.

    Returns:
        Value at nested key or default.
    """
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


def calculate_age(birth_date: datetime) -> int:
    """Calculate age from birth date.

    Args:
        birth_date: Date of birth.

    Returns:
        Age in years.
    """
    today = datetime.now()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string.

    Args:
        amount: Amount to format.
        currency: Currency code.

    Returns:
        Formatted currency string.
    """
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"
