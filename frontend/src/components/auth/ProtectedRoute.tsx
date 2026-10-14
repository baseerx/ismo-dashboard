import { Outlet, Navigate, useLocation } from "react-router-dom";
import { loginPathFor } from "./returnTo";

const ProtectedRoute = () => {
  const token = localStorage.getItem("token");
  const location = useLocation();

  // Signed out: go to the sign-in page, remembering this address so signing in
  // lands back here rather than on the dashboard.
  if (!token) {
    const here = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to={loginPathFor(here)} replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
