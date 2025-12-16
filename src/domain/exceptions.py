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
# Authentication Exceptions
# =============================================================================


class AuthenticationError(DomainError):
    """Base exception for authentication errors"""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password"""

    pass


class AuthSessionExpiredError(AuthenticationError):
    """Auth session has expired or does not exist"""

    pass


class InvalidTokenError(AuthenticationError):
    """Invalid or malformed token"""

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


class SessionExpiredError(AgentSessionError):
    """Agent session has expired"""

    pass


class InvalidSessionStateError(AgentSessionError):
    """Invalid session state for the requested operation"""

    pass


class LoopLimitExceededError(AgentSessionError):
    """Agent loop limit has been exceeded"""

    pass


class HITLTimeoutError(AgentSessionError):
    """HITL response timeout"""

    pass


# =============================================================================
# Allowlist Exceptions
# =============================================================================


class AllowlistError(DomainError):
    """Base exception for allowlist errors"""

    pass


class AllowlistViolationError(AllowlistError):
    """Access to resource not in allowlist"""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            f"Access denied: {resource_type} '{resource_id}' is not in the allowlist"
        )


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
