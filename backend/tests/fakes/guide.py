from copy import deepcopy
from dataclasses import replace

from app.courses.domain.errors import CourseConflict, CourseNotFound
from app.courses.ports.guide import GuideAgentResponse


class InMemoryGuideRepository:
    def __init__(self):
        self.threads, self.turns, self.memories, self.versions = {}, {}, {}, {}

    def add(self, thread):
        self.threads[str(thread.id)] = thread

    def require_by_id(self, identifier):
        if str(identifier) not in self.threads:
            raise CourseNotFound("Chat not found")
        return self.threads[str(identifier)]

    def list_threads(self, owner_id, resource_id, guide):
        return tuple(
            t
            for t in self.threads.values()
            if (t.owner_id, t.resource_id, t.guide) == (owner_id, resource_id, guide)
        )

    def save(self, thread, expected_revision):
        current = self.require_by_id(thread.id)
        if current.revision != expected_revision:
            raise CourseConflict("Chat changed")
        self.threads[str(thread.id)] = thread

    def add_turn(self, turn):
        self.turns[str(turn.id)] = turn

    def list_turns(self, thread_id, before=None, limit=100):
        turns = [
            t
            for t in self.turns.values()
            if t.thread_id == thread_id and (before is None or t.revision < before)
        ]
        return tuple(sorted(turns, key=lambda t: t.revision)[-limit:])

    def get_by_request_id(self, thread_id, request_id):
        return next(
            (
                t
                for t in self.turns.values()
                if t.thread_id == thread_id and t.request_id == request_id
            ),
            None,
        )

    def list_memories(self, owner_id, resource_id):
        return tuple(
            m
            for m in self.memories.values()
            if m.owner_id == owner_id and m.resource_id in ("", resource_id)
        )

    def save_memory(self, memory, expected_revision):
        before = self.memories.get(str(memory.id))
        if (before.revision if before else 0) != expected_revision:
            raise CourseConflict("Memory changed")
        self.memories[str(memory.id)] = memory

    def delete_memory(self, owner_id, memory_id, expected_revision):
        before = self.memories[memory_id]
        if before.owner_id != owner_id or before.revision != expected_revision:
            raise CourseConflict("Memory changed")
        del self.memories[memory_id]

    def list_versions(self, resource_id, limit=50, before=None):
        versions = [
            v
            for v in self.versions.values()
            if v.resource_id == resource_id and (before is None or v.revision < before)
        ]
        return tuple(sorted(versions, key=lambda v: v.revision, reverse=True)[:limit])

    def require_version(self, resource_id, revision):
        if (resource_id, revision) not in self.versions:
            raise CourseNotFound("Outline version not found")
        return self.versions[resource_id, revision]

    def add_version(self, version):
        self.versions[version.resource_id, version.revision] = version

    def annotate_version(self, resource_id, revision, description, source_message_id):
        version = self.versions.get((resource_id, revision))
        if version:
            self.versions[resource_id, revision] = replace(
                version, description=description, source_message_id=source_message_id
            )

    def search_history(self, owner_id, resource_id, query):
        return tuple(
            t
            for t in self.turns.values()
            if self.threads[str(t.thread_id)].owner_id == owner_id
            and self.threads[str(t.thread_id)].resource_id == resource_id
            and query.lower() in (t.user + t.assistant).lower()
        )[:20]


class GuideUnitOfWork:
    def __init__(self, guides, lessons, courses, syllabuses):
        self.stores = (guides, lessons, courses, syllabuses)
        self.exited = True
        self.fail_commit = False
        self.commits = 0

    def __enter__(self):
        self.snapshot = [deepcopy(store.__dict__) for store in self.stores]
        self.exited = False
        return self

    def __exit__(self, kind, error, traceback):
        if kind:
            self.rollback()
        self.exited = True

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("Commit failed")
        self.commits += 1

    def rollback(self):
        for store, state in zip(self.stores, self.snapshot, strict=True):
            store.__dict__.clear()
            store.__dict__.update(state)


class RecordingGuideAgent:
    def __init__(self, uow):
        self.uow, self.requests, self.actions, self.results = uow, [], [], []
        self.error = None
        self.during_run = None
        self.answer = "Let's discuss the lesson."

    def run(self, request, tool):
        assert self.uow.exited, "A transaction must not span a model call"
        self.requests.append(request)
        for action in self.actions:
            self.results.append(tool(action))
        if self.during_run:
            self.during_run()
        if self.error:
            raise self.error
        return GuideAgentResponse(self.answer, request.history_json + " next", request.summary)


class FakeOutlineCodec:
    def __init__(self):
        self.plans, self.curriculums = {}, {}

    def decode_plan(self, value):
        return self.plans[value]

    def decode_curriculum(self, value):
        return self.curriculums[value]
