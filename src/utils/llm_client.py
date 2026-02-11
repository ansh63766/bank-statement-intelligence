import base64
import logging
import asyncio
from typing import Optional, List, Dict, Any
import httpx
from src.config import settings

logger = logging.getLogger("bank_statement_intel.llm")
logging.basicConfig(level=logging.INFO)

class LLMClient:
    """
    Unified client for LLM providers (OpenRouter, OpenAI, DeepInfra, and Google Gemini API via OpenAI compatibility).
    """
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self._init_provider_config()

    def _init_provider_config(self):
        """Initialize headers, base URL, and model based on the selected provider."""
        if self.provider == "openrouter":
            self.base_url = "https://openrouter.ai/api/v1/chat/completions"
            self.api_key = settings.OPENROUTER_API_KEY
            self.model = settings.OPENROUTER_MODEL
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/shiva/bank-statement-intel",
                "X-Title": "Bank Statement Intelligence Pipeline",
                "Content-Type": "application/json"
            }
        elif self.provider == "openai":
            self.base_url = "https://api.openai.com/v1/chat/completions"
            self.api_key = settings.OPENAI_API_KEY
            self.model = settings.OPENAI_MODEL
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        elif self.provider == "deepinfra":
            self.base_url = "https://api.deepinfra.com/v1/chat/completions"
            self.api_key = settings.DEEPINFRA_API_KEY
            self.model = settings.DEEPINFRA_MODEL
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        elif self.provider == "google":
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            self.api_key = settings.GOOGLE_API_KEY
            self.model = settings.GOOGLE_MODEL
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        else:
            raise ValueError(
                f"Unsupported LLM provider '{self.provider}'. "
                f"Choose from: openrouter, openai, deepinfra, google"
            )

        if not self.api_key:
            logger.warning(
                f"LLM API key for provider '{self.provider}' is empty or not configured. "
                f"API calls will fail."
            )

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        image_bytes: Optional[bytes] = None,
        mime_type: str = "image/png",
        max_tokens: int = 4000,
        temperature: float = 0.1,
        retries: int = 3,
        backoff_factor: float = 2.0
    ) -> str:
        """
        Generates completions from the LLM. Supports vision inputs via Base64.
        """
        # Prepare messages structure
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        if image_bytes:
            # Base64 encode the image
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            user_content = [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    }
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        delay = 1.0
        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(retries):
                try:
                    logger.info(
                        f"Sending request to {self.provider} using model {self.model} (attempt {attempt + 1}/{retries})"
                    )
                    response = await client.post(
                        self.base_url,
                        headers=self.headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        try:
                            return data["choices"][0]["message"]["content"]
                        except (KeyError, IndexError) as e:
                            logger.error(f"Malformed LLM response: {data}. Error: {e}")
                            raise RuntimeError(f"Malformed response format from provider: {e}")
                    
                    # Log rate limit or server error
                    logger.warning(
                        f"LLM API request failed with status {response.status_code}. Response: {response.text}"
                    )
                    
                    if response.status_code in [429, 500, 502, 503, 504]:
                        # Retry on rate limit or server errors
                        if attempt < retries - 1:
                            logger.info(f"Retrying in {delay:.2f} seconds...")
                            await asyncio.sleep(delay)
                            delay *= backoff_factor
                            continue
                    
                    response.raise_for_status()

                except httpx.HTTPStatusError as e:
                    if attempt == retries - 1:
                        raise e
                except httpx.RequestError as e:
                    logger.warning(f"Network error on attempt {attempt + 1}: {e}")
                    if attempt == retries - 1:
                        raise e
                    await asyncio.sleep(delay)
                    delay *= backoff_factor

        raise RuntimeError("LLM request failed after maximum retries.")
