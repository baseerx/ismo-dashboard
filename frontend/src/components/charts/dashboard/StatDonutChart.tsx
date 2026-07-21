import Chart from "react-apexcharts";
import { ApexOptions } from "apexcharts";
import { useTheme } from "../../../context/ThemeContext";

type Props = {
  labels: string[];
  series: number[];
  colors: string[];
  centerLabel?: string;
  height?: number;
};

export default function StatDonutChart({
  labels,
  series,
  colors,
  centerLabel = "Total",
  height = 280,
}: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const total = series.reduce((sum, v) => sum + v, 0);

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "donut",
      toolbar: { show: false },
    },
    labels,
    colors,
    stroke: {
      width: 2,
      colors: [isDark ? "#1a1a19" : "#ffffff"],
    },
    legend: {
      show: true,
      position: "bottom",
      fontSize: "13px",
      labels: { colors: isDark ? "#c3c2b7" : "#52514e" },
      markers: { size: 6 } as any,
    },
    dataLabels: {
      enabled: true,
      formatter: (val: number) => `${val.toFixed(0)}%`,
      style: { fontSize: "12px" },
    },
    tooltip: {
      theme: isDark ? "dark" : "light",
      y: { formatter: (val: number) => `${val} (${total ? ((val / total) * 100).toFixed(1) : 0}%)` },
    },
    plotOptions: {
      pie: {
        donut: {
          size: "70%",
          labels: {
            show: true,
            total: {
              show: true,
              label: centerLabel,
              color: isDark ? "#ffffff" : "#0b0b0b",
              formatter: () => `${total}`,
            },
            value: {
              color: isDark ? "#ffffff" : "#0b0b0b",
            },
          },
        },
      },
    },
  };

  if (total === 0) {
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
      <Chart options={options} series={series} type="donut" height={height} />
    </div>
  );
}
