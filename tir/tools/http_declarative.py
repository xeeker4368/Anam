"""Declarative read-only HTTP skill support.

This module validates local ``skill.yaml`` files and builds callable wrappers
for simple, safe GET-only HTTP tools.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

import jsonschema
import requests
import yaml


DEFAULT_TIMEOUT_SECONDS = 10.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 200_000
MIN_MAX_RESPONSE_BYTES = 1_000
MAX_MAX_RESPONSE_BYTES = 2_000_000

_TEMPLATE_RE = re.compile(r"{([A-Za-z_][A-Za-z0-9_]*)}")
_SECRET_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
}
_SECRET_VALUE_PATTERNS = (
    "bearer ",
    "api_key",
    "apikey",
    "access_token",
    "secret",
)


class DeclarativeHttpSkillError(ValueError):
    """Raised when a declarative HTTP skill definition is invalid."""


@dataclass(frozen=True)
class DeclarativeHttpToolSpec:
    name: str
    description: str
    args_schema: dict
    function: callable


@dataclass(frozen=True)
class _AuthConfig:
    type: str
    env: str
    header: str | None = None


@dataclass(frozen=True)
class _HttpToolConfig:
    name: str
    description: str
    method: str
    url: str
    args_schema: dict
    query: dict[str, str]
    headers: dict[str, str]
    auth: _AuthConfig | None
    timeout_seconds: float
    max_response_bytes: int
    path_placeholders: tuple[str, ...]


class DeclarativeHttpTool:
    """Callable wrapper for one validated declarative HTTP GET tool."""

    def __init__(self, config: _HttpToolConfig):
        self.config = config

    def __call__(self, **kwargs) -> dict:
        args = _apply_top_level_defaults(self.config.args_schema, kwargs)
        auth_headers, auth_error = _build_auth_headers(self.config.auth)
        if auth_error:
            return {"ok": False, "error": auth_error}

        url, url_error = _build_request_url(
            self.config.url,
            self.config.path_placeholders,
            args,
        )
        if url_error:
            return {"ok": False, "error": url_error}

        query_params, query_error = _build_query_params(self.config.query, args)
        if query_error:
            return {"ok": False, "error": query_error}

        headers = dict(self.config.headers)
        headers.update(auth_headers)

        try:
            response = requests.get(
                url,
                params=query_params or None,
                headers=headers or None,
                timeout=self.config.timeout_seconds,
                stream=True,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            return {
                "ok": False,
                "error": f"HTTP request failed: {type(exc).__name__}: {exc}",
            }

        if response.status_code != 200:
            return {
                "ok": False,
                "error": f"HTTP GET returned status {response.status_code}",
            }

        try:
            response_bytes = _read_response_bytes(
                response,
                self.config.max_response_bytes,
            )
        except (requests.RequestException, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        content_type = response.headers.get("Content-Type", "")
        text = _decode_response(response_bytes, response)
        parsed_json = None
        if _is_json_content_type(content_type):
            try:
                parsed_json = json.loads(text) if text else None
            except json.JSONDecodeError:
                parsed_json = None

        return {
            "ok": True,
            "status_code": response.status_code,
            "url": response.url or url,
            "content_type": content_type,
            "json": parsed_json,
            "text": text,
        }


def load_declarative_http_tools(skill_yaml_path: str | Path) -> list[DeclarativeHttpToolSpec]:
    """Load and validate declarative HTTP tools from a local skill.yaml file."""
    path = Path(skill_yaml_path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DeclarativeHttpSkillError(f"{path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise DeclarativeHttpSkillError(f"{path}: skill.yaml must be a mapping")
    if raw.get("version") != 1:
        raise DeclarativeHttpSkillError(f"{path}: version must be 1")

    tools = raw.get("tools")
    if not isinstance(tools, list) or not tools:
        raise DeclarativeHttpSkillError(f"{path}: tools must be a non-empty list")

    specs = []
    seen_names = set()
    for index, tool_config in enumerate(tools):
        if not isinstance(tool_config, dict):
            raise DeclarativeHttpSkillError(f"{path}: tools[{index}] must be a mapping")

        config = _validate_tool_config(path, index, tool_config)
        if config.name in seen_names:
            raise DeclarativeHttpSkillError(
                f"{path}: duplicate declarative tool name '{config.name}'"
            )
        seen_names.add(config.name)

        specs.append(
            DeclarativeHttpToolSpec(
                name=config.name,
                description=config.description,
                args_schema=config.args_schema,
                function=DeclarativeHttpTool(config),
            )
        )

    return specs


def _validate_tool_config(path: Path, index: int, raw: dict) -> _HttpToolConfig:
    prefix = f"{path}: tools[{index}]"

    name = _require_nonempty_string(raw, "name", prefix)
    description = _require_nonempty_string(raw, "description", prefix)
    method = _require_nonempty_string(raw, "method", prefix).upper()
    if method != "GET":
        raise DeclarativeHttpSkillError(f"{prefix}.method: only GET is supported")

    url = _require_nonempty_string(raw, "url", prefix)
    _validate_url(url, f"{prefix}.url")

    args_schema = raw.get("args_schema")
    if not isinstance(args_schema, dict):
        raise DeclarativeHttpSkillError(f"{prefix}.args_schema must be a mapping")
    try:
        jsonschema.Draft7Validator.check_schema(args_schema)
    except jsonschema.SchemaError as exc:
        raise DeclarativeHttpSkillError(
            f"{prefix}.args_schema is not a valid JSON schema: {exc.message}"
        ) from exc

    query = _validate_string_mapping(raw.get("query", {}), f"{prefix}.query")
    path_placeholders = _validate_path_templates(url, args_schema, f"{prefix}.url")
    _validate_query_templates(query, args_schema, f"{prefix}.query")

    headers = _validate_string_mapping(raw.get("headers", {}), f"{prefix}.headers")
    _validate_static_headers(headers, f"{prefix}.headers")

    auth = _validate_auth(raw.get("auth"), f"{prefix}.auth")
    timeout_seconds = _validate_float(
        raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        f"{prefix}.timeout_seconds",
        MIN_TIMEOUT_SECONDS,
        MAX_TIMEOUT_SECONDS,
    )
    max_response_bytes = int(
        _validate_float(
            raw.get("max_response_bytes", DEFAULT_MAX_RESPONSE_BYTES),
            f"{prefix}.max_response_bytes",
            MIN_MAX_RESPONSE_BYTES,
            MAX_MAX_RESPONSE_BYTES,
        )
    )
    _validate_safety(raw.get("safety"), f"{prefix}.safety")

    return _HttpToolConfig(
        name=name,
        description=description,
        method=method,
        url=url,
        args_schema=args_schema,
        query=query,
        headers=headers,
        auth=auth,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        path_placeholders=path_placeholders,
    )


def _require_nonempty_string(raw: dict, key: str, prefix: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DeclarativeHttpSkillError(f"{prefix}.{key} must be a non-empty string")
    return value.strip()


def _validate_string_mapping(value, prefix: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise DeclarativeHttpSkillError(f"{prefix} must be a mapping")

    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise DeclarativeHttpSkillError(f"{prefix} keys must be non-empty strings")
        if not isinstance(item, str):
            raise DeclarativeHttpSkillError(f"{prefix}.{key} must be a string")
        result[key.strip()] = item
    return result


def _validate_url(url: str, prefix: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise DeclarativeHttpSkillError(f"{prefix}: only http and https URLs are allowed")
    if not parsed.netloc or not parsed.hostname:
        raise DeclarativeHttpSkillError(f"{prefix}: URL must be absolute with a hostname")
    if parsed.username or parsed.password:
        raise DeclarativeHttpSkillError(f"{prefix}: URLs with embedded credentials are rejected")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise DeclarativeHttpSkillError(f"{prefix}: localhost URLs are rejected")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return

    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise DeclarativeHttpSkillError(
            f"{prefix}: private or local network IP URLs are rejected"
        )


def _find_unbalanced_braces(value: str) -> bool:
    return "{" in _TEMPLATE_RE.sub("", value) or "}" in _TEMPLATE_RE.sub("", value)


def _validate_path_templates(
    url: str,
    args_schema: dict,
    prefix: str,
) -> tuple[str, ...]:
    parsed = urlparse(url)
    non_path_parts = {
        "scheme": parsed.scheme,
        "netloc": parsed.netloc,
        "params": parsed.params,
        "query": parsed.query,
        "fragment": parsed.fragment,
    }
    for part_name, part_value in non_path_parts.items():
        if "{" in part_value or "}" in part_value:
            raise DeclarativeHttpSkillError(
                f"{prefix}: placeholders are only allowed in the URL path "
                f"(found in {part_name})"
            )

    if _find_unbalanced_braces(parsed.path):
        raise DeclarativeHttpSkillError(f"{prefix}: malformed path template")

    properties = args_schema.get("properties", {})
    if properties is None:
        properties = {}
    if not isinstance(properties, dict):
        raise DeclarativeHttpSkillError(f"{prefix}: args_schema.properties must be a mapping")

    placeholders = tuple(dict.fromkeys(_TEMPLATE_RE.findall(parsed.path)))
    for placeholder in placeholders:
        if placeholder not in properties:
            raise DeclarativeHttpSkillError(
                f"{prefix}: unknown path template argument '{placeholder}'"
            )

    return placeholders


def _validate_query_templates(
    query: dict[str, str],
    args_schema: dict,
    prefix: str,
) -> None:
    properties = args_schema.get("properties", {})
    if properties is None:
        properties = {}
    if not isinstance(properties, dict):
        raise DeclarativeHttpSkillError(f"{prefix}: args_schema.properties must be a mapping")

    for param_name, template in query.items():
        placeholders = _TEMPLATE_RE.findall(template)
        if _find_unbalanced_braces(template):
            raise DeclarativeHttpSkillError(
                f"{prefix}.{param_name}: invalid template syntax"
            )
        for placeholder in placeholders:
            if placeholder not in properties:
                raise DeclarativeHttpSkillError(
                    f"{prefix}.{param_name}: unknown argument '{placeholder}'"
                )


def _validate_static_headers(headers: dict[str, str], prefix: str) -> None:
    for name, value in headers.items():
        lowered_name = name.lower()
        lowered_value = value.lower()
        if lowered_name in _SECRET_HEADER_NAMES:
            raise DeclarativeHttpSkillError(
                f"{prefix}.{name}: secret headers must use env auth references"
            )
        if any(pattern in lowered_value for pattern in _SECRET_VALUE_PATTERNS):
            raise DeclarativeHttpSkillError(
                f"{prefix}.{name}: secret-looking header values are rejected"
            )


def _validate_auth(value, prefix: str) -> _AuthConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise DeclarativeHttpSkillError(f"{prefix} must be a mapping")

    auth_type = value.get("type")
    env = value.get("env")
    if not isinstance(auth_type, str) or not auth_type.strip():
        raise DeclarativeHttpSkillError(f"{prefix}.type must be a non-empty string")
    if not isinstance(env, str) or not env.strip():
        raise DeclarativeHttpSkillError(f"{prefix}.env must be a non-empty string")

    auth_type = auth_type.strip()
    env = env.strip()
    if auth_type == "bearer_env":
        return _AuthConfig(type=auth_type, env=env)
    if auth_type == "header_env":
        header = value.get("header")
        if not isinstance(header, str) or not header.strip():
            raise DeclarativeHttpSkillError(
                f"{prefix}.header must be a non-empty string for header_env"
            )
        return _AuthConfig(type=auth_type, env=env, header=header.strip())

    raise DeclarativeHttpSkillError(
        f"{prefix}.type: supported values are bearer_env and header_env"
    )


def _validate_float(value, prefix: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DeclarativeHttpSkillError(f"{prefix} must be a number") from exc
    if number < minimum or number > maximum:
        raise DeclarativeHttpSkillError(
            f"{prefix} must be between {minimum:g} and {maximum:g}"
        )
    return number


def _validate_safety(value, prefix: str) -> None:
    if not isinstance(value, dict):
        raise DeclarativeHttpSkillError(f"{prefix} must be a mapping")
    if value.get("read_only") is not True:
        raise DeclarativeHttpSkillError(f"{prefix}.read_only must be true")
    if value.get("requires_approval") is not False:
        raise DeclarativeHttpSkillError(f"{prefix}.requires_approval must be false")
    if value.get("allow_redirects", False) is not False:
        raise DeclarativeHttpSkillError(f"{prefix}.allow_redirects must be false")


def _build_auth_headers(auth: _AuthConfig | None) -> tuple[dict[str, str], str | None]:
    if auth is None:
        return {}, None

    secret = os.getenv(auth.env)
    if secret is None:
        return {}, f"Missing required environment variable: {auth.env}"

    if auth.type == "bearer_env":
        return {"Authorization": f"Bearer {secret}"}, None
    if auth.type == "header_env":
        return {auth.header or "Authorization": secret}, None

    return {}, "Unsupported auth configuration"


def _build_query_params(
    query: dict[str, str],
    args: dict,
) -> tuple[dict[str, str], str | None]:
    params = {}
    for key, template in query.items():
        missing = [
            placeholder
            for placeholder in _TEMPLATE_RE.findall(template)
            if placeholder not in args
        ]
        if missing:
            return {}, f"Missing argument for query template: {missing[0]}"

        value = template
        for placeholder in _TEMPLATE_RE.findall(template):
            value = value.replace("{" + placeholder + "}", str(args[placeholder]))
        params[key] = value

    return params, None


def _apply_top_level_defaults(args_schema: dict, args: dict) -> dict:
    result = dict(args)
    properties = args_schema.get("properties", {})
    if not isinstance(properties, dict):
        return result

    for key, schema in properties.items():
        if key in result:
            continue
        if isinstance(schema, dict) and "default" in schema:
            result[key] = schema["default"]

    return result


def _build_request_url(
    template_url: str,
    path_placeholders: tuple[str, ...],
    args: dict,
) -> tuple[str | None, str | None]:
    if not path_placeholders:
        return template_url, None

    parsed = urlparse(template_url)
    path = parsed.path
    for placeholder in path_placeholders:
        if placeholder not in args:
            return None, f"Missing argument for path template: {placeholder}"
        encoded = quote(str(args[placeholder]), safe="")
        path = path.replace("{" + placeholder + "}", encoded)

    if "{" in path or "}" in path:
        return None, "Unresolved URL path template placeholder"

    final_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    try:
        _validate_url(final_url, "resolved URL")
    except DeclarativeHttpSkillError as exc:
        return None, str(exc)

    return final_url, None


def _read_response_bytes(response, max_response_bytes: int) -> bytes:
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_response_bytes:
            raise ValueError(f"HTTP response exceeded {max_response_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_response(content: bytes, response) -> str:
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def _is_json_content_type(content_type: str) -> bool:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")
