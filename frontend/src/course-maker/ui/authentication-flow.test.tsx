import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type {
  AccountSession,
  AccountUser,
  Authentication,
} from "../application/authentication";
import { AuthenticationGate, AuthenticationProvider } from "./authentication";
import { AuthenticationPage } from "./pages/AuthenticationPage";

const user: AccountUser = {
  id: "user_1",
  email: "ada@example.com",
  first_name: "Ada",
  last_name: "Lovelace",
  verified: true,
};

class FakeAuthentication implements Authentication {
  signIns: Array<{ email: string; password: string }> = [];
  signUps: Array<{ email: string; first_name: string; last_name: string }> = [];
  emails: Array<{ email: string; purpose: string }> = [];
  completions: Array<{ token: string; purpose: string; password?: string }> =
    [];
  signInFails = false;

  constructor(private current: AccountSession) {}

  async session() {
    return this.current;
  }
  async signIn(email: string, password: string) {
    this.signIns.push({ email, password });
    if (this.signInFails)
      throw new Error(
        "Unable to sign in. Check your credentials and verify your email.",
      );
    this.current = { ...this.current, user };
    return this.current;
  }
  async signUp(input: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) {
    this.signUps.push(input);
    return "If this address can be used, you’ll receive an email with the next steps.";
  }
  async signOut() {}
  async requestEmail(email: string, purpose: "verify" | "reset") {
    this.emails.push({ email, purpose });
    return "If this address can be used, you’ll receive an email with the next steps.";
  }
  async completeEmail(
    token: string,
    purpose: "verify" | "reset",
    password?: string,
  ) {
    this.completions.push({ token, purpose, password });
    return "Done.";
  }
  async beginGoogle() {
    return "https://accounts.google.com/o/oauth2/v2/auth";
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
const signedIn: AccountSession = { ...guest, user };

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname + location.search}</p>;
}

function renderApp(client: Authentication, entry: string) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[entry]}>
        <AuthenticationProvider client={client} navigateProvider={() => {}}>
          <Where />
          <AuthenticationGate>
            <Routes>
              <Route
                path="/login"
                element={<AuthenticationPage mode="login" />}
              />
              <Route
                path="/signup"
                element={<AuthenticationPage mode="signup" />}
              />
              <Route
                path="/forgot-password"
                element={<AuthenticationPage mode="forgot-password" />}
              />
              <Route
                path="/verify-email"
                element={<AuthenticationPage mode="verify-email" />}
              />
              <Route path="/" element={<p>Public home</p>} />
              <Route path="/explore" element={<p>Public explore</p>} />
              <Route path="/workspace" element={<p>My creations</p>} />
              <Route path="/lessons/new" element={<p>New lesson form</p>} />
            </Routes>
          </AuthenticationGate>
        </AuthenticationProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const where = () => screen.getByTestId("where").textContent;

describe("visitors without an account", () => {
  it("can see the home page and Explore", async () => {
    renderApp(new FakeAuthentication(guest), "/");
    expect(await screen.findByText("Public home")).toBeInTheDocument();
    expect(where()).toBe("/");
  });

  it("can see Explore", async () => {
    renderApp(new FakeAuthentication(guest), "/explore");
    expect(await screen.findByText("Public explore")).toBeInTheDocument();
  });

  it("are sent to sign in, with the reason, to open their own work", async () => {
    renderApp(new FakeAuthentication(guest), "/lessons/new");
    expect(
      await screen.findByRole("heading", { name: "Welcome back" }),
    ).toBeInTheDocument();
    expect(where()).toBe("/login?returnTo=%2Flessons%2Fnew");
    expect(screen.getByText("Sign in to create a lesson.")).toBeInTheDocument();
    expect(screen.queryByText("New lesson form")).not.toBeInTheDocument();
  });

  it("carry the destination through to sign up", async () => {
    const person = userEvent.setup();
    renderApp(new FakeAuthentication(guest), "/workspace");
    await person.click(
      await screen.findByRole("link", { name: "Create an account" }),
    );
    expect(where()).toBe("/signup?returnTo=%2Fworkspace");
    expect(
      screen.getByText("Create an account to see your creations."),
    ).toBeInTheDocument();
  });
});

describe("people who are signed in", () => {
  it("open their own pages", async () => {
    renderApp(new FakeAuthentication(signedIn), "/workspace");
    expect(await screen.findByText("My creations")).toBeInTheDocument();
  });

  it("skip the sign-in page and go where they were headed", async () => {
    renderApp(new FakeAuthentication(signedIn), "/login?returnTo=%2Fworkspace");
    expect(await screen.findByText("My creations")).toBeInTheDocument();
    expect(where()).toBe("/workspace");
  });

  it("never follow a return address that leaves the site", async () => {
    renderApp(
      new FakeAuthentication(signedIn),
      "/login?returnTo=%2F%2Fevil.example",
    );
    expect(await screen.findByText("Public home")).toBeInTheDocument();
    expect(where()).toBe("/");
  });
});

