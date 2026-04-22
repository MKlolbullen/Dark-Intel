import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
    CLAUDE_MODEL_RELATION = os.getenv("CLAUDE_MODEL_RELATION", "claude-haiku-4-5")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    DB_PATH = os.getenv("DB_PATH", "intel_graph.db")
    DB_URL = f"sqlite:///{DB_PATH}"

    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
    REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "dark-intel/0.2")

    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")

    DEFAULT_CHANNELS = tuple(
        c.strip() for c in os.getenv("DEFAULT_CHANNELS", "news,reddit,hn,competitor").split(",") if c.strip()
    )
