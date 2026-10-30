"""Read-only command interpretation endpoint for browser/mobile previews."""

from fastapi import APIRouter

from app.domain.models import CommandInterpretRequest, CommandInterpretResponse
from app.services.command_nlp import interpret_command

router = APIRouter(prefix="/commands", tags=["commands"])


@router.post("/interpret", response_model=CommandInterpretResponse)
def interpret_command_route(request: CommandInterpretRequest) -> CommandInterpretResponse:
    return interpret_command(request)
