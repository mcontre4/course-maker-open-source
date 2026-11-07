import { useEffect, useRef, useState } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import type {
  GuideChat,
  GuideMemory,
  GuideRole,
  Guides,
} from "../application/guides";
import type { GenerationMode } from "../application/generation-mode";
import { ErrorNotice } from "./components";
import { Button } from "./primitives/Button";
import {
  AgentComposer,
  AgentMessages,
  AgentThread,
} from "./assistant/AgentThread";

const suggestions: Record<GuideRole, readonly string[]> = {
  lesson: [
    "Make it simpler for beginners",
    "Add a real-world example",
    "Make the opening more engaging",
  ],
  syllabus: [
    "Add a chapter with practice problems",
    "Make the course shorter",
    "Explain why the chapters are in this order",
  ],
  storyboard: [
    "Make the narration more conversational",
    "Shorten the first scene",
  ],
  animation: ["Use simpler diagrams", "Add more movement to the key ideas"],
};

type Props = {
  api: Guides;
  resourceId: string;
  guide: "lesson" | "syllabus";
  generationMode: GenerationMode;
  disabled?: boolean;
  onBusyChange?: (busy: boolean) => void;
  onDirtyChange?: (dirty: boolean) => void;
};

export function GuidePanel({
  api,
  resourceId,
  guide,
  generationMode,
  disabled,
  onBusyChange,
  onDirtyChange,
}: Props) {
  const cache = useQueryClient();
  const [params, setParams] = useSearchParams();
  const focus = params.get("focus");
  const role: GuideRole =
    focus === "storyboard" || focus === "animation" ? focus : guide;
  const [message, setMessage] = useState("");
  useEffect(() => {
    onDirtyChange?.(!!message.trim());
    return () => onDirtyChange?.(false);
  }, [message, onDirtyChange]);
  const [showHistory, setShowHistory] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const conversation = useRef<HTMLDivElement>(null);
  // Keep the same request identity after a lost response, even when the server committed it.
  const retry = useRef<Parameters<Guides["send"]>[0] | null>(null);
  const chatsKey = ["guide-chats", resourceId, role];
  const chats = useQuery({
    queryKey: chatsKey,
    queryFn: () => api.list(resourceId, role),
  });
  const requested = params.get("chat");
  const selected =
    chats.data?.find((item) => item.id === requested) ?? chats.data?.[0];
  const chatKey = ["guide-chat", selected?.id];
  const history = useInfiniteQuery({
    queryKey: chatKey,
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => api.get(selected!.id, pageParam),
    enabled: !!selected,
    getNextPageParam: (page) =>
      page.hasMore ? page.turns[0]?.revision : undefined,
  });
  const current = history.data?.pages[0] ?? selected;
  const turns =
    history.data?.pages.toReversed().flatMap((page) => page.turns) ?? [];
  const memories = useQuery({
    queryKey: ["guide-memories", resourceId],
    queryFn: () => api.memories(resourceId),
    enabled: showSettings,
  });
  const versions = useInfiniteQuery({
    queryKey: ["guide-versions", resourceId],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ pageParam }) => api.versions(resourceId, pageParam),
    enabled: showSettings,
    getNextPageParam: (page) =>
      page.length === 50 ? page.at(-1)?.revision : undefined,
  });
  const selectChat = (id: string) => {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("chat", id);
        next.set("focus", role);
        return next;
      },
      { replace: true },
    );
  };
  const created = (chat: GuideChat) => {
    cache.setQueryData<readonly GuideChat[]>(chatsKey, (items) => [
      ...(items ?? []),
      chat,
    ]);
    cache.setQueryData(["guide-chat", chat.id], {
      pages: [chat],
      pageParams: [undefined],
    });
    selectChat(chat.id);
    return chat;
  };
  const create = useMutation({
    mutationFn: async () =>
      created(await api.create(resourceId, role, "New chat")),
    onSuccess: () => {
      setShowHistory(false);
      setMessage("");
      sending.reset();
      retry.current = null;
    },
  });
  const sending = useMutation({
    mutationFn: async (text: string) => {
      let request = retry.current?.message === text ? retry.current : null;
      if (!request) {
        const thread =
          current ??
          created(await api.create(resourceId, role, text.slice(0, 80)));
        request = {
          threadId: thread.id,
          message: text,
          requestId: crypto.randomUUID(),
          expectedRevision: thread.revision,
          generationMode,
        };
        retry.current = request;
      }
      return api.send(request);
    },
    onSuccess: async (chat, submittedText) => {
      retry.current = null;
      setMessage((draft) => (draft.trim() === submittedText ? "" : draft));
      cache.setQueryData(["guide-chat", chat.id], {
        pages: [chat],
        pageParams: [undefined],
      });
      await Promise.all([
        cache.invalidateQueries({ queryKey: ["guide-chats", resourceId] }),
        cache.invalidateQueries({ queryKey: ["guide-memories", resourceId] }),
        cache.invalidateQueries({ queryKey: ["guide-versions", resourceId] }),
        cache.invalidateQueries({ queryKey: ["lessons", resourceId] }),
        cache.invalidateQueries({ queryKey: ["courses", resourceId] }),
      ]);
    },
    onError: async (error) => {
      if ("status" in error && error.status === 409) retry.current = null;
      await cache.invalidateQueries({ queryKey: ["guide-chat"] });
    },
  });
  const busy = sending.isPending || create.isPending;
  useEffect(() => {
    onBusyChange?.(busy);
    return () => onBusyChange?.(false);
  }, [busy, onBusyChange]);
  useEffect(() => {
    conversation.current?.scrollTo?.({
      top: conversation.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns.at(-1)?.id, sending.isPending]);
  const blocked =
    disabled ||
    busy ||
    chats.isPending ||
    history.isFetching ||
    !!chats.error ||
    !!history.error;
  const send = (text: string) => {
    if (!blocked && text.trim()) sending.mutate(text.trim());
  };
  const allVersions = versions.data?.pages.flat() ?? [];

  return (
    <aside
      className="lesson-chat panel persistent-guide"
      aria-label="Chat with your guide"
    >
      <div className="lesson-chat-heading">
        <div className="guide-heading-copy">
          <h2>
            {role === "storyboard"
              ? "Your script guide"
              : role === "animation"
                ? "Your visuals guide"
                : guide === "syllabus"
                  ? "Your course guide"
                  : "Your lesson guide"}
          </h2>
          <p className="muted small">
            {current?.title ??
              "Ask a question or describe a change in plain words."}
          </p>
        </div>
        <Button
          aria-expanded={showHistory}
          aria-controls="guide-history"
          onClick={() => setShowHistory(!showHistory)}
        >
          Previous chats
        </Button>
        <Button disabled={blocked} onClick={() => create.mutate()}>
          New chat
        </Button>
      </div>
      <div className="guide-controls">
        <label>
          Helping with
          <select
            aria-label="Guide focus"
            value={role}
            disabled={blocked}
            onChange={(event) => {
              const nextRole = event.target.value;
              setParams(
                (previous) => {
                  const next = new URLSearchParams(previous);
                  next.set("focus", nextRole);
                  next.delete("chat");
                  return next;
                },
                { replace: true },
              );
              retry.current = null;
              sending.reset();
              setMessage("");
            }}
          >
            <option value={guide}>
              {guide === "syllabus" ? "Course outline" : "Lesson outline"}
            </option>
            <option value="storyboard">Script</option>
            <option value="animation">Animation</option>
          </select>
        </label>
      </div>
      {showHistory && (
        <nav
          id="guide-history"
          className="guide-history"
          aria-label="Previous chats"
        >
          <p className="eyebrow">Previous chats</p>
          {!chats.data?.length && (
            <p className="muted small">Your conversations will appear here.</p>
          )}
          {chats.data?.toReversed().map((chat) => (
            <button
              key={chat.id}
              type="button"
              disabled={blocked}
              aria-current={selected?.id === chat.id ? "true" : undefined}
              onClick={() => {
                selectChat(chat.id);
                retry.current = null;
                setMessage("");
                sending.reset();
                setShowHistory(false);
              }}
            >
              <span>{chat.title}</span>
              <span className="muted small">
                {chat.revision} {chat.revision === 1 ? "message" : "messages"}
              </span>
            </button>
          ))}
        </nav>
      )}
      <ErrorNotice error={chats.error ?? history.error ?? create.error} />
      {(chats.error || history.error) && (
        <Button
          onClick={() => {
            void chats.refetch();
            if (selected) void history.refetch();
          }}
        >
          Try again
        </Button>
      )}
      <AgentThread
        key={`${resourceId}:${role}:${selected?.id ?? "new"}`}
        turns={turns}
        pendingMessage={sending.isPending ? sending.variables : undefined}
        running={sending.isPending}
        disabled={!!blocked}
        onSend={send}
      >
        <div
          className="lesson-chat-messages"
          ref={conversation}
          role="log"
          aria-label="Guide conversation"
          aria-live="polite"
        >
          {history.hasNextPage && (
            <Button
              disabled={history.isFetchingNextPage}
              onClick={() => void history.fetchNextPage()}
            >
              Load earlier messages
            </Button>
          )}
          {(chats.isPending || (selected && history.isPending)) && (
            <p role="status">Loading conversation…</p>
          )}
          {!turns.length &&
            !sending.isPending &&
            !chats.isPending &&
            !history.isFetching &&
            !chats.error &&
            !history.error && (
              <div className="guide-empty">
                <span className="guide-avatar" aria-hidden="true">
                  ✧
                </span>
                <h3>What would you like to work on?</h3>
                <p>
                  Ask a question, explore an idea, or tell me what you’d like to
                  change. Try one of these:
                </p>
                <ul
                  className="guide-suggestions"
                  aria-label="Suggested requests"
                >
                  {suggestions[role].map((text) => (
                    <li key={text}>
                      <button
                        type="button"
                        disabled={!!blocked}
                        onClick={() => setMessage(text)}
                      >
                        {text}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          <AgentMessages />
          {sending.isPending && (
            <>
              <p className="guide-thinking" role="status">
                Your guide is thinking<span aria-hidden="true">…</span>
              </p>
            </>
          )}
        </div>
        <AgentComposer
          value={message}
          onChange={setMessage}
          onSend={() => send(message)}
          disabled={!!blocked}
          label={`Message your ${guide === "syllabus" ? "course" : "lesson"} guide`}
        >
          <ErrorNotice error={sending.error} />
          <p className="muted small">
            {guide === "syllabus"
              ? "Questions leave your course unchanged. Requested changes update the syllabus outline."
              : "Questions leave your lesson unchanged. Requested changes update the outline; your current video stays until you generate a new one."}
          </p>
        </AgentComposer>
      </AgentThread>
      <details
        className="guide-settings"
        onToggle={(event) => setShowSettings(event.currentTarget.open)}
      >
        <summary>Chat settings &amp; saved context</summary>
        <details className="outline-details">
          <summary>Saved memories</summary>
          <p className="muted small">
            Preferences apply across lessons; lesson decisions apply here.
            Forgetting a memory keeps the original chat transcript.
          </p>
          <ErrorNotice error={memories.error} />
          {memories.data?.map((memory) => (
            <MemoryEditor
              key={memory.id + ":" + memory.revision}
              api={api}
              resourceId={resourceId}
              memory={memory}
              disabled={blocked}
            />
          ))}
          {memories.data?.length === 0 && <p>No saved memories yet.</p>}
        </details>
        <details className="outline-details">
          <summary>Outline versions</summary>
          <ErrorNotice error={versions.error} />
          {allVersions.map((version) => (
            <details key={version.revision} className="guide-version">
              <summary>
                Version {version.revision} · {version.description}
              </summary>
              <p className="muted small">
                {version.createdAt.replace("T", " ")}
              </p>
              <pre>
                {JSON.stringify(JSON.parse(version.outlineJson), null, 2)}
              </pre>
              <Button
                disabled={blocked}
                onClick={() =>
                  send(`Restore outline version ${version.revision}.`)
                }
              >
                Restore this version
              </Button>
              {version.revision !== allVersions[0]?.revision && (
                <Button
                  disabled={blocked}
                  onClick={() =>
                    send(
                      `Compare outline versions ${version.revision} and ${allVersions[0]?.revision}. Explain what changed.`,
                    )
                  }
                >
                  Compare with latest
                </Button>
              )}
            </details>
          ))}
          {!allVersions.length && (
            <p>Versions appear when an outline is saved.</p>
          )}
          {versions.hasNextPage && (
            <Button
              disabled={versions.isFetchingNextPage}
              onClick={() => void versions.fetchNextPage()}
            >
              Load older versions
            </Button>
          )}
        </details>
      </details>
    </aside>
  );
}

function MemoryEditor({
  api,
  resourceId,
  memory,
  disabled,
}: {
  api: Guides;
  resourceId: string;
  memory: GuideMemory;
  disabled?: boolean;
}) {
  const cache = useQueryClient();
  const [content, setContent] = useState(memory.content);
  const mutation = useMutation({
    mutationFn: (value: string | null) =>
      api.changeMemory(resourceId, memory, value),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["guide-memories"] }),
  });
  return (
    <div className="guide-memory">
      <label>
        {memory.scope === "user" ? "Your preference" : "Lesson decision"}:{" "}
        {memory.key}
        <textarea
          value={content}
          maxLength={2000}
          disabled={disabled || mutation.isPending}
          onChange={(event) => setContent(event.target.value)}
        />
      </label>
      <Button
        disabled={
          disabled ||
          mutation.isPending ||
          !content.trim() ||
          content === memory.content
        }
        onClick={() => mutation.mutate(content.trim())}
      >
        Save memory
      </Button>
      <Button
        disabled={disabled || mutation.isPending}
        onClick={() => mutation.mutate(null)}
      >
        Forget
      </Button>
      <ErrorNotice error={mutation.error} />
    </div>
  );
}
