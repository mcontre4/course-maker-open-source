import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "../../App";
import type {
  AccountSession,
  Authentication,
} from "../application/authentication";
import type { Discovery } from "../application/creators";
import type { CourseApplication } from "../application/use-cases";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import { AuthenticationProvider } from "./authentication";

class MemoryStorage {
  private values = new Map<string, string>();
  getItem(key: string) {
    return this.values.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

class Visitor implements Authentication {
  constructor(private current: AccountSession) {}
  async session() {
    return this.current;
  }
  async signIn(): Promise<AccountSession> {
    throw new Error("unused");
  }
  async signUp() {
    return "";
  }
  async signOut() {}
  async requestEmail() {
    return "";
  }
  async completeEmail() {
    return "";
  }
  async beginGoogle() {
    return "";
  }
  subscribeExpiration() {
    return () => undefined;
  }
}

const guest: AccountSession = {
  user: null,
  csrf_token: "csrf",
  google_enabled: false,
};

const discovery: Discovery = {
  lessons: [
    {
      id: "lesson_public",
      title: "How rainbows form",
      image: "story",
      minutes: 3,
      videoUrl: null,
      courseId: null,
    },
  ],
  courses: [],
};

function mount(route: string) {
  const privateCalls: string[] = [];
  const base = createCourseApplication(new MemoryStorage(), {
    next: () => "course_created",
  });
  const application = {
    ...base,
    listCourses: {
      execute: async () => {
        privateCalls.push("courses");
        return [];
      },
    },
    lessons: {
      list: {
        execute: async () => {
          privateCalls.push("lessons");
          return [];
        },
      },
      copy: {
        execute: async () => {
          privateCalls.push("copy");
          throw new Error("A visitor cannot copy a lesson");
        },
      },
    },
    learningActivity: {
      recent: async () => {
        privateCalls.push("activity");
        return [];
      },
      record: async () => undefined,
    },
    creators: {
      own: async () => {
        privateCalls.push("creator");
        return { id: "user_1", name: "Creator", picture: null };
      },
      save: async () => ({ id: "user_1", name: "Creator", picture: null }),
      discover: async () => discovery,
      page: async () => {
        throw new Error("unused");
      },
      watch: async () => ({
        creator: null,
        lesson: discovery.lessons[0],
      }),
    },
  } as unknown as CourseApplication;
  render(
    <ApplicationContext.Provider value={application}>
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={[route]}>
          <AuthenticationProvider
            client={new Visitor(guest)}
            navigateProvider={() => {}}
          >
            <App />
          </AuthenticationProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ApplicationContext.Provider>,
  );
  return privateCalls;
}

describe("the home page for a visitor", () => {
  it("shows the page and public lessons without asking for private work", async () => {
    const privateCalls = mount("/");
    const hero = (
      await screen.findByRole("heading", {
        name: "What would you like to learn next?",
      })
    ).closest("section") as HTMLElement;
    expect(
      within(hero).getByRole("link", { name: "Create a lesson" }),
    ).toHaveAttribute("href", "/lessons/new");
    expect(
      within(hero).getByText("No account needed to watch. Sign in to create."),
    ).toBeVisible();
    expect(await screen.findByText("How rainbows form")).toBeVisible();
    expect(screen.getByText("Newest lesson")).toBeVisible();
    expect(privateCalls).toEqual([]);
  });

  it("offers Sign in and Sign up in the header, and calls the first tab Home", async () => {
    mount("/");
    const header = await screen.findByRole("banner");
    expect(within(header).getByRole("link", { name: "Home" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      within(header).queryByRole("link", { name: "My learning" }),
    ).not.toBeInTheDocument();
    expect(
      within(header).getByRole("link", { name: "Sign in" }),
    ).toHaveAttribute("href", "/login");
    expect(
      within(header).getByRole("link", { name: "Sign up" }),
    ).toHaveAttribute("href", "/signup");
  });

  it("returns to the page being viewed after signing in from the header", async () => {
    mount("/explore?q=rainbow");
    await screen.findAllByRole("banner");
    const header = screen.getAllByRole("banner")[0];
    expect(
      within(header).getByRole("link", { name: "Sign in" }),
    ).toHaveAttribute("href", "/login?returnTo=%2Fexplore%3Fq%3Drainbow");
  });

  it("sends the visitor to sign in when they choose to create", async () => {
    const person = userEvent.setup();
    mount("/");
    await person.click(
      await screen.findByRole("link", { name: "Create a lesson" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Welcome back" }),
    ).toBeVisible();
    expect(screen.getByText("Sign in to create a lesson.")).toBeVisible();
  });

  it("asks the visitor to sign in before copying a public lesson", async () => {
    const person = userEvent.setup();
    const privateCalls = mount("/watch/lessons/lesson_public");
    await person.click(
      await screen.findByRole("button", { name: "Copy lesson" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Welcome back" }),
    ).toBeVisible();
    expect(screen.getByText("Sign in to copy this lesson.")).toBeVisible();
    expect(privateCalls).toEqual([]);
  });
});
