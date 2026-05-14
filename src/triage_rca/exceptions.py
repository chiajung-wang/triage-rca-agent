class BudgetExceeded(Exception):
    def __init__(self, reason: str, state):
        self.reason = reason
        self.state = state
        super().__init__(f"Budget exceeded: {reason}")


class ConfigError(Exception):
    pass
