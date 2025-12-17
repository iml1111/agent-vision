"""Domain Layer - Pure Python business logic"""

from .exceptions import (
    DomainError,
    EntityNotFoundError,
    EntityValidationError,
    ExternalAPIError,
    ExternalServiceError,
)

__all__ = [
    "DomainError",
    "EntityNotFoundError",
    "EntityValidationError",
    "ExternalServiceError",
    "ExternalAPIError",
]
