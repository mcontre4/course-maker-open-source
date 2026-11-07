import { StrictMode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { MemoryGuides } from "../testing/guides";
import { GuidePanel } from "./GuidePanel";

function mount(api: MemoryGuides, route = "/") {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[route]}>
        <QueryClientProvider client={cache}>
          <GuidePanel
            api={api}
            resourceId="lesson_one"
            guide="lesson"
            generationMode="balanced"
          />
        </QueryClientProvider>
      </MemoryRouter>
    </StrictMode>,
  );
}

async function send(text: string) {
  const user = userEvent.setup();
  const box = screen.getByLabelText("Message your lesson guide");
  await waitFor(() => expect(box).toBeEnabled());
  await user.type(box, text);
  await user.click(screen.getByRole("button", { name: "Send message ↑" }));
  return user;
}

describe("persistent guide", () => {
  it("offers starter requests that fill the message box without sending", async () => {
    const api = new MemoryGuides();
    mount(api);
    const user = userEvent.setup();
    const suggestion = await screen.findByRole("button", {
      name: "Add a real-world example",
    });
    await waitFor(() => expect(suggestion).toBeEnabled());
    await user.click(suggestion);
    expect(screen.getByLabelText("Message your lesson guide")).toHaveValue(
      "Add a real-world example",
    );
    expect(await api.list("lesson_one", "lesson")).toHaveLength(0);
  });
  it("restores the selected guide focus and chat from the URL", async () => {
    const api = new MemoryGuides();
    await api.create("lesson_one", "lesson", "Outline ideas");
    const script = await api.create("lesson_one", "storyboard", "Script ideas");
    mount(api, "/?focus=storyboard&chat=" + script.id);
    await screen.findByText("Script ideas");
    await userEvent
      .setup()
      .click(screen.getByText("Chat settings & saved context"));
    expect(screen.getByLabelText("Guide focus")).toHaveValue("storyboard");
  });
  it("continues the same chat, switches independent chats, and reopens saved history", async () => {
    const api = new MemoryGuides();
    const view = mount(api);
    const user = await send("Explain the audience");
    await screen.findByText(
      "I remember our conversation: Explain the audience",
    );
    await send("Use that audience");
    await screen.findByText("I remember our conversation: Use that audience");
    expect(api.chats).toHaveLength(1);
    expect(api.requests.map((request) => request.expectedRevision)).toEqual([
      0, 1,
    ]);
    await user.click(screen.getByRole("button", { name: "New chat" }));
    await waitFor(() => expect(api.chats).toHaveLength(2));
    await waitFor(() =>
      expect(screen.queryByText("Use that audience")).not.toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Previous chats" }));
    await user.click(
      await screen.findByRole("button", { name: /Explain the audience/ }),
    );
    await screen.findByText("Use that audience");
    view.unmount();
    mount(api);
    await screen.findByText("Use that audience");
    expect(api.chats).toHaveLength(2);
  });

  it("reuses a request identity after the server saved a message but the response was lost", async () => {
    const api = new MemoryGuides();
    api.loseNextResponse = true;
    mount(api);
    const user = await send("Remember this decision");
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Message your lesson guide")).toHaveValue(
      "Remember this decision",
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Send message ↑" }),
      ).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "Send message ↑" }));
    await screen.findByText(
      "I remember our conversation: Remember this decision",
    );
    expect(api.requests[0].requestId).toBe(api.requests[1].requestId);
    expect(api.chats[0].turns).toHaveLength(1);
  });

  it("lets users correct and forget scoped memories", async () => {
    const api = new MemoryGuides();
    api.savedMemories = [
      {
        id: "memory_one",
        scope: "user",
        key: "language",
        content: "Spanish",
        revision: 1,
        sourceMessageId: "message_one",
      },
    ];
    mount(api);
    const user = userEvent.setup();
    await user.click(screen.getByText("Chat settings & saved context"));
    await user.click(screen.getByText("Saved memories"));
    const box = await screen.findByLabelText("Your preference: language");
    await user.clear(box);
    await user.type(box, "English");
    await user.click(screen.getByRole("button", { name: "Save memory" }));
    await waitFor(() => expect(api.savedMemories[0].content).toBe("English"));
    await user.click(screen.getByRole("button", { name: "Forget" }));
    await screen.findByText("No saved memories yet.");
  });

  it("browses outline snapshots and asks the guide to restore a version", async () => {
    const api = new MemoryGuides();
    api.savedVersions = [
      {
        revision: 1,
        description: "Initial outline",
        outlineJson: '{"title":"Original opening"}',
        sourceMessageId: "message_one",
        createdAt: "2026-10-29T12:00:00",
      },
    ];
    mount(api);
    const user = userEvent.setup();
    await user.click(screen.getByText("Chat settings & saved context"));
    await user.click(screen.getByText("Outline versions"));
    await user.click(await screen.findByText("Version 1 · Initial outline"));
    expect(screen.getByText(/Original opening/)).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Restore this version" }),
      ).toBeEnabled(),
    );
    await user.click(
      screen.getByRole("button", { name: "Restore this version" }),
    );
    await screen.findByText(
      "I remember our conversation: Restore outline version 1.",
    );
    expect(api.requests[0].message).toBe("Restore outline version 1.");
  });

  it("preserves an unsent draft when restoring an outline version", async () => {
    const api = new MemoryGuides();
    api.savedVersions = [
      {
        revision: 1,
        description: "Initial outline",
        outlineJson: "{}",
        sourceMessageId: "message_one",
        createdAt: "2026-10-29T12:00:00",
      },
    ];
    mount(api);
    const user = userEvent.setup();
    const box = screen.getByLabelText("Message your lesson guide");
    await waitFor(() => expect(box).toBeEnabled());
    await user.type(box, "An idea I have not sent yet");
    await user.click(screen.getByText("Chat settings & saved context"));
    await user.click(screen.getByText("Outline versions"));
    await user.click(await screen.findByText("Version 1 · Initial outline"));
    await user.click(
      screen.getByRole("button", { name: "Restore this version" }),
    );
    await screen.findByText(
      "I remember our conversation: Restore outline version 1.",
    );
    expect(box).toHaveValue("An idea I have not sent yet");
  });

  it("loads archived messages and keeps guide roles in independent chats", async () => {
    const api = new MemoryGuides();
    const chat = await api.create("lesson_one", "lesson", "Long chat");
    api.chats[0] = {
      ...chat,
      revision: 105,
      turns: Array.from({ length: 105 }, (_, index) => ({
        id: "message_" + index,
        revision: index + 1,
        user: "Question " + index,
        assistant: "Answer " + index,
      })),
    };
    mount(api);
    const user = userEvent.setup();
    await user.click(
      await screen.findByRole("button", { name: "Load earlier messages" }),
    );
    await screen.findByText("Question 0");
    await user.click(screen.getByText("Chat settings & saved context"));
    await waitFor(() =>
      expect(screen.getByLabelText("Guide focus")).toBeEnabled(),
    );
    await user.selectOptions(
      screen.getByLabelText("Guide focus"),
      "storyboard",
    );
    await waitFor(() =>
      expect(screen.queryByText("Question 0")).not.toBeInTheDocument(),
    );
    expect(api.chats).toHaveLength(1);
  });
});

