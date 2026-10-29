"""Server-side, facts-only AI explanation with strict number validation and fallback."""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.domain.models import BriefExplanationResponse, BusinessFactsView

logger = logging.getLogger(__name__)

# Pattern to extract numbers (integers, floats, negative numbers, percentages, currency prefixes like ₹ or Rs)
NUMBER_REGEX = re.compile(r"[-+]?\d*\.?\d+")


def _get_api_key() -> str | None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key.strip().strip("\"'")

    # Fallback to local .env in Munim-AI root or backend directory
    possible_paths = [
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[3] / ".env",
        Path(".env"),
    ]
    for p in possible_paths:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY") and "=" in line:
                        _, val = line.split("=", 1)
                        clean_val = val.strip().strip("\"'")
                        if clean_val:
                            return clean_val
            except Exception:
                continue
    return None


def generate_deterministic_fallback(
    facts_view: BusinessFactsView, validation_errors: list[str] | None = None
) -> BriefExplanationResponse:
    """Deterministic, guaranteed facts-only summary when AI fails or output is invalid."""
    facts_by_id = {f.id: f for f in facts_view.facts}

    lines = []
    evidence_ids = []

    collections = facts_by_id.get("payment_collections")
    change = facts_by_id.get("collection_change_pct")
    if collections and collections.value is not None:
        evidence_ids.append("payment_collections")
        change_text = ""
        if change and change.value is not None:
            evidence_ids.append("collection_change_pct")
            sign = "+" if change.value > 0 else ""
            change_text = f" ({sign}{change.value}% change vs previous window)"
        lines.append(
            f"UPI collections for this window were ₹{collections.value:,.2f} across {collections.count} transactions{change_text}."
        )

    median_ticket = facts_by_id.get("median_ticket")
    if median_ticket and median_ticket.value is not None:
        evidence_ids.append("median_ticket")
        lines.append(f"Median payment amount was ₹{median_ticket.value:,.2f}.")

    lapsed = facts_by_id.get("lapsed_repeat_payers")
    if lapsed and lapsed.value is not None and lapsed.value > 0:
        evidence_ids.append("lapsed_repeat_payers")
        lines.append(
            f"{lapsed.value} previously frequent payer tokens were not observed during this 7-day window."
        )

    explanation = " ".join(lines)
    if not explanation:
        explanation = "Business facts summary based on recorded transaction data."

    proposed_action = (
        "Place a counter QR notice reminding repeat customers that digital payments are accepted."
    )
    action_type = "counter_notice"

    return BriefExplanationResponse(
        explanation=explanation,
        evidence_ids=evidence_ids,
        proposed_action=proposed_action,
        action_type=action_type,
        fallback_used=True,
        validation_errors=validation_errors or [],
    )


def _collect_allowed_numbers(facts_view: BusinessFactsView) -> set[float]:
    """Collect all valid numbers from facts (values, comparison values, counts)."""
    allowed = set()

    def add_num(val: Any) -> None:
        if val is None or isinstance(val, bool):
            return
        if isinstance(val, (int, float)):
            allowed.add(round(float(val), 2))
            allowed.add(round(abs(float(val)), 2))
            # Also add integer representation if close
            if abs(round(float(val)) - float(val)) < 0.001:
                allowed.add(float(round(val)))
        elif isinstance(val, str):
            for m in NUMBER_REGEX.findall(val):
                try:
                    num = float(m)
                    allowed.add(round(num, 2))
                    allowed.add(round(abs(num), 2))
                except ValueError:
                    pass

    for fact in facts_view.facts:
        add_num(fact.value)
        add_num(fact.comparison_value)
        add_num(fact.count)

    # Allow common small counts / window lengths explicitly present in schema (7, 28)
    allowed.update({7.0, 28.0})
    return allowed


