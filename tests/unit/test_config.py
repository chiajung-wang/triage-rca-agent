import os, pytest
from triage_rca.config import load_config, ConfigError

def test_load_config_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        load_config(env_file="/dev/null")

def test_load_config_success(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    config = load_config(env_file="/dev/null")
    assert config.anthropic_api_key == "sk-test"
    assert config.langfuse_public_key == "pk-test"
    assert config.db_path == "triage_rca.db"
