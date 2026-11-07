import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../../App";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import { BrowserProfileStore } from "../adapters/persistence/browser-profile-store";
import type { Profile, ProfileStore } from "../application/profile";
import type { KeyValueStorage } from "../adapters/persistence/browser-course-repository";
class MemoryStorage implements KeyValueStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}
class UnavailableProfileStore implements ProfileStore {
  load(): Profile {
    return { name: "Learner", email: "learner@example.com", picture: null };
  }
  save(): void {
    throw new Error("Storage unavailable");
  }
}
function mount(
  route = "/settings",
  storage = new MemoryStorage(),
  profileStore: ProfileStore = new BrowserProfileStore(storage),
) {
  const app = createCourseApplication(storage, { next: () => "course_new" });
  return {
    app,
    ...render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider
          client={
            new QueryClient({
              defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
              },
            })
          }
        >
          <MemoryRouter initialEntries={[route]}>
            <App profileStore={profileStore} />
          </MemoryRouter>
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    ),
  };
}
describe("Profile and personal navigation", () => {
  it("saves a trimmed profile, updates the account menu, and survives a remount", async () => {
    const user = userEvent.setup();
    const storage = new MemoryStorage();
    const view = mount("/settings", storage);
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Name", { exact: true }));
    await user.type(
      screen.getByLabelText("Name", { exact: true }),
      "  Alex Learner  ",
    );
    await user.type(
      screen.getByLabelText("Email", { exact: true }),
      "alex@example.com",
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByRole("status")).toHaveTextContent("Profile saved.");
    const account = screen.getByLabelText("Account: Alex Learner");
    await user.click(account);
    expect(screen.getByText("alex@example.com")).toBeVisible();
    await user.keyboard("{Escape}");
    expect(account.closest("details")).not.toHaveAttribute("open");
    expect(account).toHaveFocus();
    view.unmount();
    mount("/settings", storage);
    expect(screen.getByLabelText("Name", { exact: true })).toHaveValue(
      "Alex Learner",
    );
    expect(screen.getByLabelText("Email", { exact: true })).toHaveValue(
      "alex@example.com",
    );
  });
  it("rejects a blank name and reports persistence failure without updating the profile", async () => {
    const user = userEvent.setup();
    mount("/settings", new MemoryStorage(), new UnavailableProfileStore());
    await user.clear(screen.getByLabelText("Name", { exact: true }));
    await user.type(screen.getByLabelText("Name", { exact: true }), "   ");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter your name.");
    await user.type(screen.getByLabelText("Name", { exact: true }), "Alex");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByRole("alert")).toHaveTextContent("couldn’t be saved");
    expect(screen.queryByText("Profile saved.")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Account: Learner")).toBeInTheDocument();
  });
  it("navigates to separate started courses and drafts and dismisses the menu", async () => {
    const user = userEvent.setup();
    mount("/");
    await user.click(screen.getByLabelText("Account: Learner"));
    await user.click(screen.getByRole("link", { name: "My library" }));
    await screen.findByRole("heading", { name: "My library" });
    expect(
      await screen.findByRole("heading", { name: "Python for everyday life" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: "The art of telling a good story",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("Account: Learner").closest("details"),
    ).not.toHaveAttribute("open");
    await user.click(screen.getByLabelText("Account: Learner"));
    await user.click(screen.getByRole("link", { name: "My creations" }));
    await screen.findByRole("heading", { name: "My creations" });
    expect(
      await screen.findByRole("heading", {
        name: "The art of telling a good story",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Python for everyday life" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Continue course" }));
    expect(
      await screen.findByLabelText("Detailed syllabus"),
    ).toBeInTheDocument();
  });
  it("moves a newly created draft into My library after approval", async () => {
    const user = userEvent.setup();
    mount("/courses/new");
    await user.type(screen.getByLabelText("Course title"), "Learning to draw");
    await user.type(
      screen.getByLabelText("What would you like to learn?"),
      "Learn the basics of drawing.",
    );
    await user.click(
      screen.getByRole("button", { name: "Build my syllabus →" }),
    );
    await screen.findByLabelText("Detailed syllabus");
    await user.click(screen.getByLabelText("Account: Learner"));
    await user.click(screen.getByRole("link", { name: "My creations" }));
    const draft = (
      await screen.findByRole("heading", { name: "Learning to draw" })
    ).closest("li")!;
    await user.click(
      within(draft).getByRole("link", { name: "Continue course" }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "Approve syllabus & create first lesson →",
      }),
    );
    await screen.findByRole("heading", { name: "Your syllabus is approved." });
    await user.click(screen.getByLabelText("Account: Learner"));
    await user.click(screen.getByRole("link", { name: "My library" }));
    expect(
      await screen.findByRole("heading", { name: "Learning to draw" }),
    ).toBeInTheDocument();
  });
  it("offers useful empty states", async () => {
    const storage = new MemoryStorage();
    storage.setItem(
      "course-maker:v1",
      JSON.stringify({ version: 1, courses: [] }),
    );
    const view = mount("/workspace", storage);
    expect(
      await screen.findByRole("heading", {
        name: "Your next idea starts here",
      }),
    ).toBeInTheDocument();
    view.unmount();
    mount("/library", storage);
    expect(
      await screen.findByRole("heading", { name: "Nothing to learn from yet" }),
    ).toBeInTheDocument();
  });
  it("rejects unsupported pictures", async () => {
    const user = userEvent.setup({ applyAccept: false });
    mount();
    await user.upload(
      screen.getByLabelText("Upload profile picture"),
      new File(["text"], "photo.svg", { type: "image/svg+xml" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("JPG, PNG, or WebP");
  });
  it("lets a rejected replacement cancel a pending picture read", async () => {
    const user = userEvent.setup({ applyAccept: false });
    mount("/settings", new MemoryStorage(), new UnavailableProfileStore());
    await user.type(screen.getByLabelText("Name", { exact: true }), " Learner");
    const upload = screen.getByLabelText("Upload profile picture");
    await user.upload(
      upload,
      new File(["pending image"], "photo.png", { type: "image/png" }),
    );
    expect(
      screen.getByRole("button", { name: "Reading photo…" }),
    ).toBeDisabled();
    await user.upload(
      upload,
      new File(["unsupported"], "photo.svg", { type: "image/svg+xml" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("JPG, PNG, or WebP");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  });
});
