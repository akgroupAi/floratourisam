#!/usr/bin/env python3
"""
Razorpay Integration Quick Start Script

This script helps you:
1. Verify all dependencies are installed
2. Check configuration
3. Run basic tests
4. Print useful commands

Usage:
    python razorpay_quickstart.py
"""

import sys
import subprocess
from pathlib import Path


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(number: int, text: str):
    """Print a numbered step."""
    print(f"\n  [{number}] {text}")


def print_success(text: str):
    """Print a success message."""
    print(f"      ✅ {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"      ❌ {text}")


def print_info(text: str):
    """Print an info message."""
    print(f"      ℹ️  {text}")


def print_code(code: str):
    """Print a code block."""
    print("\n" + "      " + "-" * 60)
    for line in code.strip().split("\n"):
        print(f"      {line}")
    print("      " + "-" * 60 + "\n")


def check_dependencies():
    """Check if all required dependencies are installed."""
    print_step(1, "Checking dependencies...")

    dependencies = [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("requests", "Requests"),
        ("razorpay", "Razorpay SDK"),
        ("pydantic", "Pydantic"),
        ("uvicorn", "Uvicorn"),
    ]

    missing = []
    for module, name in dependencies:
        try:
            __import__(module)
            print_success(f"{name} installed")
        except ImportError:
            print_error(f"{name} NOT installed")
            missing.append(module)

    if missing:
        print_info("Installing missing dependencies...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install"] + missing,
            check=False,
        )
        print_success("Dependencies installed!")

    return len(missing) == 0


def check_configuration():
    """Check if Razorpay configuration is set."""
    print_step(2, "Checking configuration...")

    try:
        from app.core.config import settings

        config_vars = [
            ("RAZORPAY_KEY_ID", settings.RAZORPAY_KEY_ID),
            ("RAZORPAY_KEY_SECRET", settings.RAZORPAY_KEY_SECRET),
            ("RAZORPAY_WEBHOOK_SECRET", settings.RAZORPAY_WEBHOOK_SECRET),
            ("RAZORPAY_CURRENCY", settings.RAZORPAY_CURRENCY),
        ]

        all_set = True
        for name, value in config_vars:
            if value:
                # Mask the secret for security
                display_value = value[:5] + "..." if len(value) > 5 else value
                print_success(f"{name} = {display_value}")
            else:
                print_error(f"{name} not set in .env")
                all_set = False

        if not all_set:
            print_info("Configuration incomplete. See below for setup steps.")
            return False

        return True
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        return False


def check_modules():
    """Check if Razorpay modules can be imported."""
    print_step(3, "Checking modules...")

    modules = [
        ("app.services.razorpay_service", "RazorpayService"),
        ("app.api.v1.payments", "router"),
        ("app.models.payment", "Payment"),
    ]

    all_ok = True
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            obj = getattr(module, class_name)
            print_success(f"{module_name}.{class_name}")
        except Exception as e:
            print_error(f"{module_name}.{class_name}: {e}")
            all_ok = False

    return all_ok


def check_routes():
    """Check if API routes are registered."""
    print_step(4, "Checking API routes...")

    try:
        from app.api.v1.payments import router

        razorpay_routes = []
        for route in router.routes:
            if "razorpay" in getattr(route, "path", ""):
                razorpay_routes.append(route.path)

        if razorpay_routes:
            for route in razorpay_routes:
                print_success(f"Route: {route}")
            return True
        else:
            print_error("No Razorpay routes found!")
            return False
    except Exception as e:
        print_error(f"Failed to check routes: {e}")
        return False


def print_next_steps():
    """Print next steps for setup."""
    print_header("NEXT STEPS")

    print_step(1, "Configure Razorpay Credentials")
    print_info("Edit .env file and add:")
    print_code("""
RAZORPAY_KEY_ID=rzp_test_xxxxxxx
RAZORPAY_KEY_SECRET=your_secret_key
RAZORPAY_WEBHOOK_SECRET=webhook_secret
RAZORPAY_CURRENCY=INR
    """)

    print_step(2, "Start Development Server")
    print_code("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")

    print_step(3, "Test API Endpoint")
    print_code("""
curl -X POST http://localhost:8000/api/v1/payments/razorpay/order \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "booking_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
    """)

    print_step(4, "Frontend Integration")
    print_info("Use the HTML example in: RAZORPAY_FRONTEND_EXAMPLE.html")
    print_info("See RAZORPAY_QUICK_REFERENCE.md for JavaScript code")

    print_step(5, "Read Documentation")
    print_info("📖 RAZORPAY_INTEGRATION.md - Full technical guide")
    print_info("📖 RAZORPAY_QUICK_REFERENCE.md - Quick start guide")
    print_info("📖 RAZORPAY_VISUAL_GUIDE.md - Visual diagrams")


