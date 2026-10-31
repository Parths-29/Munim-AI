"""Voice-first merchant agent: interpret → resolve → answer or propose → explicit confirm (atomic).

* Interpretation: Gemini first (structured plan, verbatim spans), deterministic Hinglish parser as fallback.
* Resolution (application code only): customer/product aliases with honorific and spoken-variant
  normalization; ambiguity → choices; amounts → integer paise deterministically.
* Context: short, per-session, per-shop memory of the last customer/action (10 minutes). Reuse is shown
  as an inference. Never crosses shops or stale sessions.
* Writes: a stored proposal; POST /agent/proposals/{id}/confirm applies every action in one transaction.
"""

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.domain.agent import (
    AgentAnswer,
    AgentConfirm,
    AgentConfirmResult,
    AgentHealth,
    AgentProposal,
    AgentTurnRequest,
    AgentTurnResponse,
    AppliedAction,
    ChoiceOption,
    Clarification,
    ProposedAction,
    ProviderStatus,
    TranscriptView,
)
from app.domain.models import LedgerWrite
from app.domain.stock import OutflowBatchWrite, OutflowLine
from app.services import agent_llm, agent_parse
from app.services.agent_language import strip_wake
from app.services.agent_parse import Draft
from app.services.database import connect, current_shop
from app.services.ledger import insert_customer_in, normalize_alias, post_entry_in
from app.services.units import canonical_unit

