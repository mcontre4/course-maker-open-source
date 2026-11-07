import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../../App";
import { createCourseApplication } from "../composition";
import { ApplicationContext } from "./application-context";
import { CheckoutRedirectContext } from "./credits-context";
import { ErrorNotice } from "./components";
import { MemoryCredits } from "../testing/credits";
import type { CreditTransaction } from "../application/credits";
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
const purchase: CreditTransaction = {
  id: "t1",
  kind: "purchase",
  credits: 550,
  description: "Creator pack",
  createdAt: "2026-10-30T09:15:00Z",
};
const usage: CreditTransaction = {
  id: "t2",
  kind: "usage",
  credits: -30,
  description: "Lesson: Why the tides move",
  createdAt: "2026-10-31T14:00:00Z",
};

function mount(credits: MemoryCredits, route = "/credits") {
  const redirects: string[] = [];
  const app = {
    ...createCourseApplication(new MemoryStorage(), { next: () => "id" }),
    credits,
  };
  render(
    <ApplicationContext.Provider value={app}>
      <CheckoutRedirectContext.Provider value={(url) => redirects.push(url)}>
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
            <App />
          </MemoryRouter>
        </QueryClientProvider>
      </CheckoutRedirectContext.Provider>
    </ApplicationContext.Provider>,
  );
  return redirects;
}

describe("Credits", () => {
  it("shows the balance in the header, the account menu and the page", async () => {
    const user = userEvent.setup();
    mount(new MemoryCredits(1240, [usage, purchase]));
    expect(
      await screen.findByRole("link", {
        name: "1,240 credits. Buy more credits",
      }),
    ).toHaveAttribute("href", "/credits");
    const balance = await screen.findByRole("region", { name: "YOUR BALANCE" });
    expect(within(balance).getByText("1,240")).toBeVisible();
    expect(within(balance).getByText(/all set to create/)).toBeVisible();
    await user.click(screen.getByLabelText(/^Account:/));
    expect(
      screen.getByRole("link", {
        name: /Credits/,
        description: /1,240 credits/,
      }),
    ).toHaveAttribute("href", "/credits");
    const activity = screen.getByRole("list");
    expect(
      within(activity).getByText("Why the tides move", { exact: false }),
    ).toBeVisible();
    expect(within(activity).getByText("−30")).toBeVisible();
    expect(within(activity).getByText("+550")).toBeVisible();
  });

  it("warns when credits are low or gone", async () => {
    mount(new MemoryCredits(0));
    expect(await screen.findByText(/out of credits/i)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "0 credits. Buy more credits" }),
    ).toHaveClass("credit-chip-empty");
    expect(screen.getByText(/Nothing here yet/)).toBeVisible();
  });

  it("hides credits when the server does not offer them", () => {
    const app = createCourseApplication(new MemoryStorage(), {
      next: () => "id",
    });
    render(
      <ApplicationContext.Provider value={app}>
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter initialEntries={["/credits"]}>
            <App />
          </MemoryRouter>
        </QueryClientProvider>
      </ApplicationContext.Provider>,
    );
    expect(screen.getByText(/Credits aren’t available yet/)).toBeVisible();
    expect(screen.queryByRole("link", { name: /Buy more credits/ })).toBeNull();
  });

  it("buys the chosen pack by sending the learner to the hosted checkout", async () => {
    const user = userEvent.setup();
    const credits = new MemoryCredits(10);
    const redirects = mount(credits);
    // The badged pack is preselected.
    await screen.findByRole("button", {
      name: "Buy 550 credits · $20.00",
    });
    await user.click(screen.getByRole("radio", { name: /Starter/ }));
    await user.click(
      screen.getByRole("button", { name: "Buy 100 credits · $5.00" }),
    );
    expect(credits.checkouts).toEqual(["pack_small"]);
    expect(redirects).toEqual(["https://pay.example.test/c/1"]);
    expect(
      await screen.findByRole("button", { name: "Taking you to checkout…" }),
    ).toBeDisabled();
  });

  it("keeps the learner on the page with a clear error when checkout cannot start", async () => {
    const user = userEvent.setup();
    const credits = new MemoryCredits(10);
    credits.failCheckout = true;
    const redirects = mount(credits);
    await user.click(
      await screen.findByRole("button", { name: /^Buy 550 credits/ }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You haven’t been charged",
    );
    expect(redirects).toEqual([]);
    expect(
      screen.getByRole("button", { name: /^Buy 550 credits/ }),
    ).toBeEnabled();
  });

  it("confirms a purchase when returning from the payment page", async () => {
    const credits = new MemoryCredits(660);
    mount(credits, "/credits?checkout=success&checkout_id=checkout_1");
    expect(await screen.findByText("Payment received")).toBeVisible();
    expect(
      screen.getByText("550 credits added to your balance."),
    ).toBeVisible();
  });

  it("explains a cancelled or failed checkout and lets the learner dismiss it", async () => {
    const user = userEvent.setup();
    mount(new MemoryCredits(5), "/credits?checkout=cancelled");
    expect(await screen.findByText("Checkout cancelled")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Dismiss message" }));
    expect(screen.queryByText("Checkout cancelled")).toBeNull();
  });

  it("reports a payment that did not go through", async () => {
    const credits = new MemoryCredits(5);
    credits.statuses = [{ status: "failed", creditsAdded: 0 }];
    mount(credits, "/credits?checkout=success&checkout_id=checkout_1");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The payment didn’t go through",
    );
  });

  it("loads older activity on request", async () => {
    const user = userEvent.setup();
    const credits = new MemoryCredits(100);
    credits.pages = [[usage], [purchase]];
    mount(credits);
    await screen.findByText(/Why the tides move/);
    expect(screen.queryByText("Creator pack")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show more" }));
    expect(await screen.findByText("Creator pack")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
  });

  it("offers a way to buy credits when an action is refused for lack of them", () => {
    render(
      <MemoryRouter>
        <ErrorNotice
          error={Object.assign(new Error("Not enough credits."), {
            status: 402,
          })}
        />
        <ErrorNotice error={new Error("Something else.")} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Buy credits" })).toHaveAttribute(
      "href",
      "/credits",
    );
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
