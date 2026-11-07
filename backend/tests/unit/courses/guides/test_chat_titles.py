import pytest

from app.courses.domain.guide import GuideThread, GuideThreadId


@pytest.mark.parametrize(
    ("title", "revision", "message", "expected"),
    [
        ("New chat", 0, "  Explain\n linked lists  ", "Explain linked lists"),
        ("My ideas", 0, "Explain nodes", "My ideas"),
        ("Existing conversation", 1, "A different topic", "Existing conversation"),
        ("New chat", 0, "x" * 200, "x" * 80),
    ],
)
def test_first_message_names_only_an_untitled_chat(title, revision, message, expected):
    thread = GuideThread(
        GuideThreadId("chat_00000000-0000-0000-0000-000000000001"),
        "user_00000000-0000-0000-0000-000000000001",
        "lesson_00000000-0000-0000-0000-000000000001",
        "lesson",
        title,
        revision=revision,
    )
    advanced = thread.advance("saved history", "summary", message)
    assert advanced.title == expected
    assert advanced.revision == revision + 1
    assert thread.title == title
