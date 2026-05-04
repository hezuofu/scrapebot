from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


StepFunc = Callable[[Any, dict[str, Any] | None], Any]


class PipelineStep(ABC):
    @abstractmethod
    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        """Process data through this pipeline step."""


class _FuncStep(PipelineStep):
    """Adapter: wraps a plain (data, ctx) -> data function as a PipelineStep."""

    def __init__(self, fn: StepFunc) -> None:
        self._fn = fn

    async def process(self, data: Any, context: dict[str, Any] | None = None) -> Any:
        result = self._fn(data, context)
        if hasattr(result, "__await__"):
            result = await result
        return result


class Pipeline:
    def __init__(self, steps: list[PipelineStep | StepFunc] | None = None) -> None:
        self._steps: list[PipelineStep] = [self._wrap(s) for s in (steps or [])]

    def add(self, step: PipelineStep | StepFunc) -> Pipeline:
        self._steps.append(self._wrap(step))
        return self

    def insert(self, index: int, step: PipelineStep | StepFunc) -> Pipeline:
        self._steps.insert(index, self._wrap(step))
        return self

    async def run(self, initial_data: Any, context: dict[str, Any] | None = None) -> Any:
        data = initial_data
        for step in self._steps:
            data = await step.process(data, context)
        return data

    @staticmethod
    def _wrap(step: PipelineStep | StepFunc) -> PipelineStep:
        if isinstance(step, PipelineStep):
            return step
        return _FuncStep(step)
