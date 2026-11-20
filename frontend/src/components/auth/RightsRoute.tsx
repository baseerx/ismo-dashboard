import { useEffect, useState } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import axios from "../../api/axios";

/**
 * Only the pages Assign Rights has granted the signed-in user may be opened -
 * typing an address that is not granted shows "no access" instead of the
 * page. Sits inside ProtectedRoute, so signed-out visitors have already been
 * sent to the sign-in page (and come back here after signing in).
 *
 * The list is asked for again on every page change, so a right taken away
 * takes effect at the next navigation. If the list cannot be loaded the page
 * stays closed: this fails shut, not open.
 *
 * This hides pages; it does not stop a determined user calling the API. The
 * API checks its own rights where it matters (see jobs/permissions.py).
 */

// Every signed-in user's own pages, which are not on the menu.
const ALWAYS_ALLOWED = ["/change-password", "/profile"];

const normalise = (path: string) => path.replace(/\/+$/, "").toLowerCase() || "/";

const RightsRoute = () => {
  const location = useLocation();
  const token = localStorage.getItem("token");
  const [granted, setGranted] = useState<string[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    axios
      .get("/assignrights/my-pages/", {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      .then((response) => {
        if (cancelled) return;
        const uris: string[] = Array.isArray(response.data?.uris) ? response.data.uris : [];
        setGranted(uris.map(normalise));
        setFailed(false);
      })
      .catch(() => {
        if (cancelled) return;
        setGranted(null);
        setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [token, location.pathname, attempt]);

  if (failed) {
    return (
      <Notice
        title="Could not check your access"
        text="Your page rights could not be loaded, so this page is not shown. Check your connection and try again."
        action={
          <button
            type="button"
            onClick={() => {
              setFailed(false);
              setAttempt((n) => n + 1);
            }}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
          >
            Try again
          </button>
        }
      />
    );
  }

  if (granted === null) {
    return <div className="py-20 text-center text-sm text-gray-400">Checking access…</div>;
  }

  const here = normalise(location.pathname);
  if (ALWAYS_ALLOWED.includes(here) || granted.includes(here)) {
    return <Outlet />;
  }

  // The dashboard is where sign-in lands by default. Someone without it goes
  // to the first page they do have rather than to a "no access" notice.
  const firstPage = granted.find((uri) => uri !== "/dashboard");
  if (here === "/dashboard" && firstPage) {
    return <Navigate to={firstPage} replace />;
  }

  const home = granted.includes("/dashboard") ? "/dashboard" : firstPage;
  return (
    <Notice
      title="You do not have access to this page"
      text="This page has not been assigned to your account. If you need it, ask the administrator to grant it through Assign Rights."
      action={
        home ? (
          <Link
            to={home}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
          >
            Go to my pages
          </Link>
        ) : null
      }
    />
  );
};

const Notice = ({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action: React.ReactNode;
}) => (
  <div className="mx-auto mt-10 max-w-lg rounded-2xl border border-gray-200 bg-white p-8 text-center dark:border-gray-800 dark:bg-white/[0.03]">
    <h2 className="text-lg font-semibold text-gray-800 dark:text-white/90">{title}</h2>
    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">{text}</p>
    {action && <div className="mt-6 flex justify-center">{action}</div>}
  </div>
);

export default RightsRoute;
