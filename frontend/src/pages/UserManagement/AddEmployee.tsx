import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import { ToastContainer, toast } from "react-toastify";
import { ColumnDef } from "@tanstack/react-table";
import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Select from "../../components/form/Select";
import Input from "../../components/form/input/InputField";
import Radio from "../../components/form/input/Radio";
import { useAuth } from "../../context/AuthContext";


// ----------------------------
// Types for Employees
// ----------------------------
type EmployeeRow = {
  id?: number;
  erp_id: string;
  hris_id: string;
  name: string;
  cnic: string;
  gender: string;
  section_id: string;
  location_id: string;
  grade_id: string;
  designation_id: string;
  position: string;
  /** On the employee record; empty for everyone entered before it existed. */
  dob: string;
  /** These two live on the login account, mapped by ERP ID through profiles. */
  email: string;
  date_joined: string;
  has_account: boolean;
  flag: boolean;
};

type EmployeeFormData = {
  erp_id: string;
  hris_id: string;
  name: string;
  cnic: string;
  gender: string;
  section_id: string;
  location_id: string;
  grade_id: string;
  designation_id: string;
  position: string;
  dob: string;
  email: string;
  date_joined: string;
  has_account: boolean;
  flag: boolean;
};

// ----------------------------
// Types for Details API
// ----------------------------
type Section = { id: number; name: string };
type Location = { id: number; name: string };
type Grade = { id: number; name: string };
type Designation = { id: number; title: string };

/** Today in the format a date input uses. */
const todayISO = () => new Date().toISOString().slice(0, 10);

