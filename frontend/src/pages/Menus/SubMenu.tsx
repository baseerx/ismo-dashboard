import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import _ from "lodash";
import { ToastContainer, toast } from "react-toastify";

import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";
import Select from "../../components/form/Select";

type MainMenu = {
  id: number;
  title: string;
  description: string;
};

export default function SubMenu() {
  const [data, setData] = useState({
    main_menu_id: "",
    sub_menu_title: "",
  });

  const [mainMenus, setMainMenus] = useState<MainMenu[]>([]);

  const [fielderror, setFieldError] = useState<Record<string, string>>({
    main_menu_id: "",
    sub_menu_title: "",
  });

  useEffect(() => {
    fetchMainMenus();
  }, []);

  const fetchMainMenus = async () => {
    try {
      const response = await axios.get("/menus/get/");
      setMainMenus(response.data.menus || []);
    } catch (error) {
      console.error("Error fetching main menus:", error);
      toast.error("Failed to load main menus");
    }
  };

  const handleSubmit = async () => {
    const errors: Record<string, string> = {};

    if (!data.main_menu_id)
      errors.main_menu_id = "Main menu selection is required";
    if (!data.sub_menu_title)
      errors.sub_menu_title = "Sub menu title is required";

    setFieldError(errors);

    if (Object.keys(errors).length > 0) {
      toast.error("Please fix all validation errors");
      return;
    }

    try {
      const submitData = {
        main_menu_id: parseInt(data.main_menu_id),
        title: data.sub_menu_title,
      };

      await axios.post("/submenus/create/", submitData);
      toast.success("Sub menu created successfully");
      setData({ main_menu_id: "", sub_menu_title: "" });
      setFieldError({});
    } catch (error) {
      console.error("Error creating sub menu:", error);
      toast.error("Failed to create sub menu");
    }
  };

  const mainMenuOptions = mainMenus.map((menu) => ({
    label: menu.title,
    value: menu.id.toString(),
  }));

  return (
    <>
      <PageMeta
        title="ISMO - Create Sub Menu"
        description="ISMO Admin Dashboard - Create Sub Menu"
      />
      <PageBreadcrumb pageTitle="Create Sub Menu" />
      <div className="space-y-6">
        <ComponentCard title="Create New Sub Menu">
          <ToastContainer position="bottom-right" />

          <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-4">
            <div className="w-full">
              <Label>Main Menu</Label>
              <Select
                options={mainMenuOptions}
                placeholder="Select main menu"
                value={data.main_menu_id}
                onChange={(value) => {
                  setData({ ...data, main_menu_id: value });
                  setFieldError({ ...fielderror, main_menu_id: "" });
                }}
                error={!!fielderror.main_menu_id}
                hint={fielderror.main_menu_id}
              />
            </div>

            <div className="w-full">
              <Label>Sub Menu Title</Label>
              <Input
                type="text"
                placeholder="Enter sub menu title"
                value={data.sub_menu_title}
                onChange={(e) => {
                  setData({ ...data, sub_menu_title: e.target.value });
                  setFieldError({ ...fielderror, sub_menu_title: "" });
                }}
                error={!!fielderror.sub_menu_title}
                hint={fielderror.sub_menu_title}
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
              Create Sub Menu
            </Button>
          </div>
        </ComponentCard>
      </div>
    </>
  );
}
