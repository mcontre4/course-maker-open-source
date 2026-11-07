import { StrictMode } from "react";
import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../../App";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { ApplicationContext } from "./application-context";

function mount(
  backend: MemoryCourseBackend,
  route = `/courses/${backend.value.id}/syllabus`,
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    ...render(
      <StrictMode>
        <ApplicationContext.Provider
          value={createBackendCourseApplication(backend)}
        >
          <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={[route]}>
              <App />
            </MemoryRouter>
          </QueryClientProvider>
        </ApplicationContext.Provider>
      </StrictMode>,
    ),
  };
}

describe("connected syllabus UI", () => {
  it("shows quality and speed in course creation without exposing technical settings", () => {
    mount(new MemoryCourseBackend(), "/courses/new");
    const quality = screen.getByRole("group", { name: "Quality & speed" });
    expect(quality).toBeVisible();
    for (const name of ["Fast", "Balanced", "Pro"]) {
      expect(within(quality).getByText(name)).toBeVisible();
      expect(
        within(quality).getByRole("radio", { name }).closest("details"),
      ).toBeNull();
    }
    expect(
      within(quality).getByText("Technical settings").closest("details"),
    ).not.toHaveAttribute("open");
    expect(
      within(quality).getByLabelText("Generation model"),
    ).not.toBeVisible();
  });

  it("opens the saved draft and recovers generation without creating another course", async () => {
    const backend = new MemoryCourseBackend();
    backend.failGeneration = true;
    const user = userEvent.setup();
    mount(backend, "/courses/new");
    await user.click(screen.getByRole("radio", { name: "Fast" }));
    await user.type(screen.getByLabelText("Course title"), "API course");
    const prompt = "  Teach me Python  ";
    await user.type(
      screen.getByLabelText("What would you like to learn?"),
      prompt,
    );
    await user.click(
      screen.getByRole("button", { name: "Build my syllabus →" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
    expect(screen.getByText("Your draft is saved.")).toBeInTheDocument();
    expect(
      screen.queryByText("Creating your syllabus…"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Approve syllabus →" }),
    ).toBeDisabled();
    expect(backend.generated).toHaveLength(1); // StrictMode must not resend the initial intent.
    expect(backend.generated[0].message).toBe(prompt);
    expect(backend.generated[0].generationMode).toBe("fast");
    await user.click(screen.getByRole("radio", { name: "Pro" }));
    backend.failGeneration = false;
    await user.click(
      screen.getByRole("button", { name: "Generate syllabus ↑" }),
    );
    expect(
      await screen.findByLabelText("Detailed syllabus"),
    ).toBeInTheDocument();
    expect(backend.created).toHaveLength(1);
    expect(backend.generated[1]).toMatchObject({
      courseId: backend.value.id,
      expectedRevision: 0,
      generationMode: "pro",
    });
  });

  it("restores conversation after remount and sends the next revision on the same course", async () => {
    const backend = new MemoryCourseBackend();
    const user = userEvent.setup();
    const first = mount(backend);
    await user.type(
      await screen.findByLabelText("Ask your course guide"),
      "First adjustment",
    );
    await user.click(screen.getByRole("button", { name: "Send request ↑" }));
    await waitFor(() =>
      expect(screen.getByLabelText("Ask your course guide")).toHaveValue(""),
    );
    first.unmount();
    mount(backend);
    expect(await screen.findByText("First adjustment")).toBeInTheDocument();
    expect(backend.generated).toHaveLength(1);
    await user.type(
      screen.getByLabelText("Ask your course guide"),
      "Add a final project",
    );
    await user.click(screen.getByRole("button", { name: "Send request ↑" }));
    await waitFor(() => expect(backend.generated).toHaveLength(2));
    expect(backend.generated[1]).toEqual({
      courseId: backend.value.id,
      message: "Add a final project",
      expectedRevision: 1,
      generationMode: "balanced",
    });
    await waitFor(() =>
      expect(screen.getByLabelText("Ask your course guide")).toHaveValue(""),
    );
    await user.click(
      screen.getByRole("button", { name: "Approve syllabus →" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Your syllabus is approved.",
      }),
    ).toBeInTheDocument();
    expect(backend.value.status).toBe("ready");
  });

  it("disables conflicting actions while a guide request is running", async () => {
    const backend = new MemoryCourseBackend();
    let finish!: () => void;
    backend.pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const user = userEvent.setup();
    mount(backend);
    await user.type(
      await screen.findByLabelText("Ask your course guide"),
      "Research official sources",
    );
    await user.click(screen.getByRole("button", { name: "Send request ↑" }));
    expect(
      await screen.findByRole("button", { name: "Working on your syllabus…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Approve syllabus →" }),
    ).toBeDisabled();
    expect(screen.getByLabelText("Ask your course guide")).toBeDisabled();
    const syllabus = screen.getByRole("region", { name: backend.value.title });
    expect(within(syllabus).getByRole("status")).toHaveTextContent(
      "Updating your syllabus…",
    );
    expect(within(syllabus).getByLabelText("Detailed syllabus")).toBeVisible();
    expect(backend.generated).toHaveLength(1);
    finish();
    await waitFor(() =>
      expect(screen.getByLabelText("Ask your course guide")).toBeEnabled(),
    );
    expect(within(syllabus).queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows creation progress in the main syllabus until the first outline arrives", async () => {
    const backend = new MemoryCourseBackend();
    backend.value = { ...backend.value, chapters: [] };
    let finish!: () => void;
    backend.pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const user = userEvent.setup();
    mount(backend);
    await user.click(
      await screen.findByRole("button", { name: "Generate syllabus ↑" }),
    );
    const syllabus = screen.getByRole("region", { name: backend.value.title });
    expect(within(syllabus).getByRole("status")).toHaveTextContent(
      "Creating your syllabus…",
    );
    expect(screen.queryByText("Your draft is saved.")).not.toBeInTheDocument();
    finish();
    expect(await screen.findByLabelText("Detailed syllabus")).toBeVisible();
    expect(within(syllabus).queryByRole("status")).not.toBeInTheDocument();
  });

  it("keeps the message and refreshes a conflicting conversation before retry", async () => {
    const backend = new MemoryCourseBackend();
    backend.conflictNext = true;
    const user = userEvent.setup();
    const { client } = mount(backend);
    await user.type(
      await screen.findByLabelText("Ask your course guide"),
      "Add more practice",
    );
    await user.click(screen.getByRole("button", { name: "Send request ↑" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "latest syllabus",
    );
    expect(screen.getByLabelText("Ask your course guide")).toHaveValue(
      "Add more practice",
    );
    await waitFor(() =>
      expect(
        client.getQueryData<{ syllabus: { revision: number } }>([
          "courses",
          backend.value.id,
        ])?.syllabus.revision,
      ).toBe(1),
    );
    await user.click(screen.getByRole("button", { name: "Send request ↑" }));
    await waitFor(() => expect(backend.generated).toHaveLength(2));
    expect(backend.generated[1].expectedRevision).toBe(1);
  });
  it("restores an agent clarification on an empty saved draft without resending", async () => {
    const backend = new MemoryCourseBackend();
    backend.value = {
      ...backend.value,
      chapters: [],
      messages: [
        { role: "learner", text: "Physics" },
        { role: "guide", text: "Which level should I teach?" },
      ],
      syllabus: { revision: 1, lessons: [], outcomes: [], warnings: [] },
    };
    const user = userEvent.setup();
    mount(backend);
    expect(
      await screen.findByText("Which level should I teach?"),
    ).toBeVisible();
    expect(backend.generated).toHaveLength(0);
    await user.type(screen.getByLabelText("Ask your course guide"), "Beginner");
    await user.click(
      screen.getByRole("button", { name: "Generate syllabus ↑" }),
    );
    await waitFor(() => expect(backend.generated).toHaveLength(1));
    expect(backend.generated[0]).toMatchObject({
      message: "Beginner",
      expectedRevision: 1,
    });
  });
  it("renders readable source links without interpreting agent HTML", async () => {
    const backend = new MemoryCourseBackend();
    backend.value = {
      ...backend.value,
      messages: [
        {
          role: "guide",
          text: "See [official docs](https://docs.python.org/3/). <img src=x onerror=alert(1)>",
        },
      ],
    };
    mount(backend);
    expect(
      await screen.findByRole("link", { name: "official docs" }),
    ).toHaveAttribute("href", "https://docs.python.org/3/");
    expect(screen.getByText(/<img src=x/)).toBeVisible();
  });
});