def validate_explanation(
    output_data: dict[str, Any], facts_view: BusinessFactsView
) -> tuple[bool, list[str]]:
    """Strictly validate AI generated explanation against facts."""
    errors = []

    explanation = output_data.get("explanation")
    if not explanation or not isinstance(explanation, str):
        errors.append("Missing or invalid explanation field.")

    proposed_action = output_data.get("proposed_action")
    if not proposed_action or not isinstance(proposed_action, str):
        errors.append("Missing or invalid proposed_action field.")

    action_type = output_data.get("action_type")
    if action_type not in facts_view.allowed_actions:
        errors.append(f"Invalid action_type: {action_type}. Allowed: {facts_view.allowed_actions}")

    evidence_ids = output_data.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        errors.append("evidence_ids must be a list.")
    else:
        valid_fact_ids = {f.id for f in facts_view.facts}
        for eid in evidence_ids:
            if eid not in valid_fact_ids:
                errors.append(f"Invalid evidence_id cited: {eid}")

    # Forbid invented external causes
    prohibited_cause_words = [
        "weather", "rain", "holiday", "festival", "competitor", "construction",
        "traffic", "footfall", "roadblock", "power outage", "strike"
    ]
    full_text = f"{explanation} {proposed_action}".lower()
    for word in prohibited_cause_words:
        if word in full_text:
            errors.append(f"Prohibited invented cause detected: '{word}'.")

    # Validate numbers in explanation and proposed_action
    allowed_numbers = _collect_allowed_numbers(facts_view)
    found_numbers = NUMBER_REGEX.findall(f"{explanation} {proposed_action}")
    for num_str in found_numbers:
        try:
            num = round(float(num_str), 2)
            abs_num = abs(num)
            if num not in allowed_numbers and abs_num not in allowed_numbers:
                errors.append(f"Unauthorized number {num_str} not found in provided facts.")
        except ValueError:
            pass

    return len(errors) == 0, errors


def explain_business_facts(facts_view: BusinessFactsView) -> BriefExplanationResponse:
    """Generate facts-only explanation with Gemini or deterministic fallback."""
    api_key = _get_api_key()
    if not api_key:
        logger.warning("No GEMINI_API_KEY configured; using deterministic fallback.")
        return generate_deterministic_fallback(facts_view, ["No GEMINI_API_KEY found."])

    # Construct concise facts payload
    facts_payload = [
        {
            "id": f.id,
            "label": f.label,
            "value": f.value,
            "unit": f.unit,
            "count": f.count,
            "comparison_value": f.comparison_value,
            "comparison_period": f.comparison_period,
            "status": f.status,
        }
        for f in facts_view.facts
    ]

    system_instruction = (
        "You are an assistant for Indian kirana shopkeepers. Your job is to explain ONLY the verified "
        "business facts provided to you in simple, clear terms and propose ONE bounded action.\n"
        "STRICT CONSTRAINTS:\n"
        "1. NEVER calculate metrics, never perform arithmetic, never extrapolate, and NEVER invent numbers. Every single number you mention MUST appear in the facts.\n"
        "2. NEVER invent causes (do not mention footfall, weather, holidays, competitors, or external events).\n"
        "3. NEVER propose contacting customers individually or inferring identities.\n"
        "4. Your proposed action must be bounded and chosen from allowed actions: 'counter_notice' or 'qr_offer_mock'.\n"
        "5. Output valid JSON only with keys: 'explanation' (string, 2-3 sentences max), 'evidence_ids' (list of fact id strings), 'proposed_action' (string), 'action_type' ('counter_notice' or 'qr_offer_mock')."
    )

    prompt = (
        f"Verified Facts: {json.dumps(facts_payload, ensure_ascii=False)}\n"
        f"Allowed Actions: {facts_view.allowed_actions}\n"
        "Generate the concise, strictly facts-only explanation and one bounded action in the specified JSON format."
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\n{prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))

        raw_text = resp_body["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Clean any potential markdown code fence
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

        parsed = json.loads(raw_text)
        is_valid, validation_errors = validate_explanation(parsed, facts_view)

        if is_valid:
            return BriefExplanationResponse(
                explanation=parsed["explanation"],
                evidence_ids=parsed.get("evidence_ids", []),
                proposed_action=parsed["proposed_action"],
                action_type=parsed["action_type"],
                fallback_used=False,
                validation_errors=[],
            )
        else:
            logger.warning("AI explanation failed validation: %s", validation_errors)
            return generate_deterministic_fallback(facts_view, validation_errors)

    except Exception as e:
        logger.exception("Error calling Gemini API for brief explanation: %s", e)
        return generate_deterministic_fallback(facts_view, [f"AI call failed: {str(e)}"])

