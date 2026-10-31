"""Check Gemini connectivity for the voice agent with a harmless synthetic request.

Run from backend/:  python -m scripts.check_gemini
Prints the status category and model only. Never prints the API key.
"""

from app.services import agent_llm


def main() -> int:
    status = agent_llm.health_check(force=True)
    print(f"model:          {agent_llm.model_name()}")
    print(f"key configured: {agent_llm._get_api_key() is not None}")
    print(f"status:         {status.status}")
    if status.detail:
        print(f"detail:         {status.detail}")
    return 0 if status.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
