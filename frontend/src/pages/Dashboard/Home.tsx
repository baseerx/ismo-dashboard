import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import StatTile from "../../components/cards/StatTile";
import MyAttendanceToday from "../../components/attendance/MyAttendanceToday";
import StatDonutChart from "../../components/charts/dashboard/StatDonutChart";
import TrendAreaChart from "../../components/charts/dashboard/TrendAreaChart";
import CategoryBarChart from "../../components/charts/dashboard/CategoryBarChart";
import RadialGaugeChart from "../../components/charts/dashboard/RadialGaugeChart";
import Badge from "../../components/ui/badge/Badge";
import Button from "../../components/ui/button/Button";
import { useTheme } from "../../context/ThemeContext";
import {
  UserIcon,
  CheckCircleIcon,
  LeaveIcon,
  BoxCubeIcon,
  AlertIcon,
  TimeIcon,
  CalenderIcon,
} from "../../icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "../../api/axios";
import moment from "moment";

type ByGrade = { grade: string; count: number };
type ByType = { type: string; requests: number; days?: number };
type MonthlyTrend = { month: string; days?: number; requests?: number };
type TrendPoint = { date: string; total: number; present: number };
type SectionBreakdown = {
  section_id: number;
  section_name: string;
  total_employees: number;
  present_today: number;
  on_leave_today: number;
  official_work_today: number;
  absent_today: number;
  pending_leaves: number;
  pending_official_work: number;
};

type DashboardStats = {
  scope: "section" | "org";
  section_id: number | null;
  section_name: string | null;
  today: string;
  is_weekend: boolean;
  is_holiday: boolean;
  holiday_name: string | null;
  financial_year: string;
  employees: { total: number; male: number; female: number; by_grade: ByGrade[] };
  attendance_today: { total: number; present: number; on_leave: number; official_work: number; absent: number };
  attendance_trend: TrendPoint[];
  leaves: { pending: number; by_type: ByType[]; monthly_trend: MonthlyTrend[] };
  official_work: { pending: number; by_type: ByType[]; monthly_trend: MonthlyTrend[] };
  upcoming_holidays: { name: string; date: string }[];
  by_section: SectionBreakdown[];
};

type Slice = { label: string; value: number };

// Cap a distribution at the top N entries and fold the remainder into "Other"
// so charts never grow an unbounded number of categorical slots.
function topNPlusOther(items: Slice[], n = 5): Slice[] {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  if (sorted.length <= n) return sorted;
  const top = sorted.slice(0, n);
  const otherTotal = sorted.slice(n).reduce((sum, i) => sum + i.value, 0);
  return otherTotal > 0 ? [...top, { label: "Other", value: otherTotal }] : top;
}

function attendanceRate(present: number, absent: number): number {
  const expected = present + absent;
  return expected > 0 ? (present / expected) * 100 : 100;
}

