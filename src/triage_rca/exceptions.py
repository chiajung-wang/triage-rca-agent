from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triage_rca.budget import BudgetState


class BudgetExceeded(Exception):
    def __init__(self, reason: str, state: BudgetState):
        self.reason = reason
        self.state = state
        super().__init__(f"Budget exceeded: {reason}")


class ConfigError(Exception):
    pass
