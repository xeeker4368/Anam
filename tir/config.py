"""
Tír Configuration

Paths, model settings, and tuning knobs.
All configuration in one place.
"""

import os
from pathlib import Path

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "prod"
ARCHIVE_DB = DATA_DIR / "archive.db"
WORKING_DB = DATA_DIR / "working.db"
CHROMA_DIR = str(DATA_DIR / "chromadb")
SKILLS_DIR = PROJECT_ROOT / "skills" / "active"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"

# --- Ollama ---
OLLAMA_HOST = "http://localhost:11434"
CHAT_MODEL = "gemma4:26b"
EMBED_MODEL = "nomic-embed-text"

# --- Chunking ---
CHUNK_TURN_SIZE = 5          # Turns per conversation chunk
EMBED_MAX_CHARS = 8000       # Max chars before embedding truncation

# --- Retrieval ---
RETRIEVAL_RESULTS = 20       # Candidates returned by retrieval pipeline
DISTANCE_THRESHOLD = 0.8     # Max cosine distance for vector results
RRF_K = 60                   # RRF fusion constant
TRUST_WEIGHTS = {
    "firsthand": 1.0,
    "secondhand": 0.85,
    "thirdhand": 0.7,
}

# --- Context budget ---
CONTEXT_WINDOW = 131072      # gemma4:26b with num_ctx=128K
OUTPUT_RESERVE = 4096        # Tokens reserved for response
RETRIEVAL_FLOOR = 3          # Minimum chunks to surface
RETRIEVAL_CEILING = 15       # Maximum chunks to surface
RETRIEVAL_DEFAULT = 8        # Default chunks when budget allows

# --- Agent loop ---
CONVERSATION_ITERATION_LIMIT = 5
AUTONOMOUS_ITERATION_LIMIT = 50

# --- Timezone ---
TIMEZONE = "America/New_York"

# --- Web server ---
WEB_HOST = os.getenv("TIR_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("TIR_WEB_PORT", "8000"))
DEFAULT_USER = "Lyle"
FRONTEND_DIR = PROJECT_ROOT / "frontend" / "dist"

# --- Web search ---
SEARXNG_URL = os.getenv("TIR_SEARXNG_URL", "http://127.0.0.1:8080")
WEB_SEARCH_TIMEOUT_SECONDS = float(os.getenv("TIR_WEB_SEARCH_TIMEOUT_SECONDS", "10"))
