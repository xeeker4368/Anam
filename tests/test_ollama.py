import json

from tir.engine import ollama


class _Response:
    def __init__(self, payload=None, lines=None):
        self.payload = payload or {"message": {"content": "ok"}}
        self.lines = lines or []

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload

    def iter_lines(self):
        for line in self.lines:
            yield line


def test_chat_completion_json_sends_top_level_think_and_timeout(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return _Response({"message": {"content": '{"ok": true}'}})

    monkeypatch.setattr(ollama.requests, "post", fake_post)
    monkeypatch.setattr(
        ollama,
        "get_model_options",
        lambda role: {"think": False, "temperature": 0.35},
    )
    monkeypatch.setattr(ollama, "get_model_timeout", lambda role: 456)

    result = ollama.chat_completion_json(
        [{"role": "system", "content": "return json"}],
        model="override-model",
        ollama_host="http://ollama",
        role="behavioral_guidance_review",
    )

    assert result == '{"ok": true}'
    assert captured["url"] == "http://ollama/api/chat"
    assert captured["timeout"] == 456
    assert captured["json"]["model"] == "override-model"
    assert captured["json"]["think"] is False
    assert captured["json"]["options"] == {"temperature": 0.35}
    assert "think" not in captured["json"].get("options", {})
    assert "temperature" not in captured["json"]


def test_chat_completion_text_preserves_role_options_with_model_override(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _Response({"message": {"content": "journal"}})

    monkeypatch.setattr(ollama.requests, "post", fake_post)
    monkeypatch.setattr(
        ollama,
        "get_model_options",
        lambda role: {"think": False, "temperature": 0.2, "timeout_seconds": 600},
    )
    monkeypatch.setattr(ollama, "get_model_timeout", lambda role: 600)

    result = ollama.chat_completion_text(
        [{"role": "user", "content": "write"}],
        model="qwen3.6:27b",
        role="reflection_journal",
    )

    assert result == "journal"
    assert captured["json"]["model"] == "qwen3.6:27b"
    assert captured["json"]["think"] is False
    assert captured["json"]["options"] == {"temperature": 0.2}
    assert captured["timeout"] == 600


def test_streaming_chat_uses_top_level_think(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return _Response(
            lines=[
                json.dumps({"message": {"content": "hello"}, "done": False}).encode(),
                json.dumps({"message": {"content": ""}, "done": True}).encode(),
            ]
        )

    monkeypatch.setattr(ollama.requests, "post", fake_post)
    monkeypatch.setattr(
        ollama,
        "get_model_options",
        lambda role: {"think": False, "temperature": 0.35},
    )
    monkeypatch.setattr(ollama, "get_model_timeout", lambda role: 300)

    chunks = list(
        ollama.chat_completion_stream_with_tools(
            system_prompt="system",
            messages=[{"role": "user", "content": "hi"}],
            model="chat-model",
            role="chat",
        )
    )

    assert chunks[0]["message"]["content"] == "hello"
    assert captured["stream"] is True
    assert captured["timeout"] == 300
    assert captured["json"]["think"] is False
    assert captured["json"]["options"] == {"temperature": 0.35}
    assert "think" not in captured["json"].get("options", {})
