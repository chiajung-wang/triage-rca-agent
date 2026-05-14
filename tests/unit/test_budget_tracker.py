import time, pytest
from triage_rca.budget import BudgetTracker
from triage_rca.exceptions import BudgetExceeded


def test_cost_limit():
    t = BudgetTracker()
    t.start()
    t.add_cost(0.49)
    t.check()  # OK at 0.49
    t.add_cost(0.02)
    with pytest.raises(BudgetExceeded, match="cost"):
        t.check()


def test_tool_calls_per_subagent():
    t = BudgetTracker()
    t.start()
    for _ in range(50):
        t.add_tool_call("classifier")
    t.check()  # OK at exactly 50
    t.add_tool_call("classifier")
    with pytest.raises(BudgetExceeded, match="tool_calls"):
        t.check()


def test_total_tool_calls():
    t = BudgetTracker()
    t.start()
    for i in range(200):
        t.add_tool_call(f"agent_{i % 5}")
    t.check()  # OK at exactly 200
    t.add_tool_call("any")
    with pytest.raises(BudgetExceeded, match="tool_calls"):
        t.check()


def test_wall_clock_timeout(monkeypatch):
    start = 1000.0
    calls = iter([start, start + 301.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(calls))
    t = BudgetTracker()
    t.start()
    with pytest.raises(BudgetExceeded, match="timeout"):
        t.check()


def test_snapshot():
    t = BudgetTracker()
    t.start()
    t.add_cost(0.10)
    t.add_tool_call("investigator")
    s = t.snapshot()
    assert s.cost_usd == pytest.approx(0.10)
    assert s.tool_calls_by_subagent["investigator"] == 1
    assert s.tool_calls_total == 1
