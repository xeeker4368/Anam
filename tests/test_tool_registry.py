from tir.tools.registry import SkillRegistry, ToolDefinition, tool


def _registry_with_tool(name, function, args_schema=None):
    registry = SkillRegistry()
    registry._tools[name] = ToolDefinition(
        name=name,
        description=f"{name} test tool",
        args_schema=args_schema or {"type": "object", "properties": {}},
        function=function,
        skill_name="test",
    )
    registry._tool_to_skill[name] = "test"
    return registry


def test_python_tool_decorator_stores_freshness_metadata():
    @tool(
        name="current_status",
        description="Read current status.",
        args_schema={"type": "object", "properties": {}},
        freshness={
            "mode": "real_time",
            "source_of_truth": True,
            "memory_may_inform_but_not_replace": True,
        },
    )
    def current_status():
        return "ok"

    metadata = current_status._tool_metadata
    assert metadata["freshness"] == {
        "mode": "real_time",
        "source_of_truth": True,
        "memory_may_inform_but_not_replace": True,
    }


def test_tool_descriptions_include_realtime_source_of_truth_marker():
    registry = SkillRegistry()
    registry._tools["current_status"] = ToolDefinition(
        name="current_status",
        description="Read current status.",
        args_schema={"type": "object", "properties": {}},
        function=lambda: "ok",
        skill_name="test",
        freshness={
            "mode": "real_time",
            "source_of_truth": True,
            "memory_may_inform_but_not_replace": True,
        },
    )
    registry._tools["memory_search"] = ToolDefinition(
        name="memory_search",
        description="Search memories.",
        args_schema={"type": "object", "properties": {}},
        function=lambda: "ok",
        skill_name="test",
    )

    descriptions = registry.list_tool_descriptions()

    assert (
        "- current_status [real-time; source-of-truth; memory may inform "
        "but not replace]: Read current status."
    ) in descriptions
    assert "- memory_search: Search memories." in descriptions


def test_tool_accepting_context_receives_it():
    context = object()

    def context_tool(value, _context=None):
        return {"value": value, "has_context": _context is context}

    registry = _registry_with_tool(
        "context_tool",
        context_tool,
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    )

    result = registry.dispatch("context_tool", {"value": "ok"}, _context=context)

    assert result["ok"] is True
    assert result["value"] == {"value": "ok", "has_context": True}


def test_tool_without_context_does_not_receive_it():
    context = object()

    def simple_tool(value):
        return value

    registry = _registry_with_tool(
        "simple_tool",
        simple_tool,
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    )

    result = registry.dispatch("simple_tool", {"value": "ok"}, _context=context)

    assert result == {
        "ok": True,
        "value": "ok",
        "normalized_args": {"value": "ok"},
    }


def test_tool_with_kwargs_receives_context():
    context = object()

    def kwargs_tool(value, **kwargs):
        return kwargs.get("_context") is context

    registry = _registry_with_tool(
        "kwargs_tool",
        kwargs_tool,
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    )

    result = registry.dispatch("kwargs_tool", {"value": "ok"}, _context=context)

    assert result["ok"] is True
    assert result["value"] is True


def test_type_error_inside_tool_body_is_real_tool_failure():
    def type_error_tool(value, _context=None):
        raise TypeError(f"internal TypeError for {value}")

    registry = _registry_with_tool(
        "type_error_tool",
        type_error_tool,
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    )

    result = registry.dispatch("type_error_tool", {"value": "x"}, _context=object())

    assert result["ok"] is False
    assert "'type_error_tool' failed: TypeError: internal TypeError for x" == result["error"]


def test_dict_args_still_work():
    def echo(value):
        return value

    registry = _registry_with_tool(
        "echo",
        echo,
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    )

    result = registry.dispatch("echo", {"value": "dict"})

    assert result["ok"] is True
    assert result["value"] == "dict"
    assert result["normalized_args"] == {"value": "dict"}


def test_json_string_args_parse_and_work():
    def echo(value):
        return value

    registry = _registry_with_tool(
        "echo",
        echo,
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    )

    result = registry.dispatch("echo", '{"value": "json"}')

    assert result["ok"] is True
    assert result["value"] == "json"
    assert result["normalized_args"] == {"value": "json"}


def test_invalid_json_string_args_return_clear_error_envelope():
    registry = _registry_with_tool("noop", lambda: "ok")

    result = registry.dispatch("noop", '{"value":')

    assert result["ok"] is False
    assert "Invalid arguments for 'noop'" in result["error"]
    assert "failed to parse JSON string" in result["error"]


def test_json_string_non_object_args_return_clear_error_envelope():
    registry = _registry_with_tool("noop", lambda: "ok")

    list_result = registry.dispatch("noop", '["not", "object"]')
    string_result = registry.dispatch("noop", '"not object"')

    assert list_result["ok"] is False
    assert "arguments must be a JSON object, got list" in list_result["error"]
    assert string_result["ok"] is False
    assert "arguments must be a JSON object, got str" in string_result["error"]


def test_non_string_non_dict_args_return_clear_error_envelope():
    registry = _registry_with_tool("noop", lambda: "ok")

    result = registry.dispatch("noop", ["not", "object"])

    assert result["ok"] is False
    assert "arguments must be a JSON object, got list" in result["error"]
