import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import type { Creators, Discovery } from "../application/creators";
import { createBackendCourseApplication } from "../composition";
import { MemoryCourseBackend } from "../testing/course-backend";
import { ApplicationContext } from "./application-context";
import { CourseSearch } from "./DiscoveryNavigation";

function publicLesson(title: string): Discovery {
  return {
    courses: [],
    lessons: [
      {
        id: title,
        title,
        image: "",
        minutes: 3,
        videoUrl: null,
        courseId: null,
      },
    ],
  };
}

function mount(discover: Creators["discover"], withCourse = false) {
  const backend = new MemoryCourseBackend();
  const app = createBackendCourseApplication(backend);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const creators: Creators = {
    discover,
    own: async () => ({ id: "user_test", name: "Creator", picture: null }),
    save: async (profile) => ({ id: "user_test", ...profile }),
    page: async () => {
      throw new Error("Unused");
    },
    watch: async () => {
      throw new Error("Unused");
    },
  };
  render(
    <QueryClientProvider client={client}>
      <ApplicationContext.Provider
        value={{
          ...app,
          creators,
          listCourses: {
            execute: async () =>
              withCourse ? [{ ...backend.value, title: "Learn algebra" }] : [],
          },
        }}
      >
        <MemoryRouter>
          <CourseSearch />
        </MemoryRouter>
      </ApplicationContext.Provider>
    </QueryClientProvider>,
  );
}

it("keeps the current query's results when an earlier search finishes late", async () => {
  const pending = new Map<string, (data: Discovery) => void>();
  mount((query = "") => new Promise((resolve) => pending.set(query, resolve)));
  const user = userEvent.setup();
  const input = screen.getByRole("combobox");
  await user.type(input, "alpha");
  await waitFor(() => expect(pending.has("alpha")).toBe(true));
  await user.clear(input);
  await user.type(input, "beta");
  await waitFor(() => expect(pending.has("beta")).toBe(true));
  await act(async () => pending.get("beta")!(publicLesson("Beta lesson")));
  expect(
    await screen.findByRole("option", { name: /Beta lesson/ }),
  ).toBeVisible();
  await act(async () => pending.get("alpha")!(publicLesson("Alpha lesson")));
  expect(
    screen.queryByRole("option", { name: /Alpha lesson/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: /Beta lesson/ })).toBeVisible();
});

it("keeps keyboard selection on the same result when new matches reorder the list", async () => {
  let resolve!: (data: Discovery) => void;
  mount(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
    true,
  );
  const user = userEvent.setup();
  await user.type(screen.getByRole("combobox"), "algebra");
  const saved = await screen.findByRole("option", { name: /Learn algebra/ });
  await user.keyboard("{ArrowDown}");
  await waitFor(() => expect(resolve).toBeDefined());
  await act(async () => resolve(publicLesson("Algebra")));
  await screen.findByRole("option", { name: /^Algebra/ });
  expect(saved).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("combobox")).toHaveAttribute(
    "aria-activedescendant",
    saved.id,
  );
});

it("retries a failed public search without losing the text or inventing sample results", async () => {
  let calls = 0;
  mount(async () => {
    if (++calls === 1) throw new Error("Offline");
    return publicLesson("Algebra");
  });
  const user = userEvent.setup();
  const input = screen.getByRole("combobox");
  await user.type(input, "algebra");
  await user.click(await screen.findByRole("button", { name: "Retry search" }));
  expect(await screen.findByRole("option", { name: /Algebra/ })).toBeVisible();
  expect(input).toHaveValue("algebra");
  expect(calls).toBe(2);
});
