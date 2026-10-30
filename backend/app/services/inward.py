"""Quick voice/text inward: a reviewed transcript becomes a stock-receipt proposal.

No costs are taken from speech, so a quantity-only delivery confirms as stock
only. A payable is possible only if the merchant later adds a verified total in
the review step and selects the supplier.
"""

from fastapi import HTTPException

from app.domain.intake import DraftContent, DraftLine, DraftSupplier, ExtractionView, InwardInterpretRequest, InwardInterpretResponse
from app.services.database import connect
from app.services.inward_parser import parse_inward
from app.services.proposals import evaluate, insert_proposal, load_row, new_line_id


def create_inward_proposal(request: InwardInterpretRequest) -> InwardInterpretResponse:
    utterance = " ".join(request.utterance.split())
    source_kind = "voice_inward" if request.source_channel == "voice" else "text_inward"
    with connect() as connection:
        existing = connection.execute(
            "SELECT * FROM intake_proposals WHERE idempotency_key = ?", (request.idempotency_key,)
        ).fetchone()
        if existing:
            if existing["source_utterance"] != utterance or existing["source_kind"] != source_kind:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different inward proposal.")
            return InwardInterpretResponse(status="proposal", parsed_by=None, proposal=evaluate(connection, existing))

    result = parse_inward(utterance)  # may call the bounded LLM; runs outside any DB transaction
    if result.clarification or not result.items:
        return InwardInterpretResponse(
            status="clarification",
            message=result.clarification or "Please describe the items received.",
            parsed_by=result.parsed_by,
            proposal=None,
        )
    draft = DraftContent(
        supplier=DraftSupplier(label=result.supplier_text),
        lines=[DraftLine(
            line_id=new_line_id(),
            source_text=item.source_text,
            product_name_text=item.product_text,
            quantity=item.quantity,
            unit_text=item.unit_text,
        ) for item in result.items],
    )
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM intake_proposals WHERE idempotency_key = ?", (request.idempotency_key,)
        ).fetchone()
        if existing:
            return InwardInterpretResponse(status="proposal", parsed_by=None, proposal=evaluate(connection, existing))
        proposal_id = insert_proposal(
            connection,
            source_kind=source_kind,
            draft=draft,
            extraction=ExtractionView(provider=result.parsed_by, status="PARSED",
                                      message="Costs and payable are not taken from speech."),
            idempotency_key=request.idempotency_key,
            source_utterance=utterance,
            actor="parser",
        )
        return InwardInterpretResponse(status="proposal", parsed_by=result.parsed_by,
                                       proposal=evaluate(connection, load_row(connection, proposal_id)))
