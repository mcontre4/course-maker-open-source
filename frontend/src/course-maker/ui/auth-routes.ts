/**
 * Which pages need an account. Everything not listed here is open to visitors:
 * the home page, Explore, public lessons and creator profiles. People only have
 * to sign in when they want to make something or open their own work.
 */
const PRIVATE_PREFIXES = [
  "/library",
  "/workspace",
  "/my-courses",
  "/settings",
  "/credits",
  "/lessons",
  "/courses",
  "/internal",
];

export const ACCOUNT_PATHS = [
  "/login",
  "/signup",
  "/forgot-password",
  "/verify-email",
  "/reset-password",
];

export function isPrivatePath(pathname: string): boolean {
  return PRIVATE_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(prefix + "/"),
  );
}

export function isAccountPath(pathname: string): boolean {
  return ACCOUNT_PATHS.includes(pathname);
}

/** Only same-site paths are accepted as a place to return to after signing in. */
export function safeReturnPath(value: string | null): string {
  return value && /^\/(?!\/)/.test(value) && !/[\\\s\x00-\x1f]/.test(value)
    ? value
    : "/";
}

/** `/login` or `/signup`, remembering where the visitor was headed. */
export function accountPath(
  page: "/login" | "/signup",
  returnTo?: string,
): string {
  const target = safeReturnPath(returnTo ?? null);
  return target === "/"
    ? page
    : page + "?returnTo=" + encodeURIComponent(target);
}

/** What the visitor is trying to do, in words that finish "Sign in to …". */
export function intentFor(returnTo: string): string {
  const path = returnTo.split(/[?#]/)[0];
  if (path === "/lessons/new") return "create a lesson";
  if (path === "/courses/new") return "create a course";
  if (path.startsWith("/workspace")) return "see your creations";
  if (path.startsWith("/library")) return "open your library";
  if (path.startsWith("/settings")) return "manage your account";
  if (path.startsWith("/credits")) return "manage your credits";
  if (path.startsWith("/lessons") || path.startsWith("/courses"))
    return "open your lesson";
  if (path.startsWith("/watch/") && path.length > "/watch/".length)
    return "copy this lesson";
  return "";
}