SESSION_TTL = timedelta(minutes=30)
CONTEXT_TTL = timedelta(minutes=10)
PROPOSAL_TTL = timedelta(minutes=15)
HONORIFICS = {
    "bhai", "bhaiya", "bhaiyya", "bhaiyaa", "ji", "jee", "saab", "sahab", "saheb", "seth", "sethji", "didi", "di", "behen",
    "bahen", "ben", "bhabhi", "aunty", "auntie", "uncle", "chacha", "chachi", "kaka", "kaki", "mama", "mami", "mausi", "dada",
    "dadi", "nana", "nani", "anna", "akka", "mr", "mrs", "ms", "shri", "shree", "smt", "sir", "madam", "bhau", "tai",
}
POSTPOSITIONS = {"ka", "ki", "ke", "ko", "ne", "se", "wala", "wali", "wale"}
WRITE_KINDS = ("customer_create", "credit", "repayment", "sale")
READ_KINDS = ("balance", "stock_check", "payment_summary", "timeline_summary")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _rupees(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    paise = abs(paise)
    return f"{sign}₹{paise // 100:,}" + (f".{paise % 100:02d}" if paise % 100 else "")


# --- Name resolution -------------------------------------------------------------

def name_core(value: str) -> str:
    words = [w for w in normalize_alias(re.sub(r"[.,!?]", " ", value)).split() if w not in HONORIFICS and w not in POSTPOSITIONS]
    return " ".join(words)


def spoken_key(value: str) -> str:
    """Collapse common spoken/STT spelling variants: Raaju/Raju, Meenaa/Meena, Iqbaal/Iqbal."""
    text = name_core(value)
    for a, b in (("aa", "a"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"), ("ph", "f"), ("w", "v"), ("z", "j")):
        text = text.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", text)


def _entities(connection, kind: str) -> list[dict]:
    if kind == "customer":
        rows = connection.execute(
            """SELECT c.customer_id AS id, c.display_name AS name, a.alias AS alias FROM customers c
               LEFT JOIN customer_aliases a ON a.shop_id = c.shop_id AND a.customer_id = c.customer_id WHERE c.shop_id = ?""",
            (current_shop(),),
        ).fetchall()
    else:
        rows = connection.execute(
            """SELECT p.product_id AS id, p.name AS name, a.alias AS alias FROM products p
               LEFT JOIN product_aliases a ON a.shop_id = p.shop_id AND a.product_id = p.product_id WHERE p.shop_id = ?""",
            (current_shop(),),
        ).fetchall()
    found: dict[str, dict] = {}
    for row in rows:
        entry = found.setdefault(row["id"], {"id": row["id"], "name": row["name"], "aliases": {row["name"]}})
        if row["alias"]:
            entry["aliases"].add(row["alias"])
    return list(found.values())


def resolve_name(connection, kind: str, text: str) -> tuple[str, list[dict], str]:
    """Returns (status, matches, how). status: RESOLVED | AMBIGUOUS | NOT_FOUND. how: exact | honorific | spoken_variant | similar."""
    items = _entities(connection, kind)
    query = normalize_alias(text)
    tiers = (
        ("exact", lambda alias: normalize_alias(alias) == query),
        ("honorific", lambda alias: bool(name_core(text)) and name_core(alias) == name_core(text)),
        ("spoken_variant", lambda alias: bool(spoken_key(text)) and spoken_key(alias) == spoken_key(text)),
    )
    for how, test in tiers:
        matches = [item for item in items if any(test(alias) for alias in item["aliases"])]
        if matches:
            return ("RESOLVED" if len(matches) == 1 else "AMBIGUOUS"), sorted(matches, key=lambda m: m["name"]), how
    words = set(name_core(text).split())
    similar = [item for item in items if words and any(words & set(name_core(alias).split()) for alias in item["aliases"])]
    return "NOT_FOUND", sorted(similar, key=lambda m: m["name"])[:6], "similar"


def _balance(connection, customer_id: str) -> int:
    return int(connection.execute(
        """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise WHEN 'REPAYMENT' THEN -amount_paise END), 0)
           FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
        (current_shop(), customer_id),
    ).fetchone()[0])


def _customer_name(connection, customer_id: str) -> str:
    return connection.execute("SELECT display_name FROM customers WHERE shop_id = ? AND customer_id = ?",
                              (current_shop(), customer_id)).fetchone()[0]


# --- Sessions and context ---------------------------------------------------------

def _load_session(connection, session_id: str | None) -> sqlite3.Row:
    moment = now_utc()
    if session_id:
        row = connection.execute("SELECT * FROM agent_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row and row["shop_id"] == current_shop() and moment - datetime.fromisoformat(row["updated_at"]) < SESSION_TTL:
            return row
    new_id = f"agent_{uuid.uuid4().hex[:16]}"
    connection.execute(
        """INSERT INTO agent_sessions (session_id, shop_id, language_code, pending_json, context_json, turn_count, created_at, updated_at)
           VALUES (?, ?, 'hi-IN', NULL, '{}', 0, ?, ?)""",
        (new_id, current_shop(), moment.isoformat(), moment.isoformat()),
    )
    return connection.execute("SELECT * FROM agent_sessions WHERE session_id = ?", (new_id,)).fetchone()


def _context(session: sqlite3.Row) -> dict:
    data = json.loads(session["context_json"] or "{}")
    last = data.get("last")
    if last and now_utc() - datetime.fromisoformat(last["at"]) > CONTEXT_TTL:
        data.pop("last", None)
    return data


def _save_session(connection, session_id: str, context: dict, pending: dict | None, turn_index: int) -> None:
    connection.execute(
        "UPDATE agent_sessions SET context_json = ?, pending_json = ?, turn_count = ?, updated_at = ? WHERE session_id = ?",
        (json.dumps(context, ensure_ascii=False), json.dumps(pending, ensure_ascii=False) if pending else None, turn_index,
         now_utc().isoformat(), session_id),
    )


def _remember(context: dict, customer_id: str | None, customer_name: str | None, action: str | None) -> None:
    if customer_id or action:
        previous = context.get("last") or {}
        context["last"] = {
            "customer_id": customer_id or previous.get("customer_id"),
            "customer_name": customer_name or previous.get("customer_name"),
            "action": action if action in ("credit", "repayment") else previous.get("action"),
            "at": now_utc().isoformat(),
        }


def _context_lines(connection, context: dict) -> list[str]:
    lines = []
    last = context.get("last")
    if last and last.get("customer_name"):
        lines.append(f"Previous turn was about customer '{last['customer_name']}'" + (f", action {last['action']}" if last.get("action") else "") + ".")
    if context.get("proposal_id"):
        row = connection.execute("SELECT actions_json, status FROM agent_proposals WHERE proposal_id = ?", (context["proposal_id"],)).fetchone()
        if row and row["status"] == "PENDING":
            lines.append("A proposal is waiting for confirmation: " + "; ".join(a["summary"] for a in json.loads(row["actions_json"])))
    return lines


# --- Building answers, proposals, and clarifications --------------------------------

class Ask(Exception):
    def __init__(self, clarification: Clarification):
        self.clarification = clarification


def _uncertain_question(draft: Draft, index: int, what: str = "amount") -> Clarification:
    word, candidates = draft.uncertain_numbers[0]
    options = [ChoiceOption(option_id=str(value * 100 if what == "amount" else value),
                            label=f"{name} = {_rupees(value * 100) if what == 'amount' else value}") for name, value in candidates]
    return Clarification(question=f"Did you mean {' or '.join(f'{n} ({v})' for n, v in candidates)} for “{word}”? I did not use it as a number.",
                         missing=[what], slot_id=f"{what}:{index}", choices=options)


def _action_question(index: int, who: str | None, amount: int | None) -> Clarification:
    detail = " ".join(part for part in (f"for {who}" if who else None, _rupees(amount) if amount else None) if part)
    return Clarification(
        question=f"Is this udhaar (credit given) or jama (payment received){' ' + detail if detail else ''}?",
        missing=["action"], slot_id=f"action:{index}",
        choices=[ChoiceOption(option_id="credit", label="Udhaar (credit given)"),
                 ChoiceOption(option_id="repayment", label="Jama (payment received)")],
    )


def _missing_question(draft: Draft) -> Clarification:
    missing = []
    if not draft.customer_text and not draft.pronoun_ref:
        missing.append("customer")
    if draft.kind is None:
        missing.append("action")
    if draft.amount_paise is None:
        missing.append("amount")
    phrases = {"customer": "which customer it is for", "action": "whether it is udhaar (credit given) or jama (payment received)",
               "amount": "the amount in rupees"}
    listed = [phrases[m] for m in missing] or ["what you would like to do"]
    text = listed[0] if len(listed) == 1 else ", ".join(listed[:-1]) + " and " + listed[-1]
    return Clarification(question=f"Please tell me {text}. For example: “Raju ko paanch sau udhaar likho”.", missing=missing)


def _resolve_customer(connection, drafts: list[Draft], index: int, context: dict, allow_create: bool) -> None:
    draft = drafts[index]
    if draft.customer_id or draft.create_ref is not None:
        return
    if draft.pronoun_ref and not draft.customer_text:
        for earlier in range(index - 1, -1, -1):  # "uske" → the customer of an earlier action in this same turn
            if drafts[earlier].kind == "customer_create":
                draft.create_ref = earlier
                return
            if drafts[earlier].customer_id:
                draft.customer_id = drafts[earlier].customer_id
                return
    last = context.get("last") or {}
    if not draft.customer_text:
        if (draft.pronoun_ref or draft.continuation) and last.get("customer_id"):
            draft.customer_id = last["customer_id"]
            draft.inferred.append(f"customer: {last['customer_name']} (from your previous request)")
            return
        choices = ([ChoiceOption(option_id=last["customer_id"], label=last["customer_name"], detail="from your previous request")]
                   if last.get("customer_id") else [])
        raise Ask(Clarification(question="Which customer is this for? I only reuse the previous customer when you say “uske” or “aur”.",
                                missing=["customer"], slot_id=f"customer:{index}", choices=choices))
    status, matches, how = resolve_name(connection, "customer", draft.customer_text)
    if status == "RESOLVED":
        draft.customer_id = matches[0]["id"]
        if how == "spoken_variant":
            draft.inferred.append(f"customer: heard “{draft.customer_text}”, matched {matches[0]['name']}")
        return
    if status == "AMBIGUOUS":
        raise Ask(Clarification(question=f"More than one customer matches “{draft.customer_text}”. Which one?", missing=["customer"],
                                slot_id=f"customer:{index}",
                                choices=[ChoiceOption(option_id=m["id"], label=m["name"]) for m in matches]))
    options = [ChoiceOption(option_id=m["id"], label=m["name"], detail="existing customer") for m in matches]
    if allow_create:
        options.append(ChoiceOption(option_id="new", label=f"New customer “{draft.customer_text}”", detail="create, then record"))
    raise Ask(Clarification(question=(f"No customer is named exactly “{draft.customer_text}”." + (" Did you mean one of these, or is this a new customer?" if matches and allow_create
                                      else " Did you mean one of these?" if matches else " Create a new customer?" if allow_create else "")),
                            missing=["customer"], slot_id=f"customer:{index}", choices=options))


def _resolve_product(connection, draft: Draft, index: int) -> None:
    if draft.product_id:
        return
    if not draft.product_text:
        raise Ask(Clarification(question="Which product?", missing=["product"]))
    status, matches, _ = resolve_name(connection, "product", draft.product_text)
    if status == "RESOLVED":
        draft.product_id = matches[0]["id"]
        return
    question = (f"More than one product matches “{draft.product_text}”. Which one?" if status == "AMBIGUOUS"
                else f"No product is named exactly “{draft.product_text}”. Did you mean one of these?" if matches
                else f"I could not find a product called “{draft.product_text}”. Add it in Inventory first, or say its exact name.")
    raise Ask(Clarification(question=question, missing=["product"],
                            slot_id=f"product:{index}" if matches else None,
                            choices=[ChoiceOption(option_id=m["id"], label=m["name"]) for m in matches]))


def _resolve(connection, drafts: list[Draft], context: dict) -> None:
    """Fill IDs, actions, and amounts in place, or raise Ask with one targeted question."""
    last = context.get("last") or {}
    for index, draft in enumerate(drafts):
        if draft.kind is None or draft.kind == "conflict":
            money_like = draft.amount_paise is not None or draft.generic_write or "GAVE_TO_CUSTOMER" in draft.issues
            if draft.kind is None and draft.continuation and last.get("action") in ("credit", "repayment") and draft.amount_paise:
                draft.kind = last["action"]
                draft.inferred.append(f"action: {'udhaar' if draft.kind == 'credit' else 'jama'} (from your previous request)")
            elif draft.uncertain_numbers and draft.amount_paise is None:
                raise Ask(_uncertain_question(draft, index))
            elif money_like and draft.amount_paise is not None or draft.kind == "conflict" or "GAVE_TO_CUSTOMER" in draft.issues:
                who = draft.customer_text or (last.get("customer_name") if (draft.pronoun_ref or draft.continuation) else None)
                raise Ask(_action_question(index, who, draft.amount_paise))
            else:
                raise Ask(_missing_question(draft))
        if draft.kind == "customer_create":
            if not draft.customer_text:
                raise Ask(Clarification(question="What is the new customer's name?", missing=["customer"]))
            if not draft.new_customer_ok:
                status, matches, how = resolve_name(connection, "customer", draft.customer_text)
                if status != "NOT_FOUND":
                    raise Ask(Clarification(
                        question=f"A customer like “{draft.customer_text}” already exists. Use the existing customer, or create a new one?",
                        missing=["customer"], slot_id=f"create:{index}",
                        choices=[ChoiceOption(option_id=m["id"], label=m["name"], detail="use existing") for m in matches]
                        + [ChoiceOption(option_id="new", label=f"Create new “{draft.customer_text}”")]))
        elif draft.kind in ("credit", "repayment"):
            if "AMBIGUOUS_AMOUNT" in draft.issues:
                raise Ask(Clarification(question="I heard more than one amount. Which single amount should I record?", missing=["amount"]))
            if "QUANTITY_NOT_MONEY" in draft.issues and draft.amount_paise is None:
                raise Ask(Clarification(question=f"“{draft.quantity_text}” is a quantity, not rupees. What is the rupee amount?", missing=["amount"]))
            if draft.amount_paise is None:
                if draft.uncertain_numbers:
                    raise Ask(_uncertain_question(draft, index))
                who = draft.customer_text or (last.get("customer_name") if draft.pronoun_ref else None)
                raise Ask(Clarification(question=f"How much {'udhaar' if draft.kind == 'credit' else 'jama'}{' for ' + who if who else ''}? Say the amount in rupees.",
                                        missing=["amount"]))
            _resolve_customer(connection, drafts, index, context, allow_create=draft.kind == "credit")
        elif draft.kind == "balance":
            _resolve_customer(connection, drafts, index, context, allow_create=False)
        elif draft.kind == "sale":
            _resolve_product(connection, draft, index)
            if draft.quantity is None:
                if draft.uncertain_numbers:
                    raise Ask(_uncertain_question(draft, index, "quantity"))
                raise Ask(Clarification(question="How many were sold?", missing=["quantity"]))
        elif draft.kind == "stock_check":
            _resolve_product(connection, draft, index)


def _apply_choice(drafts: list[Draft], slot: str, option: str) -> None:
    kind, _, raw_index = slot.partition(":")
    if not raw_index.isdigit() or int(raw_index) >= len(drafts):
        raise HTTPException(status_code=409, detail={"code": "CHOICE_EXPIRED", "message": "That question is no longer open. Please say the request again."})
    index = int(raw_index)
    draft = drafts[index]
    if kind == "action" and option in ("credit", "repayment"):
        draft.kind, draft.issues = option, [i for i in draft.issues if i != "GAVE_TO_CUSTOMER"]
    elif kind == "amount" and option.isdigit():
        draft.amount_paise, draft.uncertain_numbers = int(option), []
        draft.amount_text = draft.amount_text or _rupees(int(option))
    elif kind == "quantity" and option.isdigit():
        draft.quantity, draft.uncertain_numbers = int(option), []
    elif kind == "product":
        draft.product_id = option
    elif kind == "customer" and option == "new":
        drafts.insert(index, Draft(kind="customer_create", customer_text=draft.customer_text, new_customer_ok=True))
        for later in drafts[index + 1:]:
            if later.create_ref is not None and later.create_ref >= index:
                later.create_ref += 1
        drafts[index + 1].create_ref = index
    elif kind == "customer":
        draft.customer_id = option
    elif kind == "create" and option == "new":
        draft.new_customer_ok = True
    elif kind == "create":
        drafts.pop(index)
        for later in drafts:
            if later.create_ref == index:
                later.customer_id, later.create_ref = option, None
            elif later.create_ref is not None and later.create_ref > index:
                later.create_ref -= 1
    else:
        raise HTTPException(status_code=422, detail={"code": "INVALID_CHOICE"})


def _build_actions(connection, drafts: list[Draft]) -> tuple[list[ProposedAction], list[AgentAnswer], list[str]]:
    actions: list[ProposedAction] = []
    answers: list[AgentAnswer] = []
    created_names: dict[int, str] = {}
    action_index: dict[int, int] = {}
    pending_delta: dict[str, int] = {}
    for index, draft in enumerate(drafts):
        if draft.kind == "customer_create":
            created_names[index] = draft.customer_text.strip()
            action_index[index] = len(actions)
            actions.append(ProposedAction(index=len(actions), kind="customer_create", customer_name=created_names[index],
                                          summary=f"Create customer “{created_names[index]}” (no balance yet)", inferred=draft.inferred))
        elif draft.kind in ("credit", "repayment"):
            if draft.create_ref is not None:
                name, customer_id, before = created_names[draft.create_ref], None, 0
            else:
                customer_id = draft.customer_id
                name = _customer_name(connection, customer_id)
                before = _balance(connection, customer_id) + pending_delta.get(customer_id, 0)
            delta = draft.amount_paise if draft.kind == "credit" else -draft.amount_paise
            if draft.kind == "repayment" and draft.amount_paise > before:
                raise Ask(Clarification(question=f"{name} owes {_rupees(before)}, so a jama of {_rupees(draft.amount_paise)} is more than the balance. What amount was paid?",
                                        missing=["amount"]))
            if customer_id:
                pending_delta[customer_id] = pending_delta.get(customer_id, 0) + delta
            label = "Udhaar (credit)" if draft.kind == "credit" else "Jama (repayment)"
            actions.append(ProposedAction(
                index=len(actions), kind=draft.kind, customer_id=customer_id, customer_name=name,
                creates_customer_ref=action_index.get(draft.create_ref) if draft.create_ref is not None else None,
                amount_paise=draft.amount_paise, amount_text=draft.amount_text, balance_before_paise=before, balance_after_paise=before + delta,
                summary=f"{label} {_rupees(draft.amount_paise)} for {name}: balance {_rupees(before)} → {_rupees(before + delta)}",
                inferred=draft.inferred,
            ))
        elif draft.kind == "sale":
            from app.services.inventory import on_hand_quantity
            from app.services.proposals import stored_conversion
            from app.services.stock import latest_profile

            product = connection.execute("SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?",
                                         (current_shop(), draft.product_id)).fetchone()
            unit = canonical_unit(draft.unit_text) or canonical_unit(product["unit"]) or product["unit"]
            factor = 1 if unit == (canonical_unit(product["unit"]) or product["unit"]) else stored_conversion(connection, product["product_id"], unit)
            if factor is None:
                raise Ask(Clarification(question=f"How many {product['unit']} are in one {unit} of {product['name']}? Save that unit conversion first, or say the quantity in {product['unit']}.",
                                        missing=["unit"]))
            before = on_hand_quantity(connection, product["product_id"])[0] + pending_delta.get(product["product_id"], 0)
            base = draft.quantity * factor
            if base > before:
                raise Ask(Clarification(question=f"Records show only {before} {product['unit']} of {product['name']}. Count the shelf first, or say a smaller quantity.",
                                        missing=["quantity"]))
            pending_delta[product["product_id"]] = pending_delta.get(product["product_id"], 0) - base
            profile = latest_profile(connection, product["product_id"])
            price = profile["retail_price_paise"] if profile and profile["retail_price_paise"] is not None else None
            value = f", about {_rupees(price * base)}" if price is not None else ""
            actions.append(ProposedAction(
                index=len(actions), kind="sale", product_id=product["product_id"], product_name=product["name"], quantity=draft.quantity,
                unit=unit, on_hand_before=before, on_hand_after=before - base,
                summary=f"Sale: {draft.quantity} {unit} {product['name']}{value}; stock {before} → {before - base} {product['unit']}",
                inferred=draft.inferred,
            ))
        elif draft.kind == "balance":
            balance = _balance(connection, draft.customer_id)
            answers.append(AgentAnswer(kind="balance", customer_id=draft.customer_id, customer_name=_customer_name(connection, draft.customer_id),
                                       balance_due_paise=balance, notes=draft.inferred))
        elif draft.kind == "stock_check":
            from app.services.inventory import on_hand_quantity

            product = connection.execute("SELECT name, unit FROM products WHERE shop_id = ? AND product_id = ?",
                                         (current_shop(), draft.product_id)).fetchone()
            answers.append(AgentAnswer(kind="stock_check", product_id=draft.product_id, product_name=product["name"],
                                       on_hand_quantity=on_hand_quantity(connection, draft.product_id)[0], unit=product["unit"],
                                       notes=["Recorded stock from counts, deliveries, and sales; not a live shelf sensor."]))
        elif draft.kind in ("payment_summary", "timeline_summary"):
            answers.append(AgentAnswer(kind=draft.kind))
    notes = [note for action in actions for note in action.inferred]
    return actions, answers, notes


def _answer_text(answer: AgentAnswer) -> str:
    if answer.kind == "balance":
        return f"{answer.customer_name} owes {_rupees(answer.balance_due_paise)}."
    if answer.kind == "stock_check":
        return f"{answer.product_name}: {answer.on_hand_quantity} {answer.unit} recorded."
    return "Opening the payment summary." if answer.kind == "payment_summary" else "Opening today's shop activity."


def _store_proposal(connection, session_id: str, context: dict, actions: list[ProposedAction], utterance: str, channel: str) -> AgentProposal:
    moment = now_utc()
    if context.get("proposal_id"):
        connection.execute("UPDATE agent_proposals SET status = 'SUPERSEDED', updated_at = ? WHERE proposal_id = ? AND status = 'PENDING'",
                           (moment.isoformat(), context["proposal_id"]))
    payload = [action.model_dump() for action in actions]
    content_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
    proposal_id = f"aprop_{uuid.uuid4().hex[:16]}"
    expires = moment + PROPOSAL_TTL
    connection.execute(
        """INSERT INTO agent_proposals (proposal_id, session_id, shop_id, status, actions_json, content_hash, source_utterance,
           source_channel, created_at, expires_at, updated_at) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)""",
        (proposal_id, session_id, current_shop(), json.dumps(payload, ensure_ascii=False), content_hash, utterance[:400], channel,
         moment.isoformat(), expires.isoformat(), moment.isoformat()),
    )
    context["proposal_id"] = proposal_id
    return AgentProposal(proposal_id=proposal_id, content_hash=content_hash, actions=actions,
                         inferred_notes=[n for a in actions for n in a.inferred], expires_at=expires)


def _log_turn(connection, session_id: str, turn_index: int, channel: str, text: str, wake: bool, intent: str | None,
              status: str, reply: str, parsed_by: str) -> None:
    connection.execute(
        """INSERT INTO agent_turns (turn_id, session_id, shop_id, turn_index, source_channel, user_text, wake_detected, intent, status,
           reply_text, language_code, parsed_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'hi-IN', ?, ?)""",
        (f"aturn_{uuid.uuid4().hex[:16]}", session_id, current_shop(), turn_index, channel, text[:400] or "(empty)", int(wake),
         intent, status, reply[:1000], parsed_by, now_utc().isoformat()),
    )


def _amount_correction(connection, context: dict, parsed: agent_parse.Parsed) -> list[Draft] | None:
    """'nahi, 600' / '600 kar do' while a single-amount proposal is pending → the same proposal with the new amount."""
    if not context.get("proposal_id") or len(parsed.drafts) != 1:
        return None
    draft = parsed.drafts[0]
    if draft.amount_paise is None or draft.customer_text or draft.kind not in (None,) or draft.pronoun_ref:
        return None
    if not re.search(r"\b(?:nahi|nahin|galat|wrong|sorry|actually|matlab|kar\s+do|karo|correct)\b", parsed.text.lower()) and draft.generic_write:
        return None
    row = connection.execute("SELECT actions_json, status FROM agent_proposals WHERE proposal_id = ?", (context["proposal_id"],)).fetchone()
    if not row or row["status"] != "PENDING":
        return None
    actions = json.loads(row["actions_json"])
    money = [a for a in actions if a["kind"] in ("credit", "repayment")]
    if len(actions) != 1 or len(money) != 1 or not money[0]["customer_id"]:
        return None
    action = money[0]
    return [Draft(kind=action["kind"], customer_id=action["customer_id"], amount_paise=draft.amount_paise, amount_text=draft.amount_text,
                  inferred=[f"amount corrected from {_rupees(action['amount_paise'])} to {_rupees(draft.amount_paise)}"])]


def turn(request: AgentTurnRequest) -> AgentTurnResponse:
    utterance = (request.utterance or "").strip()
    if not utterance and request.choice is None:
        raise HTTPException(status_code=422, detail="Say or type a request first.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        session = _load_session(connection, request.session_id)
        session_id, turn_index = session["session_id"], session["turn_count"] + 1
        context = _context(session)
        pending = json.loads(session["pending_json"]) if session["pending_json"] else None
        llm = ProviderStatus(status="disabled", detail="Not needed for this turn.")
        transcript = TranscriptView(original=request.transcript_original, used=utterance or (pending or {}).get("utterance", ""))
        interpreted_by = "deterministic"
        wake = False
        drafts: list[Draft] | None = None

        def finish(status: str, message: str, **extra) -> AgentTurnResponse:
            intent = next((d.kind for d in (drafts or []) if d.kind), None)
            _log_turn(connection, session_id, turn_index, request.source_channel,
                      utterance or f"[choice {request.choice.slot_id}={request.choice.option_id}]" if request.choice else utterance,
                      wake, intent, status, message, interpreted_by)
            new_pending = extra.pop("_pending", None)
            _save_session(connection, session_id, context, new_pending, turn_index)
            return AgentTurnResponse(session_id=session_id, turn_index=turn_index, status=status, message=message,
                                     interpreted_by=interpreted_by, llm=llm, transcript=transcript, **extra)

        if request.choice is not None:
            if not pending:
                raise HTTPException(status_code=409, detail={"code": "CHOICE_EXPIRED", "message": "That question is no longer open. Please say the request again."})
            drafts = [Draft(**d) for d in pending["drafts"]]
            _apply_choice(drafts, request.choice.slot_id, request.choice.option_id)
            utterance_for_record = pending["utterance"]
            interpreted_by = "choice"
        else:
            utterance_for_record = utterance
            _, wake = strip_wake(utterance)
            parsed = agent_parse.parse(utterance)
            if parsed.control == "cancel":
                if context.get("proposal_id"):
                    connection.execute("UPDATE agent_proposals SET status = 'CANCELLED', updated_at = ? WHERE proposal_id = ? AND status = 'PENDING'",
                                       (now_utc().isoformat(), context.pop("proposal_id")))
                    return finish("cancelled", "Cancelled. Nothing was saved.")
                return finish("info", "There is nothing waiting to cancel." if not pending else "Okay, I dropped that question.")
            if parsed.control == "affirm":
                return finish("info", "Please tap Confirm to save. I do not save on a spoken yes." if context.get("proposal_id")
                              else "Okay. What would you like to record or check?")
            drafts = _amount_correction(connection, context, parsed)
            if drafts is not None:
                interpreted_by = "context"
            else:
                customers = [e["name"] for e in _entities(connection, "customer")]
                products = [e["name"] for e in _entities(connection, "product")]
                llm, data = agent_llm.interpret(utterance, _context_lines(connection, context), customers, products)
                model_drafts = None
                if data is not None:
                    model_drafts, corrected, question = agent_llm.to_drafts(utterance, data)
                    if model_drafts is None:
                        llm = agent_llm.provider_status("invalid_output")
                    else:
                        transcript.model_corrected = corrected
                        if any(d.kind == "cancel" for d in model_drafts) and context.get("proposal_id"):
                            connection.execute("UPDATE agent_proposals SET status = 'CANCELLED', updated_at = ? WHERE proposal_id = ? AND status = 'PENDING'",
                                               (now_utc().isoformat(), context.pop("proposal_id")))
                            interpreted_by = "gemini"
                            return finish("cancelled", "Cancelled. Nothing was saved.")
                        model_drafts = [d for d in model_drafts if d.kind not in ("cancel", "confirm")] or None
                        # A deterministic credit/repayment reading that disagrees with the model → ask, never pick.
                        det_kinds = {d.kind for d in parsed.drafts if d.kind in ("credit", "repayment")}
                        model_kinds = {d.kind for d in (model_drafts or []) if d.kind in ("credit", "repayment")}
                        if det_kinds and model_kinds and det_kinds != model_kinds:
                            for d in model_drafts:
                                if d.kind in ("credit", "repayment"):
                                    d.kind = "conflict"
                if model_drafts:
                    drafts, interpreted_by = model_drafts, "gemini"
                else:
                    drafts = parsed.drafts
        try:
            _resolve(connection, drafts, context)
            actions, answers, notes = _build_actions(connection, drafts)
        except Ask as ask:
            pending_state = {"drafts": [asdict(d) for d in drafts], "utterance": utterance_for_record}
            return finish("clarification", ask.clarification.question, clarification=ask.clarification,
                          _pending=pending_state if ask.clarification.slot_id else None)
        read_text = " ".join(_answer_text(a) for a in answers)
        last_customer = next((d.customer_id for d in reversed(drafts) if d.customer_id), None)
        last_action = next((d.kind for d in reversed(drafts) if d.kind in ("credit", "repayment")), None)
        _remember(context, last_customer, _customer_name(connection, last_customer) if last_customer else None, last_action)
        if not actions:
            return finish("answer", read_text or "Done.", answer=answers[0] if answers else None)
        proposal = _store_proposal(connection, session_id, context, actions, utterance_for_record, request.source_channel)
        message = (read_text + " " if read_text else "") + "Please review and confirm: " + "; ".join(a.summary for a in actions) + "."
        if notes:
            message += " I inferred: " + "; ".join(notes) + "."
        return finish("proposal", message, proposal=proposal, answer=answers[0] if answers else None)


def cancel(proposal_id: str) -> dict:
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT status FROM agent_proposals WHERE proposal_id = ? AND shop_id = ?", (proposal_id, current_shop())).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found in this shop.")
        if row["status"] == "PENDING":
            connection.execute("UPDATE agent_proposals SET status = 'CANCELLED', updated_at = ? WHERE proposal_id = ?", (now_utc().isoformat(), proposal_id))
        return {"proposal_id": proposal_id, "status": "CANCELLED" if row["status"] == "PENDING" else row["status"]}


def confirm(proposal_id: str, request: AgentConfirm) -> AgentConfirmResult:
    """Apply every action of the proposal in ONE transaction. Any failure rolls all of it back."""
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Explicit merchant confirmation is required.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM agent_proposals WHERE proposal_id = ? AND shop_id = ?", (proposal_id, current_shop())).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Proposal not found in this shop.")
        if row["status"] == "APPLIED":
            if row["confirm_idempotency_key"] == request.idempotency_key:
                return AgentConfirmResult(proposal_id=proposal_id, applied=[AppliedAction(**a) for a in json.loads(row["result_json"])],
                                          idempotent_replay=True)
            raise HTTPException(status_code=409, detail={"code": "ALREADY_APPLIED"})
        if row["status"] != "PENDING":
            raise HTTPException(status_code=409, detail={"code": f"PROPOSAL_{row['status']}"})
        if now_utc() > datetime.fromisoformat(row["expires_at"]):
            raise HTTPException(status_code=409, detail={"code": "PROPOSAL_EXPIRED", "message": "This proposal expired. Please say it again."})
        if request.content_hash != row["content_hash"]:
            raise HTTPException(status_code=409, detail={"code": "PROPOSAL_CHANGED", "message": "The proposal changed. Review it again."})
        actions = [ProposedAction(**a) for a in json.loads(row["actions_json"])]
        channel = "voice" if row["source_channel"] == "voice" else "text"
        utterance = row["source_utterance"][:240]
        created: dict[int, str] = {}
        applied: list[AppliedAction] = []
        for action in actions:
            key = f"agent:{proposal_id}:{action.index}"
            if action.kind == "customer_create":
                created[action.index] = insert_customer_in(connection, action.customer_name, [action.customer_name], key, channel, utterance)
                applied.append(AppliedAction(index=action.index, kind=action.kind, entity_id=created[action.index], summary=action.summary))
            elif action.kind in ("credit", "repayment"):
                customer_id = action.customer_id or created[action.creates_customer_ref]
                entry = post_entry_in(connection, LedgerWrite(
                    customer_id=customer_id, amount_paise=action.amount_paise, source_event_id=key, idempotency_key=key,
                    confirmed=True, source_utterance=utterance, source_channel=channel,
                ), "CREDIT" if action.kind == "credit" else "REPAYMENT")
                applied.append(AppliedAction(index=action.index, kind=action.kind, entity_id=entry.entry_id, summary=action.summary))
            elif action.kind == "sale":
                from app.services.stock import record_outflows_in

                batch = record_outflows_in(connection, OutflowBatchWrite(
                    reason="SALE", lines=[OutflowLine(product_id=action.product_id, quantity=action.quantity, unit_text=action.unit)],
                    confirmed=True, idempotency_key=key, source_channel=channel, source_utterance=utterance,
                ), now_utc())
                applied.append(AppliedAction(index=action.index, kind=action.kind, entity_id=batch.batch_id, summary=action.summary))
        connection.execute(
            "UPDATE agent_proposals SET status = 'APPLIED', confirm_idempotency_key = ?, result_json = ?, updated_at = ? WHERE proposal_id = ?",
            (request.idempotency_key, json.dumps([a.model_dump() for a in applied], ensure_ascii=False), now_utc().isoformat(), proposal_id),
        )
        session = connection.execute("SELECT context_json FROM agent_sessions WHERE session_id = ?", (row["session_id"],)).fetchone()
        context = json.loads(session["context_json"] or "{}")
        if context.get("proposal_id") == proposal_id:
            context.pop("proposal_id")
        last_money = next((a for a in reversed(actions) if a.kind in ("credit", "repayment")), None)
        if last_money:
            customer_id = last_money.customer_id or created.get(last_money.creates_customer_ref)
            _remember(context, customer_id, last_money.customer_name, last_money.kind)
        connection.execute("UPDATE agent_sessions SET context_json = ?, updated_at = ? WHERE session_id = ?",
                           (json.dumps(context, ensure_ascii=False), now_utc().isoformat(), row["session_id"]))
        return AgentConfirmResult(proposal_id=proposal_id, applied=applied)


def health(force: bool = False) -> AgentHealth:
    return AgentHealth(llm=agent_llm.health_check(force), model=agent_llm.model_name(), key_configured=agent_llm._get_api_key() is not None)
