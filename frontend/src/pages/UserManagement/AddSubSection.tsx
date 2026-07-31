import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect, useCallback } from "react";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import { Modal } from "../../components/ui/modal";

// ----------------------------
// Types
// ----------------------------
type Section = { id: number; name: string };

type SectionEmployee = {
  id: number;
  erp_id: number;
  hris_id: number;
  name: string;
  position: string;
};

type SubSectionRow = {
  id: number;
  sub_section_name: string;
  section_id: number;
  section__name: string;
  head_employee_id: number;
  head_employee__name: string;
  created_at: string;
};

type SubSectionFormData = {
  sub_section_name: string;
  section_id: number | "";
  head_employee_id: number | "";
};

const emptyForm: SubSectionFormData = {
  sub_section_name: "",
  section_id: "",
  head_employee_id: "",
};

export default function AddSubSection() {
  const [sections, setSections] = useState<Section[]>([]);
  const [sectionEmployees, setSectionEmployees] = useState<SectionEmployee[]>([]);
  const [subSections, setSubSections] = useState<SubSectionRow[]>([]);

  const [data, setData] = useState<SubSectionFormData>(emptyForm);
  const [fielderror, setFieldError] = useState<Record<string, string>>({
    sub_section_name: "",
    section_id: "",
    head_employee_id: "",
  });
  const [submitting, setSubmitting] = useState(false);

  // Edit modal state
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editRow, setEditRow] = useState<SubSectionRow | null>(null);
  const [editForm, setEditForm] = useState<SubSectionFormData>(emptyForm);
  const [editEmployees, setEditEmployees] = useState<SectionEmployee[]>([]);
  const [editErrors, setEditErrors] = useState<Record<string, string>>({});
  const [editSubmitting, setEditSubmitting] = useState(false);

  useEffect(() => {
    getSections();
    getSubSections();
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
  // Fetch employees of a section (new API)
  // ----------------------------
  const getEmployeesBySection = async (sectionId: number | "", target: "create" | "edit") => {
    if (!sectionId) {
      if (target === "create") setSectionEmployees([]);
      else setEditEmployees([]);
      return;
    }
    try {
      const response = await axios.get(`/users/by_section/${sectionId}/`);
      const employees = response.data?.employees || [];
      if (target === "create") setSectionEmployees(employees);
      else setEditEmployees(employees);
    } catch (error) {
      console.error("Error fetching employees by section:", error);
      toast.error("Failed to load employees for the selected section");
    }
  };

  // ----------------------------
  // Fetch all existing sub sections (existing API, untouched)
  // ----------------------------
  const getSubSections = useCallback(async () => {
    try {
      const response = await axios.get("/subsections/", {
        params: { is_superuser: "true" },
      });
      setSubSections(response.data || []);
    } catch (error) {
      console.error("Error fetching sub sections:", error);
      toast.error("Failed to load sub sections");
    }
  }, []);

  // ----------------------------
  // Create sub section
  // ----------------------------
  const validate = (form: SubSectionFormData) => {
    const errors: Record<string, string> = {};
    if (!form.sub_section_name.trim()) errors.sub_section_name = "Sub section name is required";
    if (!form.section_id) errors.section_id = "Section is required";
    if (!form.head_employee_id) errors.head_employee_id = "Head employee is required";
    return errors;
  };

  const handleCreate = async () => {
    const errors = validate(data);
    setFieldError({ sub_section_name: "", section_id: "", head_employee_id: "", ...errors });
    if (Object.keys(errors).length > 0) {
      toast.error("Please fix all validation errors");
      return;
    }

    try {
      setSubmitting(true);
      await axios.post("/subsections/create/", {
        sub_section_name: data.sub_section_name.trim(),
        section_id: data.section_id,
        head_employee_id: data.head_employee_id,
      });
      toast.success("Sub section created successfully");
      setData(emptyForm);
      setSectionEmployees([]);
      setFieldError({ sub_section_name: "", section_id: "", head_employee_id: "" });
      getSubSections();
    } catch (error: any) {
      toast.error(error?.response?.data?.error || "Failed to create sub section");
    } finally {
      setSubmitting(false);
    }
  };

  // ----------------------------
  // Edit sub section
  // ----------------------------
  const openEdit = (row: SubSectionRow) => {
    setEditRow(row);
    setEditForm({
      sub_section_name: row.sub_section_name,
      section_id: row.section_id,
      head_employee_id: row.head_employee_id,
    });
    setEditErrors({});
    getEmployeesBySection(row.section_id, "edit");
    setIsEditOpen(true);
  };

  const closeEdit = () => {
    setIsEditOpen(false);
    setEditRow(null);
    setEditEmployees([]);
  };

  const handleUpdate = async () => {
    if (!editRow) return;
    const errors = validate(editForm);
    setEditErrors(errors);
    if (Object.keys(errors).length > 0) {
      toast.error("Please fix all validation errors");
      return;
    }

    try {
      setEditSubmitting(true);
      await axios.put(`/subsections/update/${editRow.id}/`, {
        sub_section_name: editForm.sub_section_name.trim(),
        section_id: editForm.section_id,
        head_employee_id: editForm.head_employee_id,
      });
      toast.success("Sub section updated successfully");
      closeEdit();
      getSubSections();
    } catch (error: any) {
      toast.error(error?.response?.data?.error || "Failed to update sub section");
    } finally {
      setEditSubmitting(false);
    }
  };

  // ----------------------------
  // Delete sub section
  // ----------------------------
  const handleDelete = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this sub section?")) return;
    try {
      const response = await axios.delete(`/subsections/delete/${id}/`);
      const unassigned = response.data?.unassigned_employees || 0;
      toast.success(
        unassigned > 0
          ? `Sub section deleted successfully (${unassigned} employee(s) unassigned)`
          : "Sub section deleted successfully"
      );
      getSubSections();
    } catch (error: any) {
      const status = error?.response?.status;
      const message: string = error?.response?.data?.error || "Failed to delete sub section";

      // 409 = employees are still assigned to this sub section. Offer to
      // unassign them automatically and retry the delete (force=true).
      if (status === 409) {
        const proceed = window.confirm(
          `${message}\n\nDo you want to unassign these employees automatically and delete this sub section anyway?`
        );
        if (!proceed) return;

        try {
          const forcedResponse = await axios.delete(`/subsections/delete/${id}/`, {
            params: { force: "true" },
          });
          const unassigned = forcedResponse.data?.unassigned_employees || 0;
          toast.success(
            `Sub section deleted successfully (${unassigned} employee(s) unassigned)`
          );
          getSubSections();
        } catch (forceError: any) {
          toast.error(forceError?.response?.data?.error || "Failed to delete sub section");
        }
        return;
      }

      toast.error(message);
    }
  };

  // ----------------------------
  // Table columns
  // ----------------------------
  const columns: ColumnDef<SubSectionRow>[] = [
    { header: "ID", accessorKey: "id" },
    { header: "Sub Section Name", accessorKey: "sub_section_name" },
    { header: "Section", accessorKey: "section__name" },
    { header: "Head Employee", accessorKey: "head_employee__name" },
    {
      header: "Created Date",
      accessorKey: "created_at",
      cell: ({ getValue }) => {
        const value = getValue<string>();
        return value ? new Date(value).toLocaleDateString() : "-";
      },
    },
    {
      header: "Actions",
      id: "actions",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Button size="xs" variant="primary" onClick={() => openEdit(row.original)}>
            Edit
          </Button>
          <Button size="xs" variant="danger" onClick={() => handleDelete(row.original.id)}>
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageMeta
        title="ISMO - Add Sub Section"
        description="ISMO Admin Dashboard - Add Sub Section"
      />
      <PageBreadcrumb pageTitle="Add Sub Section" />
      <div className="space-y-6">
        <ComponentCard title="Create New Sub Section">
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 mb-4 gap-4">
            <div className="w-full">
              <SearchableDropdown
                options={sections.map((s) => ({ label: s.name, value: s.id }))}
                placeholder="Select section"
                label="Section"
                id="add-sub-section-section"
                value={data.section_id}
                onChange={(value) => {
                  const section_id = value === "" || value === undefined ? "" : Number(value);
                  setData({ ...data, section_id, head_employee_id: "" });
                  getEmployeesBySection(section_id, "create");
                }}
                error={!!fielderror.section_id}
                hint={fielderror.section_id}
              />
            </div>

            <div className="w-full">
              <Label>Sub Section Name</Label>
              <Input
                type="text"
                placeholder="Enter sub section name"
                value={data.sub_section_name}
                onChange={(e) => setData({ ...data, sub_section_name: e.target.value })}
                error={!!fielderror.sub_section_name}
                hint={fielderror.sub_section_name}
              />
            </div>

            <div className="w-full">
              <SearchableDropdown
                options={sectionEmployees.map((e) => ({
                  label: `${e.name} (ERP-${e.erp_id})`,
                  value: e.erp_id,
                }))}
                placeholder={data.section_id ? "Select head employee" : "Select a section first"}
                label="Head Employee (ERP)"
                id="add-sub-section-head-employee"
                value={data.head_employee_id}
                onChange={(value) =>
                  setData({ ...data, head_employee_id: value === "" || value === undefined ? "" : Number(value) })
                }
                disabled={!data.section_id}
                error={!!fielderror.head_employee_id}
                hint={fielderror.head_employee_id}
              />
            </div>

            <div className="w-full">
              <Label>Created Date</Label>
              <Input type="text" value={new Date().toLocaleDateString()} disabled />
            </div>
          </div>

          <div className="w-full flex justify-center items-center">
            <Button
              size="sm"
              className="w-full sm:w-1/3 mt-4"
              variant="primary"
              onClick={handleCreate}
              disabled={submitting}
            >
              {submitting ? "Saving..." : "Add Sub Section"}
            </Button>
          </div>
        </ComponentCard>

        <ComponentCard title="Sub Sections">
          <EnhancedDataTable<SubSectionRow> data={subSections} columns={columns} />
        </ComponentCard>
      </div>

      {/* Edit Modal */}
      <Modal isOpen={isEditOpen} onClose={closeEdit} className="max-w-xl p-6 lg:p-8">
        <h4 className="mb-6 text-lg font-semibold text-gray-800 dark:text-white/90">
          Edit Sub Section
        </h4>
        <div className="grid grid-cols-1 gap-4">
          <div className="w-full">
            <Label>Section</Label>
            <SearchableDropdown
              options={sections.map((s) => ({ label: s.name, value: s.id }))}
              placeholder="Select section"
              id="edit-sub-section-section"
              value={editForm.section_id}
              onChange={(value) => {
                const section_id = value === "" || value === undefined ? "" : Number(value);
                setEditForm({ ...editForm, section_id, head_employee_id: "" });
                getEmployeesBySection(section_id, "edit");
              }}
              error={!!editErrors.section_id}
              hint={editErrors.section_id}
            />
          </div>

          <div className="w-full">
            <Label>Sub Section Name</Label>
            <Input
              type="text"
              value={editForm.sub_section_name}
              onChange={(e) => setEditForm({ ...editForm, sub_section_name: e.target.value })}
              error={!!editErrors.sub_section_name}
              hint={editErrors.sub_section_name}
            />
          </div>

          <div className="w-full">
            <Label>Head Employee (ERP)</Label>
            <SearchableDropdown
              options={editEmployees.map((e) => ({
                label: `${e.name} (ERP-${e.erp_id})`,
                value: e.erp_id,
              }))}
              placeholder="Select head employee"
              id="edit-sub-section-head-employee"
              value={editForm.head_employee_id}
              onChange={(value) =>
                setEditForm({ ...editForm, head_employee_id: value === "" || value === undefined ? "" : Number(value) })
              }
              disabled={!editForm.section_id}
              error={!!editErrors.head_employee_id}
              hint={editErrors.head_employee_id}
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <Button size="sm" variant="outline" onClick={closeEdit}>
            Cancel
          </Button>
          <Button size="sm" variant="primary" onClick={handleUpdate} disabled={editSubmitting}>
            {editSubmitting ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </Modal>
    </>
  );
}
