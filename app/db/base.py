"""SQLAlchemy declarative base and metadata."""

from sqlalchemy.orm import DeclarativeBase, registry


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    registry = registry()

    def __repr__(self) -> str:
        """Return string representation of model."""
        columns = ", ".join(
            f"{c.name}={getattr(self, c.name)!r}"
            for c in self.__table__.columns
            if c.name not in ("created_at", "updated_at")
        )
        return f"{self.__class__.__name__}({columns})"
