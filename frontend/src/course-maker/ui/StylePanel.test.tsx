import { useQuery } from "@tanstack/react-query";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type {
  StyleBackend,
  StyleResponse,
  UpdateStyleRequest,
} from "../application/style";
import { ListVoices, UpdateStyle } from "../application/style";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { MemoryStandaloneBackend } from "../testing/standalone-backend";
import { ApplicationContext } from "./application-context";
import { StyleFields, emptyStyle } from "./StyleFields";
import { StylePanel } from "./StylePanel";
import { useState } from "react";

const original: StyleResponse = {
  request: "Professional but warm",
  audience: "Professionals",
  summary: "Clear, warm teaching.",
  teaching: "Practical examples",
  writing: "Conversational and precise",
  visuals: "Clear diagrams",
  motion: "Gentle reveals",
  pacing: "Measured",
  voiceDescription: "Warm narrator",
  delivery: "Warm and confident",
  voiceId: "friendly",
  voiceName: "Friendly",
  version: 1,
};

class MemoryStyleBackend implements StyleBackend {
  calls: UpdateStyleRequest[] = [];
  voiceLoads = 0;
  fail = false;
  conflict = false;
  constructor(readonly lessons: MemoryStandaloneBackend) {}
  async voices() {
    this.voiceLoads++;
    return [
      {
        id: "friendly",
        name: "Friendly",
        description: "Warm and curious",
        previewUrl: "https://example.com/friendly.mp3",
        labels: ["accent: American"],
      },
      {
        id: "british",
        name: "British narrator",
        description: "Measured British narrator",
        previewUrl: null,
        labels: ["accent: british"],
      },
      {
        id: "steady",
        name: "Steady",
        description: "Calm and measured",
        previewUrl: "https://example.com/steady.mp3",
        labels: ["accent: American"],
      },
    ];
  }
  async update(request: UpdateStyleRequest) {
    this.calls.push(request);
    if (this.conflict) {
      const old = await this.lessons.get();
      this.lessons.value = {
        ...old,
        content: {
          ...old.content,
          style: { ...original, summary: "Changed in another tab", version: 2 },
        },
      };
      throw new Error("Style changed; review the latest style before saving");
    }
    if (this.fail) throw new Error("Style planning unavailable. Please retry.");
    const old = await this.lessons.get();
    this.lessons.value = {
      ...old,
      revision: old.revision + 1,
      content: {
        ...old.content,
        style: {
          ...original,
          request: request.style?.description ?? "",
          accent: request.style?.accent ?? "American",
          tone: request.style?.tone ?? "",
          requestedPacing: request.style?.pacing ?? "",
          voiceId: request.style?.voiceId ?? "friendly",
          voiceName: "Steady",
          version: 2,
        },
        styleHistory: [original],
      },
    };
    return this.lessons.value;
  }
}

async function setup(
  focus?: "voice" | "visuals",
  style: StyleResponse = original,
) {
  const lessons = new MemoryStandaloneBackend();
  await lessons.create({
    title: "Bonds",
    description: "Explain bonds",
    minutes: 1,
  });
  lessons.value = {
    ...lessons.value!,
    content: { ...lessons.value!.content, style },
  };
  const backend = new MemoryStyleBackend(lessons);
  const app = {
    ...createBackendCourseApplication(new MemoryCourseBackend()),
    styles: {
      voices: new ListVoices(backend),
      update: new UpdateStyle(backend),
    },
  };
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Workspace() {
    const data = useQuery({
      queryKey: ["lessons", "lesson_one"],
      queryFn: () => lessons.get(),
    }).data;
    return data ? (
      <StylePanel
        id={data.id}
        kind="lesson"
        style={data.content.style}
        history={data.content.styleHistory}
        generationMode="fast"
        focus={focus}
      />
    ) : null;
  }
  const view = render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider client={cache}>
        <Workspace />
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  if (!focus) await screen.findByText(original.summary);
  else await screen.findByRole("region", { name: /Visual style|Voice/ });
  return { backend, view, app, cache };
}

