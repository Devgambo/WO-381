import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")
        _client = OpenAI(api_key=api_key)
    return _client


VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
ORCHESTRATOR_MODEL = os.getenv("OPENAI_ORCHESTRATOR_MODEL", "gpt-4o-mini")
VALIDATOR_MODEL = os.getenv("OPENAI_VALIDATOR_MODEL", "gpt-4o-mini")
FINAL_REPORT_MODEL = os.getenv("OPENAI_FINAL_REPORT_MODEL", "o4-mini")
