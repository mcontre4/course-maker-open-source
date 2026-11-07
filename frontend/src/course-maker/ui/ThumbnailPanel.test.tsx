import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import {
  GenerateThumbnail,
  type ThumbnailRequest,
} from "../application/thumbnails";
import { ApplicationContext } from "./application-context";
import { Thumbnail } from "./components";
import { ThumbnailPanel } from "./ThumbnailPanel";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { CreateCoursePage } from "./pages/CreateCoursePage";

const image = "data:image/svg+xml;base64,PHN2Zy8+";

describe("generated thumbnails", () => {
  it("keeps syllabus generation available while a thumbnail is being regenerated", async () => {
    const backend = new MemoryCourseBackend();
    backend.value = { ...backend.value, status: "draft", chapters: [] };
    let finish: () => void = () => {};
    const pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const app = {
      ...createBackendCourseApplication(backend),
      thumbnails: new GenerateThumbnail({
        async generate() {
          await pending;
          return { ...backend.value, image };
        },
      }),
    };
    render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter initialEntries={[`/courses/${backend.value.id}/edit`]}>
            <Routes>
              <Route
                path="/courses/:courseId/edit"
                element={<CreateCoursePage />}
              />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    const draw = await screen.findByRole("button", {
      name: /(?:Generate|Regenerate) thumbnail/,
    });
    await userEvent.setup().click(draw);
    await screen.findByRole("button", { name: "Drawing thumbnail…" });
    expect(screen.getByLabelText("Course title")).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Build my syllabus →" }),
    ).toBeEnabled();
    finish();
    await waitFor(() =>
      expect(screen.getByLabelText("Course title")).toBeEnabled(),
    );
  });

  it("renders saved SVG images and falls back if an image cannot load", () => {
    const view = render(<Thumbnail name={image} variant="course" />);
    const img = view.container.querySelector("img")!;
    expect(img).toHaveAttribute("src", image);
    fireEvent.error(img);
    expect(img.getAttribute("src")).toContain("home-imgThumbnailStory");
  });

  it("does not insert arbitrary SVG markup into the document", () => {
    const view = render(<Thumbnail name={'<svg onload="alert(1)"/>'} />);
    expect(view.container.querySelector("svg")).toBeNull();
    expect(view.container.querySelector("img")?.getAttribute("src")).toContain(
      "ThumbnailStory",
    );
  });

  it("saves the generated response to the cache and requests regeneration explicitly", async () => {
    const backend = new MemoryCourseBackend();
    const requests: ThumbnailRequest[] = [];
    const app = {
      ...createBackendCourseApplication(backend),
      thumbnails: new GenerateThumbnail({
        async generate(request) {
          requests.push(request);
          return { ...backend.value, image };
        },
      }),
    };
    const cache = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    function Preview() {
      const [value, setValue] = useState("");
      return (
        <ThumbnailPanel
          kind="course"
          id={backend.value.id}
          image={value}
          onSaved={(result) => {
            if ("chapters" in result) setValue(result.image);
          }}
        />
      );
    }
    const view = render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={cache}>
          <Preview />
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Generate thumbnail" }),
    );
    await screen.findByRole("button", { name: "Regenerate thumbnail" });
    expect(view.container.querySelector("img")).toHaveAttribute("src", image);
    expect(cache.getQueryData(["courses", backend.value.id])).toMatchObject({
      image,
    });
    await user.click(
      screen.getByRole("button", { name: "Regenerate thumbnail" }),
    );
    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests.map((request) => request.regenerate)).toEqual([
      false,
      true,
    ]);
  });

  it("preserves the preview and shows a retryable provider error", async () => {
    const backend = new MemoryCourseBackend();
    const app = {
      ...createBackendCourseApplication(backend),
      thumbnails: new GenerateThumbnail({
        async generate() {
          throw new Error("Provider unavailable. Try again.");
        },
      }),
    };
    const view = render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={new QueryClient()}>
          <ThumbnailPanel kind="course" id={backend.value.id} image={image} />
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Regenerate thumbnail" }));
    await screen.findByText("Provider unavailable. Try again.");
    expect(view.container.querySelector("img")).toHaveAttribute("src", image);
    expect(
      screen.getByRole("button", { name: "Regenerate thumbnail" }),
    ).toBeEnabled();
  });
});
