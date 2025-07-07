import PageBreadcrumb from "../../components/common/PageBreadCrumb";
import ComponentCard from "../../components/common/ComponentCard";
import PageMeta from "../../components/common/PageMeta";
import axios from "../../api/axios";
import { useState } from "react";
import _ from "lodash";
import { ToastContainer, toast } from "react-toastify";

import Button from "../../components/ui/button/Button";
import Label from "../../components/form/Label";
import Input from "../../components/form/input/InputField";




export default function MainMenu() {
    const [data, setData] = useState({
        title: "",
        description: "",
    });

    const [fielderror, setFieldError] = useState<Record<string, string>>({
        title: "",
        description: "",
    });

    const handleSubmit = async () => {
        const errors: Record<string, string> = {};
        if (!data.title) errors.title = "Main menu title is required";
        if (!data.description) errors.description = "Description is required";

        setFieldError(errors);

        if (Object.keys(errors).length > 0) {
            toast.error("Please fix all validation errors");
            return;
        }

        try {
            // Replace with your API endpoint
            await axios.post("/menus/create/", data);
            toast.success("Main menu created successfully");
            setData({ title: "", description: "" });
            setFieldError({});
        } catch (error) {
            toast.error("Failed to create main menu");
        }
    };

    return (
        <>
            <PageMeta
                title="ISMO - Create Main Menu"
                description="ISMO Admin Dashboard - Create Main Menu"
            />
            <PageBreadcrumb pageTitle="Create Main Menu" />
            <div className="space-y-6">
                <ComponentCard title="Create New Main Menu">
                    <ToastContainer position="bottom-right" />

                    <div className="grid grid-cols-1 sm:grid-cols-2 mb-4 gap-4">
                        <div className="w-full">
                            <Label>Main Menu Title</Label>
                            <Input
                                type="text"
                                placeholder="Enter main menu title"
                                value={data.title}
                                onChange={(e) => setData({ ...data, title: e.target.value })}
                                error={!!fielderror.title}
                                hint={fielderror.title}
                            />
                        </div>
                        <div className="w-full">
                            <Label>Description</Label>
                            <Input
                                type="text"
                                placeholder="Enter description"
                                value={data.description}
                                onChange={(e) => setData({ ...data, description: e.target.value })}
                                error={!!fielderror.description}
                                hint={fielderror.description}
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
                            Create Main Menu
                        </Button>
                    </div>
                </ComponentCard>
            </div>
        </>
    );
}
