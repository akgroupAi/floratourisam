# Medical Tourism Platform - Backend API

A production-grade FastAPI backend for a Medical Tourism Platform with comprehensive features including RBAC, WebSocket support, CMS, and AI chat integration.

## Tech Stack

- **Python 3.11+**
- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - Async ORM
- **Alembic** - Database migrations
- **PostgreSQL** - Primary database
- **Pydantic v2** - Data validation
- **JWT** - Authentication
- **Redis** - Caching (optional)
- **WebSocket** - Real-time chat

## Project Structure

```
medical_tourism_backend/
├── app/
│   ├── main.py              # Application entry point
│   ├── core/                # Core configuration
│   │   ├── config.py        # Settings management
│   │   ├── security.py      # JWT & password hashing
│   │   ├── middleware.py    # Request logging, CORS
│   │   ├── dependencies.py  # DI and RBAC
│   │   └── logging.py       # Structured logging
│   ├── db/                  # Database layer
│   │   ├── base.py          # SQLAlchemy base
│   │   ├── session.py       # Async session factory
│   │   └── init_db.py       # Database seeding
│   ├── models/              # SQLAlchemy models (14 files)
│   ├── schemas/             # Pydantic schemas (11 files)
│   ├── services/            # Business logic (8 files)
│   ├── api/v1/              # API endpoints (13 files)
│   └── utils/               # Helpers, constants, enums
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── .env.example             # Environment template
├── requirements.txt         # Dependencies
└── README.md
```

## Quick Start

### 1. Clone and Setup

```bash
cd medical_tourism_backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database credentials:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/medical_tourism
# SECRET_KEY=your-super-secret-key-min-32-chars
```

### 3. Create Database

```bash
# Create PostgreSQL database
createdb medical_tourism

# Run migrations
alembic upgrade head
```

### 4. Run Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Access API

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Default Credentials

On first run, a superuser is created:
- Email: `admin@medicaltourism.com`
- Password: `Admin@123456`

## User Roles (RBAC)

| Role | Permissions |
|------|-------------|
| `super_admin` | Full system access |
| `admin` | Manage users, content, settings |
| `patient` | Own profile, bookings, consultations |
| `doctor` | Own profile, assigned consultations |
| `hotel_manager` | Own hotel management |
| `restaurant_manager` | Own restaurant management |

## API Endpoints Summary

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | User login |
| POST | `/api/v1/auth/register` | User registration |
| POST | `/api/v1/auth/refresh` | Refresh tokens |
| POST | `/api/v1/auth/logout` | User logout |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get current user |
| PUT | `/api/v1/users/me` | Update profile |
| GET | `/api/v1/users` | List users (admin) |

### Patients & Doctors
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/patients/me` | Patient profile |
| GET | `/api/v1/doctors` | List doctors |
| GET | `/api/v1/doctors/{id}` | Doctor details |

### Bookings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/bookings` | List bookings |
| POST | `/api/v1/bookings/hotel` | Create hotel booking |
| POST | `/api/v1/bookings/restaurant` | Create restaurant booking |

### CMS
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cms/pages/{slug}` | Get public page |
| GET | `/api/v1/cms/admin/pages` | List pages (admin) |
| POST | `/api/v1/cms/admin/pages` | Create page (admin) |

### Chat & AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/api/v1/chat/ws/{room_id}` | WebSocket chat |
| POST | `/api/v1/ai/chat` | AI assistant |

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/medical_tourism
    depends_on:
      - db
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=medical_tourism
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
volumes:
  postgres_data:
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test
pytest tests/test_auth.py -v
```

## License

MIT License
