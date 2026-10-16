import GroupAttendanceReport, { GroupKind } from "../../components/attendance/GroupAttendanceReport";

/** Biometric Attendance > Section Attendance: one row per employee in a section. */
const SECTION: GroupKind = {
  noun: "Section",
  optionsUrl: "/sections/get/",
  employeeField: "section_id",
  reportUrl: "/attendance/sections/",
  requestField: "section",
};

export default function SectionAttendanceReport() {
  return <GroupAttendanceReport kind={SECTION} />;
}
