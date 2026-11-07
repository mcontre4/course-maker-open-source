# Syllabus frontend verification

Verified locally on 2026-10-28 in the `codex/syllabus-frontend` worktree, using the running Vite frontend and an isolated Docker Compose project (`course-maker-syllabus-ui`). Live provider keys stayed in the ignored backend environment file.

## Automated checks

- 60 frontend tests passed, including HTTP response mapping, exact message forwarding, revision handling, pagination, saved-draft recovery, StrictMode single submission, persisted chat restoration, and disabled actions during generation.
- Production TypeScript/Vite build passed.
- Frontend architecture boundary check and formatting check passed.
- Backend hexagonal boundary check passed; backend application code was unchanged.
- Checked the built JavaScript against all three configured API credentials: none appeared in the browser bundle.

## Manual browser flow

1. Submitted a new course through the form: a one-week, one-hour uv packaging course, explicitly requesting research of current official Astral documentation.
2. Confirmed immediate navigation to the saved draft URL and a pending agent state with editing and approval disabled.
3. Received a complete syllabus with four lessons and 60 minutes split across video, practice, reading, and review. Verified outcomes, lesson objectives, and clickable source citations.
4. Inspected persisted agent history: model `openai/gpt-6.1-sol`, three `tavily_search` calls and three matching tool returns. The course response alone was not treated as proof of research.
5. Sent a follow-up in the same course to rename the final lesson and add a console-command verification step. The agent preserved the project and budget and returned the revised plan.
6. Reloaded the browser. Both conversation turns and the updated syllabus were restored. The saved conversation was revision 2, with four lessons totaling 60 minutes.
7. Added a manual topic, verified its appearance, then removed it through the UI and verified removal.
8. Approved the syllabus, verified the approval screen, visited the course library, and reopened the approved syllabus from its permanent URL.

Verified course: `course_5f979dcc-a699-4009-861f-2bdb3a9c0018` in the isolated local database. Video and quiz generation remain separate, unavailable features; approval saves the syllabus without simulating their creation.

Production deployment still requires the authenticated same-origin API gateway described in `frontend/README.md`. The local Vite proxy is a development facility.

## Review against the latest main branch

Consolidated the lesson-generation HTTP application into the injected backend port and single-execute application services. Preserved the complete lesson-plan response, the generate-lesson action, and explicit demo mode. Replaced the duplicate missing-syllabus page with the shared syllabus workspace and added regression coverage for clarification recovery, lesson-plan mapping, provider failures, malformed responses, and safe citation rendering.

All pre-commit gates passed, including Ruff, mypy, affected backend tests, the 95% unit coverage gate, role-based architecture checks, and Tach. The reviewed frontend production build and all 60 tests passed.

The final browser check generated the approved syllabus’s first real lesson plan through the consolidated API wiring. Verified its objectives, teaching progression, examples, source links, and persistence after a full reload. Fixed narrow-screen grid overflow exposed by that generated content.
