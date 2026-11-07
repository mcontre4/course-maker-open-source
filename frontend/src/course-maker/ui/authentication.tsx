import {
  Fragment,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type {
  Authentication,
  AccountSession,
} from "../application/authentication";
import { accountPath, isPrivatePath } from "./auth-routes";

type AuthState = {
  client: Authentication;
  session: AccountSession | null;
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
  accept: (session: AccountSession) => void;
  signOut: () => Promise<void>;
  navigateProvider: (url: string) => void;
};
const AuthContext = createContext<AuthState | null>(null);
export const useAuthentication = () => useContext(AuthContext);

/**
 * Whether this visitor may use account features. Demo mode and screens rendered
 * without an authentication provider have no accounts, so nothing is locked.
 */
export function useSignedIn(): boolean {
  const auth = useAuthentication();
  return !auth || !!auth.session?.user;
}

export function AuthenticationProvider({
  client,
  navigateProvider,
  children,
}: {
  client: Authentication;
  navigateProvider: (url: string) => void;
  children: ReactNode;
}) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<AccountSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const previousUser = useRef<string | undefined>(undefined);
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const started = generation.current;
    try {
      const next = await client.session();
      if (started !== generation.current) return;
      if (previousUser.current !== next.user?.id) queryClient.clear();
      previousUser.current = next.user?.id;
      setSession(next);
      setError("");
    } catch {
      if (started !== generation.current) return;
      setError("Couldn’t check your session. Please try again.");
      setSession(null);
    } finally {
      if (started === generation.current) setLoading(false);
    }
  }, [client, queryClient]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(
    () =>
      client.subscribeExpiration(() => {
        if (!previousUser.current) return;
        previousUser.current = undefined;
        generation.current++;
        queryClient.clear();
        setSession(null);
        void refresh();
      }),
    [client, queryClient, refresh],
  );
  const accept = (next: AccountSession) => {
    generation.current++;
    queryClient.clear();
    previousUser.current = next.user?.id;
    setSession(next);
    setError("");
    setLoading(false);
  };
  const signOut = async () => {
    await client.signOut();
    previousUser.current = undefined;
    generation.current++;
    await queryClient.cancelQueries();
    queryClient.clear();
    setSession(null);
    await refresh();
  };
  return (
    <AuthContext.Provider
      value={{
        client,
        session,
        loading,
        error,
        refresh,
        accept,
        signOut,
        navigateProvider,
      }}
    >
      {loading ? (
        <p role="status" className="session-check">
          Checking your session…
        </p>
      ) : (
        <Fragment key={session?.user?.id ?? "guest"}>{children}</Fragment>
      )}
    </AuthContext.Provider>
  );
}

/**
 * Keeps visitors out of pages that show or change someone's own work. Every
 * other page, including the home page, renders for signed-out visitors.
 */
export function AuthenticationGate({ children }: { children: ReactNode }) {
  const auth = useAuthentication();
  const location = useLocation();
  // Demo and existing isolated screen tests supply no authentication provider.
  if (!auth) return children;
  if (!isPrivatePath(location.pathname)) return children;
  if (auth.loading)
    return (
      <p role="status" className="session-check">
        Checking your session…
      </p>
    );
  if (auth.error)
    return (
      <div role="alert" className="status-panel">
        <h1>We couldn’t check your session.</h1>
        <p className="muted">{auth.error}</p>
        <button className="btn btn-primary" onClick={() => void auth.refresh()}>
          Try again
        </button>
      </div>
    );
  if (!auth.session?.user)
    return (
      <Navigate
        replace
        to={accountPath("/login", location.pathname + location.search)}
      />
    );
  return children;
}
