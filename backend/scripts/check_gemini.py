"""Check Gemini connectivity for the voice agent with a harmless synthetic request.

Run from backend/:  python -m scripts.check_gemini
Prints the status category and model only. Never prints the API key.
"""

from app.services import agent_llm


def main() -> int:
    status = agent_llm.health_check(force=True)
    print(f"model:          {agent_llm.model_name()}")
    print(f"key slots:      {', '.join(slot for slot, _ in agent_llm._api_keys()) or 'none'}")
    print(f"status:         {status.status}")
    if status.key_slot:
        print(f"answered by:    {status.key_slot} (attempts: {status.attempts})")
    if status.detail:
        print(f"detail:         {status.detail}")
    return 0 if status.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
