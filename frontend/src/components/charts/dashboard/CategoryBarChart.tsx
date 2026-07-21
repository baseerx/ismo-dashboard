import Chart from "react-apexcharts";
import { ApexOptions } from "apexcharts";
import { useTheme } from "../../../context/ThemeContext";
import { categoricalColors } from "./palette";

type Series = { name: string; data: number[] };

type Props = {
  categories: string[];
  series: Series[];
  height?: number;
  horizontal?: boolean;
  /** Color each bar by its category (only meaningful for a single series). */
  distributed?: boolean;
  colors?: string[];
  valueSuffix?: string;
};

export default function CategoryBarChart({
  categories,
  series,
  height = 300,
  horizontal = false,
  distributed = false,
  colors,
  valueSuffix = "",
}: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const barColors =
    colors ?? (distributed ? categoricalColors(theme, categories.length) : categoricalColors(theme, series.length));

  const hasData = series.some((s) => s.data.some((v) => v > 0));

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "bar",
      toolbar: { show: false },
    },
    colors: barColors,
    plotOptions: {
      bar: {
        horizontal,
        borderRadius: 4,
        borderRadiusApplication: "end",
        distributed,
        columnWidth: "45%",
        barHeight: "55%",
      },
    },
    dataLabels: { enabled: false },
    legend: {
      show: series.length > 1,
      position: "top",
      horizontalAlign: "left",
      labels: { colors: isDark ? "#c3c2b7" : "#52514e" },
    },
    grid: {
      borderColor: isDark ? "#2c2c2a" : "#e1e0d9",
      strokeDashArray: 4,
    },
    xaxis: {
      categories,
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: { style: { colors: isDark ? "#898781" : "#898781", fontSize: "11px" } },
    },
    yaxis: {
      labels: {
        style: { colors: isDark ? "#898781" : "#898781" },
        formatter: horizontal ? undefined : (val: number) => `${val}${valueSuffix}`,
      },
    },
    tooltip: {
      theme: isDark ? "dark" : "light",
      y: { formatter: (val: number) => `${val}${valueSuffix}` },
    },
  };

  if (!hasData) {
    return (
      <div
        className="flex items-center justify-center text-sm text-gray-400 dark:text-gray-500"
        style={{ height }}
      >
        No data available
      </div>
    );
  }

  return (
    <div className="max-w-full overflow-x-auto custom-scrollbar">
      <div className="min-w-[320px]">
        <Chart options={options} series={series} type="bar" height={height} />
      </div>
    </div>
  );
}