describe("signing in", () => {
  it("explains what is missing without calling the server", async () => {
    const client = new FakeAuthentication(guest);
    const person = userEvent.setup();
    renderApp(client, "/login");
    await person.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Enter your email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveFocus();
    expect(client.signIns).toEqual([]);
  });

  it("signs in and returns to the page the visitor wanted", async () => {
    const client = new FakeAuthentication(guest);
    const person = userEvent.setup();
    renderApp(client, "/login?returnTo=%2Fworkspace");
    await person.type(
      await screen.findByLabelText("Email"),
      " ada@example.com ",
    );
    await person.type(screen.getByLabelText("Password"), "correct horse");
    await person.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("My creations")).toBeInTheDocument();
    expect(client.signIns).toEqual([
      { email: "ada@example.com", password: "correct horse" },
    ]);
    expect(where()).toBe("/workspace");
  });

  it("shows a failed sign-in with ways forward and keeps the email", async () => {
    const client = new FakeAuthentication(guest);
    client.signInFails = true;
    const person = userEvent.setup();
    renderApp(client, "/login");
    await person.type(await screen.findByLabelText("Email"), "ada@example.com");
    await person.type(screen.getByLabelText("Password"), "nope");
    await person.click(screen.getByRole("button", { name: "Sign in" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Unable to sign in");
    expect(
      screen.getByRole("link", { name: "Reset your password" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("ada@example.com");
  });

  it("can show and hide the password", async () => {
    const person = userEvent.setup();
    renderApp(new FakeAuthentication(guest), "/login");
    const field = await screen.findByLabelText("Password");
    expect(field).toHaveAttribute("type", "password");
    await person.click(screen.getByRole("button", { name: "Show password" }));
    expect(field).toHaveAttribute("type", "text");
    await person.click(screen.getByRole("button", { name: "Hide password" }));
    expect(field).toHaveAttribute("type", "password");
  });
});

describe("creating an account", () => {
  async function fillSignUp(person: ReturnType<typeof userEvent.setup>) {
    await person.type(await screen.findByLabelText("First name"), "Ada");
    await person.type(screen.getByLabelText("Last name"), "Lovelace");
    await person.type(screen.getByLabelText("Email"), "ada@example.com");
  }

  it("counts toward the minimum length and rejects a short password", async () => {
    const client = new FakeAuthentication(guest);
    const person = userEvent.setup();
    renderApp(client, "/signup");
    await fillSignUp(person);
    await person.type(screen.getByLabelText("Password"), "too short");
    expect(screen.getByText("9 of 15 characters")).toBeInTheDocument();
    await person.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Use at least 15 characters.")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveFocus();
    expect(client.signUps).toEqual([]);
  });

  it("asks the person to check their email, and can start over", async () => {
    const client = new FakeAuthentication(guest);
    const person = userEvent.setup();
    renderApp(client, "/signup");
    await fillSignUp(person);
    await person.type(
      screen.getByLabelText("Password"),
      "a unique long passphrase 47!",
    );
    await person.click(screen.getByRole("button", { name: "Create account" }));
    const heading = await screen.findByRole("heading", {
      name: "Check your email",
    });
    expect(heading).toBeInTheDocument();
    // Focus moves with the content so keyboard users aren't left behind.
    expect(heading).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("receive an email");
    expect(client.signUps).toHaveLength(1);
    // A fresh message can't be requested straight away.
    expect(
      screen.getByRole("button", { name: /Resend email in \d+s/ }),
    ).toBeDisabled();
    await person.click(
      screen.getByRole("button", { name: "Use a different email" }),
    );
    expect(await screen.findByLabelText("Email")).toHaveValue(
      "ada@example.com",
    );
  });
});

describe("email links", () => {
  it("confirms an address from the emailed link", async () => {
    const client = new FakeAuthentication(guest);
    const person = userEvent.setup();
    renderApp(client, "/verify-email#token=" + "t".repeat(40));
    await person.click(
      await screen.findByRole("button", { name: "Verify your email" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Email verified" }),
      ).toBeInTheDocument(),
    );
    expect(client.completions).toEqual([
      { token: "t".repeat(40), purpose: "verify", password: "" },
    ]);
    expect(
      screen.getByRole("link", { name: "Continue to sign in" }),
    ).toBeInTheDocument();
  });

  it("sends a reset link and carries the email from the sign-in page", async () => {
    const client = new FakeAuthentication(guest);
    const person = userEvent.setup();
    renderApp(client, "/login");
    await person.type(await screen.findByLabelText("Email"), "ada@example.com");
    await person.click(screen.getByRole("link", { name: "Forgot password?" }));
    expect(await screen.findByLabelText("Email")).toHaveValue(
      "ada@example.com",
    );
    await person.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(
      await screen.findByRole("heading", { name: "Check your email" }),
    ).toBeInTheDocument();
    expect(client.emails).toEqual([
      { email: "ada@example.com", purpose: "reset" },
    ]);
  });
});
