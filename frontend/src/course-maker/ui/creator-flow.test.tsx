import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import App from "../../App";
import { createApiCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import type { Creator, PublishedLesson } from "../application/creators";

class CreatorServer {
  creator: Creator = { id: "user_ada", name: "Ada Lovelace", picture: null };
  writes: unknown[] = [];
  missing = false;
  lesson: PublishedLesson = {
    id: "lesson_inertia",
    title: "Understanding inertia",
    minutes: 3,
    image: "",
    videoUrl: "https://media.example/inertia.mp4",
    courseId: null,
  };
  courseLesson: PublishedLesson = {
    ...this.lesson,
    id: "lesson_velocity",
    title: "Velocity",
    courseId: "course_physics",
  };
  nextLesson: PublishedLesson = {
    ...this.courseLesson,
    id: "lesson_acceleration",
    title: "Acceleration",
  };
  transport = async (url: string, init?: RequestInit) => {
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      this.writes.push(body);
      this.creator = { ...this.creator, ...body };
    }
    if (url.endsWith("/creators/me")) return Response.json(this.creator);
    if (this.missing) return Response.json({}, { status: 404 });
    if (url.includes("/published/lessons/"))
      return Response.json({
        creator: this.creator,
        lesson: url.includes("lesson_acceleration")
          ? this.nextLesson
          : url.includes("course_id=")
            ? this.courseLesson
            : this.lesson,
      });
    if (url.includes("/creators/") || url.endsWith("/published/discovery"))
      return Response.json({
        ...(url.endsWith("/published/discovery")
          ? {}
          : { creator: this.creator }),
        lessons: [this.lesson],
        courses: [
          {
            id: "course_physics",
            title: "Physics",
            description: "Motion basics",
            image: "",
            lessons: [this.courseLesson, this.nextLesson],
          },
        ],
      });
    if (url.includes("/courses?"))
      return Response.json({ items: [], total: 0 });
    if (url.includes("/lessons?")) return Response.json([]);
    throw new Error("Unexpected request: " + url);
  };
}
function mount(server: CreatorServer, route = "/creators/user_ada") {
  return render(
    <ApplicationContext.Provider
      value={createApiCourseApplication(server.transport)}
    >
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={[route]}>
          <App />
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
}
describe("Public creator browsing", () => {
  it("loads real discovery items and opens the public player", async () => {
    const user = userEvent.setup();
    mount(new CreatorServer(), "/explore");
    const lessons = await screen.findByRole("region", {
      name: "Newest lessons",
    });
    await user.click(
      await within(lessons).findByRole("link", {
        name: /Understanding inertia/,
      }),
    );
    expect(
      await screen.findByLabelText("Understanding inertia"),
    ).toHaveAttribute("src", "https://media.example/inertia.mp4");
  });
  it("opens a real course from discovery", async () => {
    const user = userEvent.setup();
    mount(new CreatorServer(), "/explore");
    await user.click(
      await screen.findByRole("link", { name: "Start course →" }),
    );
    expect(await screen.findByLabelText("Velocity")).toBeInTheDocument();
  });
  it("opens a published lesson and links back to its creator", async () => {
    const user = userEvent.setup();
    const server = new CreatorServer();
    mount(server);
    expect(
      await screen.findByRole("heading", { name: "Ada Lovelace" }),
    ).toBeInTheDocument();
    const section = screen.getByRole("region", { name: "Lessons" });
    await user.click(
      within(section).getByRole("link", { name: /Understanding inertia/ }),
    );
    const video = await screen.findByLabelText("Understanding inertia");
    expect(video).toHaveAttribute("src", "https://media.example/inertia.mp4");
    expect(video).toHaveAttribute("controls");
    await user.click(
      screen.getByRole("link", { name: /Created by Ada Lovelace/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "Ada Lovelace" }),
    ).toBeInTheDocument();
  });
  it("starts a course and shows its published lessons", async () => {
    const user = userEvent.setup();
    mount(new CreatorServer());
    await user.click(await screen.findByRole("link", { name: "Start course" }));
    expect(await screen.findByLabelText("Velocity")).toHaveAttribute(
      "src",
      "https://media.example/inertia.mp4",
    );
    const nav = await screen.findByRole("navigation", {
      name: "Course lessons",
    });
    expect(within(nav).getByRole("link", { name: "Velocity" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
  it("loads persisted creator details into Settings and the account after browser storage is cleared", async () => {
    const server = new CreatorServer();
    mount(server, "/settings");
    expect(await screen.findByLabelText("Name")).toHaveValue("Ada Lovelace");
    expect(screen.getByLabelText("Email")).toHaveValue("");
    expect(screen.getByLabelText("Account: Ada Lovelace")).toBeInTheDocument();
  });
  it("recreates the player when different lessons share a media URL", async () => {
    const user = userEvent.setup();
    mount(new CreatorServer());
    await user.click(await screen.findByRole("link", { name: "Start course" }));
    const firstVideo = await screen.findByLabelText("Velocity");
    const nav = await screen.findByRole("navigation", {
      name: "Course lessons",
    });
    await user.click(within(nav).getByRole("link", { name: "Acceleration" }));
    expect(await screen.findByLabelText("Acceleration")).not.toBe(firstVideo);
  });
  it("persists public name separately from private email", async () => {
    const server = new CreatorServer();
    const user = userEvent.setup();
    const first = mount(server, "/settings");
    await user.clear(await screen.findByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Ada Byron");
    await user.type(screen.getByLabelText("Email"), "private@example.com");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Profile saved.",
    );
    expect(server.writes).toEqual([{ name: "Ada Byron", picture: null }]);
    first.unmount();
    mount(server);
    expect(
      await screen.findByRole("heading", { name: "Ada Byron" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("private@example.com")).not.toBeInTheDocument();
  });
  it("reports missing profiles with a retry action", async () => {
    const server = new CreatorServer();
    server.missing = true;
    mount(server);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "could not be found",
    );
    expect(
      screen.getByRole("button", { name: /Try again/i }),
    ).toBeInTheDocument();
  });
});
