"""Shared SQLAlchemy registry for domain entities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for the NetGuard domain models."""
