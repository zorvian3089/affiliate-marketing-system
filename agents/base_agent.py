import time
import logging
from datetime import datetime
from abc import ABC, abstractmethod
from anthropic import Anthropic
from database.database import get_db
from database.models import AgentLog
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class all agents inherit from."""

    name: str = "BaseAgent"

    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = CLAUDE_MODEL

    def ask_claude(self, system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def ask_claude_json(self, system_prompt: str, user_message: str, max_tokens: int = 4096) -> dict | list:
        import json, re
        text = self.ask_claude(system_prompt, user_message, max_tokens)
        # Extract JSON from markdown code blocks if present
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            text = match.group(1)
        return json.loads(text.strip())

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
