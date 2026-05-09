from unittest.mock import Mock, patch

import pytest
import requests

from tir.tools.http_declarative import DeclarativeHttpSkillError
from tir.tools.registry import SkillRegistry


def _write_skill(
    root,
    name="example_api",
    skill_yaml=None,
    python_source=None,
):
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        f"""---
name: {name}
description: Example API skill.
version: "1.0"
---

# Example API
""",
        encoding="utf-8",
    )
    if skill_yaml is not None:
        skill_dir.joinpath("skill.yaml").write_text(skill_yaml, encoding="utf-8")
    if python_source is not None:
        skill_dir.joinpath("tool.py").write_text(python_source, encoding="utf-8")
    return skill_dir


def _base_skill_yaml(extra="", query="", headers="", auth=""):
    return f"""version: 1
tools:
  - name: example_status
    description: Get public service status.
    method: GET
    url: https://example.com/api/status
    args_schema:
      type: object
      properties:
        service:
          type: string
      required: []
{query}{headers}{auth}    safety:
      read_only: true
      requires_approval: false
{extra}"""


def _path_skill_yaml(url="https://example.com/api/posts/{post_id}", extra=""):
    return f"""version: 1
tools:
  - name: example_post
    description: Read one post.
    method: GET
    url: {url}
    args_schema:
      type: object
      properties:
        post_id:
          type: string
          minLength: 1
      required: [post_id]
    safety:
      read_only: true
      requires_approval: false
{extra}"""


def _response(
    status_code=200,
    chunks=None,
    headers=None,
    url="https://example.com/api/status",
    encoding="utf-8",
    apparent_encoding=None,
):
    response = Mock()
    response.status_code = status_code
    response.headers = headers if headers is not None else {"Content-Type": "application/json"}
    response.url = url
    response.encoding = encoding
    response.apparent_encoding = apparent_encoding
    response.iter_content.return_value = chunks if chunks is not None else [b'{"ok": true}']
    return response


def test_declarative_skill_loads_and_tool_appears_in_registry(tmp_path):
    _write_skill(tmp_path, skill_yaml=_base_skill_yaml())

    registry = SkillRegistry.from_directory(tmp_path)
    tools = registry.list_tools()

    assert {tool["function"]["name"] for tool in tools} == {"example_status"}
    assert registry.get_skill_for_tool("example_status").name == "example_api"


def test_declarative_freshness_loads_and_marks_tool_description(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: example_status
    description: Get public service status.
    method: GET
    url: https://example.com/api/status
    args_schema:
      type: object
      properties: {}
      required: []
    freshness:
      mode: real_time
      source_of_truth: true
      memory_may_inform_but_not_replace: true
    safety:
      read_only: true
      requires_approval: false
""",
    )

    registry = SkillRegistry.from_directory(tmp_path)
    tool_def = registry._tools["example_status"]

    assert tool_def.freshness == {
        "mode": "real_time",
        "source_of_truth": True,
        "memory_may_inform_but_not_replace": True,
    }
    assert (
        "- example_status [real-time; source-of-truth; memory can provide "
        "context; use live tool results for current state]: Get public service status."
    ) in registry.list_tool_descriptions()


def test_declarative_freshness_unknown_keys_fail_loudly(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: example_status
    description: Get public service status.
    method: GET
    url: https://example.com/api/status
    args_schema:
      type: object
      properties: {}
      required: []
    freshness:
      mode: real_time
      stale_after_seconds: 60
    safety:
      read_only: true
      requires_approval: false
""",
    )

    with pytest.raises(DeclarativeHttpSkillError, match="unknown keys"):
        SkillRegistry.from_directory(tmp_path)


