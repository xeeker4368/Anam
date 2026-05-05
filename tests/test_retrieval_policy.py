from tir.engine.retrieval_policy import classify_retrieval_policy


def test_url_content_prompt_skips_memory():
    policy = classify_retrieval_policy(
        "Can you summarize this URL: https://example.com/article"
    )

    assert policy == {
        "mode": "skip_memory",
        "reason": "direct_url_content",
    }


def test_moltbook_posts_by_author_prompt_skips_memory():
    policy = classify_retrieval_policy("Can you check Moltbook for posts by xkai?")

    assert policy == {
        "mode": "skip_memory",
        "reason": "direct_moltbook_state",
    }


def test_moltbook_profile_feed_comments_prompt_skips_memory():
    prompts = [
        "Read the Moltbook profile for xkai",
        "Show the Moltbook feed",
        "Find Moltbook comments for this post",
        "List the Moltbook submolt moderators",
    ]

    for prompt in prompts:
        policy = classify_retrieval_policy(prompt)
        assert policy == {
            "mode": "skip_memory",
            "reason": "direct_moltbook_state",
        }


def test_what_has_user_posted_skips_memory():
    policy = classify_retrieval_policy("What has xkai posted?")

    assert policy == {
        "mode": "skip_memory",
        "reason": "direct_moltbook_state",
    }


def test_web_latest_current_prompt_skips_memory():
    prompts = [
        "Search the web for current information about Python releases",
        "Look up the latest news about SearXNG",
        "Find recent updates on OpenAI Codex",
        "What is happening today with this outage?",
    ]

    for prompt in prompts:
        policy = classify_retrieval_policy(prompt)
        assert policy == {
            "mode": "skip_memory",
            "reason": "direct_web_current",
        }


def test_project_anam_architecture_question_keeps_normal_retrieval():
    policy = classify_retrieval_policy("How does Project Anam context assembly work?")

    assert policy == {
        "mode": "normal",
        "reason": "project_or_internal_context",
    }


def test_moltbook_integration_decision_question_keeps_normal_retrieval():
    policy = classify_retrieval_policy(
        "What did we decide about Moltbook integration?"
    )

    assert policy == {
        "mode": "normal",
        "reason": "normal",
    }


def test_ordinary_chat_keeps_normal_retrieval():
    policy = classify_retrieval_policy("How should I think about this design?")

    assert policy == {
        "mode": "normal",
        "reason": "normal",
    }


def test_greeting_policy_is_normal_and_route_handles_greeting_skip():
    policy = classify_retrieval_policy("hello")

    assert policy == {
        "mode": "normal",
        "reason": "normal",
    }
