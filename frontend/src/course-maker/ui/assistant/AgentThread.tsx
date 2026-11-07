import { type ReactNode, lazy, Suspense, useMemo } from "react";
import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import {
  MarkdownTextPrimitive,
  type SyntaxHighlighterProps,
} from "@assistant-ui/react-markdown";

type Turn = {
  readonly id?: string;
  readonly user: string;
  readonly assistant: string;
};

// Use the application's durable state as the source of truth. Sending and retry
// identities continue to belong to the existing use cases, not a second chat store.
export function AgentThread({
  turns = [],
  entries,
  pendingMessage,
  running = false,
  disabled = false,
  onSend,
  children,
}: {
  turns?: readonly Turn[];
  entries?: readonly { role: "user" | "assistant"; text: string }[];
  pendingMessage?: string;
  running?: boolean;
  disabled?: boolean;
  onSend: (text: string) => void;
  children: ReactNode;
}) {
  const messages = useMemo<ThreadMessageLike[]>(
    () => [
      ...(entries?.map((entry, index): ThreadMessageLike => ({
        id: `entry-${index}`,
        role: entry.role,
        content: [{ type: "text", text: entry.text }],
      })) ?? []),
      ...turns.flatMap((turn, index): ThreadMessageLike[] => [
        {
          id: `${turn.id ?? index}-user`,
          role: "user",
          content: [{ type: "text", text: turn.user }],
        },
        {
          id: `${turn.id ?? index}-assistant`,
          role: "assistant",
          content: [{ type: "text", text: turn.assistant }],
        },
      ]),
      ...(pendingMessage
        ? [
            {
              id: "pending-user",
              role: "user" as const,
              content: [{ type: "text" as const, text: pendingMessage }],
            },
          ]
        : []),
    ],
    [turns, entries, pendingMessage],
  );
  const runtime = useExternalStoreRuntime({
    messages,
    convertMessage: (message) => message,
    isRunning: running,
    isDisabled: disabled,
    onNew: async (message) => {
      const text = message.content
        .filter((part) => part.type === "text")
        .map((part) => part.text)
        .join("\n");
      if (text.trim() && !disabled && !running) onSend(text.trim());
    },
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="agent-thread">
        {children}
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}

const OpenUIAnswer = lazy(() => import("./OpenUIAnswer"));
function RichAnswer(props: SyntaxHighlighterProps) {
  return (
    <Suspense fallback={<p role="status">Preparing answer…</p>}>
      <OpenUIAnswer {...props} />
    </Suspense>
  );
}

const richComponents = {
  openui: { SyntaxHighlighter: RichAnswer, CodeHeader: () => null },
};
function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="lesson-message guide agent-message">
      <span className="eyebrow">GUIDE</span>
      <MessagePrimitive.Parts components={{ Text: AssistantText }} />
    </MessagePrimitive.Root>
  );
}
function AssistantText() {
  return (
    <MarkdownTextPrimitive
      className="agent-markdown"
      componentsByLanguage={richComponents}
      preprocess={(text) =>
        /^\s*root\s*=\s*Answer\s*\(/.test(text)
          ? `\`\`\`openui\n${text}\n\`\`\``
          : text
      }
      smooth={false}
    />
  );
}
function UserMessage() {
  return (
    <MessagePrimitive.Root className="lesson-message learner agent-message">
      <span className="eyebrow">YOU</span>
      <MessagePrimitive.Parts />
    </MessagePrimitive.Root>
  );
}
export function AgentMessages() {
  return (
    <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
  );
}

// Controlled drafts are intentional: failed sends and version-restore commands
// must preserve unsent text. Prevent the primitive's automatic draft clearing.
export function AgentComposer({
  value,
  onChange,
  onSend,
  disabled,
  sendDisabled,
  label,
  maxLength = 20000,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  sendDisabled?: boolean;
  label: string;
  maxLength?: number;
  children?: ReactNode;
}) {
  const submit = () => {
    if (!disabled && !sendDisabled && value.trim()) onSend();
  };
  return (
    <ComposerPrimitive.Root
      className="lesson-chat-compose"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <ComposerPrimitive.Input
        aria-label={label}
        rows={2}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder="Ask a question or describe a change…"
        submitMode="none"
        onKeyDown={(event) => {
          if (
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing
          ) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <button
        className="btn btn-primary guide-send"
        type="submit"
        disabled={disabled || sendDisabled || !value.trim()}
      >
        Send message ↑
      </button>
      {children}
    </ComposerPrimitive.Root>
  );
}
