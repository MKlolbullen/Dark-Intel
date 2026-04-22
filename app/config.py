import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    DB_PATH = os.getenv("DB_PATH", "intel_graph.db")
    DB_URL = f"sqlite:///{DB_PATH}"
