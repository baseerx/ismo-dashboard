import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect, useCallback } from "react";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import Button from "../../components/ui/button/Button";
import Select from "../../components/form/Select";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";

// ----------------------------
// Types
// ----------------------------
type Section = { id: number; name: string };

type SubSectionOption = { id: number; sub_section_name: string };

type EmployeeRow = {
  id: number;
  erp_id: number;
  hris_id: number;
  name: string;
  position: string;
  sub_section_id: number | null;
  sub_section_name: string | null;
};

export default function AssignSubSection() {
  const [sections, setSections] = useState<Section[]>([]);
  const [selectedSection, setSelectedSection] = useState<number | "">("");

  const [employees, setEmployees] = useState<EmployeeRow[]>([]);
  const [subSectionOptions, setSubSectionOptions] = useState<SubSectionOption[]>([]);

  // Pending (unsaved) selection per employee row: { [employeeId]: subSectionId }
  const [pendingSelection, setPendingSelection] = useState<Record<number, string>>({});
  const [savingId, setSavingId] = useState<number | null>(null);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSections();
  }, []);

  // ----------------------------
  // Fetch sections (existing API, untouched)
  // ----------------------------
  const getSections = async () => {
    try {
      const response = await axios.get("/sections/get/");
      setSections(response.data || []);
    } catch (error) {
      console.error("Error fetching sections:", error);
      toast.error("Failed to load sections");
    }
  };

  // ----------------------------
  // Fetch sub sections that belong to the selected section (existing API, untouched)
  // ----------------------------
  const getSubSectionsOfSection = async (sectionId: number | "") => {
    try {
      const response = await axios.get("/subsections/", {
        params: { section_id: sectionId },
      });
      const options = (response.data || []).map((s: any) => ({
        id: s.id,
        sub_section_name: s.sub_section_name,
      }));
      setSubSectionOptions(options);
    } catch (error) {
      console.error("Error fetching sub sections:", error);
      toast.error("Failed to load sub sections for this section");
    }
  };

  // ----------------------------
  // Fetch employees of the selected section (new API)
  // ----------------------------
  const getEmployeesOfSection = useCallback(async (sectionId: number | "") => {
    if (!sectionId) {
      setEmployees([]);
      return;
    }
    try {
      setLoading(true);
      const response = await axios.get(`/users/by_section/${sectionId}/`);
      setEmployees(response.data?.employees || []);
      setPendingSelection({});
    } catch (error) {
      console.error("Error fetching employees:", error);
      toast.error("Failed to load employees for this section");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSectionChange = (value: number | "") => {
    setSelectedSection(value);
    setEmployees([]);
    setSubSectionOptions([]);
    setPendingSelection({});
    if (value) {
      getSubSectionsOfSection(value);
      getEmployeesOfSection(value);
    }
  };

  // ----------------------------
  // Save sub-section assignment for one employee
  // ----------------------------
  const handleAssign = async (employeeId: number) => {
    const subSectionId = pendingSelection[employeeId];
    if (subSectionId === undefined) {
      toast.error("Please select a sub section first");
      return;
    }
    try {
      setSavingId(employeeId);
      await axios.post(`/users/assign_sub_section/${employeeId}/`, {
        sub_section_id: subSectionId || null,
      });
      toast.success("Sub section assigned successfully");
      await getEmployeesOfSection(selectedSection);
    } catch (error: any) {
      toast.error(error?.response?.data?.error || "Failed to assign sub section");
    } finally {
      setSavingId(null);
    }
  };

  // ----------------------------
  // Table columns — only Sub Section column is editable
  // ----------------------------
  const columns: ColumnDef<EmployeeRow>[] = [
    { header: "ERP ID", accessorKey: "erp_id" },
    { header: "HRIS ID", accessorKey: "hris_id" },
    { header: "Name", accessorKey: "name" },
    { header: "Position", accessorKey: "position" },
    {
      header: "Sub Section",
      id: "sub_section",
      cell: ({ row }) => {
        const emp = row.original;
        const currentValue =
          pendingSelection[emp.id] !== undefined
            ? pendingSelection[emp.id]
            : emp.sub_section_id
            ? String(emp.sub_section_id)
            : "";

        return (
          <div className="min-w-[180px]">
            <Select
              key={`${emp.id}-${emp.sub_section_id ?? "none"}`}
              options={subSectionOptions.map((s) => ({
                label: s.sub_section_name,
                value: String(s.id),
              }))}
              placeholder="Select sub section"
              defaultValue={currentValue}
              onChange={(value) =>
                setPendingSelection((prev) => ({ ...prev, [emp.id]: value }))
              }
            />
          </div>
        );
      },
    },
    {
      header: "Actions",
      id: "actions",
      cell: ({ row }) => (
        <Button
          size="xs"
          variant="primary"
          onClick={() => handleAssign(row.original.id)}
          disabled={savingId === row.original.id}
        >
          {savingId === row.original.id ? "Saving..." : "Add"}
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageMeta
        title="ISMO - Assign Sub Section"
        description="ISMO Admin Dashboard - Assign Sub Section"
      />
      <PageBreadcrumb pageTitle="Assign Sub Section" />
      <div className="space-y-6">
        <ComponentCard title="Assign Sub Section">
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 mb-4 gap-4">
            <div className="w-full">
              <SearchableDropdown
                options={sections.map((s) => ({ label: s.name, value: s.id }))}
                placeholder="Select section"
                label="Section"
                id="assign-sub-section-section"
                value={selectedSection}
                onChange={(value) =>
                  handleSectionChange(value === "" || value === undefined ? "" : Number(value))
                }
              />
            </div>
          </div>

          {loading && (
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading employees...</p>
          )}

          {!loading && selectedSection && employees.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No employees found in this section.
            </p>
          )}

          {!loading && employees.length > 0 && (
            <EnhancedDataTable<EmployeeRow> data={employees} columns={columns} />
          )}
        </ComponentCard>
      </div>
    </>
  );
}
