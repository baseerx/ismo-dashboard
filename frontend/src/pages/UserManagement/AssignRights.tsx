
import Select from "../../components/form/Select";
import MultiSelect from "../../components/form/MultiSelect"; // Assume you have a MultiSelect component
import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import EnhancedDataTable from "../../components/tables/DataTables/DataTableOne";
import axios from "../../api/axios";
import { useState, useEffect } from "react";
import moment from "moment";
import _ from "lodash";
import { ToastContainer, toast } from "react-toastify";

import Label from "../../components/form/Label";
import Button from "../../components/ui/button/Button";



type MenuOption = { label: string; value: string  };
type SubMenuOption = { label: string; value: string ; main_id: string };

export default function AssignRights() {
    // ...existing state

    // New state for dropdowns
    const [userOptions, setUserOptions] = useState<MenuOption[]>([]);
    const [selectedUser, setSelectedUser] = useState<string | number | null>(null);

    const [mainMenuOptions, setMainMenuOptions] = useState<MenuOption[]>([]);
    const [selectedMainMenus, setSelectedMainMenus] = useState<(string | number)[]>([]);

    const [subMenuOptions, setSubMenuOptions] = useState<SubMenuOption[]>([]);
    const [filteredSubMenuOptions, setFilteredSubMenuOptions] = useState<SubMenuOption[]>([]);
    const [selectedSubMenus, setSelectedSubMenus] = useState<(string | number)[]>([]);

    // Fetch users for dropdown
    useEffect(() => {
        axios.get("/users/get/").then(res => {
            setUserOptions(
                res.data.users.map((u: any) => ({
                    label: `${u.username} (${u.email})`,
                    value: u.id,
                }))
            );
        });
        // Fetch main menus
        axios.get("/menus/main/").then(res => {
            setMainMenuOptions(
                res.data.map((m: any) => ({
                    label: m.name,
                    value: m.id,
                }))
            );
        });
    }, []);

    // Fetch sub menus when main menus change
    useEffect(() => {
        if (selectedMainMenus.length === 0) {
            setFilteredSubMenuOptions([]);
            setSelectedSubMenus([]);
            return;
        }
        axios
            .get(`/menus/sub/?main_ids=${selectedMainMenus.join(",")}`)
            .then(res => {
                setSubMenuOptions(res.data); // [{label, value, main_id}]
                setFilteredSubMenuOptions(res.data);
                setSelectedSubMenus([]); // Reset sub menu selection
            });
    }, [selectedMainMenus]);

    // UI
    return (
      <>
        {/* ...existing code */}
        <ComponentCard title="Assign Rights">
          {/* User Dropdown */}
          <div className="mb-4">
            <Label>User</Label>
            <Select
              options={userOptions}
              placeholder="Select user"
              defaultValue={selectedUser}
              onChange={setSelectedUser}
            />
          </div>
          {/* Main Menu Multi-Select */}
          <div className="mb-4">
            <Label>Main Menu</Label>
            <MultiSelect
              options={mainMenuOptions}
              placeholder="Select main menu(s)"
              defaultValue={selectedMainMenus}
              onChange={setSelectedMainMenus}
            />
          </div>
          {/* Sub Menu Multi-Select */}
          <div className="mb-4">
            <Label>Sub Menu</Label>
            <MultiSelect
              options={filteredSubMenuOptions.map((sm) => ({
                label: sm.label,
                value: sm.value,
              }))}
              placeholder="Select sub menu(s)"
              value={selectedSubMenus}
              onChange={setSelectedSubMenus}
              isDisabled={selectedMainMenus.length === 0}
            />
          </div>

          <div className="w-full flex justify-center items-center">
            <Button
              size="sm"
              className="w-1/3 mt-7"
              variant="primary"
              onClick={() => console.log("Assign Rights")}
            >
              Create User
            </Button>
          </div>
          {/* ...rest of your form/buttons */}
        </ComponentCard>
        {/* ...existing code */}
      </>
    );
}