describe("lesson style", () => {
  it("edits visuals directly in a focused panel and confirms the save", async () => {
    const { backend } = await setup("visuals", {
      ...original,
      visualStyleId: "whiteboard",
    });
    const user = userEvent.setup();
    expect(screen.getByText(/Whiteboard Explainer · AI review/)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Edit style" }),
    ).not.toBeInTheDocument();
    const save = screen.getByRole("button", { name: "Save visuals" });
    expect(save).toBeDisabled();
    const input = screen.getByLabelText("Visual instructions");
    await user.clear(input);
    await user.type(input, "Labeled diagrams");
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(input).toHaveValue(original.request);
    await user.type(input, ", with arrows");
    await user.click(save);
    expect(
      await screen.findByText(/Saved\. Generate an updated video/),
    ).toBeVisible();
    expect(backend.calls[0].style?.description).toBe(
      original.request + ", with arrows",
    );
    expect(screen.getByLabelText("Visual instructions")).toHaveValue(
      original.request + ", with arrows",
    );
    expect(screen.getByRole("button", { name: "Save visuals" })).toBeDisabled();
  });

  it("loads voice previews on demand, saves with version and fast mode, and restores style history", async () => {
    const { backend } = await setup();
    const user = userEvent.setup();
    expect(backend.voiceLoads).toBe(0);
    await user.click(screen.getByText("Advanced settings"));
    await user.click(screen.getByRole("button", { name: "Edit style" }));

    await screen.findByRole("option", { name: "Steady" });
    await user.selectOptions(screen.getByLabelText("Narrator voice"), "steady");
    expect(screen.getByLabelText("Preview Steady")).toHaveAttribute(
      "src",
      "https://example.com/steady.mp3",
    );
    await user.click(screen.getByRole("button", { name: "Save style" }));
    await waitFor(() => expect(backend.calls).toHaveLength(1));
    expect(backend.calls[0]).toMatchObject({
      id: "lesson_one",
      expectedVersion: 1,
      generationMode: "fast",
      style: {
        description: original.request,
        audience: "Professionals",
        voiceId: "steady",
      },
    });
    await screen.findByText(/Narrator: Steady/);
    expect(screen.getByText("Previous style versions (1)")).toBeInTheDocument();
  });

  it("preserves the edited description after a failed save", async () => {
    const { backend } = await setup();
    backend.fail = true;
    const user = userEvent.setup();
    await user.click(screen.getByText("Advanced settings"));
    await user.click(screen.getByRole("button", { name: "Edit style" }));
    const input = screen.getByLabelText(
      "Teaching tone and preferences (optional)",
      {
        selector: "textarea",
      },
    );
    await user.clear(input);
    await user.type(input, "Warm and supportive, no humor");
    await user.click(screen.getByRole("button", { name: "Save style" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
    expect(input).toHaveValue("Warm and supportive, no humor");
  });

  it("keeps unsaved text when a conflicting save refreshes the style version", async () => {
    const { backend } = await setup();
    backend.conflict = true;
    const user = userEvent.setup();
    await user.click(screen.getByText("Advanced settings"));
    await user.click(screen.getByRole("button", { name: "Edit style" }));
    const input = screen.getByLabelText(
      "Teaching tone and preferences (optional)",
      {
        selector: "textarea",
      },
    );
    await user.clear(input);
    await user.type(input, "My unsaved warm style");
    await user.click(screen.getByRole("button", { name: "Save style" }));
    await screen.findByText("Changed in another tab");
    expect(screen.getByRole("alert")).toHaveTextContent("Style changed");
    expect(
      screen.getByLabelText("Teaching tone and preferences (optional)", {
        selector: "textarea",
      }),
    ).toHaveValue("My unsaved warm style");
  });

  it("requires visual selection and keeps audience, tone and review independent", async () => {
    const { app, cache, view } = await setup();
    view.unmount();
    function Fields() {
      const [value, setValue] = useState(emptyStyle);
      return <StyleFields value={value} onChange={setValue} />;
    }
    render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={cache}>
          <Fields />
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    const user = userEvent.setup();
    await user.click(screen.getByText("Advanced settings"));
    expect(
      screen.getByRole("radio", { name: /^Flat-Vector Science/ }),
    ).not.toBeChecked();
    await user.click(
      screen.getByRole("radio", { name: /^Flat-Vector Science/ }),
    );
    expect(screen.getByLabelText("AI review before delivery")).toBeChecked();
    await user.click(screen.getByLabelText("AI review before delivery"));
    expect(
      screen.getByLabelText("AI review before delivery"),
    ).not.toBeChecked();
    const input = screen.getByLabelText(
      "Teaching tone and preferences (optional)",
    );
    await user.type(input, " For professionals learning a new tool.");

    await user.type(screen.getByLabelText("Who is this for?"), "Professionals");
    expect((input as HTMLTextAreaElement).value).toContain("professionals");
    expect(screen.getByLabelText("Who is this for?")).toHaveValue(
      "Professionals",
    );
  });
});

it("hides advanced settings, filters accents and saves custom tone and pacing", async () => {
  const { backend } = await setup();
  const user = userEvent.setup();
  const advanced = screen.getByText("Advanced settings").closest("details");
  expect(advanced).not.toHaveAttribute("open");
  expect(screen.getByRole("button", { name: "Edit style" })).not.toBeVisible();
  await user.click(screen.getByText("Advanced settings"));
  await user.click(screen.getByRole("button", { name: "Edit style" }));
  await screen.findByRole("option", { name: "Friendly" });
  expect(screen.getByLabelText("Accent")).toHaveValue("American");
  expect(
    screen.queryByRole("option", { name: "British narrator" }),
  ).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Accent"), "British");
  expect(screen.getByLabelText("Narrator voice")).toHaveValue("");
  expect(
    screen.queryByRole("option", { name: "Friendly" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Preview Friendly")).not.toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Narrator voice"), "british");
  expect(
    screen.getByText("No sample is available for this voice."),
  ).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Tone"), "custom");
  await user.type(
    screen.getByLabelText("Custom tone"),
    "Reassuring and curious",
  );
  await user.selectOptions(screen.getByLabelText("Pacing"), "Relaxed");
  await user.click(screen.getByRole("button", { name: "Save style" }));
  await waitFor(() => expect(backend.calls).toHaveLength(1));
  expect(backend.calls[0].style).toMatchObject({
    accent: "British",
    voiceId: "british",
    tone: "Reassuring and curious",
    pacing: "Relaxed",
  });
});

it("loads creation voice options only when advanced settings opens and retains tone when collapsed", async () => {
  const { app, cache, view, backend } = await setup();
  view.unmount();
  function Fields() {
    const [value, setValue] = useState(emptyStyle);
    return <StyleFields value={value} onChange={setValue} />;
  }
  render(
    <ApplicationContext.Provider value={app}>
      <QueryClientProvider client={cache}>
        <Fields />
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  const user = userEvent.setup();
  expect(backend.voiceLoads).toBe(0);
  expect(screen.getByRole("combobox", { name: "Tone" })).not.toBeVisible();
  await user.click(screen.getByText("Advanced settings"));
  await screen.findByRole("option", { name: "Friendly" });
  expect(backend.voiceLoads).toBe(1);
  await user.selectOptions(screen.getByLabelText("Tone"), "Calm");
  await user.click(screen.getByText("Advanced settings"));
  await user.click(screen.getByText("Advanced settings"));
  expect(screen.getByLabelText("Tone")).toHaveValue("Calm");
});
