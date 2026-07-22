import { useEffect, useState } from "react";
import moment from "moment";
import axios from "../../api/axios";
import Badge from "../ui/badge/Badge";
import {
  CalenderIcon,
  TimeIcon,
  CheckCircleIcon,
  BiometricRecognitionIcon,
} from "../../icons";

type BadgeColor = "primary" | "success" | "error" | "warning" | "info" | "light" | "dark";

type MyAttendance = {
  erp_id: number;
  name: string;
  designation: string | null;
  grade: string | null;
  section: string | null;
  date: string;
  checkin_time: string | null;
  checkout_time: string | null;
  late_status: string; // "Late" | "On Time" | "-"
  early_status: string; // "Early" | "On Time" | "-"
  flag: string; // "Present" | "Absent" | leave type | holiday name | "Weekend"
  flag_type: "present" | "leave" | "official" | "holiday" | "weekend" | "absent";
};

// Map the server-side day status to a colour + accent so the whole card
// reads at a glance without the user having to parse the label.
const STATUS_THEME: Record<
  MyAttendance["flag_type"],
  { badge: BadgeColor; dot: string; ring: string; gradient: string }
> = {
  present: {
    badge: "success",
    dot: "bg-success-500",
    ring: "ring-success-500/30",
    gradient: "from-success-500/10 to-transparent",
  },
  leave: {
    badge: "warning",
    dot: "bg-warning-500",
    ring: "ring-warning-500/30",
    gradient: "from-warning-500/10 to-transparent",
  },
  official: {
    badge: "info",
    dot: "bg-blue-light-500",
    ring: "ring-blue-light-500/30",
    gradient: "from-blue-light-500/10 to-transparent",
  },
  holiday: {
    badge: "info",
    dot: "bg-blue-light-500",
    ring: "ring-blue-light-500/30",
    gradient: "from-blue-light-500/10 to-transparent",
  },
  weekend: {
    badge: "light",
    dot: "bg-gray-400",
    ring: "ring-gray-400/30",
    gradient: "from-gray-400/10 to-transparent",
  },
  absent: {
    badge: "error",
    dot: "bg-error-500",
    ring: "ring-error-500/30",
    gradient: "from-error-500/10 to-transparent",
  },
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const fmtTime = (value: string | null) =>
  value ? moment(value).format("hh:mm A") : "—";

function PunchTile({
  label,
  icon,
  time,
  sub,
  subColor,
}: {
  label: string;
  icon: React.ReactNode;
  time: string;
  sub?: string;
  subColor?: BadgeColor;
}) {
  return (
    <div className="flex flex-col rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-2">
        <span className="text-title-sm font-bold text-gray-800 dark:text-white/90">
          {time}
        </span>
        {sub && sub !== "-" && (
          <Badge color={subColor} size="sm">
            {sub}
          </Badge>
        )}
      </div>
    </div>
  );
}

export default function MyAttendanceToday({ erpId }: { erpId: number | string }) {
  const [data, setData] = useState<MyAttendance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(() => moment());

  // Live clock for the "current time" readout.
  useEffect(() => {
    const id = setInterval(() => setNow(moment()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let active = true;
    const fetchAttendance = async () => {
      setLoading(true);
      setError(false);
      try {
        const res = await axios.get("/attendance/my-today/", {
          params: { erp_id: erpId },
        });
        if (active) setData(res.data);
      } catch (err) {
        console.error("Error fetching my attendance:", err);
        if (active) setError(true);
      } finally {
        if (active) setLoading(false);
      }
    };
    if (erpId) fetchAttendance();
    return () => {
      active = false;
    };
  }, [erpId]);

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center rounded-2xl border border-gray-200 bg-white text-sm text-gray-400 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-500">
        Loading your attendance...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-40 items-center justify-center rounded-2xl border border-gray-200 bg-white text-sm text-gray-400 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-500">
        Unable to load your attendance today.
      </div>
    );
  }

  const theme = STATUS_THEME[data.flag_type] ?? STATUS_THEME.absent;

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      {/* Hero header with status-tinted background */}
      <div className={`bg-gradient-to-r ${theme.gradient}`}>
        <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5">
          <div className="flex items-center gap-4">
            <div
              className={`flex size-14 shrink-0 items-center justify-center rounded-full bg-brand-500 text-lg font-semibold text-white ring-4 ${theme.ring}`}
            >
              {initials(data.name)}
            </div>
            <div>
              <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
                {data.name}
              </h3>
              <p className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
                {[data.designation, data.section, data.grade].filter(Boolean).join(" · ") ||
                  "—"}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-start gap-2 sm:items-end">
            <Badge color={theme.badge} variant="solid" size="md">
              <span className={`mr-1 inline-block size-2 rounded-full ${theme.dot} ring-2 ring-white/40`} />
              {data.flag}
            </Badge>
            <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
              <span className="flex items-center gap-1.5">
                <CalenderIcon className="size-4" />
                {moment(data.date).format("ddd, DD MMM YYYY")}
              </span>
              <span className="flex items-center gap-1.5 font-medium tabular-nums text-gray-700 dark:text-gray-300">
                <TimeIcon className="size-4" />
                {now.format("hh:mm:ss A")}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Punch tiles */}
      <div className="grid grid-cols-1 gap-4 border-t border-gray-100 p-6 dark:border-gray-800 sm:grid-cols-3">
        <PunchTile
          label="Checked In"
          icon={<BiometricRecognitionIcon className="size-4" />}
          time={fmtTime(data.checkin_time)}
          sub={data.checkin_time ? data.late_status : undefined}
          subColor={data.late_status === "Late" ? "warning" : "success"}
        />
        <PunchTile
          label="Checked Out"
          icon={<BiometricRecognitionIcon className="size-4" />}
          time={fmtTime(data.checkout_time)}
          sub={data.checkout_time ? data.early_status : undefined}
          subColor={data.early_status === "Early" ? "warning" : "success"}
        />
        <PunchTile
          label="Today's Status"
          icon={<CheckCircleIcon className="size-4" />}
          time={data.flag}
          sub={
            data.flag_type === "present" && data.late_status !== "-"
              ? data.late_status === "Late"
                ? "Late arrival"
                : "On time"
              : undefined
          }
          subColor={data.late_status === "Late" ? "warning" : "success"}
        />
      </div>
    </div>
  );
}
