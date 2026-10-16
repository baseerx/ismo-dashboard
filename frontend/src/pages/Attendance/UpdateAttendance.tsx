import { useEffect, useMemo, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import moment from "moment";
import PageMeta from "../../components/common/PageMeta";
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import TextArea from "../../components/form/input/TextArea";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import DateField from "../../components/form/DateField";
import Button from "../../components/ui/button/Button";
import axios from "../../api/axios";

/**
 * Biometric Attendance > Update Attendance.
 *
 * Insert or correct one employee's check-in and check-out for one date. Only
 * the day's first check-in and last check-out are changed - what every report
 * reads - and every change is kept with its reason (attendance/manual_entry.py).
 */

type Day = {
  erp_id: number;
  name: string;
  date: string;
  check_in: string;
  check_out: string;
  punches: { time: string; status: string }[];
  history: {
    changed_at: string;
    changed_by: string;
    check_in: [string, string];
    check_out: [string, string];
    reason: string;
  }[];
};

const today = () => moment().format("YYYY-MM-DD");

const authHeader = () => {
  const token = localStorage.getItem("token");
  return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined;
};

/** "08:20 → 08:25", or "—" when nothing changed. */
const change = ([before, after]: [string, string]) =>
  after ? `${before || "none"} → ${after}` : "—";

export default function UpdateAttendance() {
  const [employees, setEmployees] = useState<any[]>([]);
  const [erpId, setErpId] = useState<string>("");
  const [workDate, setWorkDate] = useState(today());
  const [day, setDay] = useState<Day | null>(null);
  const [loadingDay, setLoadingDay] = useState(false);
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);

  useEffect(() => {
    axios
      .get("/users/employees/")
      .then((response) =>
        setEmployees(
          (Array.isArray(response.data) ? response.data : []).filter(
            (e: any) => e.flag === undefined || Number(e.flag) === 1
          )
        )
      )
      .catch(() => toast.error("Could not load the employee list"));
  }, []);

  const options = useMemo(
    () =>
      [...employees]
        .sort((a, b) => String(a.name).localeCompare(String(b.name)))
        .map((e: any) => ({ label: `${e.name} (${e.erp_id})`, value: String(e.erp_id) })),
    [employees]
  );

  const loadDay = async (erp: string, date: string) => {
    if (!erp || !date) {
      setDay(null);
      return;
    }
    setLoadingDay(true);
    try {
      const response = await axios.get("/attendance/manual-entry/", {
        ...authHeader(),
        params: { erp_id: erp, date },
      });
      showDay(response.data);
      setRefused(null);
    } catch (error: any) {
      setDay(null);
      setRefused(error?.response?.data?.error ?? "The attendance could not be loaded");
    } finally {
      setLoadingDay(false);
    }
  };

  /** Show a day and start the form from its current times. */
  const showDay = (loaded: Day) => {
    setDay(loaded);
    setCheckIn(loaded.check_in);
    setCheckOut(loaded.check_out);
    setErrors({});
  };

  useEffect(() => {
    loadDay(erpId, workDate);
    setReason("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [erpId, workDate]);

  const save = async () => {
    const problems: Record<string, string> = {};
    if (!erpId) problems.erp_id = "Choose the employee";
    if (!workDate) problems.date = "Choose the date";
    const changedIn = !!checkIn && checkIn !== day?.check_in;
    const changedOut = !!checkOut && checkOut !== day?.check_out;
    if (!changedIn && !changedOut) problems.check_in = "Change the check-in or the check-out time";
    if (checkIn && checkOut && checkOut <= checkIn) {
      problems.check_out = "The check-out must be later than the check-in";
    }
    if (reason.trim().length < 5) problems.reason = "Say why the attendance is being changed";
    setErrors(problems);
    if (Object.keys(problems).length) return;

    setSaving(true);
    try {
      const response = await axios.post(
        "/attendance/manual-entry/save/",
        {
          erp_id: Number(erpId),
          date: workDate,
          // Only what was changed is sent; the other time is kept as recorded.
          check_in: changedIn ? checkIn : "",
          check_out: changedOut ? checkOut : "",
          reason: reason.trim(),
        },
        authHeader()
      );
      toast.success("Attendance saved");
      showDay(response.data.day);
      setReason("");
    } catch (error: any) {
      const returned = error?.response?.data;
      if (returned?.errors) setErrors(returned.errors);
      else toast.error(returned?.error ?? "The attendance could not be saved");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageMeta title="ISMO - Update Attendance" description="Insert or correct an employee's attendance" />
      <PageBreadcrumb pageTitle="Update Attendance" />
      <ToastContainer position="bottom-right" />

      <div className="space-y-6">
        <ComponentCard
          title="Insert or correct attendance"
          desc="Choose an employee and a date. The day's first check-in and last check-out can be entered or changed; every change is recorded with its reason."
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <SearchableDropdown
                id="employee-dropdown"
                label="Employee"
                placeholder="Search by name or ERP ID"
                options={options}
                value={erpId}
                onChange={(value) => setErpId(String(value))}
                error={!!errors.erp_id}
                hint={errors.erp_id}
              />
            </div>
            <div>
              <Label htmlFor="work-date">Date</Label>
              <DateField
                id="work-date"
                value={workDate}
                maxDate={today()}
                onChange={setWorkDate}
                error={!!errors.date}
                hint={errors.date}
              />
            </div>
          </div>

          {refused && (
            <p className="mt-4 rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400" data-refused>
              {refused}
            </p>
          )}

          {loadingDay ? (
            <p className="mt-6 text-sm text-gray-400">Loading the day...</p>
          ) : day ? (
            <div className="mt-6 space-y-5" data-day>
              <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
                <p className="text-sm font-medium text-gray-800 dark:text-white/90">
                  {day.name} · {moment(day.date).format("dddd, DD MMM YYYY")}
                </p>
                <p className="mt-1 text-sm text-gray-500" data-recorded>
                  Recorded: check-in <strong>{day.check_in || "none"}</strong>, check-out{" "}
                  <strong>{day.check_out || "none"}</strong>
                  {day.punches.length > 2 && ` (${day.punches.length} punches that day)`}
                </p>
                {day.punches.length > 0 && (
                  <p className="mt-1 text-xs text-gray-400">
                    All punches: {day.punches.map((p) => `${p.time.slice(0, 5)} ${p.status}`).join(" · ")}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <Label htmlFor="check-in">Check-in time</Label>
                  <Input
                    id="check-in"
                    type="time"
                    value={checkIn}
                    onChange={(e) => {
                      setCheckIn(e.target.value);
                      setErrors((prev) => ({ ...prev, check_in: "" }));
                    }}
                    error={!!errors.check_in}
                    hint={errors.check_in || (day.check_in ? "" : "None recorded - enter one to insert it")}
                  />
                </div>
                <div>
                  <Label htmlFor="check-out">Check-out time</Label>
                  <Input
                    id="check-out"
                    type="time"
                    value={checkOut}
                    onChange={(e) => {
                      setCheckOut(e.target.value);
                      setErrors((prev) => ({ ...prev, check_out: "" }));
                    }}
                    error={!!errors.check_out}
                    hint={errors.check_out || (day.check_out ? "" : "None recorded - enter one to insert it")}
                  />
                </div>
                <div className="md:col-span-2">
                  <Label htmlFor="reason">
                    Reason <span className="text-error-500">*</span>
                  </Label>
                  <TextArea
                    id="reason"
                    rows={2}
                    placeholder="e.g., Biometric device was down; confirmed by the section head"
                    value={reason}
                    onChange={(value) => {
                      setReason(value.slice(0, 300));
                      setErrors((prev) => ({ ...prev, reason: "" }));
                    }}
                    error={!!errors.reason}
                    hint={errors.reason}
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button size="sm" variant="primary" onClick={save} disabled={saving}>
                  {saving ? "Saving..." : "Save attendance"}
                </Button>
              </div>

              {day.history.length > 0 && (
                <div data-history>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Changes made to this day
                  </p>
                  <div className="max-w-full overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800">
                          <th className="py-2 pr-4 font-medium">When</th>
                          <th className="py-2 pr-4 font-medium">By</th>
                          <th className="py-2 pr-4 font-medium">Check-in</th>
                          <th className="py-2 pr-4 font-medium">Check-out</th>
                          <th className="py-2 pr-4 font-medium">Reason</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                        {day.history.map((edit, index) => (
                          <tr key={index} className="text-gray-700 dark:text-gray-300">
                            <td className="py-2 pr-4 whitespace-nowrap">{edit.changed_at}</td>
                            <td className="py-2 pr-4">{edit.changed_by || "—"}</td>
                            <td className="py-2 pr-4 whitespace-nowrap">{change(edit.check_in)}</td>
                            <td className="py-2 pr-4 whitespace-nowrap">{change(edit.check_out)}</td>
                            <td className="py-2 pr-4">{edit.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ) : !refused ? (
            <p className="mt-6 text-sm text-gray-500">Choose an employee to see and update their attendance.</p>
          ) : null}
        </ComponentCard>
      </div>
    </>
  );
}
