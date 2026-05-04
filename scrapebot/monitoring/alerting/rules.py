from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AlertRule:
    name: str
    description: str = ""
    condition: Callable[[dict[str, Any]], bool] = lambda _: False
    severity: str = "warning"
    cooldown_seconds: float = 300.0


class AlertRuleEngine:
    def __init__(self) -> None:
        self._rules: list[AlertRule] = []
        self._last_triggered: dict[str, float] = {}

    def add(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def evaluate(self, stats: dict[str, Any]) -> list[AlertRule]:
        import time

        now = time.monotonic()
        triggered: list[AlertRule] = []

        for rule in self._rules:
            last = self._last_triggered.get(rule.name, 0)
            if now - last < rule.cooldown_seconds:
                continue
            if rule.condition(stats):
                triggered.append(rule)
                self._last_triggered[rule.name] = now

        return triggered
