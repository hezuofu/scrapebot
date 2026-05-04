from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from scrapebot.types import ParseResult, TaskResult


class PipelineStep(ABC):
    @abstractmethod
    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        """Process data through this pipeline step."""


class Pipeline:
    def __init__(self, steps: list[PipelineStep] | None = None) -> None:
        self._steps: list[PipelineStep] = steps or []

    def add(self, step: PipelineStep) -> Pipeline:
        self._steps.append(step)
        return self

    def insert(self, index: int, step: PipelineStep) -> Pipeline:
        self._steps.insert(index, step)
        return self

    async def run(
        self,
        initial_data: ParseResult,
        context: dict[str, Any] | None = None,
    ) -> Any:
        data: Any = initial_data
        for step in self._steps:
            data = await step.process(data, context)
        return data
