/**
 * Sending someone back to the page they asked for after they sign in.
 *
 * A signed-out visit to a protected page (a link shared by email, say) lands on
 * the sign-in page with the address in `?next=`. It is a query parameter
 * rather than router state so it survives a refresh of the sign-in page.
 */

const DEFAULT_AFTER_LOGIN = "/dashboard";

/** The sign-in page's address, remembering `path` to return to. */
export const loginPathFor = (path: string): string =>
  path && path !== "/" ? `/?next=${encodeURIComponent(path)}` : "/";

/**
 * Where to go after signing in. Only a path inside this app is accepted:
 * `next` comes from the address bar, so anything that could leave the site
 * (`//evil.example`, `https://...`, `/\evil`) falls back to the dashboard.
 */
export const afterLoginPath = (search: string): string => {
  const next = new URLSearchParams(search).get("next");
  if (!next) return DEFAULT_AFTER_LOGIN;
  const safe =
    next.startsWith("/") &&
    !next.startsWith("//") &&
    !next.startsWith("/\\") &&
    !/[\u0000-\u001f]/.test(next) &&
    next !== "/";
  return safe ? next : DEFAULT_AFTER_LOGIN;
};
