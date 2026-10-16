import GroupAttendanceReport, { GroupKind } from "../../components/attendance/GroupAttendanceReport";

/**
 * Biometric Attendance > Location Attendance: one row per employee at an office
 * location (Head Office, Jamshoro, Lahore, Shaheen Plaza), with the same
 * columns as the Section report.
 */
const LOCATION: GroupKind = {
  noun: "Location",
  optionsUrl: "/attendance/locations/",
  employeeField: "location_id",
  reportUrl: "/attendance/location/",
  requestField: "location",
};

export default function LocationAttendanceReport() {
  return <GroupAttendanceReport kind={LOCATION} />;
}
