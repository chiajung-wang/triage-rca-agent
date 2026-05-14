import os
from dataclasses import dataclass
from dotenv import load_dotenv
from .exceptions import ConfigError

_DEFAULT_LANGFUSE_HOST = "https://cloud.langfuse.com"
_DEFAULT_DB_PATH = "triage_rca.db"


@dataclass
class Config:
    anthropic_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str = _DEFAULT_LANGFUSE_HOST
    db_path: str = _DEFAULT_DB_PATH


def load_config(env_file: str | None = None) -> Config:
    # env_file=None uses default .env discovery; pass "/dev/null" in tests
    load_dotenv(dotenv_path=env_file)
    missing = [k for k in ("ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not os.getenv(k)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")
    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        langfuse_secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        langfuse_host=os.getenv("LANGFUSE_HOST", _DEFAULT_LANGFUSE_HOST),
        db_path=os.getenv("TRIAGE_RCA_DB", _DEFAULT_DB_PATH),
    )
