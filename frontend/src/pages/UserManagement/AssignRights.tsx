import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import axios from "../../api/axios";
import { useEffect, useState } from "react";
import _, { assign, get, set } from "lodash";
import { ToastContainer, toast } from "react-toastify";
import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import { ColumnDef } from "@tanstack/react-table";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import MultiSelect from "../../components/form/MultiSelect";

// 1. Define Type
type UserRightsType = {
  id: number;
  mainmenu: any;
  submenu: any;
  user: any;
};

export default function AssignRights() {
  const [mainmenu, setMainMenu] = useState<{ id: number; name: string }[]>([]);
  const [users, setUsers] = useState<
    { id: number; full_name: string; email: string }[]
  >([]);
  const [submenus, setSubMenus] = useState<{ id: number; submenu: string }[]>(
    []
  );
  const [data, setData] = useState<{userid:number,menuid:number,submenuid:number}>({
      userid: 0,
        menuid: 0,
    submenuid: 0,
  });

  const [records, setRecords] = useState<UserRightsType[]>([]);

const [fielderror, setFieldError] = useState<Record<string, string>>({
    userid: "",
    menuid: "",
    submenuid: "",
});     
 

  const [updateid, setUpdateId] = useState<number>(0);
  useEffect(() => {
      getMainMenus();
      getUsers();

  }, []);

    const getUsers = async () => {
        try {
            const response = await axios.get("/users/get_auth_users/");
            if (response.status === 200) {
                const userData = response.data.map((item: any) => ({
                    id: item.id,
                    full_name: item.first_name+' '+item.last_name,
                    email: item.email,
                }));
                setUsers(userData);
            }
        } catch (error) {
            console.error("Error fetching users:", error);
        }
    }
    const getSubMenus = async (id: any) => {
    try {
      const response = await axios.get(`/submenu/bymenu/${id}/`);
      if (response.status === 200) {
        const submenuData = response.data.map((item: any) => ({
          id: item.id,
          submenu: item.submenu,
        }));
        setSubMenus(submenuData);
      }
    } catch (error) {
      console.error("Error fetching submenu records:", error);
    }
  };
  const getRecords = async (id:any) => {
    try {
        const response = await axios.get(`/assignrights/get/${id}/`);
      if (response.status === 200) {
        const assignrights = response.data.map((item: any) => ({
          id: item.id,
          mainmenu: item.mainmenu, // m.name from main_menu
          submenu: item.submenu,
          username: item.username,
          email: item.email, // s.sub_menu from sub_menu

        }));
        setRecords(assignrights);
      }
    } catch (error) {
      console.error("Error fetching submenu records:", error);
    }
  };
  const getMainMenus = async () => {
    try {
      const response = await axios.get("/mainmenu/get/");
      if (response.status === 200) {
        const menuData = response.data.main_menus.map((item: any) => ({
          id: item.id,
          name: item.name,
        }));
        setMainMenu(menuData);
      } else {
        console.error("Failed to fetch main menu data");
      }
    } catch (error) {
      console.error("Error fetching records:", error);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await axios.post(`/submenu/delete/${id}/`);
      toast.success("Main menu deleted successfully");
    } catch (error) {
      console.error("Delete error:", error);
      toast.error("Failed to delete main menu");
    }
  };

const handleSubmit = async () => {
    const errors: Record<string, string> = {};
    if (!data.userid) errors.userid = "Employee is required";
    if (!data.menuid) errors.menuid = "Main menu is required";
    if (!data.submenuid) errors.submenuid = "Sub menu is required";

    setFieldError(errors);

    if (Object.keys(errors).length > 0) {
        toast.error("Please fix all validation errors");
        return;
    }

    if (updateid > 0) {
        try {
            await axios.post(`/assignrights/update/${updateid}/`, data);
            toast.success("Rights updated successfully");
            setData({ userid: 0, menuid: 0, submenuid: 0 });
            setFieldError({ userid: "", menuid: "", submenuid: "" });
            setUpdateId(0);
        } catch (error) {
            toast.error("Failed to update rights");
        }
    } else {
        try {
            await axios.post("/assignrights/create/", data);
            toast.success("Rights assigned successfully");
            setData({ userid: 0, menuid: 0, submenuid: 0 });
            setFieldError({ userid: "", menuid: "", submenuid: "" });
        } catch (error) {
            toast.error("Failed to assign rights");
        }
    }
};

  const handleEdit = async (id: number) => {
    setUpdateId(id);
    try {
      const response = await axios.get(`/submenu/record/${id}/`);
      if (response.status === 200) {
        const menu = response.data;
        setData({
          userid: menu.userid,
          menuid: menu.menuid,
          submenuid: menu.submenuid,
        });
      }
    } catch (error) {
      console.error("Error fetching menu for edit:", error);
      toast.error("Failed to fetch menu for editing");
    }
  };

  // Implement edit functionality here

  // 2. Define Columns
const columns: ColumnDef<UserRightsType>[] = [
    {
        header: "Main Menu",
        accessorKey: "mainmenu",
    },
    {
        header: "Sub Menu",
        accessorKey: "submenu",
    },
    {
        header: "Username",
        accessorKey: "username",
    },
    {
        header: "Email",
        accessorKey: "email",
    },
    {
        header: "Actions",
        id: "actions",
        cell: ({ row }) => (
            <div className="flex space-x-2">
                <Button
                    size="xs"
                    variant="primary"
                    onClick={() => handleEdit(row.original.id)}
                >
                    Edit
                </Button>
                <Button
                    size="xs"
                    variant="danger"
                    onClick={() => handleDelete(row.original.id)}
                >
                    Delete
                </Button>
            </div>
        ),
    },
];

  return (
    <>
      <PageMeta
        title="ISMO - Create Main Menu"
        description="ISMO Admin Dashboard - Create Main Menu"
      />
      <PageBreadcrumb pageTitle="Create Sub Menu" />
      <div className="space-y-6">
        <ComponentCard title="Create New Sub Menu">
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-4">
            <div className="w-full">
              <SearchableDropdown
                options={users.map((item) => ({
                  label: item.full_name + ' (' + item.email+ ')',
                  value: item.id,
                }))}
                placeholder="Select a Employee"
                label="Employees"
                id="menu-dropdown"
                value={
                  updateid == 0
                    ? data.userid
                    : users.find((item) => item.id === data.userid)?.id || 0
                }
                              onChange={(value) => {
                    getRecords(value);
                  setData({
                    ...data,
                    userid: value ? parseInt(value.toString(), 10) : 0,
                  });
                }}
                error={!!fielderror.userid}
                hint={fielderror.userid}
              />
            </div>
            <div className="w-full">
              <SearchableDropdown
                options={mainmenu.map((item) => ({
                  label: item.name,
                  value: item.id,
                }))}
                placeholder="Select a menu"
                label="Main Menu"
                id="menu-dropdown"
                value={
                  updateid == 0
                    ? data.menuid
                    : mainmenu.find((item) => item.id === data.menuid)?.id || 0
                }
                onChange={(value) => {
                  getSubMenus(value);
                  setSubMenus([]); // Clear submenus on main menu change
                  setData({
                    ...data,
                    menuid: value ? parseInt(value.toString(), 10) : 0,
                    submenuid: 0, // Clear selected submenu
                  });
                }}
                error={!!fielderror.menuid}
                hint={fielderror.menuid}
              />
            </div>
            <div className="w-full">
              <MultiSelect
                options={submenus.map((item) => ({
                  value: item.id.toString(),
                  text: item.submenu,
                }))}
                label="Sub Menu"
                defaultSelected={
                  data.submenuid ? [data.submenuid.toString()] : []
                }
                onChange={(selected) => {
                  setData({
                    ...data,
                    submenuid: selected.length > 0 ? parseInt(selected[0], 10) : 0,
                  });
                }}
                disabled={false}
              />
            </div>
      
          </div>

          <div className="w-full flex justify-center items-center">
            <Button
              size="sm"
              className="w-1/3 mt-7"
              variant="primary"
              onClick={handleSubmit}
            >
              {updateid > 0 ? "Update Record" : "Add Record"}
            </Button>
          </div>
        </ComponentCard>

        {/* 3. Display table below the form */}
        <ComponentCard title="Sub Menu Records">
          <EnhancedDataTable<UserRightsType> data={records} columns={columns} />
        </ComponentCard>
      </div>
    </>
  );
}
