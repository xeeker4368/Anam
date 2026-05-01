import logging
import importlib
from unittest.mock import patch

import run_server
from tir.api.routes import app
import tir.config as config


def test_run_server_creates_configured_log_parent_before_starting(tmp_path):
    data_dir = tmp_path / "missing" / "data"

    with patch.object(run_server, "DATA_DIR", data_dir), \
         patch.object(run_server, "WEB_HOST", "127.0.0.1"), \
         patch.object(run_server, "WEB_PORT", 9123), \
         patch("run_server.uvicorn.run") as mock_run, \
         patch("sys.argv", ["run_server.py"]):
        run_server.main()

    assert (data_dir / "tir.log").parent.exists()
    mock_run.assert_called_once_with(
        "tir.api.routes:app",
        host="127.0.0.1",
        port=9123,
        reload=False,
        log_level="info",
    )

    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()


def test_default_web_host_is_local_only(monkeypatch):
    monkeypatch.delenv("TIR_WEB_HOST", raising=False)
    reloaded_config = importlib.reload(config)

    assert reloaded_config.WEB_HOST == "127.0.0.1"


def test_web_host_can_opt_into_lan_binding(monkeypatch):
    monkeypatch.setenv("TIR_WEB_HOST", "0.0.0.0")
    reloaded_config = importlib.reload(config)

    assert reloaded_config.WEB_HOST == "0.0.0.0"


def test_cors_includes_localhost_and_loopback_dev_origins():
    cors_middleware = next(
        middleware for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )

    assert "http://localhost:5173" in cors_middleware.kwargs["allow_origins"]
    assert "http://127.0.0.1:5173" in cors_middleware.kwargs["allow_origins"]
