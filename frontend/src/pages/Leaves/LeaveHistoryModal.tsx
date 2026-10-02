import { useEffect, useState } from "react";
import axios from "../../api/axios";

type StageRow = {
  sequence: number;
  label: string;
  role: string;
  assigned_erp_id: number | null;
  status: string;
  acted_by_erp_id: number | null;
  comment: string | null;
  acted_at: string | null;
};

export default function LeaveHistoryModal({
  leaveId,
  employeesData,
  onClose,
}: {
  leaveId: number;
  employeesData: any[];
  onClose: () => void;
}) {
  const [stages, setStages] = useState<StageRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios
      .get(`/leaves/history/${leaveId}/`)
      .then((res) => setStages(res.data.stages))
      .finally(() => setLoading(false));
  }, [leaveId]);

  const nameFor = (erpId: number | null) => {
    if (!erpId) return "—";
    const emp = employeesData.find((e) => Number(e.erp_id) === Number(erpId));
    return emp ? `${emp.name} (${erpId})` : `ERP ${erpId}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-6 dark:bg-gray-900">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            Approval History
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : (
          <div className="space-y-3">
            {stages.map((stage) => (
              <div
                key={stage.sequence}
                className="rounded-xl border border-gray-200 p-4 dark:border-gray-700"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-800 dark:text-white/90">
                    {stage.sequence + 1}. {stage.label}
                  </span>
                  <span
                    className={`rounded-full px-3 py-0.5 text-xs font-semibold ${
                      stage.status === "approved"
                        ? "bg-success-50 text-success-600"
                        : stage.status === "rejected"
                        ? "bg-error-50 text-error-600"
                        : stage.status === "skipped"
                        ? "bg-gray-100 text-gray-500"
                        : "bg-warning-50 text-warning-600"
                    }`}
                  >
                    {stage.status}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Assigned to: {nameFor(stage.assigned_erp_id)}
                </p>
                {stage.acted_by_erp_id && (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Acted by {nameFor(stage.acted_by_erp_id)}
                    {stage.acted_at ? ` on ${stage.acted_at}` : ""}
                  </p>
                )}
                {stage.comment && (
                  <p className="mt-2 rounded-lg bg-gray-50 p-2 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    "{stage.comment}"
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}