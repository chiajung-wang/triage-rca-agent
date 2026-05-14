import time
from dataclasses import dataclass, field
from .exceptions import BudgetExceeded


@dataclass
class BudgetState:
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    tool_calls_total: int = 0
    tool_calls_by_subagent: dict[str, int] = field(default_factory=dict)


class BudgetTracker:
    COST_LIMIT = 0.50
    WALL_CLOCK_LIMIT = 300.0
    TOOL_CALLS_PER_SUBAGENT = 50
    TOOL_CALLS_TOTAL = 200

    def __init__(self):
        self._state = BudgetState()
        self._start_time: float | None = None

    def start(self) -> None:
        self._start_time = time.monotonic()

    def add_cost(self, usd: float) -> None:
        self._state.cost_usd += usd

    def add_tool_call(self, subagent: str) -> None:
        self._state.tool_calls_total += 1
        self._state.tool_calls_by_subagent[subagent] = (
            self._state.tool_calls_by_subagent.get(subagent, 0) + 1
        )

    def check(self) -> None:
        if self._start_time is not None:
            self._state.elapsed_s = time.monotonic() - self._start_time
        if self._state.cost_usd > self.COST_LIMIT:
            raise BudgetExceeded("cost", self._state)
        if self._state.elapsed_s > self.WALL_CLOCK_LIMIT:
            raise BudgetExceeded("timeout", self._state)
        if self._state.tool_calls_total > self.TOOL_CALLS_TOTAL:
            raise BudgetExceeded("tool_calls_total", self._state)
        for agent, count in self._state.tool_calls_by_subagent.items():
            if count > self.TOOL_CALLS_PER_SUBAGENT:
                raise BudgetExceeded(f"tool_calls per subagent ({agent})", self._state)

    def snapshot(self) -> BudgetState:
        if self._start_time is not None:
            self._state.elapsed_s = time.monotonic() - self._start_time
        return BudgetState(
            cost_usd=self._state.cost_usd,
            elapsed_s=self._state.elapsed_s,
            tool_calls_total=self._state.tool_calls_total,
            tool_calls_by_subagent=dict(self._state.tool_calls_by_subagent),
        )
