"""Domain Exceptions

Pure Python domain exceptions without HTTP/infrastructure concerns.
These exceptions represent domain-level error conditions.
"""


class DomainError(Exception):
    """
    Base exception for all domain errors.

    All domain-specific exceptions should inherit from this class.
    This allows catch-all handling at upper layers while keeping
    the domain layer pure (no HTTP status codes or API concerns).
    """

    pass


# =============================================================================
# Entity-Related Exceptions
# =============================================================================


class EntityNotFoundError(DomainError):
    """Entity with given ID does not exist"""

    pass


class EntityValidationError(DomainError):
    """Entity data validation failed"""

    pass


# =============================================================================
# External Integration Exceptions
# =============================================================================


class ExternalServiceError(DomainError):
    """
    External service call failed.

    Base exception for all external service integration errors.
    Subclass for specific service failures.
    """

    pass


class ExternalAPIError(ExternalServiceError):
    """External API call failed"""

    pass


# =============================================================================
# Agent Session Exceptions
# =============================================================================


class AgentSessionError(DomainError):
    """Base exception for agent session errors"""

    pass


class AgentSessionNotFoundError(AgentSessionError, EntityNotFoundError):
    """Agent session with given ID does not exist"""

    pass


class InvalidSessionStateError(AgentSessionError):
    """Invalid session state for the requested operation"""

    pass


# =============================================================================
# External Service Exceptions (Agent-specific)
# =============================================================================


class EmbeddingServiceError(ExternalServiceError):
    """Embedding generation failed"""

    pass


class SlackAPIError(ExternalServiceError):
    """Slack API call failed"""

    pass


class NotionAPIError(ExternalServiceError):
    """Notion API call failed"""

    pass
