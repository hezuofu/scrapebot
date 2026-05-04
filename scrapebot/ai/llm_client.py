from __future__ import annotations

import json
import logging
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


class PromptTemplate:
    """Named prompt template with variable substitution."""
    def __init__(self, name: str, template: str, variables: list[str] | None = None) -> None:
        self.name = name
        self.template = template
        self.variables = variables or []

    def render(self, **kwargs: Any) -> str:
        return self.template.format(**kwargs)


DEFAULT_TEMPLATES = {
    "extract_json": PromptTemplate(
        "extract_json",
        "Extract structured data from the following content as a JSON array of objects. "
        "Instruction: {instruction}\n\nContent:\n{content}",
        ["instruction", "content"],
    ),
    "classify": PromptTemplate(
        "classify",
        "Classify this content into one of: {categories}. Respond with just the category name.\n\nContent:\n{content}",
        ["categories", "content"],
    ),
    "generate_selectors": PromptTemplate(
        "generate_selectors",
        "Given this HTML snippet, generate CSS selectors to extract these fields: {fields}. "
        "Return a JSON object mapping field_name → css_selector.\n\nHTML:\n{html}",
        ["fields", "html"],
    ),
    "summarize": PromptTemplate(
        "summarize",
        "Summarize this content in under {max_length} characters:\n\n{content}",
        ["max_length", "content"],
    ),
    "detect_change": PromptTemplate(
        "detect_change",
        "Compare the structure of these two HTML pages. Has the page structure changed significantly? "
        "Answer 'yes' or 'no'.\n\nBaseline:\n{baseline}\n\nCurrent:\n{current}",
        ["baseline", "current"],
    ),
}


class LLMClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None
        self._templates: dict[str, PromptTemplate] = dict(DEFAULT_TEMPLATES)
        self._instruction_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def add_template(self, name: str, template: str, variables: list[str] | None = None) -> None:
        self._templates[name] = PromptTemplate(name, template, variables)

    def get_template(self, name: str) -> PromptTemplate | None:
        return self._templates.get(name)

    def cache_instruction(self, instruction: str, result: dict[str, Any]) -> None:
        self._instruction_cache[instruction] = result
        if len(self._instruction_cache) > 100:
            self._instruction_cache.popitem(last=False)

    def get_cached_instruction(self, instruction: str) -> dict[str, Any] | None:
        return self._instruction_cache.get(instruction)

    def _ensure_client(self) -> None:
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def extract(self, instruction: str, content: str) -> list[dict[str, Any]]:
        self._ensure_client()
        tmpl = self._templates.get("extract_json", DEFAULT_TEMPLATES["extract_json"])
        prompt = tmpl.render(instruction=instruction, content=content)

        response = await self._client.chat.completions.create(
            model=self.model, max_tokens=self.max_tokens, temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or "{}"
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data.get("items", [data])
            return data if isinstance(data, list) else [{"result": data}]
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON: %s", text[:200])
            return [{"raw": text}]

    async def classify(self, content: str, categories: list[str]) -> str:
        self._ensure_client()
        tmpl = self._templates["classify"]
        prompt = tmpl.render(categories=", ".join(categories), content=content[:4000])
        response = await self._client.chat.completions.create(
            model=self.model, max_tokens=50, temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        result = (response.choices[0].message.content or "").strip().lower()
        for cat in categories:
            if cat.lower() in result:
                return cat
        return result or "unknown"

    async def generate_selectors(self, html: str, fields: list[str]) -> dict[str, str]:
        self._ensure_client()
        tmpl = self._templates["generate_selectors"]
        prompt = tmpl.render(fields=", ".join(fields), html=html[:6000])
        response = await self._client.chat.completions.create(
            model=self.model, max_tokens=1024, temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    async def validate_selectors(self, html: str, selectors: dict[str, str]) -> dict[str, bool]:
        """Test whether generated selectors actually match elements in the HTML."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        results: dict[str, bool] = {}
        for field, css in selectors.items():
            results[field] = soup.select_one(css) is not None
        return results
