import json

from pydantic_ai import ConversationTypeAdapter

from app.courses.ports.guide import GuideAgentRequest, GuideToolResponse


def test_native_conversation_survives_compaction_without_losing_its_identity(
    compacting_guide, model_script
):
    history, summary, identity = "", "", None
    for index in range(14):
        result = compacting_guide.run(
            GuideAgentRequest(f"Discuss idea {index}", "{}", history, summary),
            lambda request: GuideToolResponse("Saved"),
        )
        history, summary = result.history_json, result.summary
        conversation = ConversationTypeAdapter.validate_json(history)
        if identity is None:
            identity = conversation.conversation_id
        assert conversation.conversation_id == identity
    assert model_script.summary_calls
    assert "Spanish" in summary
    assert len(conversation.messages) < 28
    assert "Discuss idea 13" in history


def test_legacy_messages_are_imported_into_native_history(compacting_guide):
    context = json.dumps(
        {"previous_messages": [{"user": "Use a water example", "assistant": "Included water"}]}
    )
    first = compacting_guide.run(
        GuideAgentRequest("Hello", context, "", ""), lambda request: GuideToolResponse("Saved")
    )
    second = compacting_guide.run(
        GuideAgentRequest("What example?", "{}", first.history_json, ""),
        lambda request: GuideToolResponse("Saved"),
    )
    assert "Use a water example" in second.history_json
    assert "Included water" in second.history_json