export default function AddEmployee() {
  const [employees, setEmployees] = useState<EmployeeRow[]>([]);
  const { user } = useAuth();
  console.log("Current User:", user);
  // details state
  const [sections, setSections] = useState<Section[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [hrisid, setHrisId] = useState<number>(0);
  // null = create mode; a number = the id of the employee being edited.
  const [editingId, setEditingId] = useState<number | null>(null);

  const [data, setData] = useState<EmployeeFormData>({
    erp_id: "",
    hris_id: "",
    name: "",
    cnic: "",
    gender: "",
    section_id: "",
    location_id: "",
    grade_id: "",
    designation_id: "",
    position: "",
    dob: "",
    email: "",
    date_joined: "",
    has_account: false,
    flag: true,
  });

  const emptyErrors: Record<string, string> = {
    erp_id: "",
    hris_id: "",
    name: "",
    cnic: "",
    gender: "",
    section_id: "",
    location_id: "",
    grade_id: "",
    designation_id: "",
    position: "",
    dob: "",
    email: "",
    date_joined: "",
    flag: "",
  };
  const [fielderror, setFieldError] =
    useState<Record<string, string>>(emptyErrors);

  useEffect(() => {
    getEmployees();
    getDetails();
  }, []);

  // ----------------------------
  // Fetch employees
  // ----------------------------
  const getEmployees = async () => {
    try {
      const response = await axios.get("/users/get_employees/");
      if (response.data) {
        // The API returns nested objects for section, location, grade, and designation.
        // We need to flatten them to just their IDs for the table and form.
        const employeesData = response.data.employees.map((emp: any) => ({
          id: emp.id,
          erp_id: String(emp.erp_id),
          hris_id: String(emp.hris_id),
          name: emp.name,
          cnic: emp.cnic,
          gender: emp.gender,
          section_id: emp.section?.id ? String(emp.section.id) : "",
          location_id: emp.location?.id ? String(emp.location.id) : "",
          grade_id: emp.grade?.id ? String(emp.grade.id) : "",
          designation_id: emp.designation?.id ? String(emp.designation.id) : "",
          position: emp.position,
          dob: emp.dob ?? "",
          email: emp.email ?? "",
          date_joined: emp.date_joined ?? "",
          has_account: !!emp.has_account,
          flag: !!emp.flag,
        }));
        setEmployees(employeesData);
      } else {
        setEmployees([]);
      }
    } catch (error) {
      console.error("Error fetching employees:", error);
      toast.error("Failed to load employees");
    }
  };

  // ----------------------------
  // Fetch dropdown details
  // ----------------------------
  const getDetails = async () => {
    try {
      const response = await axios.get("/users/details/");

      if (response.data) {
        setSections(response.data.sections || []);
        setLocations(response.data.locations || []);
        setGrades(response.data.grades || []);
        setDesignations(response.data.designations || []);
        setHrisId(response.data.new_hris_id || 0);
        setData((prevData) => ({
          ...prevData,
          hris_id: response.data.new_hris_id || 0,
        }));
      }
    } catch (error) {
      console.error("Error fetching employee details:", error);
      toast.error("Failed to load employee details");
    }
  };

  // ----------------------------
  // Delete employee
  // ----------------------------
  const handleDeleteEmployee = async (employeeId: number) => {
    try {
      if (window.confirm("Are you sure you want to change the status (inactive) of this employee?")) {
        await axios.post(`/users/delete_employee/${employeeId}/`);
        toast.success("Employee Status changed successfully");
        getEmployees();
      }
    } catch (error) {
      console.error("Error changing status employee:", error);
      toast.error("Failed to change employee status");
    }
  };

  // ----------------------------
  // Shared field validation
  // ----------------------------
  // `requireHris` only matters on create — on edit the HRIS ID is locked and
  // never sent for validation because it can never change.
  const validateEmployee = (
    empData: EmployeeFormData,
    requireHris: boolean
  ): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (!empData.erp_id) errors.erp_id = "ERP ID is required";
    if (requireHris && !empData.hris_id) errors.hris_id = "HRIS ID is required";
    if (!empData.name) errors.name = "Name is required";
    if (!empData.cnic) {
      errors.cnic = "CNIC is required";
    } else if (!/^(\d{13}|\d{5}-\d{7}-\d)$/.test(empData.cnic)) {
      // Accept both the plain 13-digit form (11201-6655448-9) and the
      // dashed form (11201-6655448-9).
      errors.cnic = "CNIC must be 13 digits, e.g. 1120166554489 or 11201-6655448-9";
    }
    if (!empData.gender) errors.gender = "Gender is required";
    if (!empData.section_id) errors.section_id = "Section is required";
    if (!empData.location_id) errors.location_id = "Location is required";
    if (!empData.grade_id) errors.grade_id = "Grade is required";
    if (!empData.designation_id) errors.designation_id = "Designation is required";
    if (!empData.position) errors.position = "Position is required";

    // Optional, but checked when filled in - the backend applies the same rules.
    if (empData.dob) {
      const dob = new Date(empData.dob);
      const years = (Date.now() - dob.getTime()) / (365.25 * 24 * 3600 * 1000);
      if (Number.isNaN(dob.getTime())) errors.dob = "That is not a valid date";
      else if (empData.dob > todayISO()) errors.dob = "Date of birth cannot be in the future";
      else if (years < 18) errors.dob = "An employee must be at least 18";
      else if (years > 75) errors.dob = "Check the date of birth - that is over 75 years ago";
    }

    if (empData.email && !/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(empData.email.trim())) {
      errors.email = "That does not look like an email address";
    }

    if (empData.date_joined) {
      if (empData.date_joined > todayISO()) {
        errors.date_joined = "Date joined cannot be in the future";
      } else if (empData.dob) {
        const joined = new Date(empData.date_joined).getTime();
        const dob = new Date(empData.dob).getTime();
        if ((joined - dob) / (365.25 * 24 * 3600 * 1000) < 16) {
          errors.date_joined = "Date joined is before the employee turned 16";
        }
      }
    }

    return errors;
  };

  // Reset the form back to create mode with a fresh generated HRIS ID.
  const resetForm = () => {
    setEditingId(null);
    setData({
      erp_id: "",
      hris_id: String(hrisid || ""),
      name: "",
      cnic: "",
      gender: "",
      section_id: "",
      location_id: "",
      grade_id: "",
      designation_id: "",
      position: "",
      dob: "",
      email: "",
      date_joined: "",
      has_account: false,
      flag: true,
    });
    setFieldError(emptyErrors);
  };

  // ----------------------------
  // Validation + Create employee
  // ----------------------------
  const createEmployee = async (empData: EmployeeFormData) => {
    try {
      const errors = validateEmployee(empData, true);
      if (Object.keys(errors).length > 0) {
        setFieldError(errors);
        toast.error("Please fix all validation errors");
        return;
      }
      const response = await axios.post("/users/create_employee/", empData);
      // The email and date joined need a login account to land on; when there
      // is none the server says so rather than silently dropping them.
      if (response.data?.note) toast.info(response.data.note);

      resetForm();
      // Pull a fresh HRIS ID so the next create doesn't reuse this one.
      getDetails();
      getEmployees();
      toast.success("Employee created successfully");
    } catch (error: any) {
      toast.error(
        error?.response?.data?.error ??
        "Failed to create employee: " +
        (error instanceof Error ? error.message : "Unknown error")
      );
    }
  };

  // ----------------------------
  // Load a row into the form for editing
  // ----------------------------
  const handleEditClick = (row: EmployeeRow) => {
    setEditingId(row.id ?? null);
    setData({
      erp_id: row.erp_id,
      hris_id: row.hris_id, // shown read-only; never updated
      name: row.name,
      cnic: row.cnic,
      gender: row.gender,
      section_id: row.section_id,
      location_id: row.location_id,
      grade_id: row.grade_id,
      designation_id: row.designation_id,
      position: row.position,
      dob: row.dob,
      email: row.email,
      date_joined: row.date_joined,
      has_account: row.has_account,
      flag: row.flag,
    });
    setFieldError(emptyErrors);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // ----------------------------
  // Validation + Update employee
  // ----------------------------
  const updateEmployee = async (empData: EmployeeFormData) => {
    if (editingId == null) return;
    try {
      const errors = validateEmployee(empData, false);
      if (Object.keys(errors).length > 0) {
        setFieldError(errors);
        toast.error("Please fix all validation errors");
        return;
      }
      // Confirm before committing the update.
      if (
        !window.confirm(
          `Are you sure you want to update the record for ${empData.name || "this employee"}?`
        )
      ) {
        return;
      }
      // hris_id is intentionally omitted — the backend ignores it too.
      const response = await axios.post(
        `/users/update_employee/${editingId}/`,
        empData
      );
      if (response.data?.note) toast.info(response.data.note);

      resetForm();
      getEmployees();
      toast.success("Employee updated successfully");
    } catch (error: any) {
      toast.error(
        error?.response?.data?.error ??
        "Failed to update employee: " +
        (error instanceof Error ? error.message : "Unknown error")
      );
    }
  };

  // ----------------------------
  // Table columns
  // ----------------------------
  const columns: ColumnDef<EmployeeRow>[] = [
    { header: "ID", accessorKey: "id" },
    { header: "ERP ID", accessorKey: "erp_id" },
    { header: "HRIS ID", accessorKey: "hris_id" },
    { header: "Name", accessorKey: "name" },
    { header: "CNIC", accessorKey: "cnic" },
    {
      header: "Date of Birth",
      accessorKey: "dob",
      cell: ({ row }) => row.original.dob || "—",
    },
    { header: "Gender", accessorKey: "gender" },
    {
      header: "Email",
      accessorKey: "email",
      cell: ({ row }) => row.original.email || "—",
    },
    {
      header: "Date Joined",
      accessorKey: "date_joined",
      cell: ({ row }) => row.original.date_joined || "—",
    },
    {
      header: "Section",
      accessorKey: "section_id",
      cell: ({ getValue }) => {
        const id = getValue<string>();
        return sections.find((s) => String(s.id) === id)?.name || id;
      },
    },
    {
      header: "Location",
      accessorKey: "location_id",
      cell: ({ getValue }) => {
        const id = getValue<string>();
        return locations.find((l) => String(l.id) === id)?.name || id;
      },
    },
    {
      header: "Grade",
      accessorKey: "grade_id",
      cell: ({ getValue }) => {
        const id = getValue<string>();
        return grades.find((g) => String(g.id) === id)?.name || id;
      },
    },
    {
      header: "Designation",
      accessorKey: "designation_id",
      cell: ({ getValue }) => {
        const id = getValue<string>();
        return designations.find((d) => String(d.id) === id)?.title || id;
      },
    },
    { header: "Position", accessorKey: "position" },
    {
      header: "Flag",
      accessorKey: "flag",
      cell: ({ getValue }) => (getValue<boolean>() ? "Active" : "Inactive"),
    },
    {
      header: "Actions",
      id: "actions",
      cell: ({ row }) =>
        (
          <div className="flex items-center gap-2">
            <Button
              size="xs"
              variant="outline"
              onClick={() => handleEditClick(row.original)}
            >
              Edit
            </Button>
            {row.original?.flag === true && user?.user_id === 3 ? (
              <Button
                size="xs"
                variant="danger"
                onClick={() => handleDeleteEmployee(row.original.id || 0)}
              >
                Disable
              </Button>
            ) : user?.user_id === 3 ? (
              <Button
                size="xs"
                variant="primary"
                onClick={() => handleDeleteEmployee(row.original.id || 0)}
              >
                Enable
              </Button>
            ) : null}
          </div>
        ),
    },
  ];

  // ----------------------------
  // UI
  // ----------------------------
  return (
    <>
      <PageMeta
        title="ISMO - Create Employee"
        description="ISMO Admin Dashboard - Create Employee"
      />
      <PageBreadcrumb pageTitle="Create Employee" />
      <div className="space-y-6">
        <ComponentCard title={editingId ? "Edit Employee" : "Create New Employee"}>
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-4">
            <div className="w-full">
              <Label>ERP ID</Label>
              <Input
                type="text"
                placeholder="Enter ERP ID"
                value={data.erp_id}
                onChange={(e) => setData({ ...data, erp_id: e.target.value })}
                error={!!fielderror.erp_id}
                hint={fielderror.erp_id}
              />
            </div>

            <div className="w-full">
              <Label>HRIS ID</Label>
              <Input
                type="text"
                placeholder="Enter HRIS ID"
                value={editingId ? data.hris_id : hrisid}
                disabled
                error={!!fielderror.hris_id}
                hint={fielderror.hris_id}
              />
            </div>

            <div className="w-full">
              <Label>Name</Label>
              <Input
                type="text"
                placeholder="Enter name"
                value={data.name}
                onChange={(e) => setData({ ...data, name: e.target.value })}
                error={!!fielderror.name}
                hint={fielderror.name}
              />
            </div>

            <div className="w-full">
              <Label>CNIC</Label>
              <Input
                type="text"
                placeholder="Enter CNIC (e.g. 11201-5366438-9)"
                value={data.cnic}
                onChange={(e) => setData({ ...data, cnic: e.target.value })}
                error={!!fielderror.cnic}
                hint={fielderror.cnic}
              />
            </div>

            <div className="w-full">
              <Label>Date of Birth</Label>
              <Input
                id="dob"
                type="date"
                max={todayISO()}
                value={data.dob}
                onChange={(e) => setData({ ...data, dob: e.target.value })}
                error={!!fielderror.dob}
                hint={fielderror.dob}
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                Blank for employees entered before this field existed - fill it in
                and it is saved on the employee record.
              </p>
            </div>

            <div className="w-full">
              <Label>Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="name@ismo.gov.pk"
                value={data.email}
                onChange={(e) => setData({ ...data, email: e.target.value })}
                disabled={!!editingId && !data.has_account}
                error={!!fielderror.email}
                hint={fielderror.email}
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                {editingId && !data.has_account
                  ? "No login account is linked to this ERP ID yet - create it from Create User first."
                  : "Saved on the employee's login account."}
              </p>
            </div>

            <div className="w-full">
              <Label>Date Joined</Label>
              <Input
                id="date_joined"
                type="date"
                max={todayISO()}
                value={data.date_joined}
                onChange={(e) => setData({ ...data, date_joined: e.target.value })}
                disabled={!!editingId && !data.has_account}
                error={!!fielderror.date_joined}
                hint={fielderror.date_joined}
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                {editingId && !data.has_account
                  ? "Also part of the login account."
                  : "The date on the login account, editable here."}
              </p>
            </div>

            <div className="w-full">
              <Label>Gender</Label>
              <Select
                key={`gender-${editingId ?? "new"}`}
                options={[
                  { label: "Male", value: "M" },
                  { label: "Female", value: "F" },
                  { label: "Other", value: "O" },
                ]}
                placeholder="Select gender"
                defaultValue={data.gender}
                onChange={(value) => setData({ ...data, gender: value })}
                error={!!fielderror.gender}
                hint={fielderror.gender}
              />
            </div>

            <div className="w-full">
              <Label>Section</Label>
              <Select
                key={`section-${editingId ?? "new"}`}
                options={sections.map((s) => ({
                  label: s.name,
                  value: String(s.id),
                }))}
                placeholder="Select section"
                defaultValue={data.section_id}
                onChange={(value) => setData({ ...data, section_id: value })}
                error={!!fielderror.section_id}
                hint={fielderror.section_id}
              />
            </div>

            <div className="w-full">
              <Label>Location</Label>
              <Select
                key={`location-${editingId ?? "new"}`}
                options={locations.map((l) => ({
                  label: l.name,
                  value: String(l.id),
                }))}
                placeholder="Select location"
                defaultValue={data.location_id}
                onChange={(value) => setData({ ...data, location_id: value })}
                error={!!fielderror.location_id}
                hint={fielderror.location_id}
              />
            </div>

            <div className="w-full">
              <Label>Grade</Label>
              <Select
                key={`grade-${editingId ?? "new"}`}
                options={grades.map((g) => ({
                  label: g.name,
                  value: String(g.id),
                }))}
                placeholder="Select grade"
                defaultValue={data.grade_id}
                onChange={(value) => setData({ ...data, grade_id: value })}
                error={!!fielderror.grade_id}
                hint={fielderror.grade_id}
              />
            </div>

            <div className="w-full">
              <Label>Designation</Label>
              <Select
                key={`designation-${editingId ?? "new"}`}
                options={designations.map((d) => ({
                  label: d.title,
                  value: String(d.id),
                }))}
                placeholder="Select designation"
                defaultValue={data.designation_id}
                onChange={(value) =>
                  setData({ ...data, designation_id: value })
                }
                error={!!fielderror.designation_id}
                hint={fielderror.designation_id}
              />
            </div>

            <div className="w-full">
              <Label>Position</Label>
              <Input
                type="text"
                placeholder="Enter Position"
                value={data.position}
                onChange={(e) => setData({ ...data, position: e.target.value })}
                error={!!fielderror.position}
                hint={fielderror.position}
              />
            </div>

            <div className="w-full">
              <Label>Flag</Label>
              <div className="mt-2 flex gap-3">
                <Radio
                  id="flag-yes"
                  name="flag"
                  value="1"
                  checked={data.flag === true}
                  label="Active"
                  onChange={() => setData({ ...data, flag: true })}
                />
                <Radio
                  id="flag-no"
                  name="flag"
                  value="0"
                  checked={data.flag === false}
                  label="Inactive"
                  onChange={() => setData({ ...data, flag: false })}
                />
              </div>
            </div>
          </div>

          <div className="w-full flex justify-center items-center gap-3">
            {editingId ? (
              <>
                <Button
                  size="sm"
                  className="mt-7"
                  variant="primary"
                  onClick={() => updateEmployee(data)}
                >
                  Update Employee
                </Button>
                <Button
                  size="sm"
                  className="mt-7"
                  variant="outline"
                  onClick={resetForm}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <Button
                size="sm"
                className="w-1/3 mt-7"
                variant="primary"
                onClick={() => createEmployee(data)}
              >
                Create Employee
              </Button>
            )}
          </div>

          <EnhancedDataTable<EmployeeRow> data={employees} columns={columns} />
        </ComponentCard>
      </div>
    </>
  );
}
