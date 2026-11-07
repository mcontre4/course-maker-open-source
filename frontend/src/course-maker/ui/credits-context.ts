import { createContext, useContext, useState } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useApplication } from "./application-context";

/** Give up polling a checkout after this many checks (about a minute). */
export const CHECKOUT_POLL_LIMIT = 30;
const CHECKOUT_POLL_MS = 2000;

/** How the browser leaves for the hosted payment page. Tests substitute it. */
export type CheckoutRedirect = (url: string) => void;
export const CheckoutRedirectContext = createContext<CheckoutRedirect>((url) =>
  window.location.assign(url),
);

function useCredits() {
  return useApplication().credits;
}

export function useCreditBalance() {
  const api = useCredits();
  return useQuery({
    queryKey: ["credits", "balance"],
    enabled: !!api,
    queryFn: () => api!.balance(),
    staleTime: 10_000,
  });
}

export function useCreditPacks() {
  const api = useCredits();
  return useQuery({
    queryKey: ["credits", "packs"],
    enabled: !!api,
    queryFn: () => api!.packs(),
    staleTime: 5 * 60_000,
  });
}

export function useCreditHistory() {
  const api = useCredits();
  return useInfiniteQuery({
    queryKey: ["credits", "history"],
    enabled: !!api,
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => api!.history(pageParam),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
}

export function useCheckoutStatus(checkoutId: string | null) {
  const api = useCredits();
  const [checks, setChecks] = useState(0);
  const query = useQuery({
    queryKey: ["credits", "checkout", checkoutId],
    enabled: !!api && !!checkoutId,
    queryFn: () => {
      setChecks((count) => count + 1);
      return api!.checkoutStatus(checkoutId!);
    },
    staleTime: 0,
    refetchInterval: (current) =>
      current.state.data?.status === "pending" &&
      current.state.dataUpdateCount < CHECKOUT_POLL_LIMIT
        ? CHECKOUT_POLL_MS
        : false,
  });
  return {
    ...query,
    /** True once polling stopped while the payment was still pending. */
    gaveUp: query.data?.status === "pending" && checks >= CHECKOUT_POLL_LIMIT,
  };
}

/** Start checkout, then hand the browser to the hosted payment page. */
export function useStartCheckout() {
  const api = useCredits();
  const redirect = useContext(CheckoutRedirectContext);
  return useMutation({
    mutationFn: async (packId: string) => {
      if (!api) throw new Error("Credits aren’t available right now.");
      const session = await api.startCheckout(packId);
      redirect(session.url);
      return session;
    },
  });
}

/** Refetch balance and activity after anything that may have changed them. */
export function useRefreshCredits() {
  const cache = useQueryClient();
  return () =>
    Promise.all([
      cache.invalidateQueries({ queryKey: ["credits", "balance"] }),
      cache.invalidateQueries({ queryKey: ["credits", "history"] }),
    ]);
}
