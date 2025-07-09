import { BrowserRouter as Router, Routes, Route } from "react-router";
import SignIn from "./pages/AuthPages/SignIn";
import SignUp from "./pages/AuthPages/SignUp";
import NotFound from "./pages/OtherPage/NotFound";
import UserProfiles from "./pages/UserProfiles";
import Videos from "./pages/UiElements/Videos";
import Images from "./pages/UiElements/Images";
import Alerts from "./pages/UiElements/Alerts";
import Badges from "./pages/UiElements/Badges";
import Avatars from "./pages/UiElements/Avatars";
import Buttons from "./pages/UiElements/Buttons";
import LineChart from "./pages/Charts/LineChart";
import BarChart from "./pages/Charts/BarChart";
import Calendar from "./pages/Calendar";
import BasicTables from "./pages/Tables/BasicTables";
import DataTableOne from "./pages/Tables/TodaysAttendance";
import AttendanceHistory from "./pages/Tables/AttendanceHistory";
import FormElements from "./pages/Forms/FormElements";
import Blank from "./pages/Blank";
import AppLayout from "./layout/AppLayout";
import { ScrollToTop } from "./components/common/ScrollToTop";

import SectionAttendanceReport from "./pages/Tables/SectionAttendanceReport";
import ApplyLeave from "./pages/Leaves/ApplyLeave";
import PublicHoliday from "./pages/Leaves/PublicHolidays";
// import TodaysAttendance from "./pages/Tables/TodaysAttendance";
import IndividualAttendance from "./pages/Tables/IndividualAttendance";
import CreateUser from "./pages/UserManagement/CreateUser";
import AssignRights from "./pages/UserManagement/AssignRights";
import MainMenu from "./pages/Menus/MainMenu";
import SubMenu from "./pages/Menus/SubMenu";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import Home from "./pages/Dashboard/Home";
import AttendanceOverview from "./pages/Attendance/AttendanceOverview";

export default function App() {
  return (
    <>
      <Router>
        <ScrollToTop />
        <Routes>
          {/* Dashboard Layout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/dashboard" index element={<Home />} />

              {/* Others Page */}
              <Route path="/profile" element={<UserProfiles />} />
              <Route path="/calendar" element={<Calendar />} />
              <Route path="/blank" element={<Blank />} />

              {/* Forms */}
              <Route path="/form-elements" element={<FormElements />} />

              {/* Tables */}
              <Route path="/basic-tables" element={<BasicTables />} />
              <Route path="/attendance/today" element={<DataTableOne />} />
              <Route
                path="/attendance/history"
                element={<AttendanceHistory />}
              />
              <Route
                path="/attendance/individual"
                element={<IndividualAttendance />}
              />
              <Route
                path="/attendance/section"
                element={<SectionAttendanceReport />}
              />
              <Route
                path="/attendance/overview"
                element={<AttendanceOverview />}
              />

              {/* User managment */}
              <Route path="/users/create" element={<CreateUser />} />
              <Route path="/users/assign-rights" element={<AssignRights />} />

              {/* Menu Management */}
              <Route path="/create-menu" element={<MainMenu />} />
              <Route path="/sub-menu" element={<SubMenu />} />

              {/* Leaves */}
              <Route path="/leaves/apply" element={<ApplyLeave />} />
              <Route
                path="/leaves/public-holidays"
                element={<PublicHoliday />}
              />

              {/* Plugins */}
              {/* Ui Elements */}
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/avatars" element={<Avatars />} />
              <Route path="/badge" element={<Badges />} />
              <Route path="/buttons" element={<Buttons />} />
              <Route path="/images" element={<Images />} />
              <Route path="/videos" element={<Videos />} />

              {/* Charts */}
              <Route path="/line-chart" element={<LineChart />} />
              <Route path="/bar-chart" element={<BarChart />} />
            </Route>
          </Route>
          {/* Auth Layout */}
          <Route path="/" element={<SignIn />} />
          <Route path="/signup" element={<SignUp />} />

          {/* Fallback Route */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Router>
    </>
  );
}
