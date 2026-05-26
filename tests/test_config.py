import importlib
import os
import sys


CONFIG_ENV_VARS = [
    "ANAM_API_HOST",
    "ANAM_API_PORT",
    "ANAM_BEHAVIORAL_GUIDANCE_REVIEW_MODEL",
    "ANAM_BEHAVIORAL_GUIDANCE_REVIEW_MODEL_THINK",
    "ANAM_CHAT_MODEL",
    "ANAM_CHAT_MODEL_THINK",
    "ANAM_EMBED_MODEL",
    "ANAM_COMFYUI_BASE_URL",
    "ANAM_COMFYUI_POLL_INTERVAL_SECONDS",
    "ANAM_COMFYUI_TIMEOUT_SECONDS",
    "ANAM_COMFYUI_WORKFLOW_PATH",
    "ANAM_IMAGE_GENERATION_ALLOW_AGENT_TOOL",
    "ANAM_IMAGE_GENERATION_DEFAULT_BACKEND",
    "ANAM_IMAGE_GENERATION_ENABLED",
    "ANAM_IMAGE_GENERATION_MAX_HEIGHT",
    "ANAM_IMAGE_GENERATION_MAX_PROMPT_CHARS",
    "ANAM_IMAGE_GENERATION_MAX_WIDTH",
    "ANAM_MODEL_TEMPERATURE",
    "ANAM_MODEL_THINK",
    "ANAM_OLLAMA_HOST",
    "ANAM_OLLAMA_TIMEOUT_SECONDS",
    "ANAM_OPERATIONAL_REFLECTION_MODEL",
    "ANAM_OPERATIONAL_REFLECTION_MODEL_THINK",
    "ANAM_REFLECTION_JOURNAL_MODEL",
    "ANAM_REFLECTION_JOURNAL_MODEL_THINK",
    "ANAM_REFLECTION_JOURNAL_TIMEOUT_SECONDS",
    "ANAM_SCHEDULER_ALLOW_BOUNDED_RESEARCH",
    "ANAM_SCHEDULER_ALLOW_IMAGE_GENERATION",
    "ANAM_SCHEDULER_ALLOW_MOLTBOOK",
    "ANAM_SCHEDULER_ALLOW_WEB",
    "ANAM_SCHEDULER_ENABLED",
    "ANAM_SCHEDULER_MAX_ACTIONS_PER_TICK",
    "ANAM_SCHEDULER_NIGHTLY_TICK_ENABLED",
    "ANAM_SEARXNG_URL",
    "ANAM_WEB_SEARCH_TIMEOUT_SECONDS",
    "TIR_SEARXNG_URL",
    "TIR_WEB_HOST",
    "TIR_WEB_PORT",
    "TIR_WEB_SEARCH_TIMEOUT_SECONDS",
]


def _reload_config(monkeypatch, config_dir, *, clear_env=True):
    monkeypatch.setenv("ANAM_CONFIG_DIR", str(config_dir))
    if clear_env:
        for name in CONFIG_ENV_VARS:
            monkeypatch.delenv(name, raising=False)
    import tir.config as config

    return importlib.reload(config)


def test_missing_config_files_use_code_fallbacks(tmp_path, monkeypatch):
    config = _reload_config(monkeypatch, tmp_path)

    assert config.CHAT_MODEL == "gemma4:26b"
    assert config.REFLECTION_JOURNAL_MODEL == "gemma4:26b"
    assert config.BEHAVIORAL_GUIDANCE_REVIEW_MODEL == "gemma4:26b"
    assert config.OPERATIONAL_REFLECTION_MODEL == "gemma4:26b"
    assert config.EMBED_MODEL == "nomic-embed-text"
    assert config.OLLAMA_HOST == "http://localhost:11434"
    assert config.OLLAMA_TIMEOUT_SECONDS == 300
    assert config.IMAGE_GENERATION_ENABLED is False
    assert config.IMAGE_GENERATION_DEFAULT_BACKEND == "comfyui"
    assert config.IMAGE_GENERATION_MAX_PROMPT_CHARS == 2000
    assert config.IMAGE_GENERATION_MAX_WIDTH == 2048
    assert config.IMAGE_GENERATION_MAX_HEIGHT == 2048
    assert config.IMAGE_GENERATION_ALLOW_AGENT_TOOL is False
    assert config.COMFYUI_BASE_URL == "http://127.0.0.1:8188"
    assert config.SCHEDULER_ENABLED is False
    assert config.SCHEDULER_NIGHTLY_TICK_ENABLED is False
    assert config.SCHEDULER_MAX_ACTIONS_PER_TICK == 1
    assert config.SCHEDULER_ALLOW_BOUNDED_RESEARCH is False
    assert config.SCHEDULER_ALLOW_MOLTBOOK is False
    assert config.SCHEDULER_ALLOW_WEB is False
    assert config.SCHEDULER_ALLOW_IMAGE_GENERATION is False
    assert config.get_model_options("chat")["think"] is False
    assert config.get_model_options("chat")["temperature"] == 0.35