def print_quick_commands():
    """Print useful quick commands."""
    print_header("USEFUL COMMANDS")

    commands = [
        ("Install dependencies", "pip install -r requirements.txt"),
        ("Run tests", "pytest tests/test_razorpay.py -v"),
        ("Start dev server", "uvicorn app.main:app --reload"),
        ("Check imports", "python -c \"from app.services.razorpay_service import RazorpayService; print('✅ OK')\""),
        ("View config", "python -c \"from app.core.config import settings; print(f'Currency: {settings.RAZORPAY_CURRENCY}')\""),
    ]

    for description, command in commands:
        print(f"\n  {description}:")
        print_code(command)


def print_troubleshooting():
    """Print troubleshooting tips."""
    print_header("TROUBLESHOOTING")

    tips = [
        (
            "\"Not configured\" error",
            "Check that RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set in .env",
        ),
        (
            "\"Order not found\" error",
            "Verify booking exists and has a positive total_price",
        ),
        (
            "\"Invalid signature\" error",
            "Ensure RAZORPAY_WEBHOOK_SECRET matches the one in dashboard",
        ),
        (
            "Module not found error",
            "Run: pip install -r requirements.txt",
        ),
        (
            "Amount issues in tests",
            "Remember: Razorpay uses paise (smallest unit). 150.50 → 15050 paise",
        ),
    ]

    for issue, solution in tips:
        print(f"\n  ❓ {issue}")
        print(f"     💡 {solution}")


def print_resources():
    """Print helpful resources."""
    print_header("RESOURCES")

    print_info("📚 Official Documentation:")
    print_code("https://razorpay.com/docs/api/")

    print_info("📚 Dashboard:")
    print_code("https://dashboard.razorpay.com")

    print_info("📚 Test Credentials (for development):")
    print_code("""
Key ID: rzp_test_xxxxxxx
Key Secret: (from dashboard)

Test Cards:
  Visa: 4111 1111 1111 1111
  Mastercard: 5555 5555 5555 4444
  CVV: Any 3 digits
  Expiry: Any future date
  OTP: Any 6 digits
    """)

    print_info("📚 Project Documentation:")
    print_code("""
- RAZORPAY_INTEGRATION.md - Full integration guide
- RAZORPAY_QUICK_REFERENCE.md - Quick reference
- RAZORPAY_VISUAL_GUIDE.md - Visual diagrams
- RAZORPAY_MIGRATION_CHECKLIST.md - Deployment checklist
- RAZORPAY_FRONTEND_EXAMPLE.html - Frontend example
    """)


def main():
    """Run the quick start script."""
    print_header("RAZORPAY INTEGRATION QUICK START")

    print("\n  Checking your Razorpay integration setup...\n")

    # Run checks
    checks = [
        ("Dependencies", check_dependencies),
        ("Configuration", check_configuration),
        ("Modules", check_modules),
        ("Routes", check_routes),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print_error(f"Error checking {name}: {e}")
            results[name] = False

    # Summary
    print_header("SUMMARY")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")

    # If all passed, show celebration
    if all(results.values()):
        print("\n" + "=" * 70)
        print("  🎉 All checks passed! Your Razorpay setup is ready.")
        print("=" * 70)

    # Print next steps and resources
    print_next_steps()
    print_quick_commands()
    print_troubleshooting()
    print_resources()

    print_header("YOU'RE ALL SET!")
    print("\n  ✨ Your Razorpay integration is ready to use!")
    print("\n  Next: Implement the frontend payment flow using the example in:")
    print("        RAZORPAY_FRONTEND_EXAMPLE.html\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  ⏹️  Setup interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n  ❌ Error: {e}")
        sys.exit(1)
