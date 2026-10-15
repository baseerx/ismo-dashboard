import { useEffect, useState } from "react";
import axios from "../api/axios";
import { DEPARTMENT_SECTION_NAME } from "./sectionHead";

/**
 * The id of the section holding the department head (the ISMO section), for
 * the approver rule in sectionHead.ts. `undefined` while it is being looked
 * up, `null` when it could not be found - in which case everyone falls back
 * to their own section head.
 */
export function useDepartmentSectionId(): number | null | undefined {
  const [sectionId, setSectionId] = useState<number | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    axios
      .get("/sections/get/")
      .then((response) => {
        const department = (Array.isArray(response.data) ? response.data : []).find(
          (section: any) =>
            String(section.name).trim().toLowerCase() ===
            DEPARTMENT_SECTION_NAME.toLowerCase()
        );
        if (!cancelled) setSectionId(department ? Number(department.id) : null);
      })
      .catch(() => {
        if (!cancelled) setSectionId(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return sectionId;
}
