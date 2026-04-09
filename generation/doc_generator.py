import os
import time
from typing import Optional
from mistralai import Mistral
from embedding.chunker import Chunk
from generation.prompts import (
    SYSTEM_PROMPT,
    prompt_for_function,
    prompt_for_class,
    prompt_for_table,
    prompt_for_module,
    prompt_for_project,
)

class DocGenerator:
    def __init__(self, model: str = "mistral-large-latest", delay: float = 0.3):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable is not set. "
                "Please set it before running: export MISTRAL_API_KEY='...'"
            )
        self.client = Mistral(api_key=api_key)
        self.model = model
        self.delay = delay  # délai entre les appels pour éviter le rate limit
        self._call_count = 0

    def _call(self, prompt: str, max_tokens: int = 1024) -> str:
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
            return content
        if isinstance(content, list):
            return "\n".join(getattr(item, "text", str(item)) for item in content)
        if content is None:
            raise RuntimeError("LLM API returned empty content")
        return str(content)

    def document_function(self, chunk: Chunk) -> str:
        return self._call(prompt_for_function(chunk))

    def document_class(
        self, chunk: Chunk, method_docs: Optional[list[str]] = None
    ) -> str:
        return self._call(prompt_for_class(chunk, method_docs or []), max_tokens=1500)

    def document_table(self, chunk: Chunk) -> str:
        return self._call(prompt_for_table(chunk))

    def document_module(
        self,
        file_path: str,
        function_docs: list[str],
        class_docs: list[str],
        imports: list[str],
    ) -> str:
        return self._call(
            prompt_for_module(file_path, function_docs, class_docs, imports),
            max_tokens=2000,
        )

    def document_project(self, modules_summary: list[dict]) -> str:
        return self._call(prompt_for_project(modules_summary), max_tokens=3000)
