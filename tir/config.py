"""
Tír Configuration

Paths, model settings, and tuning knobs.
All configuration in one place.
"""

from copy import deepcopy
import os
from pathlib import Path
import tomllib

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = Path(os.getenv("ANAM_CONFIG_DIR", PROJECT_ROOT / "config"))
DATA_DIR = PROJECT_ROOT / "data" / "prod"
ARCHIVE_DB = DATA_DIR / "archive.db"
WORKING_DB = DATA_DIR / "working.db"
CHROMA_DIR = str(DATA_DIR / "chromadb")
SKILLS_DIR = PROJECT_ROOT / "skills" / "active"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
BACKUP_DIR = PROJECT_ROOT / "backups"


_FALLBACK_CONFIG = {
    "models": {
        "chat": "gemma4:26b",
        "reflection_journal": "gemma4:26b",
        "behavioral_guidance_review": "gemma4:26b",
        "operational_reflection": "gemma4:26b",
        "embedding": "nomic-embed-text",
    },
    "ollama": {
        "host": "http://localhost:11434",
        "timeout_seconds": 300,
    },
    "model_options": {
        "default": {"think": False, "temperature": 0.35, "num_ctx": 32768},
        "chat": {"think": False},
        "reflection_journal": {"think": False, "timeout_seconds": 600},
        "behavioral_guidance_review": {"think": False},
        "operational_reflection": {"think": False},
    },
    "retrieval": {
        "results": 20,
        "retrieved_context_budget_chars": 14000,
        "prompt_budget_warning_chars": 30000,
    },
    "embedding": {
        "expected_dimension": 768,
    },
    "journals": {
        "transcript_budget_chars": 24000,
        "activity_packet_budget_chars": 12000,
        "relevant_memory_max_chunks": 5,
        "relevant_memory_budget_chars": 6000,
        "relevant_memory_query_budget_chars": 4000,
        "primary_journal_context_budget_chars": 8000,
    },
    "behavioral_guidance": {
        "runtime_budget_chars": 3000,
    },
    "operational_reflection": {
        "packet_budget_chars": 16000,
    },
    "artifacts": {
        "recent_artifact_context_budget_chars": 2000,
    },
    "api": {
        "host": "127.0.0.1",
        "port": 8000,
    },
    "web_search": {
        "searxng_url": "http://127.0.0.1:8080",
        "timeout_seconds": 10,
    },
    "scheduler": {
        "enabled": False,
        "nightly_tick_enabled": False,
        "max_actions_per_tick": 1,
        "allow_bounded_research": False,
        "allow_moltbook": False,
        "allow_web": False,
        "allow_image_generation": False,
        "go_live": False,
    },
    "image_generation": {
        "enabled": False,
        "default_backend": "comfyui",
        "max_prompt_chars": 2000,
        "max_width": 2048,
        "max_height": 2048,
        "allow_agent_tool": False,
        "comfyui": {
            "base_url": "http://127.0.0.1:8188",
            "workflow_path": "config/comfyui/workflows/default_text_to_image.json",
            "timeout_seconds": 300,
            "poll_interval_seconds": 1,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _load_config() -> dict:
    config = deepcopy(_FALLBACK_CONFIG)
    config = _deep_merge(config, _read_toml(CONFIG_DIR / "defaults.toml"))
    config = _deep_merge(config, _read_toml(CONFIG_DIR / "local.toml"))
    return config


_CONFIG = _load_config()


def _config_value(section: str, key: str, default=None):
    return _CONFIG.get(section, {}).get(key, default)


def _config_section(section: str) -> dict:
    value = _CONFIG.get(section, {})
    return value if isinstance(value, dict) else {}


def _env_text(name: str, current):
    value = os.getenv(name)
    return current if value is None else value


def _env_int(name: str, current: int) -> int:
    value = os.getenv(name)
    return current if value is None else int(value)


def _env_float(name: str, current: float) -> float:
    value = os.getenv(name)
    return current if value is None else float(value)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean environment value: {value}")


def _env_bool(name: str, current: bool) -> bool:
    value = os.getenv(name)
    return current if value is None else _parse_bool(value)


# --- Ollama ---
OLLAMA_HOST = _env_text("ANAM_OLLAMA_HOST", _config_value("ollama", "host"))
OLLAMA_TIMEOUT_SECONDS = _env_int(
    "ANAM_OLLAMA_TIMEOUT_SECONDS",
    int(_config_value("ollama", "timeout_seconds")),
)
CHAT_MODEL = _env_text("ANAM_CHAT_MODEL", _config_value("models", "chat"))
REFLECTION_JOURNAL_MODEL = _env_text(
    "ANAM_REFLECTION_JOURNAL_MODEL",
    _config_value("models", "reflection_journal"),
)
BEHAVIORAL_GUIDANCE_REVIEW_MODEL = _env_text(
    "ANAM_BEHAVIORAL_GUIDANCE_REVIEW_MODEL",
    _config_value("models", "behavioral_guidance_review"),
)
OPERATIONAL_REFLECTION_MODEL = _env_text(
    "ANAM_OPERATIONAL_REFLECTION_MODEL",
    _config_value("models", "operational_reflection"),
)
EMBED_MODEL = _env_text("ANAM_EMBED_MODEL", _config_value("models", "embedding"))
EXPECTED_EMBEDDING_DIM = int(_config_value("embedding", "expected_dimension", 768))


_ROLE_THINK_ENV = {
    "chat": "ANAM_CHAT_MODEL_THINK",
    "reflection_journal": "ANAM_REFLECTION_JOURNAL_MODEL_THINK",
    "behavioral_guidance_review": "ANAM_BEHAVIORAL_GUIDANCE_REVIEW_MODEL_THINK",
    "operational_reflection": "ANAM_OPERATIONAL_REFLECTION_MODEL_THINK",
}
_ROLE_TIMEOUT_ENV = {
    "chat": "ANAM_CHAT_TIMEOUT_SECONDS",
    "reflection_journal": "ANAM_REFLECTION_JOURNAL_TIMEOUT_SECONDS",
    "behavioral_guidance_review": "ANAM_BEHAVIORAL_GUIDANCE_REVIEW_TIMEOUT_SECONDS",
    "operational_reflection": "ANAM_OPERATIONAL_REFLECTION_TIMEOUT_SECONDS",
}


def get_model_options(role: str) -> dict:
    """Return Ollama /api/chat model options for a role.

    The top-level ``think`` option is included here for callers to place at
    the top level of the Ollama payload, not under ``options``.
    """
    role = role or "default"
    default_options = dict(_CONFIG.get("model_options", {}).get("default", {}))
    role_options = dict(_CONFIG.get("model_options", {}).get(role, {}))
    options = {**default_options, **role_options}
    if os.getenv("ANAM_MODEL_THINK") is not None:
        options["think"] = _env_bool(
            "ANAM_MODEL_THINK",
            bool(options.get("think", False)),
        )
    if os.getenv("ANAM_MODEL_TEMPERATURE") is not None:
        options["temperature"] = _env_float(
            "ANAM_MODEL_TEMPERATURE",
            float(options.get("temperature", 0.35)),
        )
    if os.getenv("ANAM_MODEL_NUM_CTX") is not None:
        options["num_ctx"] = _env_int(
            "ANAM_MODEL_NUM_CTX",
            int(options.get("num_ctx", 32768)),
        )
    think_env = _ROLE_THINK_ENV.get(role)
    if think_env and os.getenv(think_env) is not None:
        options["think"] = _env_bool(think_env, bool(options.get("think", False)))
    return options


def get_model_timeout(role: str) -> int:
    """Return the Ollama /api/chat timeout for a role."""
    role = role or "default"
    options = get_model_options(role)
    timeout = int(options.get("timeout_seconds", OLLAMA_TIMEOUT_SECONDS))
    timeout_env = _ROLE_TIMEOUT_ENV.get(role)
    if timeout_env and os.getenv(timeout_env) is not None:
        timeout = _env_int(timeout_env, timeout)
    return timeout

# --- Chunking ---
CHUNK_TURN_SIZE = 5          # Turns per conversation chunk
EMBED_MAX_CHARS = 8000       # Max chars before embedding truncation

# --- Retrieval ---
RETRIEVAL_RESULTS = int(_config_value("retrieval", "results"))  # Candidates returned by retrieval pipeline
DISTANCE_THRESHOLD = 0.8     # Max cosine distance for vector results
RRF_K = 60                   # RRF fusion constant
TRUST_WEIGHTS = {
    "firsthand": 1.0,
    "secondhand": 0.85,
    "thirdhand": 0.7,
}

# --- Context budget ---
CONTEXT_WINDOW = 32768       # gemma4:26b pinned num_ctx=32K
OUTPUT_RESERVE = 4096        # Tokens reserved for response
RETRIEVAL_FLOOR = 3          # Minimum chunks to surface
RETRIEVAL_CEILING = 15       # Maximum chunks to surface
RETRIEVAL_DEFAULT = 8        # Default chunks when budget allows
RETRIEVED_CONTEXT_BUDGET_CHARS = int(
    _config_value("retrieval", "retrieved_context_budget_chars")
)
PROMPT_BUDGET_WARNING_CHARS_CONFIG = int(
    _config_value("retrieval", "prompt_budget_warning_chars")
)

# --- Feature budgets ---
REFLECTION_TRANSCRIPT_BUDGET_CHARS = int(
    _config_value("journals", "transcript_budget_chars")
)
REFLECTION_ACTIVITY_BUDGET_CHARS = int(
    _config_value("journals", "activity_packet_budget_chars")
)
REFLECTION_MEMORY_MAX_CHUNKS_CONFIG = int(
    _config_value("journals", "relevant_memory_max_chunks")
)
REFLECTION_MEMORY_BUDGET_CHARS = int(
    _config_value("journals", "relevant_memory_budget_chars")
)
REFLECTION_MEMORY_QUERY_BUDGET_CHARS = int(
    _config_value("journals", "relevant_memory_query_budget_chars")
)
PRIMARY_JOURNAL_CONTEXT_BUDGET_CHARS = int(
    _config_value("journals", "primary_journal_context_budget_chars")
)
BEHAVIORAL_GUIDANCE_RUNTIME_BUDGET_CHARS = int(
    _config_value("behavioral_guidance", "runtime_budget_chars")
)
OPERATIONAL_REFLECTION_PACKET_BUDGET_CHARS = int(
    _config_value("operational_reflection", "packet_budget_chars")
)
RECENT_ARTIFACT_CONTEXT_BUDGET_CHARS = int(
    _config_value("artifacts", "recent_artifact_context_budget_chars")
)

# --- Agent loop ---
CONVERSATION_ITERATION_LIMIT = 5
AUTONOMOUS_ITERATION_LIMIT = 50

# --- Timezone ---
TIMEZONE = "America/New_York"

# --- Web server ---
WEB_HOST = os.getenv(
    "TIR_WEB_HOST",
    _env_text("ANAM_API_HOST", _config_value("api", "host")),
)
WEB_PORT = int(
    os.getenv(
        "TIR_WEB_PORT",
        _env_int("ANAM_API_PORT", int(_config_value("api", "port"))),
    )
)
DEFAULT_USER = "Lyle"
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"

# --- Web search ---
SEARXNG_URL = os.getenv(
    "TIR_SEARXNG_URL",
    _env_text("ANAM_SEARXNG_URL", _config_value("web_search", "searxng_url")),
)
WEB_SEARCH_TIMEOUT_SECONDS = float(
    os.getenv(
        "TIR_WEB_SEARCH_TIMEOUT_SECONDS",
        _env_float(
            "ANAM_WEB_SEARCH_TIMEOUT_SECONDS",
            float(_config_value("web_search", "timeout_seconds")),
        ),
    )
)

# --- Scheduler / nightly tick ---
_SCHEDULER_CONFIG = _config_section("scheduler")

SCHEDULER_ENABLED = _env_bool(
    "ANAM_SCHEDULER_ENABLED",
    bool(_SCHEDULER_CONFIG.get("enabled", False)),
)
SCHEDULER_NIGHTLY_TICK_ENABLED = _env_bool(
    "ANAM_SCHEDULER_NIGHTLY_TICK_ENABLED",
    bool(_SCHEDULER_CONFIG.get("nightly_tick_enabled", False)),
)
SCHEDULER_MAX_ACTIONS_PER_TICK = _env_int(
    "ANAM_SCHEDULER_MAX_ACTIONS_PER_TICK",
    int(_SCHEDULER_CONFIG.get("max_actions_per_tick", 1)),
)
SCHEDULER_ALLOW_BOUNDED_RESEARCH = _env_bool(
    "ANAM_SCHEDULER_ALLOW_BOUNDED_RESEARCH",
    bool(_SCHEDULER_CONFIG.get("allow_bounded_research", False)),
)
SCHEDULER_ALLOW_MOLTBOOK = _env_bool(
    "ANAM_SCHEDULER_ALLOW_MOLTBOOK",
    bool(_SCHEDULER_CONFIG.get("allow_moltbook", False)),
)
SCHEDULER_ALLOW_WEB = _env_bool(
    "ANAM_SCHEDULER_ALLOW_WEB",
    bool(_SCHEDULER_CONFIG.get("allow_web", False)),
)
SCHEDULER_ALLOW_IMAGE_GENERATION = _env_bool(
    "ANAM_SCHEDULER_ALLOW_IMAGE_GENERATION",
    bool(_SCHEDULER_CONFIG.get("allow_image_generation", False)),
)
SCHEDULER_GO_LIVE = _env_bool(
    "ANAM_SCHEDULER_GO_LIVE",
    bool(_SCHEDULER_CONFIG.get("go_live", False)),
)

# --- Image generation ---
_IMAGE_GENERATION_CONFIG = _config_section("image_generation")
_COMFYUI_CONFIG = _IMAGE_GENERATION_CONFIG.get("comfyui", {})
if not isinstance(_COMFYUI_CONFIG, dict):
    _COMFYUI_CONFIG = {}

IMAGE_GENERATION_ENABLED = _env_bool(
    "ANAM_IMAGE_GENERATION_ENABLED",
    bool(_IMAGE_GENERATION_CONFIG.get("enabled", False)),
)
IMAGE_GENERATION_DEFAULT_BACKEND = _env_text(
    "ANAM_IMAGE_GENERATION_DEFAULT_BACKEND",
    _IMAGE_GENERATION_CONFIG.get("default_backend", "comfyui"),
)
IMAGE_GENERATION_MAX_PROMPT_CHARS = _env_int(
    "ANAM_IMAGE_GENERATION_MAX_PROMPT_CHARS",
    int(_IMAGE_GENERATION_CONFIG.get("max_prompt_chars", 2000)),
)
IMAGE_GENERATION_MAX_WIDTH = _env_int(
    "ANAM_IMAGE_GENERATION_MAX_WIDTH",
    int(_IMAGE_GENERATION_CONFIG.get("max_width", 2048)),
)
IMAGE_GENERATION_MAX_HEIGHT = _env_int(
    "ANAM_IMAGE_GENERATION_MAX_HEIGHT",
    int(_IMAGE_GENERATION_CONFIG.get("max_height", 2048)),
)
IMAGE_GENERATION_ALLOW_AGENT_TOOL = _env_bool(
    "ANAM_IMAGE_GENERATION_ALLOW_AGENT_TOOL",
    bool(_IMAGE_GENERATION_CONFIG.get("allow_agent_tool", False)),
)
COMFYUI_BASE_URL = _env_text(
    "ANAM_COMFYUI_BASE_URL",
    _COMFYUI_CONFIG.get("base_url", "http://127.0.0.1:8188"),
)
COMFYUI_WORKFLOW_PATH = _env_text(
    "ANAM_COMFYUI_WORKFLOW_PATH",
    _COMFYUI_CONFIG.get(
        "workflow_path",
        "config/comfyui/workflows/default_text_to_image.json",
    ),
)
COMFYUI_TIMEOUT_SECONDS = _env_int(
    "ANAM_COMFYUI_TIMEOUT_SECONDS",
    int(_COMFYUI_CONFIG.get("timeout_seconds", 300)),
)
COMFYUI_POLL_INTERVAL_SECONDS = _env_float(
    "ANAM_COMFYUI_POLL_INTERVAL_SECONDS",
    float(_COMFYUI_CONFIG.get("poll_interval_seconds", 1)),
)
