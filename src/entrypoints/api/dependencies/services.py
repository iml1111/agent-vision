"""
Service Dependencies

Provides access to application services with dependency injection.
"""
from fastapi import Request

from service_layer.application.session_management_service import SessionManagementService
from service_layer.application.agent_orchestration_service import AgentOrchestrationService


def get_session_service(request: Request) -> SessionManagementService:
    """Dependency for SessionManagementService"""
    return SessionManagementService(
        db_client=request.app.state.db_client
    )


def get_orchestration_service(request: Request) -> AgentOrchestrationService:
    """Dependency for AgentOrchestrationService"""
    return AgentOrchestrationService(
        db_client=request.app.state.db_client
    )
