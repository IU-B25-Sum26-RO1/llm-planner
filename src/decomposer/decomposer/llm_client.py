import httpx
import time
import traceback
from openai import AsyncOpenAI

from decomposer.json_utils import is_valid_command_dict, parse_llm_json


class LLMClient:
    MAX_ATTEMPTS = 3
    DEFAULT_TEMPERATURE = 0.1

    def __init__(self, base_url: str, model: str, api_key: str = None, system_prompt: str = None, logger=None):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.logger = logger
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(30.0, connect=5.0),
            http_client=httpx.AsyncClient(proxy=None),
        )
        if self.logger:
            self.logger.info("LLM Client | Client has started.")

    async def decompose(self, message: str, temperature: float = DEFAULT_TEMPERATURE) -> dict:
        if self.client is None:
            self.client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )

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

            self.logger.info(f"LLM Client | Calling LLM (attempt {attempt}/{self.MAX_ATTEMPTS})...")

            try:
                start_time = time.time()
                response = await self._call_llm(user_message, attempt_temperature)
                latency = time.time() - start_time
                raw_content = response.choices[0].message.content or ""
                self.logger.info(f"LLM Client | Response latency: {latency:.2f} s")

                result = parse_llm_json(raw_content)
                if not is_valid_command_dict(result):
                    raise ValueError(f"LLM JSON has invalid structure: {result}")

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
        self.logger.error(traceback.format_exc())
        return {"error": str(last_error)}

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
            if self.logger:
                self.logger.warning(
                    f"LLM Client | JSON response_format unsupported, retrying without it: {exc}"
                )
            return await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