it("sends with Enter and keeps Shift+Enter as a newline", async () => {
  const api = new MemoryGuides();
  mount(api);
  const user = userEvent.setup();
  const box = screen.getByLabelText("Message your lesson guide");
  await waitFor(() => expect(box).toBeEnabled());
  await user.type(box, "Explain nodes{Shift>}{Enter}{/Shift}with an example");
  expect(api.requests).toHaveLength(0);
  expect(box).toHaveValue("Explain nodes\nwith an example");
  await user.keyboard("{Enter}");
  await screen.findByText(
    "I remember our conversation: Explain nodes with an example",
    { exact: false },
  );
  expect(api.requests[0].message).toBe("Explain nodes\nwith an example");
});

it("lets a failed chat load recover without creating or sending a message", async () => {
  class RecoveringGuides extends MemoryGuides {
    attempts = 0;
    override async list(...args: Parameters<MemoryGuides["list"]>) {
      if (this.attempts++ === 0)
        throw new Error(
          "Your guide is temporarily unavailable. Please try again.",
        );
      return super.list(...args);
    }
  }
  const api = new RecoveringGuides();
  mount(api);
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Message your lesson guide")).toBeDisabled();
  await userEvent
    .setup()
    .click(screen.getByRole("button", { name: "Try again" }));
  await waitFor(() =>
    expect(screen.getByLabelText("Message your lesson guide")).toBeEnabled(),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(api.chats).toHaveLength(0);
  expect(api.requests).toHaveLength(0);
});