def test_declarative_freshness_invalid_mode_fails_loudly(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: example_status
    description: Get public service status.
    method: GET
    url: https://example.com/api/status
    args_schema:
      type: object
      properties: {}
      required: []
    freshness:
      mode: cached
    safety:
      read_only: true
      requires_approval: false
""",
    )

    with pytest.raises(DeclarativeHttpSkillError, match="mode must be real_time"):
        SkillRegistry.from_directory(tmp_path)


@patch("tir.tools.http_declarative.requests.get")
def test_declarative_tool_successful_mocked_get(mock_get, tmp_path):
    _write_skill(tmp_path, skill_yaml=_base_skill_yaml())
    mock_get.return_value = _response(
        chunks=[b'{"state": "ok"}'],
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {})

    assert result["ok"] is True
    assert result["value"] == {
        "ok": True,
        "status_code": 200,
        "url": "https://example.com/api/status",
        "content_type": "application/json; charset=utf-8",
        "json": {"state": "ok"},
        "text": '{"state": "ok"}',
    }
    mock_get.assert_called_once_with(
        "https://example.com/api/status",
        params=None,
        headers=None,
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_declarative_tool_query_param_mapping(mock_get, tmp_path):
    skill_yaml = _base_skill_yaml(
        query="""    query:
      service: "{service}"
      fixed: "public"
"""
    )
    _write_skill(tmp_path, skill_yaml=skill_yaml)
    mock_get.return_value = _response()
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {"service": "api"})

    assert result["ok"] is True
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["params"] == {
        "service": "api",
        "fixed": "public",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_declarative_tool_args_validation_through_registry(mock_get, tmp_path):
    skill_yaml = """version: 1
tools:
  - name: example_status
    description: Get public service status.
    method: GET
    url: https://example.com/api/status
    args_schema:
      type: object
      properties:
        service:
          type: string
      required: [service]
    query:
      service: "{service}"
    safety:
      read_only: true
      requires_approval: false
"""
    _write_skill(tmp_path, skill_yaml=skill_yaml)
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {})

    assert result["ok"] is False
    assert "Invalid arguments for 'example_status'" in result["error"]
    mock_get.assert_not_called()


@patch("tir.tools.http_declarative.requests.get")
def test_declarative_tool_non_200_response(mock_get, tmp_path):
    _write_skill(tmp_path, skill_yaml=_base_skill_yaml())
    mock_get.return_value = _response(status_code=503)
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {})

    assert result["ok"] is True
    assert result["value"] == {
        "ok": False,
        "error": "HTTP GET returned status 503",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_declarative_tool_timeout_and_connection_failure(mock_get, tmp_path):
    _write_skill(tmp_path, skill_yaml=_base_skill_yaml())
    registry = SkillRegistry.from_directory(tmp_path)

    mock_get.side_effect = requests.Timeout("timed out")
    timeout_result = registry.dispatch("example_status", {})

    mock_get.side_effect = requests.ConnectionError("down")
    connection_result = registry.dispatch("example_status", {})

    assert timeout_result["value"] == {
        "ok": False,
        "error": "HTTP request failed: Timeout: timed out",
    }
    assert connection_result["value"] == {
        "ok": False,
        "error": "HTTP request failed: ConnectionError: down",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_declarative_tool_response_size_cap(mock_get, tmp_path):
    skill_yaml = _base_skill_yaml(extra="      allow_redirects: false\n    max_response_bytes: 1000\n")
    _write_skill(tmp_path, skill_yaml=skill_yaml)
    response = _response(chunks=[b"x" * 700, b"y" * 400])
    mock_get.return_value = response
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {})

    assert result["value"] == {
        "ok": False,
        "error": "HTTP response exceeded 1000 bytes",
    }


def test_malformed_yaml_fails_loudly(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 2
tools: []
""",
    )

    with pytest.raises(DeclarativeHttpSkillError, match="version must be 1"):
        SkillRegistry.from_directory(tmp_path)


def test_unsafe_url_rejected(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: local_status
    description: Bad local status.
    method: GET
    url: http://127.0.0.1/status
    args_schema:
      type: object
      properties: {}
    safety:
      read_only: true
      requires_approval: false
""",
    )

    with pytest.raises(DeclarativeHttpSkillError, match="private or local network"):
        SkillRegistry.from_directory(tmp_path)


def test_unsupported_method_rejected(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: post_status
    description: Bad POST.
    method: POST
    url: https://example.com/api/status
    args_schema:
      type: object
      properties: {}
    safety:
      read_only: true
      requires_approval: false
""",
    )

    with pytest.raises(DeclarativeHttpSkillError, match="only GET is supported"):
        SkillRegistry.from_directory(tmp_path)


def test_duplicate_tool_name_rejected(tmp_path):
    _write_skill(tmp_path, name="one", skill_yaml=_base_skill_yaml())
    _write_skill(tmp_path, name="two", skill_yaml=_base_skill_yaml())

    with pytest.raises(ValueError, match="Duplicate tool name 'example_status'"):
        SkillRegistry.from_directory(tmp_path)


def test_plaintext_secret_looking_header_rejected(tmp_path):
    skill_yaml = _base_skill_yaml(
        headers="""    headers:
      Authorization: "Bearer plaintext"
"""
    )
    _write_skill(tmp_path, skill_yaml=skill_yaml)

    with pytest.raises(DeclarativeHttpSkillError, match="secret headers"):
        SkillRegistry.from_directory(tmp_path)


@patch("tir.tools.http_declarative.requests.get")
def test_env_bearer_auth_success(mock_get, monkeypatch, tmp_path):
    skill_yaml = _base_skill_yaml(
        auth="""    auth:
      type: bearer_env
      env: EXAMPLE_API_TOKEN
"""
    )
    _write_skill(tmp_path, skill_yaml=skill_yaml)
    monkeypatch.setenv("EXAMPLE_API_TOKEN", "super-secret-token")
    mock_get.return_value = _response()
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {})

    assert result["ok"] is True
    assert mock_get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer super-secret-token",
    }
    assert "super-secret-token" not in str(result["value"])


