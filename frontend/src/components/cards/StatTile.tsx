import Badge from "../ui/badge/Badge";

type BadgeColor = "primary" | "success" | "error" | "warning" | "info" | "light" | "dark";

type StatTileProps = {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  subtext?: string;
  badge?: { text: string; color: BadgeColor };
  onClick?: () => void;
};

export default function StatTile({ title, value, icon, subtext, badge, onClick }: StatTileProps) {
  return (
    <div
      className={`w-full rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] md:p-6 ${
        onClick ? "cursor-pointer hover:border-gray-300 hover:bg-gray-50 dark:hover:bg-white/[0.06]" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-center w-12 h-12 bg-gray-100 rounded-xl dark:bg-gray-800">
        {icon}
      </div>

      <div className="mt-5">
        <span className="text-sm text-gray-500 dark:text-gray-400">{title}</span>
        <div className="mt-2 flex items-end justify-between gap-2">
          <h4 className="font-bold text-gray-800 text-title-sm dark:text-white/90">{value}</h4>
          {badge && <Badge color={badge.color}>{badge.text}</Badge>}
        </div>
        {subtext && (
          <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">{subtext}</p>
        )}
      </div>
    </div>
  );
}
