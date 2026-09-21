"""Uvicorn entrypoint for the AgentFlow runtime."""

from agentflow.api.app import create_app

app = create_app()
