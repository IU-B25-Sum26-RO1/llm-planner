import logging
import time

import httpx
from openai import AsyncOpenAI

from decomposer.json_utils import parse_llm_json, validate_command_dict


class LLMClient:
    MAX_ATTEMPTS = 3
    DEFAULT_TEMPERATURE = 0.1

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = None,
        system_prompt: str = None,
        logger=None,
    ):
        if not base_url:
            raise ValueError("LLM base_url is required")
        if not model:
            raise ValueError("LLM model is required")
        if not system_prompt:
            raise ValueError("LLM system_prompt is required")

        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.logger = logger or logging.getLogger(__name__)
        self.client = self._create_client()
        self.logger.info("LLM Client | Client has started.")

    def _create_client(self):
        return AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(30.0, connect=5.0),
            http_client=httpx.AsyncClient(proxy=None),
        )

    async def close(self):
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def decompose(self, message: str, temperature: float = DEFAULT_TEMPERATURE) -> dict:
        if self.client is None:
            self.client = self._create_client()

        last_error = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            attempt_temperature = temperature if attempt == 1 else 0.0
            user_message = message
            if attempt > 1:
                user_message = (
                    f"{message}\n\n"
                    "Return ONLY one valid JSON object. "
                    "No markdown, no comments, no extra text."
                )

            self.logger.info(
                f"LLM Client | Calling LLM (attempt {attempt}/{self.MAX_ATTEMPTS})..."
            )

            try:
                start_time = time.time()
                response = await self._call_llm(user_message, attempt_temperature)
                latency = time.time() - start_time
                raw_content = response.choices[0].message.content or ""
                self.logger.info(f"LLM Client | Response latency: {latency:.2f} s")

                result = validate_command_dict(parse_llm_json(raw_content))

                self.logger.info(
                    f"LLM Client | Parsed command type={result.get('type')}, "
                    f"tasks={len(result.get('tasks', []))}"
                )
                self.logger.info(f"LLM Client | Parsed command: {result}")
                return result

            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    f"LLM Client | Attempt {attempt} failed: {exc}"
                )
                if attempt == self.MAX_ATTEMPTS:
                    break

        self.logger.error(f"Error during LLM decomposition: {last_error}")
        return {"error": str(last_error)}

    @staticmethod
    def _is_response_format_unsupported(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        message = str(exc).lower()
        return status_code in {400, 422} and (
            "response_format" in message or "json_object" in message
        )

    async def _call_llm(self, user_message: str, temperature: float):
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            return await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            if not self._is_response_format_unsupported(exc):
                raise
            self.logger.warning(
                f"LLM Client | JSON response_format unsupported, retrying without it: {exc}"
            )
            return await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
