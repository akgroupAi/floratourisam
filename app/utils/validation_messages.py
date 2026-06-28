"""User-friendly validation error message formatting."""

from typing import Any, Optional

# Human-readable field labels keyed by JSON path / field name
FIELD_LABELS: dict[str, str] = {
    "email": "Email",
    "password": "Password",
    "full_name": "Name",
    "name": "Name",
    "phone": "Phone number",
    "date_of_birth": "Date of birth",
    "passport_expiry": "Passport expiry date",
    "gender": "Gender",
    "nationality": "Nationality",
    "blood_group": "Blood group",
    "title": "Title",
    "body": "Review text",
    "rating": "Rating",
    "category": "Category",
    "category_id": "Category",
    "room_id": "Room",
    "apartment_id": "Apartment",
    "restaurant_id": "Restaurant",
    "check_in_date": "Check-in date",
    "check_out_date": "Check-out date",
    "booking_date": "Booking date",
    "booking_time": "Booking time",
    "guest_count": "Guest count",
    "approve": "Approval status",
    "rejection_reason": "Rejection reason",
    "description": "Description",
    "price": "Price",
    "slug": "Slug",
    "address_line1": "Address",
    "city": "City",
    "country": "Country",
}


def _field_label(field: str) -> str:
    """Return a user-friendly label for a field path."""
    leaf = field.split(".")[-1].split("[")[0]
    return FIELD_LABELS.get(leaf, leaf.replace("_", " ").capitalize())


def format_validation_message(error: dict[str, Any]) -> str:
    """Convert a singleQuote validation error dict into a user-friendly message."""
    error_type = error.get("type", "")
    field = error.get("loc", ())
    field_name = _field_label(str(field[-1])) if field else "This field"

    ctx = error.get("ctx") or {}

    if error_type == "missing":
        return f"{field_name} is required."

    if error_type in ("string_type", "string_parsing"):
        return f"Please enter a valid {field_name.lower()}."

    if error_type in ("int_parsing", "float_parsing", "decimal_parsing"):
        return f"Please enter a valid number for {field_name.lower()}."

    if error_type == "date_parsing":
        return f"Please enter a valid date for {field_name.lower()}."

    if error_type == "time_parsing":
        return f"Please enter a valid time for {field_name.lower()}."

    if error_type == "uuid_parsing":
        return f"Please provide a valid {field_name.lower()}."

    if error_type == "enum":
        return f"Please select a valid {field_name.lower()}."

    if error_type == "value_error.email":
        return "Please enter a valid email address."

    if error_type == "value_error.url":
        return f"Please enter a valid URL for {field_name.lower()}."

    if error_type == "greater_than":
        limit = ctx.get("gt")
        return f"{field_name} must be greater than {limit}."

    if error_type == "greater_than_equal":
        limit = ctx.get("ge")
        return f"{field_name} must be at least {limit}."

    if error_type == "less_than":
        limit = ctx.get("lt")
        return f"{field_name} must be less than {limit}."

    if error_type == "less_than_equal":
        limit = ctx.get("le")
        return f"{field_name} must be at most {limit}."

    if error_type == "string_too_short":
        min_len = ctx.get("min_length")
        return f"{field_name} must be at least {min_len} characters."

    if error_type == "string_too_long":
        max_len = ctx.get("max_length")
        return f"{field_name} must be at most {max_len} characters."

    if error_type == "value_error":
        msg = error.get("msg", "")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        return msg or f"Please check {field_name.lower()}."

    # Fallback: strip technical prefixes from Pydantic messages
    msg = error.get("msg", "Invalid input.")
    for prefix in ("Value error, ", "Input should be ", "Field required"):
        if msg.startswith(prefix):
            break
    if msg == "Field required":
        return f"{field_name} is required."
    if "valid email" in msg.lower():
        return "Please enter a valid email address."
    if "valid string" in msg.lower():
        return f"Please enter a valid {field_name.lower()}."

    return msg


def format_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Format all validation errors for API responses."""
    formatted = []
    for err in errors:
        loc = err.get("loc", ())
        field_path = ".".join(str(part) for part in loc if part != "body")
        formatted.append(
            {
                "field": field_path or "body",
                "message": format_validation_message(err),
            }
        )
    return formatted


def primary_validation_message(errors: list[dict[str, Any]]) -> str:
    """Return the first user-friendly validation message."""
    if not errors:
        return "Please check your input and try again."
    return format_validation_message(errors[0])