def test_defaults_and_local_config_precedence(tmp_path, monkeypatch):
    (tmp_path / "defaults.toml").write_text(
        """
[models]
chat = "default-chat"
reflection_journal = "default-journal"

[ollama]
host = "http://defaults:11434"

[model_options.default]
think = false
temperature = 0.4

[model_options.reflection_journal]
think = false
timeout_seconds = 600
""",
        encoding="utf-8",
    )
    (tmp_path / "local.toml").write_text(
        """
[models]
chat = "local-chat"

[ollama]
host = "http://local:11434"

[model_options.reflection_journal]
think = true
timeout_seconds = 900
""",
        encoding="utf-8",
    )

    config = _reload_config(monkeypatch, tmp_path)

    assert config.CHAT_MODEL == "local-chat"
    assert config.REFLECTION_JOURNAL_MODEL == "default-journal"
    assert config.OLLAMA_HOST == "http://local:11434"
    assert config.get_model_options("reflection_journal")["think"] is True
    assert config.get_model_options("reflection_journal")["temperature"] == 0.4
    assert config.get_model_options("chat")["temperature"] == 0.4
    assert config.get_model_timeout("reflection_journal") == 900


def test_environment_overrides_config_files(tmp_path, monkeypatch):
    (tmp_path / "defaults.toml").write_text(
        """
[models]
chat = "default-chat"
reflection_journal = "default-journal"
embedding = "default-embed"

[ollama]
host = "http://defaults:11434"
timeout_seconds = 100

[model_options.default]
think = false
temperature = 0.4

[model_options.reflection_journal]
think = true
timeout_seconds = 900

[api]
host = "127.0.0.1"
port = 8000

[web_search]
searxng_url = "http://defaults:8080"
timeout_seconds = 10

[image_generation]
enabled = false
default_backend = "comfyui"
max_prompt_chars = 1000
max_width = 1024
max_height = 1024
allow_agent_tool = false

[image_generation.comfyui]
base_url = "http://127.0.0.1:8188"
workflow_path = "config/comfyui/default.json"
timeout_seconds = 100
poll_interval_seconds = 1
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("ANAM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ANAM_CHAT_MODEL", "env-chat")
    monkeypatch.setenv("ANAM_REFLECTION_JOURNAL_MODEL", "env-journal")
    monkeypatch.setenv("ANAM_EMBED_MODEL", "env-embed")
    monkeypatch.setenv("ANAM_OLLAMA_HOST", "http://env:11434")
    monkeypatch.setenv("ANAM_OLLAMA_TIMEOUT_SECONDS", "321")
    monkeypatch.setenv("ANAM_MODEL_THINK", "false")
    monkeypatch.setenv("ANAM_MODEL_TEMPERATURE", "0.22")
    monkeypatch.setenv("ANAM_REFLECTION_JOURNAL_MODEL_THINK", "true")
    monkeypatch.setenv("ANAM_REFLECTION_JOURNAL_TIMEOUT_SECONDS", "654")
    monkeypatch.setenv("ANAM_API_HOST", "0.0.0.0")
    monkeypatch.setenv("ANAM_API_PORT", "8123")
    monkeypatch.setenv("ANAM_SEARXNG_URL", "http://env:8080")
    monkeypatch.setenv("ANAM_WEB_SEARCH_TIMEOUT_SECONDS", "4.5")
    monkeypatch.setenv("ANAM_IMAGE_GENERATION_ENABLED", "true")
    monkeypatch.setenv("ANAM_IMAGE_GENERATION_MAX_PROMPT_CHARS", "111")
    monkeypatch.setenv("ANAM_IMAGE_GENERATION_MAX_WIDTH", "222")
    monkeypatch.setenv("ANAM_IMAGE_GENERATION_MAX_HEIGHT", "333")
    monkeypatch.setenv("ANAM_IMAGE_GENERATION_ALLOW_AGENT_TOOL", "false")
    monkeypatch.setenv("ANAM_COMFYUI_BASE_URL", "http://localhost:8188")
    monkeypatch.setenv("ANAM_COMFYUI_WORKFLOW_PATH", "config/comfyui/env.json")
    monkeypatch.setenv("ANAM_COMFYUI_TIMEOUT_SECONDS", "44")
    monkeypatch.setenv("ANAM_COMFYUI_POLL_INTERVAL_SECONDS", "0.5")
    import tir.config as config

    config = importlib.reload(config)

    assert config.CHAT_MODEL == "env-chat"
    assert config.REFLECTION_JOURNAL_MODEL == "env-journal"
    assert config.EMBED_MODEL == "env-embed"
    assert config.OLLAMA_HOST == "http://env:11434"
    assert config.OLLAMA_TIMEOUT_SECONDS == 321
    assert config.get_model_options("chat")["think"] is False
    assert config.get_model_options("chat")["temperature"] == 0.22
    assert config.get_model_options("reflection_journal")["think"] is True
    assert config.get_model_options("reflection_journal")["temperature"] == 0.22
    assert config.get_model_timeout("reflection_journal") == 654
    assert config.WEB_HOST == "0.0.0.0"
    assert config.WEB_PORT == 8123
    assert config.SEARXNG_URL == "http://env:8080"
    assert config.WEB_SEARCH_TIMEOUT_SECONDS == 4.5
    assert config.IMAGE_GENERATION_ENABLED is True
    assert config.IMAGE_GENERATION_MAX_PROMPT_CHARS == 111
    assert config.IMAGE_GENERATION_MAX_WIDTH == 222
    assert config.IMAGE_GENERATION_MAX_HEIGHT == 333
    assert config.IMAGE_GENERATION_ALLOW_AGENT_TOOL is False
    assert config.COMFYUI_BASE_URL == "http://localhost:8188"
    assert config.COMFYUI_WORKFLOW_PATH == "config/comfyui/env.json"
    assert config.COMFYUI_TIMEOUT_SECONDS == 44
    assert config.COMFYUI_POLL_INTERVAL_SECONDS == 0.5


def test_legacy_tir_environment_variables_still_work(tmp_path, monkeypatch):
    monkeypatch.setenv("ANAM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("TIR_WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("TIR_WEB_PORT", "9999")
    monkeypatch.setenv("TIR_SEARXNG_URL", "http://tir:8080")
    monkeypatch.setenv("TIR_WEB_SEARCH_TIMEOUT_SECONDS", "7")
    import tir.config as config

    config = importlib.reload(config)

    assert config.WEB_HOST == "0.0.0.0"
    assert config.WEB_PORT == 9999
    assert config.SEARXNG_URL == "http://tir:8080"
    assert config.WEB_SEARCH_TIMEOUT_SECONDS == 7.0


def test_anam_api_secret_remains_env_only(tmp_path, monkeypatch):
    (tmp_path / "local.toml").write_text(
        """
[api]
secret = "not-used"
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("ANAM_API_SECRET", raising=False)
    _reload_config(monkeypatch, tmp_path, clear_env=False)
    sys.modules.pop("tir.api.auth", None)
    import tir.api.auth as auth

    assert auth.is_api_secret_configured() is False
    monkeypatch.setenv("ANAM_API_SECRET", "env-secret")
    assert auth.verify_api_secret("env-secret") is True


def test_invalid_model_temperature_env_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("ANAM_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("ANAM_MODEL_TEMPERATURE", "not-a-float")
    import tir.config as config

    config = importlib.reload(config)

    try:
        config.get_model_options("chat")
    except ValueError as exc:
        assert "could not convert string to float" in str(exc)
    else:
        raise AssertionError("Expected invalid ANAM_MODEL_TEMPERATURE to fail")


def test_committed_defaults_keep_one_primary_model_and_global_temperature(monkeypatch):
    monkeypatch.delenv("ANAM_CONFIG_DIR", raising=False)
    import tomllib
    from pathlib import Path

    defaults = tomllib.loads(
        Path("config/defaults.toml").read_text(encoding="utf-8")
    )

    model_names = {
        defaults["models"]["chat"],
        defaults["models"]["reflection_journal"],
        defaults["models"]["behavioral_guidance_review"],
        defaults["models"]["operational_reflection"],
    }
    assert model_names == {"gemma4:26b"}
    assert defaults["model_options"]["default"]["temperature"] == 0.35
    assert "temperature" not in defaults["model_options"]["chat"]
    assert "temperature" not in defaults["model_options"]["reflection_journal"]
    assert "temperature" not in defaults["model_options"]["behavioral_guidance_review"]
    assert "temperature" not in defaults["model_options"]["operational_reflection"]
