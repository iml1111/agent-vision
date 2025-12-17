"""
Service Dependencies

Provides access to application services with dependency injection.
"""
from fastapi import Request

from service_layer.application.agent_orchestration_service import AgentOrchestrationService


def get_orchestration_service(request: Request) -> AgentOrchestrationService:
    """Dependency for AgentOrchestrationService"""
    return AgentOrchestrationService(
        db_client=request.app.state.db_client,
        embedding_client=request.app.state.openai_client
    )
