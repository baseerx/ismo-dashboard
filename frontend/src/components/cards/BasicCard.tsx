import { ArrowUpIcon } from "../../icons";
import Badge from "../ui/badge/Badge";

type CardProps = {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  displayAbsentEmployees?: () => void;
  percentage: string;
  badgeclr: any;
};

export default function BasicCard({
  title,
  value,
  icon,
  displayAbsentEmployees,
  percentage,
  badgeclr
}: CardProps) {
  const handleClick = () => {
    if (title === "Absent Today" && displayAbsentEmployees) {
      displayAbsentEmployees();
    }
  };
  return (
    <div className="w-full max-w-md rounded-2xl border hover:border-gray-300 hover:bg-gray-100 cursor-pointer p-5 dark:border-gray-800 dark:bg-white/[0.03] md:p-6" onClick={handleClick}>
      {/* Icon */}
      <div className="flex items-center justify-center w-12 h-12 bg-gray-100 rounded-xl dark:bg-gray-800">
        {icon}
      </div>

      {/* Content */}
      <div className="flex items-end justify-between mt-5">
        <div>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {title} {title === "Absent Today" && (
              <small className="text-xs text-gray-400 dark:text-gray-500">click me to see all absent employees</small>
            )}
          </span>
          <h4 className="mt-2 font-bold text-gray-800 text-title-sm dark:text-white/90">
            {value}
          </h4>
        </div>
        <Badge color={badgeclr}>
          <ArrowUpIcon />
          {percentage}
        </Badge>
      </div>
    </div>
  );
}