@patch("tir.tools.http_declarative.requests.get")
def test_missing_env_var_returns_ok_false_without_secret_leak(
    mock_get,
    monkeypatch,
    tmp_path,
):
    skill_yaml = _base_skill_yaml(
        auth="""    auth:
      type: bearer_env
      env: EXAMPLE_API_TOKEN
"""
    )
    _write_skill(tmp_path, skill_yaml=skill_yaml)
    monkeypatch.delenv("EXAMPLE_API_TOKEN", raising=False)
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_status", {})

    assert result["ok"] is True
    assert result["value"] == {
        "ok": False,
        "error": "Missing required environment variable: EXAMPLE_API_TOKEN",
    }
    assert "super-secret-token" not in str(result)
    mock_get.assert_not_called()


@patch("tir.tools.http_declarative.requests.get")
def test_path_placeholder_substitution(mock_get, tmp_path):
    _write_skill(tmp_path, skill_yaml=_path_skill_yaml())
    mock_get.return_value = _response()
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_post", {"post_id": "post-123"})

    assert result["ok"] is True
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == "https://example.com/api/posts/post-123"


@patch("tir.tools.http_declarative.requests.get")
def test_path_placeholder_encoding_keeps_slash_inside_segment(mock_get, tmp_path):
    _write_skill(tmp_path, skill_yaml=_path_skill_yaml())
    mock_get.return_value = _response()
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_post", {"post_id": "a/b c"})

    assert result["ok"] is True
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == "https://example.com/api/posts/a%2Fb%20c"


def test_path_placeholders_rejected_outside_path_host(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml=_path_skill_yaml(url="https://{host}/api/posts"),
    )

    with pytest.raises(DeclarativeHttpSkillError, match="only allowed in the URL path"):
        SkillRegistry.from_directory(tmp_path)


def test_path_placeholders_rejected_outside_path_query(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml=_path_skill_yaml(url="https://example.com/api/posts?x={value}"),
    )

    with pytest.raises(DeclarativeHttpSkillError, match="only allowed in the URL path"):
        SkillRegistry.from_directory(tmp_path)


def test_malformed_path_template_braces_rejected(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml=_path_skill_yaml(url="https://example.com/api/posts/{post_id"),
    )

    with pytest.raises(DeclarativeHttpSkillError, match="malformed path template"):
        SkillRegistry.from_directory(tmp_path)


def test_path_placeholder_must_exist_in_args_schema_properties(tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml=_path_skill_yaml(url="https://example.com/api/posts/{missing}"),
    )

    with pytest.raises(DeclarativeHttpSkillError, match="unknown path template argument"):
        SkillRegistry.from_directory(tmp_path)


@patch("tir.tools.http_declarative.requests.get")
def test_unresolved_path_placeholder_fails_without_request(mock_get, tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: example_post
    description: Read one post.
    method: GET
    url: https://example.com/api/posts/{post_id}
    args_schema:
      type: object
      properties:
        post_id:
          type: string
          minLength: 1
      required: []
    safety:
      read_only: true
      requires_approval: false
""",
    )
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_post", {})

    assert result["ok"] is True
    assert result["value"] == {
        "ok": False,
        "error": "Missing argument for path template: post_id",
    }
    mock_get.assert_not_called()


@patch("tir.tools.http_declarative.requests.get")
def test_final_url_safety_validation_runs_after_path_substitution(mock_get, tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml=_path_skill_yaml(url="https://example.com/api/{post_id}"),
    )
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_post", {"post_id": "safe"})

    assert result["ok"] is True
    mock_get.assert_called_once_with(
        "https://example.com/api/safe",
        params=None,
        headers=None,
        timeout=10.0,
        stream=True,
        allow_redirects=False,
    )


@patch("tir.tools.http_declarative.requests.get")
def test_defaults_apply_to_missing_top_level_optional_args(mock_get, tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: example_feed
    description: Read feed.
    method: GET
    url: https://example.com/api/feed
    args_schema:
      type: object
      properties:
        sort:
          type: string
          default: hot
        limit:
          type: integer
          default: 25
      required: []
    query:
      sort: "{sort}"
      limit: "{limit}"
    safety:
      read_only: true
      requires_approval: false
""",
    )
    mock_get.return_value = _response()
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_feed", {})

    assert result["ok"] is True
    assert mock_get.call_args.kwargs["params"] == {
        "sort": "hot",
        "limit": "25",
    }


@patch("tir.tools.http_declarative.requests.get")
def test_explicit_args_override_defaults(mock_get, tmp_path):
    _write_skill(
        tmp_path,
        skill_yaml="""version: 1
tools:
  - name: example_feed
    description: Read feed.
    method: GET
    url: https://example.com/api/feed
    args_schema:
      type: object
      properties:
        sort:
          type: string
          default: hot
        limit:
          type: integer
          default: 25
      required: []
    query:
      sort: "{sort}"
      limit: "{limit}"
    safety:
      read_only: true
      requires_approval: false
""",
    )
    mock_get.return_value = _response()
    registry = SkillRegistry.from_directory(tmp_path)

    result = registry.dispatch("example_feed", {"sort": "new", "limit": 5})

    assert result["ok"] is True
    assert mock_get.call_args.kwargs["params"] == {
        "sort": "new",
        "limit": "5",
    }
