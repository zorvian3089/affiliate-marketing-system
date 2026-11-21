import time
import logging
import json
import re
from datetime import datetime
from abc import ABC, abstractmethod
import google.generativeai as genai
from database.database import get_db
from database.models import AgentLog
from config.settings import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

# Resolved once per process: the model name that actually works for this API key.
_resolved_model: str | None = None


def _discover_model(preferred: str) -> str:
    """Return `preferred` if the key can use it, else the best available flash model."""
    try:
        names = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
    except Exception as e:
        logger.warning(f"Could not list Gemini models ({e}); using {preferred}")
        return preferred
    if preferred and preferred in names:
        return preferred
    # Pick the newest plain "gemini-<ver>-flash" (not lite/omni/image/preview/exp/tts).
    def _ver(n: str):
        m = re.fullmatch(r"gemini-(\d+(?:\.\d+)?)-flash", n)
        return float(m.group(1)) if m else None
    versions = sorted(((_ver(n), n) for n in names if _ver(n) is not None), reverse=True)
    chosen = versions[0][1] if versions else ("gemini-flash-latest" if "gemini-flash-latest" in names
                                              else (names[0] if names else preferred))
    logger.info(f"Gemini model auto-selected: {chosen}")
    return chosen


def _extract_json(text: str):
    """Parse JSON from an LLM reply: tolerates code fences and surrounding prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost {...} or [...] block
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1], strict=False)
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No valid JSON in model reply: {text[:200]!r}")


class BaseAgent(ABC):
    """Base class all agents inherit from."""

    name: str = "BaseAgent"

    def __init__(self):
        global _resolved_model
        if _resolved_model is None:
            _resolved_model = _discover_model(GEMINI_MODEL) if GEMINI_API_KEY else GEMINI_MODEL
        self.model = _resolved_model
        self.client = genai.GenerativeModel(self.model)

    def ask_claude(self, system_prompt: str, user_message: str, max_tokens: int = 4096,
                   json_mode: bool = False, retries: int = 3) -> str:
        """Ask Gemini. (Name kept for backwards compatibility with all agents.)"""
        cfg = {"max_output_tokens": max_tokens}
        if json_mode:
            cfg["response_mime_type"] = "application/json"
        prompt = f"{system_prompt}\n\n{user_message}"

        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.client.generate_content(
                    prompt, generation_config=genai.types.GenerationConfig(**cfg),
                    request_options={"timeout": 120},
                )
                return response.text
            except Exception as e:  # rate limit (429), transient 5xx, empty/blocked reply
                last_err = e
                wait = 5 * (3 ** attempt)  # 5s, 15s, 45s — free tier is rate-limited
                logger.warning(f"[{self.name}] Gemini call failed ({e}); retry in {wait}s")
                time.sleep(wait)
        raise RuntimeError(f"Gemini call failed after {retries} attempts: {last_err}")

    def ask_claude_json(self, system_prompt: str, user_message: str, max_tokens: int = 4096) -> dict | list:
        text = self.ask_claude(system_prompt, user_message, max_tokens, json_mode=True)
        try:
            return _extract_json(text)
        except ValueError:
            # One re-ask: truncated / malformed output is the usual cause
            text = self.ask_claude(
                system_prompt,
                user_message + "\n\nReturn ONLY compact, valid JSON. Escape all newlines inside strings as \\n.",
                max_tokens, json_mode=True, retries=1,
            )
            return _extract_json(text)

    def log(self, task: str, status: str, result: str = "", error: str = "", duration: float = 0.0):
        try:
            with get_db() as db:
                entry = AgentLog(
                    agent_name=self.name,
                    task=task[:499],
                    status=status,
                    result_summary=result[:2000] if result else None,
                    error_message=error[:1000] if error else None,
                    duration_seconds=duration,
                    completed_at=datetime.utcnow(),
                )
                db.add(entry)
        except Exception as e:
            logger.warning(f"Failed to write agent log: {e}")

    def run(self, **kwargs):
        start = time.time()
        logger.info(f"[{self.name}] Starting run...")
        try:
            result = self.execute(**kwargs)
            duration = time.time() - start
            self.log(self.name, "success", str(result)[:500], duration=duration)
            logger.info(f"[{self.name}] Completed in {duration:.1f}s")
            return result
        except Exception as e:
            duration = time.time() - start
            self.log(self.name, "failed", error=str(e), duration=duration)
            logger.error(f"[{self.name}] Failed: {e}")
            raise

    @abstractmethod
    def execute(self, **kwargs):
        pass
