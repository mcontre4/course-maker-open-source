from app.courses.ports.syllabus_agent import SyllabusAgentRequest, SyllabusAgentResponse
from app.courses.ports.syllabus_errors import SyllabusUnavailable


class UnconfiguredSyllabusAgent:
    def run(self, request: SyllabusAgentRequest) -> SyllabusAgentResponse:
        raise SyllabusUnavailable("Configure OpenRouter and Tavily API keys to generate syllabi")
