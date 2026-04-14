import os
import re
import time
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


class DocGenerator:
    def __init__(self, model: str = "mistral-large-latest", delay: float = 0.15):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable is not set. "
                "Please set it before running: export MISTRAL_API_KEY='...'"
            )
        self.client = Mistral(api_key=api_key)
        self.model = model
        self.delay = delay  # d�lai entre les appels pour �viter le rate limit
        self._call_count = 0

    @staticmethod
    def _sanitize_markdown_response(content: str) -> str:
        cleaned = content.strip()
        cleaned = re.sub(
            r"```(?:markdown|md)\\s*\\n([\\s\\S]*?)```",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        )

        wrapped = re.match(r"^```[\\w-]*\\s*\\n([\\s\\S]*?)\\n```$", cleaned)
        if wrapped:
            cleaned = wrapped.group(1)

        return cleaned.strip()

    def _call(self, prompt: str, max_tokens: int = 420) -> str:
        self._call_count += 1
        if self._call_count > 1:
            time.sleep(self.delay)

        response = self.client.chat.complete(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
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
