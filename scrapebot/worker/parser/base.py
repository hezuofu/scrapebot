from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from scrapebot.types import ParseResult


class BaseParser(ABC):
    @abstractmethod
    async def parse(
        self,
        html: str,
        instructions: dict[str, Any],
    ) -> ParseResult:
        """Parse HTML content according to instructions and return structured data."""