export default function Home() {
  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const isAdmin = !!user.is_superuser;
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const [scope, setScope] = useState<"section" | "org">(isAdmin ? "org" : "section");
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const getDashboardStats = async () => {
    setLoading(true);
    try {
      const response = await axios.get("/users/dashboard-stats/", {
        params: { erp_id: user.erpid, scope },
      });
      setStats(response.data);
    } catch (error) {
      console.error("Error fetching dashboard stats:", error);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    getDashboardStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  const statusColors = {
    good: "#12b76a",
    warning: "#f79009",
    critical: "#f04438",
    info: "#0ba5ec",
    neutral: isDark ? "#98a2b3" : "#667085",
  };

  const scopeLabel =
    scope === "org" ? "Organization-wide" : stats?.section_name ? `${stats.section_name} Section` : "My Section";

  if (loading && !stats) {
    return (
      <>
        <PageMeta title="ISMO - Dashboard" description="Attendance & leave insights dashboard" />
        <div className="flex h-64 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
          Loading dashboard...
        </div>
      </>
    );
  }

  if (!stats) {
    return (
      <>
        <PageMeta title="ISMO - Dashboard" description="Attendance & leave insights dashboard" />
        <div className="flex h-64 items-center justify-center text-sm text-gray-400 dark:text-gray-500">
          Unable to load dashboard data.
        </div>
      </>
    );
  }

  const { attendance_today: att, employees } = stats;
  const dayOff = Math.max(0, att.total - att.present - att.on_leave - att.official_work - att.absent);
  const rate = attendanceRate(att.present, att.absent);

  const donutLabels = ["Present", "On Leave", "Official Work", "Absent"];
  const donutSeries = [att.present, att.on_leave, att.official_work, att.absent];
  const donutColors = [statusColors.good, statusColors.warning, statusColors.info, statusColors.critical];
  if (dayOff > 0) {
    donutLabels.push("Day Off");
    donutSeries.push(dayOff);
    donutColors.push(statusColors.neutral);
  }

  const leaveTypeSlices = topNPlusOther(
    stats.leaves.by_type.map((t) => ({ label: t.type, value: t.days || 0 }))
  );
  const gradeSlices = [...employees.by_grade].sort((a, b) => b.count - a.count);

  const sectionSlices = stats.by_section.map((s) => ({
    ...s,
    rate: attendanceRate(s.present_today, s.absent_today),
  }));
  const sectionColors = sectionSlices.map((s) =>
    s.rate >= 90 ? statusColors.good : s.rate >= 70 ? statusColors.warning : statusColors.critical
  );

  return (
    <>
      <PageMeta title="ISMO - Dashboard" description="Attendance & leave insights dashboard" />
      <PageBreadcrumb pageTitle="Dashboard" />

      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {scopeLabel} Overview
          </h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {moment(stats.today).format("dddd, DD MMMM YYYY")} &middot; FY {stats.financial_year}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isAdmin && (
            <div className="flex items-center gap-2 rounded-lg border border-gray-200 p-1 dark:border-gray-800">
              <Button
                size="xs"
                variant={scope === "org" ? "primary" : "outline"}
                className={scope === "org" ? "" : "!ring-0"}
                onClick={() => setScope("org")}
              >
                Organization
              </Button>
              <Button
                size="xs"
                variant={scope === "section" ? "primary" : "outline"}
                className={scope === "section" ? "" : "!ring-0"}
                onClick={() => setScope("section")}
              >
                My Section
              </Button>
            </div>
          )}
        </div>
      </div>

      {(stats.is_holiday || stats.is_weekend) && (
        <div className="mb-6 flex items-center gap-2 rounded-2xl border border-warning-200 bg-warning-50 px-5 py-3 text-sm text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/15 dark:text-orange-400">
          <CalenderIcon className="size-4 shrink-0" />
          {stats.is_holiday
            ? `Today is a public holiday${stats.holiday_name ? ` — ${stats.holiday_name}` : ""}.`
            : "Today is a weekend."}
        </div>
      )}

      {/* My attendance today — personal snapshot on the section view */}
      {scope === "section" && user.erpid && (
        <div className="mb-6">
          <MyAttendanceToday erpId={user.erpid} />
        </div>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 xl:grid-cols-3 2xl:grid-cols-6">
        <StatTile
          title="Total Employees"
          value={employees.total}
          icon={<UserIcon className="text-brand-500 size-6 dark:text-white/90" />}
          subtext={`${employees.male} Male / ${employees.female} Female`}
        />
        <StatTile
          title="Present Today"
          value={att.present}
          icon={<CheckCircleIcon className="text-success-500 size-6 dark:text-white/90" />}
          badge={{ text: `${rate.toFixed(0)}%`, color: rate >= 90 ? "success" : rate >= 70 ? "warning" : "error" }}
        />
        <StatTile
          title="On Leave Today"
          value={att.on_leave}
          icon={<LeaveIcon className="text-warning-500 size-6 dark:text-white/90" />}
        />
        <StatTile
          title="Official Work Today"
          value={att.official_work}
          icon={<BoxCubeIcon className="text-blue-light-500 size-6 dark:text-white/90" />}
        />
        <StatTile
          title="Absent Today"
          value={att.absent}
          icon={<AlertIcon className="text-error-500 size-6 dark:text-white/90" />}
          onClick={() =>
            scope === "section" && stats.section_id != null
              ? navigate("/attendance/status", {
                  state: {
                    section: String(stats.section_id),
                    status: "absent",
                    date: stats.today,
                  },
                })
              : navigate("/attendance/total-absent")
          }
          subtext="Click to view details"
        />
        <StatTile
          title="Pending Approvals"
          value={stats.leaves.pending + stats.official_work.pending}
          icon={<TimeIcon className="text-warning-500 size-6 dark:text-white/90" />}
          badge={
            stats.leaves.pending + stats.official_work.pending > 0
              ? { text: "Needs action", color: "warning" }
              : { text: "All clear", color: "success" }
          }
          onClick={() => navigate("/leaves/apply")}
        />
      </div>

      {/* Today snapshot */}
      <div className="mt-6 grid grid-cols-1 gap-4 md:gap-6 lg:grid-cols-3">
        <ComponentCard title="Today's Attendance Breakdown">
          <StatDonutChart labels={donutLabels} series={donutSeries} colors={donutColors} centerLabel="Total" />
        </ComponentCard>
        <ComponentCard title="Attendance Rate" desc="Present ÷ (Present + Absent)">
          <div className="flex items-center justify-center">
            <RadialGaugeChart label="Attendance" value={rate} />
          </div>
        </ComponentCard>
        <ComponentCard title="Upcoming Holidays">
          {stats.upcoming_holidays.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-gray-500">No upcoming holidays.</p>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-gray-800">
              {stats.upcoming_holidays.map((h) => {
                const daysAway = moment(h.date).startOf("day").diff(moment(stats.today).startOf("day"), "days");
                return (
                  <li key={h.date + h.name} className="flex items-center justify-between py-2.5">
                    <div>
                      <p className="text-sm font-medium text-gray-800 dark:text-white/90">{h.name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {moment(h.date).format("DD MMM YYYY")}
                      </p>
                    </div>
                    <Badge color="light" size="sm">
                      {daysAway === 0 ? "Today" : daysAway === 1 ? "Tomorrow" : `In ${daysAway} days`}
                    </Badge>
                  </li>
                );
              })}
            </ul>
          )}
        </ComponentCard>
      </div>

      {/* Attendance trend */}
      <div className="mt-6">
        <ComponentCard title="Attendance Trend — Last 14 Days" desc={scopeLabel}>
          <TrendAreaChart
            categories={stats.attendance_trend.map((t) => moment(t.date).format("DD MMM"))}
            series={[
              {
                name: "Present %",
                data: stats.attendance_trend.map((t) => (t.total > 0 ? Math.round((t.present / t.total) * 100) : 0)),
              },
            ]}
            valueSuffix="%"
            colors={["#465fff"]}
          />
        </ComponentCard>
      </div>

      {/* Leave distribution & trend */}
      <div className="mt-6 grid grid-cols-1 gap-4 md:gap-6 lg:grid-cols-2">
        <ComponentCard title="Leave Type Distribution" desc={`Days used — FY ${stats.financial_year}`}>
          <CategoryBarChart
            categories={leaveTypeSlices.map((s) => s.label)}
            series={[{ name: "Days", data: leaveTypeSlices.map((s) => s.value) }]}
            horizontal
            distributed
            valueSuffix=" days"
          />
        </ComponentCard>
        <ComponentCard title="Leave Days — Monthly Trend">
          <CategoryBarChart
            categories={stats.leaves.monthly_trend.map((m) => moment(`${m.month}-01`).format("MMM YYYY"))}
            series={[{ name: "Leave Days", data: stats.leaves.monthly_trend.map((m) => m.days || 0) }]}
            colors={["#465fff"]}
          />
        </ComponentCard>
      </div>

      {/* Workforce composition */}
      <div className="mt-6 grid grid-cols-1 gap-4 md:gap-6 lg:grid-cols-2">
        <ComponentCard title="Workforce by Gender">
          <StatDonutChart
            labels={["Male", "Female"]}
            series={[employees.male, employees.female]}
            colors={["#465fff", "#7a5af8"]}
            centerLabel="Employees"
          />
        </ComponentCard>
        <ComponentCard title="Workforce by Grade">
          <CategoryBarChart
            categories={gradeSlices.map((g) => g.grade)}
            series={[{ name: "Employees", data: gradeSlices.map((g) => g.count) }]}
            horizontal
            colors={["#465fff"]}
          />
        </ComponentCard>
      </div>

      {/* Admin-only: organization-wide section breakdown */}
      {isAdmin && scope === "org" && stats.by_section.length > 0 && (
        <>
          <div className="mt-6">
            <ComponentCard title="Section-wise Attendance Rate Today" desc="Present ÷ (Present + Absent), colored by severity">
              <CategoryBarChart
                categories={sectionSlices.map((s) => s.section_name)}
                series={[{ name: "Attendance Rate", data: sectionSlices.map((s) => Math.round(s.rate)) }]}
                horizontal
                distributed
                colors={sectionColors}
                valueSuffix="%"
              />
            </ComponentCard>
          </div>

          <div className="mt-6">
            <ComponentCard title="Section Breakdown">
              <div className="max-w-full overflow-x-auto custom-scrollbar">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800 dark:text-gray-400">
                      <th className="py-2 pr-4 font-medium">Section</th>
                      <th className="py-2 pr-4 font-medium">Employees</th>
                      <th className="py-2 pr-4 font-medium">Present</th>
                      <th className="py-2 pr-4 font-medium">On Leave</th>
                      <th className="py-2 pr-4 font-medium">Official Work</th>
                      <th className="py-2 pr-4 font-medium">Absent</th>
                      <th className="py-2 pr-4 font-medium">Pending Leaves</th>
                      <th className="py-2 pr-4 font-medium">Pending Official Work</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {stats.by_section.map((s) => (
                      <tr key={s.section_id} className="text-gray-700 dark:text-gray-300">
                        <td className="py-2.5 pr-4 font-medium text-gray-800 dark:text-white/90">
                          {s.section_name}
                        </td>
                        <td className="py-2.5 pr-4">{s.total_employees}</td>
                        <td className="py-2.5 pr-4">{s.present_today}</td>
                        <td className="py-2.5 pr-4">{s.on_leave_today}</td>
                        <td className="py-2.5 pr-4">{s.official_work_today}</td>
                        <td className="py-2.5 pr-4">{s.absent_today}</td>
                        <td className="py-2.5 pr-4">
                          {s.pending_leaves > 0 ? (
                            <Badge color="warning" size="sm">{s.pending_leaves}</Badge>
                          ) : (
                            0
                          )}
                        </td>
                        <td className="py-2.5 pr-4">
                          {s.pending_official_work > 0 ? (
                            <Badge color="warning" size="sm">{s.pending_official_work}</Badge>
                          ) : (
                            0
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ComponentCard>
          </div>
        </>
      )}
    </>
  );
}
