import pytest
from triage_rca.issue_store import IssueStore, SimilarIssue

def test_insert_and_search(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)

    store.insert("bug-1", "pandas", "TypeError in merge", [0.1, 0.2, 0.3, 0.4])
    store.insert("bug-2", "numpy", "IndexError in reshape", [0.9, 0.8, 0.7, 0.6])
    store.insert("bug-3", "pandas", "NullPointerError in concat", [0.15, 0.25, 0.35, 0.45])

    results = store.search([0.1, 0.2, 0.3, 0.4], k=2)
    assert len(results) == 2
    assert results[0].bug_id == "bug-1"
    assert results[1].bug_id == "bug-3"
    assert results[0].similarity >= results[1].similarity

def test_count_empty(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    assert store.count() == 0

def test_count_after_insert(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    store.insert("bug-1", "pandas", "test", [0.1, 0.2, 0.3, 0.4])
    assert store.count() == 1

def test_insert_idempotent(tmp_path):
    store = IssueStore(str(tmp_path / "test.db"))
    store.init_vec_table(dimensions=4)
    store.insert("bug-1", "pandas", "first description", [0.1, 0.2, 0.3, 0.4])
    store.insert("bug-1", "pandas", "updated description", [0.1, 0.2, 0.3, 0.4])
    assert store.count() == 1
    results = store.search([0.1, 0.2, 0.3, 0.4], k=1)
    assert results[0].description == "updated description"
