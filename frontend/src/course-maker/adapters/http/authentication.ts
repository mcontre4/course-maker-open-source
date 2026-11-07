import { z } from "zod";
import type {
  Authentication,
  AccountSession,
} from "../../application/authentication";

const sessionSchema = z.object({
  user: z
    .object({
      id: z.string(),
      email: z.string(),
      first_name: z.string(),
      last_name: z.string(),
      verified: z.boolean(),
    })
    .nullable(),
  csrf_token: z.string(),
  google_enabled: z.boolean(),
});

export async function accountAuthenticationEnabled(
  transport: typeof fetch,
): Promise<boolean> {
  const response = await transport("/api/v1/auth/config", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Couldn’t load account configuration");
  return z.object({ enabled: z.boolean() }).parse(await response.json())
    .enabled;
}

/** Turn the server's field errors into a sentence. It never echoes what was typed. */
function validationMessage(detail: unknown): string {
  const fields = Array.isArray(detail)
    ? detail.flatMap((item) =>
        item && typeof item === "object" && Array.isArray(item.loc)
          ? item.loc.map(String)
          : [],
      )
    : [];
  if (fields.includes("password"))
    return "Use a password of 15 to 128 characters.";
  if (fields.includes("email")) return "Enter a valid email address.";
  return "Please check the fields and try again.";
}

export class HttpAuthentication implements Authentication {
  private csrf: string | null = null;
  private generation = 0;
  private accountRequests = new AbortController();
  private principal: string | null | undefined;
  private sessionRequest: Promise<AccountSession> | null = null;
  private bootstrap: Promise<AccountSession> | null = null;
  private listeners = new Set<() => void>();

  constructor(private readonly transport: typeof fetch) {}

  session(): Promise<AccountSession> {
    if (this.sessionRequest) return this.sessionRequest;
    const pending = this.readSession().finally(() => {
      if (this.sessionRequest === pending) this.sessionRequest = null;
    });
    this.sessionRequest = pending;
    return pending;
  }

  private async readSession(): Promise<AccountSession> {
    const started = this.generation;
    const response = await this.transport("/api/v1/auth/session", {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok)
      throw new Error("Couldn’t check your session. Please try again.");
    const result = sessionSchema.parse(await response.json());
    if (started === this.generation) {
      const principal = result.user?.id ?? null;
      if (this.principal !== undefined && this.principal !== principal)
        this.rotateAccountRequests();
      this.principal = principal;
      this.csrf = result.csrf_token;
    }
    return result;
  }

  /** Shared by every application API call, including generation and streaming. */
  async fetch(url: string, init?: RequestInit): Promise<Response> {
    if (!url.startsWith("/api/"))
      throw new Error("Account requests must use the app API");
    const privateRequest = !url.startsWith("/api/v1/auth/");
    const started = this.generation;
    const signal = privateRequest
      ? init?.signal
        ? AbortSignal.any([init.signal, this.accountRequests.signal])
        : this.accountRequests.signal
      : init?.signal;
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = new Headers(init?.headers);
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      if (!this.csrf) {
        if (!this.bootstrap) {
          const pending = this.session().finally(() => {
            if (this.bootstrap === pending) this.bootstrap = null;
          });
          this.bootstrap = pending;
        }
        await this.bootstrap;
      }
      headers.set("X-CSRF-Token", this.csrf!);
    }
    if (privateRequest) this.requireCurrentAccount(started);
    signal?.throwIfAborted();
    const response = await this.transport(url, {
      ...init,
      signal,
      method,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
    if (privateRequest && started !== this.generation) {
      void response.body?.cancel().catch(() => undefined);
      this.requireCurrentAccount(started);
    }
    if (
      response.status === 401 &&
      started === this.generation &&
      privateRequest
    ) {
      this.rotateAccountRequests();
      this.csrf = null;
      this.listeners.forEach((listener) => listener());
    }
    return response;
  }

  private rotateAccountRequests() {
    this.generation++;
    // Clearing UI caches alone cannot stop old mutations or unread response bodies.
    this.accountRequests.abort();
    this.accountRequests = new AbortController();
    this.bootstrap = null;
    this.sessionRequest = null;
  }

  private requireCurrentAccount(started: number) {
    if (started !== this.generation)
      throw new DOMException(
        "Your account changed. Please try again.",
        "AbortError",
      );
  }

  private async post(path: string, body: object = {}): Promise<unknown> {
    const response = await this.fetch("/api/v1/auth/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        typeof error.detail === "string"
          ? error.detail
          : response.status === 429
            ? "Too many attempts. Please try again later."
            : validationMessage(error.detail),
      );
    }
    return response.status === 204 ? undefined : response.json();
  }

  private async message(path: string, body: object): Promise<string> {
    return z.object({ message: z.string() }).parse(await this.post(path, body))
      .message;
  }

  async signIn(email: string, password: string): Promise<AccountSession> {
    const result = sessionSchema.parse(
      await this.post("signin", { email, password }),
    );
    this.rotateAccountRequests();
    this.principal = result.user?.id ?? null;
    this.csrf = result.csrf_token;
    return result;
  }

  signUp(input: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }) {
    return this.message("signup", input);
  }

  async signOut(): Promise<void> {
    await this.post("signout");
    this.rotateAccountRequests();
    this.principal = null;
    this.csrf = null;
  }

  requestEmail(email: string, purpose: "verify" | "reset") {
    return this.message(
      purpose === "reset" ? "forgot-password" : "resend-verification",
      { email },
    );
  }

  completeEmail(token: string, purpose: "verify" | "reset", password?: string) {
    return this.message(
      purpose === "reset" ? "reset-password" : "verify-email",
      purpose === "reset" ? { token, password } : { token },
    );
  }

  async beginGoogle(): Promise<string> {
    return z
      .object({ url: z.string().url() })
      .parse(await this.post("google/start")).url;
  }

  subscribeExpiration(listener: () => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}
