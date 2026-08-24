import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import axios from "../../api/axios";
import { useEffect, useState } from "react";
import { ToastContainer, toast } from "react-toastify";
import Button from "../../components/ui/button/Button";

import { ColumnDef } from "@tanstack/react-table";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import SearchableDropdown from "../../components/form/input/SearchableDropDown";
import MultiSelect from "../../components/form/MultiSelect";

type ChatbotMode = "all" | "specific" | "none";

const CHATBOT_MODES: { value: ChatbotMode; title: string; detail: string }[] = [
  { value: "all", title: "All users", detail: "Everyone who signs in sees the assistant" },
  { value: "specific", title: "Specific users", detail: "Only the users selected below" },
  { value: "none", title: "Nobody", detail: "The launcher is hidden for everyone" },
];

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

  const [data, setData] = useState<{
    userid: number;
    menuid: number;
    submenuid: number[];
  }>({
    userid: 0,
    menuid: 0,
    submenuid: [],
  });

  const [records, setRecords] = useState<UserRightsType[]>([]);

  const [fielderror, setFieldError] = useState<Record<string, string>>({
    userid: "",
    menuid: "",
    submenuid: "",
  });

  // Who sees the HR Assistant launcher. Stored centrally so it applies to
  // every browser; the widget itself does the showing and hiding.
  const [chatbotMode, setChatbotMode] = useState<ChatbotMode>("all");
  const [chatbotUserIds, setChatbotUserIds] = useState<number[]>([]);
  // Bumped once the saved rule arrives, to remount the user picker: it seeds
  // its selection from defaultSelected only on first render.
  const [chatbotFormKey, setChatbotFormKey] = useState(0);
  const [savingChatbot, setSavingChatbot] = useState(false);
  // Set when the saved rule could not be read, so the card can say the setting
  // is unavailable instead of showing a default that then fails to save.
  const [chatbotUnavailable, setChatbotUnavailable] = useState<string | null>(null);

 

  useEffect(() => {
    getMainMenus();
    getUsers();
    getChatbotVisibility();
  }, []);

  const getChatbotVisibility = async () => {
    try {
      const response = await axios.get("/assignrights/chatbot-visibility/");
      const mode: ChatbotMode = response.data?.mode ?? "all";
      setChatbotMode(mode);
      setChatbotUserIds(
        Array.isArray(response.data?.user_ids) ? response.data.user_ids : []
      );
      setChatbotFormKey((key) => key + 1);
      setChatbotUnavailable(null);
    } catch (error: any) {
      // Say so on the card rather than showing a default that cannot be saved.
      console.error("Error fetching chatbot visibility:", error);
      setChatbotUnavailable(
        error?.response?.status === 404
          ? "This setting needs the latest backend deployed on the API server."
          : "The API server did not answer, so the current setting is unknown."
      );
    }
  };

  const saveChatbotVisibility = async () => {
    if (chatbotMode === "specific" && chatbotUserIds.length === 0) {
      toast.error("Choose at least one user, or set it to nobody");
      return;
    }

    setSavingChatbot(true);
    try {
      // This endpoint requires an administrator, and the shared axios instance
      // does not attach the login token, so it is passed explicitly.
      const token = localStorage.getItem("token");
      const response = await axios.post(
        "/assignrights/chatbot-visibility/set/",
        {
          mode: chatbotMode,
          user_ids: chatbotMode === "specific" ? chatbotUserIds : [],
        },
        token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
      );
      setChatbotMode(response.data?.mode ?? chatbotMode);
      setChatbotUserIds(response.data?.user_ids ?? []);
      setChatbotFormKey((key) => key + 1);
      toast.success("Chatbot visibility saved");
    } catch (error: any) {
      // Prefer the server's own words; it explains 403s and validation
      // failures far better than a generic message can.
      const status = error?.response?.status;
      toast.error(
        error?.response?.data?.error ??
          (status === 404
            ? "This setting needs the latest backend deployed on the API server."
            : !error?.response
              ? "Could not reach the API server. Check that it is running."
              : `Failed to save chatbot visibility (HTTP ${status})`)
      );
    } finally {
      setSavingChatbot(false);
    }
  };

  const getUsers = async () => {
    try {
      const response = await axios.get("/users/get_auth_users/");
      if (response.status === 200) {
        const userData = response.data.map((item: any) => ({
          id: item.id,
          full_name: item.first_name + " " + item.last_name,
          email: item.email,
        }));
        setUsers(userData);
      }
    } catch (error) {
      console.error("Error fetching users:", error);
    }
  };

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

  const getRecords = async (id: any) => {
    try {
      const response = await axios.get(`/assignrights/get/${id}/`);
      if (response.status === 200) {
        const assignrights = response.data.map((item: any) => ({
          id: item.id,
          mainmenu: item.mainmenu,
          submenu: item.submenu,
          username: item.username,
          email: item.email,
        }));
        setRecords(assignrights);
      }
    } catch (error) {
      console.error("Error fetching assigned records:", error);
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
      console.error("Error fetching main menus:", error);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await axios.post(`/assignrights/delete/${id}/`);
      getRecords(data.userid);
      toast.success("Assign rights deleted successfully");
    } catch (error) {
      console.error("Delete error:", error);
      toast.error("Failed to delete assign rights");
    }
  };

  const handleSubmit = async () => {
    const errors: Record<string, string> = {};
    if (!data.userid) errors.userid = "Employee is required";
    if (!data.menuid) errors.menuid = "Main menu is required";
    if (!data.submenuid.length) errors.submenuid = "Sub menu is required";

    setFieldError(errors);

    if (Object.keys(errors).length > 0) {
      toast.error("Please fix all validation errors");
      return;
    }

    try {
  
        await axios.post("/assignrights/create/", data);
        toast.success("Rights assigned successfully");
      

      setFieldError({ userid: "", menuid: "", submenuid: "" });
      setData({ userid: 0, menuid: 0, submenuid: [] });
        setSubMenus([]);
        location.reload();
      getRecords(data.userid);
    } catch (error) {
      toast.error("Failed to assign/update rights");
    }
  };

  // 2. Define Columns
  const columns: ColumnDef<UserRightsType>[] = [
    { header: "Main Menu", accessorKey: "mainmenu" },
    { header: "Sub Menu", accessorKey: "submenu" },
    { header: "Username", accessorKey: "username" },
    { header: "Email", accessorKey: "email" },
    {
      header: "Actions",
      id: "actions",
      cell: ({ row }) => (
        <div className="flex space-x-2">
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
          <div className="grid grid-cols-1 md:grid-cols-3 mb-4 gap-4">
            <div className="w-full md:col-span-1">
              <SearchableDropdown
                options={users.map((item) => ({
                  label: item.full_name + " (" + item.email + ")",
                  value: item.id,
                }))}
                placeholder="Select an Employee"
                label="Employees"
                id="employee-dropdown"
                value={data.userid}
                onChange={(value) => {
                  const userid = value ? parseInt(value.toString(), 10) : 0;
                  setData({ ...data, userid });
                  getRecords(userid);
                }}
                error={!!fielderror.userid}
                hint={fielderror.userid}
              />
            </div>
            <div className="w-full md:col-span-1">
              <SearchableDropdown
                options={mainmenu.map((item) => ({
                  label: item.name,
                  value: item.id,
                }))}
                placeholder="Select a Main Menu"
                label="Main Menu"
                id="mainmenu-dropdown"
                value={data.menuid}
                onChange={async (value) => {
                  const menuid = value ? parseInt(value.toString(), 10) : 0;
                  setData({ ...data, menuid, submenuid: [] });
                  setSubMenus([]);
                  if (menuid > 0) {
                    await getSubMenus(menuid);
                  }
                }}
                error={!!fielderror.menuid}
                hint={fielderror.menuid}
              />
            </div>
            <div className="w-full md:col-span-1">
              <MultiSelect
                options={submenus.map((item) => ({
                  value: item.id.toString(),
                  text: item.submenu,
                }))}
                label="Sub Menu"
                defaultSelected={data.submenuid.map((id) => id.toString())}
                onChange={(selected) => {
                  setData({
                    ...data,
                    submenuid: selected.map((item) => parseInt(item, 10)),
                  });
                }}
                disabled={data.menuid === 0}
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
              Add Rights
            </Button>
          </div>
        </ComponentCard>

        <ComponentCard
          title="HR Assistant (Chatbot)"
          desc="Controls whether the assistant's launcher appears in the corner of the dashboard. It does not change what the assistant can answer, or who its answers are scoped to."
        >
          {chatbotUnavailable && (
            <div className="mb-4 rounded-xl border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:border-warning-500/30 dark:bg-warning-500/15 dark:text-orange-400">
              {chatbotUnavailable}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {CHATBOT_MODES.map((option) => {
              const active = chatbotMode === option.value;
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors ${
                    active
                      ? "border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-500/10"
                      : "border-gray-200 hover:border-gray-300 dark:border-gray-800 dark:hover:border-gray-700"
                  }`}
                >
                  <input
                    type="radio"
                    name="chatbot-visibility"
                    className="mt-0.5 size-4 accent-brand-500"
                    checked={active}
                    onChange={() => setChatbotMode(option.value)}
                  />
                  <span>
                    <span className="block text-sm font-medium text-gray-800 dark:text-white/90">
                      {option.title}
                    </span>
                    <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">
                      {option.detail}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>

          {chatbotMode === "specific" && (
            <div className="mt-4">
              <MultiSelect
                key={`chatbot-users-${chatbotFormKey}`}
                options={users.map((item) => ({
                  value: item.id.toString(),
                  text: `${item.full_name} (${item.email})`,
                }))}
                label="Users who can see the assistant"
                defaultSelected={chatbotUserIds.map((id) => id.toString())}
                onChange={(selected) =>
                  setChatbotUserIds(selected.map((value) => parseInt(value, 10)))
                }
              />
            </div>
          )}

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {chatbotMode === "all"
                ? "Currently visible to every signed-in user."
                : chatbotMode === "none"
                  ? "Currently hidden for everyone."
                  : `Currently visible to ${chatbotUserIds.length} selected user${
                      chatbotUserIds.length === 1 ? "" : "s"
                    }.`}
            </p>
            <Button
              size="sm"
              variant="primary"
              onClick={saveChatbotVisibility}
              disabled={savingChatbot}
            >
              {savingChatbot ? "Saving..." : "Save Visibility"}
            </Button>
          </div>
        </ComponentCard>

        <ComponentCard title="Sub Menu Records">
          <EnhancedDataTable<UserRightsType> data={records} columns={columns} />
        </ComponentCard>
      </div>
    </>
  );
}
