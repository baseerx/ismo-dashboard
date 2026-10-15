import { useEffect, useState } from "react";
import { Outlet, Navigate, useLocation, useNavigate } from "react-router-dom";
import axios from "../../api/axios";
import { loginPathFor } from "./returnTo";
import ForcePasswordChange from "./ForcePasswordChange";

const storedUser = () => {
  try {
    return JSON.parse(localStorage.getItem("user") || "{}");
  } catch {
    return {};
  }
};

const ProtectedRoute = () => {
  const token = localStorage.getItem("token");
  const location = useLocation();
  const navigate = useNavigate();

  // After an administrator reset, nothing but the change-password step is
  // shown. Starts from what sign-in said and is confirmed by the server on
  // every page change, so clearing it in the browser does not skip the step.
  const [mustChange, setMustChange] = useState<boolean>(() => !!storedUser().must_change_password);
  const [email, setEmail] = useState<string>(() => storedUser().email || "");

  const signOut = (reason?: { tone: "locked" | "ended"; text: string }) => {
    if (reason) {
      try {
        sessionStorage.setItem("ismo:signout-reason", JSON.stringify(reason));
      } catch { /* storage unavailable */ }
    }
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    const here = `${location.pathname}${location.search}${location.hash}`;
    navigate(loginPathFor(here), { replace: true });
  };

  // Sign-in tokens do not expire, so ask the server - on every page change -
  // whether this account may still be used. A locked (or removed) account is
  // signed out here, with the reason carried to the sign-in page.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    axios
      .get("/users/session_check/", { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (cancelled) return;
        setMustChange(!!response.data?.must_change_password);
        if (response.data?.email) setEmail(response.data.email);
      })
      .catch((error) => {
        const status = error?.response?.status;
        if (cancelled || (status !== 423 && status !== 401)) return; // network trouble: leave it
        signOut({
          tone: status === 423 ? "locked" : "ended",
          text: error?.response?.data?.error ?? "Your session has ended. Sign in again.",
        });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, location.pathname, location.search, location.hash]);

  // Signed out: go to the sign-in page, remembering this address so signing in
  // lands back here rather than on the dashboard.
  if (!token) {
    const here = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={loginPathFor(here)} replace />;
  }

  if (mustChange) {
    return (
      <ForcePasswordChange
        email={email}
        onSignOut={() => signOut()}
        onDone={(newEmail) => {
          const user = storedUser();
          localStorage.setItem(
            "user",
            JSON.stringify({ ...user, email: newEmail, must_change_password: false })
          );
          setEmail(newEmail);
          setMustChange(false);
        }}
      />
    );
  }

  return <Outlet />;
};

export default ProtectedRoute;
