import Chart from "react-apexcharts";
import { ApexOptions } from "apexcharts";
import { useTheme } from "../../../context/ThemeContext";
import { categoricalColors } from "./palette";

type Series = { name: string; data: number[] };

type Props = {
  categories: string[];
  series: Series[];
  height?: number;
  valueSuffix?: string;
  colors?: string[];
};

export default function TrendAreaChart({
  categories,
  series,
  height = 300,
  valueSuffix = "",
  colors,
}: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const seriesColors = colors ?? categoricalColors(theme, series.length);

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "area",
      toolbar: { show: false },
      zoom: { enabled: false },
    },
    colors: seriesColors,
    dataLabels: { enabled: false },
    stroke: { curve: "smooth", width: 2 },
    fill: {
      type: "gradient",
      gradient: { opacityFrom: 0.35, opacityTo: 0.05 },
    },
    markers: { size: 0, hover: { size: 6 } },
    grid: {
      borderColor: isDark ? "#2c2c2a" : "#e1e0d9",
      strokeDashArray: 4,
    },
    legend: {
      show: series.length > 1,
      position: "top",
      horizontalAlign: "left",
      labels: { colors: isDark ? "#c3c2b7" : "#52514e" },
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
        formatter: (val: number) => `${val}${valueSuffix}`,
      },
    },
    tooltip: {
      theme: isDark ? "dark" : "light",
      x: { show: true },
      y: { formatter: (val: number) => `${val}${valueSuffix}` },
    },
  };

  return (
    <div className="max-w-full overflow-x-auto custom-scrollbar">
      <div className="min-w-[500px]">
        <Chart options={options} series={series} type="area" height={height} />
      </div>
    </div>
  );
}
