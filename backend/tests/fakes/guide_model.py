from contextlib import asynccontextmanager
from pathlib import Path

from fixtures.guide_answer import RICH_GUIDE_ANSWER
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel

from app.courses.adapters.ai.guide import (
    GUIDE_TOOLS,
    GuideRunDependencies,
    PydanticGuideAgent,
    current_guide_context,
)


class GuideModelScript:
    """Deterministic provider boundary; the real Pydantic AI tool loop still runs."""

    def __init__(self):
        self.calls = []
        self.summary_calls = []

    def respond(self, messages, info):
        self.calls.append((messages, info))
        last = messages[-1]
        if isinstance(last, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in last.parts
        ):
            return ModelResponse(parts=[TextPart("Done. " + str(last.parts[-1].content))])
        prompt = next(
            (
                p.content
                for m in reversed(messages)
                if isinstance(m, ModelRequest)
                for p in m.parts
                if isinstance(p, UserPromptPart)
            ),
            "",
        )
        if prompt == "Explain bonds visually":
            return ModelResponse(parts=[TextPart(RICH_GUIDE_ANSWER)])
        if prompt == "Explain bonds in Markdown":
            return ModelResponse(
                parts=[
                    TextPart(
                        "### Bond basics\n\n**Electrons** matter.\n\n"
                        "1. Count them\n2. Compare the atoms"
                    )
                ]
            )
        if prompt == "Show malformed UI":
            return ModelResponse(parts=[TextPart('```openui\nroot = Unknown("Oops")\n```')])
        if prompt == "Remember Spanish":
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "remember", {"key": "language", "content": "Spanish", "scope": "user"}
                    )
                ]
            )
        if prompt == "Remember audience":
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "remember",
                        {"key": "audience", "content": "Chemistry beginners", "scope": "lesson"},
                    )
                ]
            )
        if str(prompt).startswith("Revise"):
            return ModelResponse(
                parts=[ToolCallPart("revise_outline", {"instructions": str(prompt)})]
            )
        if str(prompt).startswith("Restore "):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "restore_outline_version", {"revision": int(str(prompt).split()[-1])}
                    )
                ]
            )
        if prompt == "Compare 1 2":
            return ModelResponse(
                parts=[
                    ToolCallPart("compare_outline_versions", {"revision": 1, "other_revision": 2})
                ]
            )
        if prompt == "Find audience":
            return ModelResponse(
                parts=[ToolCallPart("search_lesson_history", {"query": "audience"})]
            )
        if prompt == "List versions":
            return ModelResponse(parts=[ToolCallPart("list_outline_versions", {})])
        if prompt == "Read version 1":
            return ModelResponse(parts=[ToolCallPart("get_outline_version", {"revision": 1})])
        if prompt == "Read current outline":
            return ModelResponse(
                parts=[ToolCallPart("get_lesson_artifact", {"artifact": "outline"})]
            )
        if prompt == "Forget language":
            return ModelResponse(
                parts=[ToolCallPart("forget_memory", {"key": "language", "scope": "user"})]
            )
        return ModelResponse(parts=[TextPart("We can discuss this without changing the outline.")])

    def summarize(self, messages, info):
        self.summary_calls.append(messages)
        return ModelResponse(
            parts=[TextPart("Earlier decision: use Spanish. Keep examples concrete.")]
        )


def scripted_guide(script, threshold=100000):
    prompt_path = Path(__file__).parents[2] / "src/app/courses/adapters/ai"
    instructions = (prompt_path / "guide_prompt.md").read_text()
    instructions += "\n" + (prompt_path / "answer_prompt.md").read_text()

    @asynccontextmanager
    async def scope(mode):
        yield (
            Agent(
                FunctionModel(script.respond),
                deps_type=GuideRunDependencies,
                instructions=[instructions, current_guide_context],
                tools=GUIDE_TOOLS,
            ),
            Agent(FunctionModel(script.summarize), output_type=str),
        )

    return PydanticGuideAgent(scope, compaction_threshold=threshold)
