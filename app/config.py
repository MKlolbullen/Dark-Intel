import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()

    # Provider API keys — only the active provider's key is required at runtime
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # always used for FAISS embeddings

    # Per-provider model pairs (long-form / relation)
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
    CLAUDE_MODEL_RELATION = os.getenv("CLAUDE_MODEL_RELATION", "claude-haiku-4-5")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    GEMINI_MODEL_RELATION = os.getenv("GEMINI_MODEL_RELATION", "gemini-2.5-flash")
    GROK_MODEL = os.getenv("GROK_MODEL", "grok-4")
    GROK_MODEL_RELATION = os.getenv("GROK_MODEL_RELATION", "grok-3-mini")

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

    @classmethod
    def default_model(cls) -> str:
        return {
            "anthropic": cls.CLAUDE_MODEL,
            "gemini": cls.GEMINI_MODEL,
            "grok": cls.GROK_MODEL,
        }.get(cls.LLM_PROVIDER, cls.CLAUDE_MODEL)

    @classmethod
    def relation_model(cls) -> str:
        return {
            "anthropic": cls.CLAUDE_MODEL_RELATION,
            "gemini": cls.GEMINI_MODEL_RELATION,
            "grok": cls.GROK_MODEL_RELATION,
        }.get(cls.LLM_PROVIDER, cls.CLAUDE_MODEL_RELATION)
