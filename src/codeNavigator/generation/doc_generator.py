import os
import re
import time
import logging
from typing import Optional
from mistralai import Mistral
from src.codeNavigator.embedding.chunker import Chunk
from src.codeNavigator.generation.prompts import (
    SYSTEM_PROMPT,
    prompt_for_function,
    prompt_for_class,
    prompt_for_table,
    prompt_for_module,
    prompt_for_project,
)


LOGGER = logging.getLogger(__name__)


class DocGenerator:
    def __init__(
        self,
        model: str = "mistral-large-latest",
        delay: float = 0.15,
        fallback_model: str = "mistral-medium-latest",
    ):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable is not set. "
                "Please set it before running: export MISTRAL_API_KEY='...'"
            )
        self.client = Mistral(api_key=api_key)
        self.model = model
        self.fallback_model = fallback_model
        self.delay = delay  # délai entre les appels pour éviter le rate limit
        self.retry_attempts = 3
        self._call_count = 0

    @staticmethod
    def _sanitize_markdown_response(content: str) -> str:
        cleaned = content.strip()
        cleaned = re.sub(
            r"```(?:markdown|md)\s*\n([\s\S]*?)```",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        )

        wrapped = re.match(r"^```[\w-]*\s*\n([\s\S]*?)\n```$", cleaned)
        if wrapped:
            cleaned = wrapped.group(1)

        return cleaned.strip()

    @staticmethod
    def _extract_error_status_code(error: Exception) -> Optional[int]:
        status = getattr(error, "status_code", None)
        if isinstance(status, int):
            return status

        response = getattr(error, "response", None)
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status

        return None

    def _is_retryable_llm_error(self, error: Exception) -> bool:
        status_code = self._extract_error_status_code(error)
        if status_code in {408, 429, 500, 502, 503, 504}:
            return True

        message = str(error).lower()
        retryable_patterns = (
            "rate limit",
            "too many requests",
            "timeout",
            "temporarily unavailable",
            "overloaded",
        )
        return any(pattern in message for pattern in retryable_patterns)

    def _complete_once(self, prompt: str, max_tokens: int, model: str):
        return self.client.chat.complete(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

    def _invoke_with_retries(self, prompt: str, max_tokens: int, model: str):
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return self._complete_once(prompt, max_tokens, model)
            except Exception as error:
                retryable = self._is_retryable_llm_error(error)
                if attempt >= self.retry_attempts or not retryable:
                    raise

                wait_seconds = self.delay * (2 ** (attempt - 1))
                status_code = self._extract_error_status_code(error)
                LOGGER.warning(
                    "LLM call failed (model=%s, status=%s, attempt=%d/%d): %s. "
                    "Retry in %.2fs.",
                    model,
                    status_code,
                    attempt,
                    self.retry_attempts,
                    error,
                    wait_seconds,
                )
                time.sleep(wait_seconds)

    def _call(self, prompt: str, max_tokens: int = 420) -> str:
        self._call_count += 1
        if self._call_count > 1:
            time.sleep(self.delay)

        try:
            response = self._invoke_with_retries(prompt, max_tokens, self.model)
        except Exception as primary_error:
            if not self.fallback_model or self.fallback_model == self.model:
                raise

            LOGGER.warning(
                "Primary model '%s' failed after retries (%s). "
                "Switching to fallback model '%s'.",
                self.model,
                primary_error,
                self.fallback_model,
            )
            response = self._invoke_with_retries(
                prompt,
                max_tokens,
                self.fallback_model,
            )
            self.model = self.fallback_model

        if response is None or response.choices is None or not response.choices:
            raise RuntimeError("LLM API returned an empty response")

        content = response.choices[0].message.content
        if isinstance(content, str):
            return self._sanitize_markdown_response(content)
        if isinstance(content, list):
            merged = "\n".join(getattr(item, "text", str(item)) for item in content)
            return self._sanitize_markdown_response(merged)
        if content is None:
            raise RuntimeError("LLM API returned empty content")
        return self._sanitize_markdown_response(str(content))

    def document_function(self, chunk: Chunk) -> str:
        return self._call(prompt_for_function(chunk), max_tokens=420)

    def document_class(
        self, chunk: Chunk, method_docs: Optional[list[str]] = None
    ) -> str:
        return self._call(prompt_for_class(chunk, method_docs or []), max_tokens=560)

    def document_table(self, chunk: Chunk) -> str:
        return self._call(prompt_for_table(chunk), max_tokens=520)

    def document_module(
        self,
        file_path: str,
        function_docs: list[str],
        class_docs: list[str],
        imports: list[str],
    ) -> str:
        return self._call(
            prompt_for_module(file_path, function_docs, class_docs, imports),
            max_tokens=1200,
        )

    def document_project(self, modules_summary: list[dict]) -> str:
        return self._call(prompt_for_project(modules_summary), max_tokens=1200)
