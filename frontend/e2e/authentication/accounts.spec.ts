import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

const password = "a unique long passphrase 47!";

async function signIn(page: Page, email: string, secret = password) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(secret);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL("/");
}

async function mailLink(
  request: APIRequestContext,
  email: string,
  subject: string,
) {
  const response = await request.get("http://127.0.0.1:5183/__test/mail", {
    params: { email, subject },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).url as string;
}

test("email signup, verification, reload, signout and password recovery", async ({
  page,
  request,
  context,
}) => {
  const email = "browser-account@example.com";
  const errors: string[] = [];
  const privateGuestRequests: string[] = [];
  const trackGuestRequest = (request: import("@playwright/test").Request) => {
    if (/\/api\/v1\/(lessons|courses)(\?|$)/.test(request.url()))
      privateGuestRequests.push(request.url());
  };
  page.on("request", trackGuestRequest);
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/workspace");
  await expect(page).toHaveURL(/\/login\?returnTo=/);
  await expect(page.getByText("Sign in to see your creations.")).toBeVisible();
  await page
    .getByRole("link", { name: "Create an account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/signup\?returnTo=/);
  await page.getByLabel("First name").fill("Ada");
  await page.getByLabel("Last name").fill("Lovelace");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Check your email" }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("receive an email");
  expect(privateGuestRequests).toEqual([]);
  page.off("request", trackGuestRequest);
  await page.goto(await mailLink(request, email, "Verify your email"));
  await page
    .getByRole("button", { name: "Verify your email", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Email verified" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Continue to sign in" }).click();
  await expect(page).toHaveURL("/login");
  await signIn(page, email);
  await page.goto("/workspace");
  await expect(
    page.getByRole("heading", { name: "My creations", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "My creations", exact: true }),
  ).toBeVisible();
  const cookies = await context.cookies();
  expect(cookies.find((c) => c.name === "cm_session")?.httpOnly).toBe(true);
  const stored = await page.evaluate(() => ({ ...localStorage }));
  expect(JSON.stringify(stored)).not.toContain(password);
  expect(JSON.stringify(stored)).not.toContain(
    cookies.find((c) => c.name === "cm_session")!.value,
  );
  await page.getByLabel(/^Account:/).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(
    page.getByRole("heading", { name: "Reset your password", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByRole("status")).toContainText("receive an email");
  await page.goto(await mailLink(request, email, "Reset your password"));
  const replacement = "a different unique passphrase 93!";
  await page.getByLabel("New password", { exact: true }).fill(replacement);
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(
    page.getByRole("heading", { name: "Password updated" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Continue to sign in" }).click();
  await signIn(page, email, replacement);
  expect(errors).toEqual([]);
  await page.screenshot({
    path: "test-results/authenticated-account.png",
    fullPage: true,
  });
});

test("visitors can look around without an account and sign in only to create", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  const privateRequests: string[] = [];
  const rejected: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (call) => {
    const path = new URL(call.url()).pathname;
    if (
      path.startsWith("/api/") &&
      !path.startsWith("/api/v1/auth/") &&
      !path.startsWith("/api/v1/published/") &&
      !path.startsWith("/api/v1/creators/")
    )
      privateRequests.push(path);
  });
  page.on("response", (reply) => {
    if (reply.status() === 401) rejected.push(reply.url());
  });

  // The home page is open to everyone.
  await page.goto("/");
  await expect(page).toHaveURL("/");
  await expect(
    page.getByRole("heading", { name: "What would you like to learn next?" }),
  ).toBeVisible();
  const header = page.getByRole("banner");
  await expect(header.getByRole("link", { name: "Sign in" })).toBeVisible();
  await expect(header.getByRole("link", { name: "Sign up" })).toBeVisible();
  await expect(
    header.getByRole("link", { name: "Home", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("No account needed to watch")).toBeVisible();
  await page.screenshot({
    path: "test-results/visitor-home.png",
    fullPage: true,
    animations: "disabled",
  });

  // So are Explore and search; none of it asks for private data.
  await header.getByText("Explore", { exact: true }).click();
  await page.getByRole("link", { name: /View all lessons/ }).click();
  await expect(page).toHaveURL("/explore");
  await expect(
    page.getByRole("heading", { name: "All lessons", exact: true }),
  ).toBeVisible();
  const search = page.getByRole("combobox", { name: "Search lessons" });
  await search.fill("physics");
  await search.press("Enter");
  await expect(page).toHaveURL(/physics/);
  await page.goto("/");
  expect(privateRequests).toEqual([]);
  expect(rejected).toEqual([]);

  // Making something asks for an account and remembers the destination.
  await page.getByRole("link", { name: "Create a lesson" }).click();
  await expect(page).toHaveURL(/\/login\?returnTo=%2Flessons%2Fnew$/);
  await expect(page.getByText("Sign in to create a lesson.")).toBeVisible();
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(page).toHaveURL(/\/signup\?returnTo=%2Flessons%2Fnew$/);
  await expect(
    page.getByText("Create an account to create a lesson."),
  ).toBeVisible();

  // Sign up, verify, then land on the page the visitor was heading for.
  const email = "visitor-creator@example.com";
  await page.getByLabel("First name").fill("Grace");
  await page.getByLabel("Last name").fill("Hopper");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(
    page.getByRole("heading", { name: "Check your email" }),
  ).toBeVisible();
  await page.goto(await mailLink(request, email, "Verify your email"));
  await page.getByRole("button", { name: "Verify your email" }).click();
  await page.goto("/lessons/new");
  await expect(page).toHaveURL(/\/login\?returnTo=%2Flessons%2Fnew$/);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL("/lessons/new");
  await expect(
    page.getByRole("heading", { name: "Let’s make a lesson." }),
  ).toBeVisible();
  await expect(page.getByLabel(/^Account:/)).toBeVisible();
  await expect(
    page.getByRole("banner").getByRole("link", { name: "Sign in" }),
  ).toHaveCount(0);

  // Signed in, the sign-in pages step aside.
  await page.goto("/login");
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("link", { name: "My learning" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("sign in and sign up explain problems before and after sending", async ({
  page,
}) => {
  await page.goto("/signup");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Enter your first name.")).toBeVisible();
  await expect(page.getByText("Enter your last name.")).toBeVisible();
  await expect(page.getByText("Enter your email address.")).toBeVisible();
  await expect(page.getByText("Choose a password.")).toBeVisible();
  await expect(page.getByLabel("First name")).toBeFocused();

  await page.getByLabel("Email", { exact: true }).fill("not-an-email");
  await page.getByLabel("Password", { exact: true }).fill("too short");
  await expect(
    page.getByText("Enter a valid email, like name@example.com."),
  ).toBeVisible();
  await expect(page.getByText("Use at least 15 characters.")).toBeVisible();
  await expect(page.getByText("9 of 15 characters")).toBeVisible();
  await page.getByLabel("Password", { exact: true }).fill(password);
  await expect(page.getByText("Long enough.")).toBeVisible();

  // The password can be revealed and hidden again.
  const field = page.getByLabel("Password", { exact: true });
  await expect(field).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(field).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Hide password" }).click();
  await expect(field).toHaveAttribute("type", "password");

  // A wrong password says what to try next and keeps the email.
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("nobody@example.com");
  await page.getByLabel("Password", { exact: true }).fill("not the password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("Unable to sign in");
  await expect(
    alert.getByRole("link", { name: "Reset your password" }),
  ).toBeVisible();
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue(
    "nobody@example.com",
  );
  await alert.getByRole("link", { name: "Reset your password" }).click();
  await expect(page).toHaveURL("/forgot-password");
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue(
    "nobody@example.com",
  );

  // A reset page opened without its emailed link points to a new one.
  await page.goto("/reset-password");
  await expect(
    page.getByText(/needs the link from your password/),
  ).toBeVisible();
  await page.getByRole("link", { name: "Send a new reset link" }).click();
  await expect(page).toHaveURL("/forgot-password");
});

test("account pages fit a phone without sideways scrolling", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  for (const path of [
    "/",
    "/login",
    "/signup",
    "/forgot-password",
    "/explore",
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
  for (const [name, path] of [
    ["home-mobile", "/"],
    ["signup-mobile", "/signup"],
    ["login-mobile", "/login?returnTo=%2Flessons%2Fnew"],
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
    await page.screenshot({
      path: `test-results/${name}.png`,
      fullPage: true,
      animations: "disabled",
    });
  }
});

test("Google redirect round trip establishes a server session", async ({
  page,
}) => {
  // Replace only the external consent screen. State cookies, callback, Redis flow,
  // account creation and session persistence execute in the real backend.
  await page.route("https://accounts.google.com/**", async (route) => {
    const state = new URL(route.request().url()).searchParams.get("state")!;
    await route.fulfill({
      status: 302,
      headers: {
        location:
          "http://127.0.0.1:5182/api/v1/auth/google/callback?code=valid-code&state=" +
          encodeURIComponent(state),
      },
    });
  });
  await page.goto("/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL("/");
  await page.getByLabel(/^Account:/).click();
  await expect(page.locator(".account-panel")).toContainText(
    "google@example.com",
  );
  await page.reload();
  await expect(page.getByLabel(/^Account:/)).toBeVisible();
});
