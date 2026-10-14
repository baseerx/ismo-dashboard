import { useEffect } from "react";
import { Outlet, Navigate, useLocation, useNavigate } from "react-router-dom";
import axios from "../../api/axios";
import { loginPathFor } from "./returnTo";

const ProtectedRoute = () => {
  const token = localStorage.getItem("token");
  const location = useLocation();
  const navigate = useNavigate();

  // Sign-in tokens do not expire, so ask the server - on every page change -
  // whether this account may still be used. A locked (or removed) account is
  // signed out here, with the reason carried to the sign-in page.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    axios
      .get("/users/session_check/", { headers: { Authorization: `Bearer ${token}` } })
      .catch((error) => {
        const status = error?.response?.status;
        if (cancelled || (status !== 423 && status !== 401)) return; // network trouble: leave it
        try {
          sessionStorage.setItem(
            "ismo:signout-reason",
            JSON.stringify({
              tone: status === 423 ? "locked" : "ended",
              text: error?.response?.data?.error ?? "Your session has ended. Sign in again.",
            })
          );
        } catch { /* storage unavailable */ }
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        const here = `${location.pathname}${location.search}${location.hash}`;
        navigate(loginPathFor(here), { replace: true });
      });
    return () => {
      cancelled = true;
    };
  }, [token, location.pathname, location.search, location.hash, navigate]);

  // Signed out: go to the sign-in page, remembering this address so signing in
  // lands back here rather than on the dashboard.
  if (!token) {
    const here = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={loginPathFor(here)} replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
