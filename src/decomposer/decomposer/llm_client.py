import httpx
import json
import traceback
from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str = None, system_prompt: str = None, logger=None):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.logger = logger
        self.client = AsyncOpenAI(
            base_url = self.base_url,
            api_key = self.api_key,
            timeout=httpx.Timeout(10.0, connect=5.0),
            http_client=httpx.AsyncClient(proxy=None) 
        )
        if self.logger:
            self.logger.info("LLM Client | Client has started.")

    async def decompose(self, message: str, temperature: float = 0.7) -> dict:
        """
        Calls the LLM API to decompose the given natural language command into json format.
        """
        if self.client is None:
            self.client = AsyncOpenAI(
                base_url = self.base_url,
                api_key = self.api_key,
            )

        self.logger.info("LLM Client | Calling LLM...")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=temperature,
            )
            self.logger.info(f"LLM response: {response.choices[0].message.content}")
            return json.loads(response.choices[0].message.content)
        
        except Exception as e:
            self.logger.error(f"Error during LLM decomposition: {str(e)}")
            full_error = traceback.format_exc()
            return {"error": str(e)}