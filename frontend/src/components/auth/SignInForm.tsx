import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { EyeCloseIcon, EyeIcon } from "../../icons";
import Label from "../form/Label";
import Input from "../form/input/InputField";
import Checkbox from "../form/input/Checkbox";
import Button from "../ui/button/Button";
import { ToastContainer,toast } from "react-toastify";
import axios from '../../api/axios';
import { useAuth } from "../../context/AuthContext";
import { Link } from "react-router-dom";
import { afterLoginPath } from "./returnTo";
export default function SignInForm() {
    const [isChecked, setIsChecked] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const { login } = useAuth();
    const [user,setUser]=useState<{email:string,password:string}>({
        email:"",
        password:""
    });
    const navigate=useNavigate();
    const location=useLocation();
    // The page the user was sent here from (?next=...), or the dashboard.
    const destination=afterLoginPath(location.search);

    // A lasting warning above the form: tries left, or a locked account.
    // Set by a failed sign-in, or carried over when a locked account's open
    // session was ended (see ProtectedRoute).
    const [warning,setWarning]=useState<{tone:"locked"|"attempts"|"ended";text:string}|null>(()=>{
        try {
            const carried=sessionStorage.getItem("ismo:signout-reason");
            if (carried) {
                sessionStorage.removeItem("ismo:signout-reason");
                const parsed=JSON.parse(carried);
                return {tone:parsed.tone==="locked"?"locked":"ended",text:String(parsed.text)};
            }
        } catch { /* storage unavailable or unreadable - nothing carried over */ }
        return null;
    });

    // Already signed in and following a link to a page: go straight there.
    useEffect(()=>{
        if (localStorage.getItem("token") && new URLSearchParams(location.search).has("next")) {
            navigate(destination,{replace:true});
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    },[]);
    const handleSignIn = async(e:any) => {
        e.preventDefault();
        if (!user.email || !user.password) {
            toast.error("Please fill in all fields");
            return;
        }
        
        try {
            const response = await axios.post("/users/login/", user);
            if (response.status === 200) {
                const userData = response.data;
                // console.log("Login response:", userData);
                toast.loading("Logging in...");
                login(userData);
                toast.success("Login successful");
                toast.dismiss();
                // Back to the page that was asked for, or the dashboard.
                navigate(destination,{replace:true});
            }
        }
        catch (error:any) {
          const returned=error?.response?.data;
          const status=error?.response?.status;
          if (status===423 || returned?.locked) {
            setWarning({tone:"locked",text:returned?.error ?? "Your account is locked."});
          } else if (typeof returned?.attempts_left==="number") {
            setWarning({tone:"attempts",text:returned.error});
          } else {
            setWarning(null);
            toast.error(returned?.error ?? (error?.response
              ? "Login failed. Please check your credentials."
              : "Could not reach the server. Please try again."));
          }
        }
      
      
    }
  return (
    <div className="flex flex-col flex-1 ">
      <div className="w-full max-w-md pt-10 mx-auto">
        <div className="rounded-lg shadow-2xl bg-white flex justify-center animate-pulse mb-5">
          <img
            src="/images/logo/ismo_logo.png"
            width={200}
            height={50}
            alt="Ismo Logo"
          />
        </div>
        {/* <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 mt-2"
        >
          <ChevronLeftIcon className="size-5" />
          Back to dashboard
        </Link> */}
      </div>
      <div className="flex flex-col justify-center mt-[5%] w-full max-w-md mx-auto">
        <div>
          <div className="mb-5 sm:mb-8">
            <h1 className="mb-2 font-semibold text-gray-800 text-title-sm dark:text-white/90 sm:text-title-md">
              Sign In
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Enter your email and password to sign in!
            </p>
          </div>
          <div>
            {warning && (
              <div
                role="alert"
                data-signin-warning={warning.tone}
                className={`mb-5 rounded-lg border px-4 py-3 text-sm ${
                  warning.tone==="locked"
                    ? "border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400"
                    : "border-warning-200 bg-warning-50 text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/10 dark:text-warning-400"
                }`}
              >
                <p className="font-semibold">
                  {warning.tone==="locked" ? "Account locked"
                    : warning.tone==="ended" ? "Signed out" : "Wrong password"}
                </p>
                <p className="mt-0.5">{warning.text}</p>
              </div>
            )}
            <form onSubmit={handleSignIn} className="space-y-6">
              <div className="space-y-6">
                <div>
                  <Label>
                    Email <span className="text-error-500">*</span>{" "}
                  </Label>
                  <Input
                    onChange={(e) =>
                      setUser({ ...user, email: e.target.value })
                    }
                    placeholder="info@gmail.com"
                  />
                </div>
                <div>
                  <Label>
                    Password <span className="text-error-500">*</span>{" "}
                  </Label>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      onChange={(e) =>
                        setUser({ ...user, password: e.target.value })
                      }
                      placeholder="Enter your password"
                    />
                    <span
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute z-30 -translate-y-1/2 cursor-pointer right-4 top-1/2"
                    >
                      {showPassword ? (
                        <EyeIcon className="fill-gray-500 dark:fill-gray-400 size-5" />
                      ) : (
                        <EyeCloseIcon className="fill-gray-500 dark:fill-gray-400 size-5" />
                      )}
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Checkbox checked={isChecked} onChange={setIsChecked} />
                    <span className="block font-normal text-gray-700 text-theme-sm dark:text-gray-400">
                      Keep me logged in
                    </span>
                  </div>
                  {/* <Link
                    to="/reset-password"
                    className="text-sm text-brand-500 hover:text-brand-600 dark:text-brand-400"
                  >
                    Forgot password?
                  </Link> */}
                </div>
                <div>
                  <Button
                    type="submit"
                    className="w-full"
                    size="sm"
                  >
                    Sign in
                  </Button>
                </div>
              </div>
            </form>

            <div className="mt-5">
              <p className="text-sm font-normal text-center text-gray-700 dark:text-gray-400 sm:text-start">
                Don&apos;t have an account? {""}
                <Link
                  to="/signup"
                  className="text-brand-500 hover:text-brand-600 dark:text-brand-400"
                >
                  Sign Up
                </Link>
              </p>
            </div> 
            <ToastContainer position="bottom-right" />
          </div>
        </div>
      </div>
    </div>
  );
}
