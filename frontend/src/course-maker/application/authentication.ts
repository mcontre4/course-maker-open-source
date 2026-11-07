/** Account transport port. Browser session secrets stay in HttpOnly cookies. */
export type AccountUser = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  verified: boolean;
};

export type AccountSession = {
  user: AccountUser | null;
  csrf_token: string;
  google_enabled: boolean;
};

export interface Authentication {
  session(): Promise<AccountSession>;
  signIn(email: string, password: string): Promise<AccountSession>;
  signUp(input: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }): Promise<string>;
  signOut(): Promise<void>;
  requestEmail(email: string, purpose: "verify" | "reset"): Promise<string>;
  completeEmail(
    token: string,
    purpose: "verify" | "reset",
    password?: string,
  ): Promise<string>;
  beginGoogle(): Promise<string>;
  subscribeExpiration(listener: () => void): () => void;
}
