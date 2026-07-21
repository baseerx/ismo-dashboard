import Chart from "react-apexcharts";
import { ApexOptions } from "apexcharts";
import { useTheme } from "../../../context/ThemeContext";

type Props = {
  label: string;
  value: number; // 0-100
  color?: string;
  height?: number;
};

export default function RadialGaugeChart({ label, value, color, height = 220 }: Props) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const clamped = Math.max(0, Math.min(100, value));
  const resolvedColor = color ?? (clamped >= 90 ? "#12b76a" : clamped >= 70 ? "#f79009" : "#f04438");

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "radialBar",
      toolbar: { show: false },
    },
    colors: [resolvedColor],
    plotOptions: {
      radialBar: {
        hollow: { size: "65%" },
        track: { background: isDark ? "#2c2c2a" : "#e1e0d9" },
        dataLabels: {
          name: {
            show: true,
            fontSize: "13px",
            color: isDark ? "#c3c2b7" : "#52514e",
            offsetY: -8,
          },
          value: {
            show: true,
            fontSize: "24px",
            fontWeight: 700,
            color: isDark ? "#ffffff" : "#0b0b0b",
            formatter: (val: number) => `${val.toFixed(0)}%`,
          },
        },
      },
    },
    stroke: { lineCap: "round" },
    labels: [label],
  };

  return (
    <div className="max-w-full overflow-x-auto custom-scrollbar">
      <Chart options={options} series={[clamped]} type="radialBar" height={height} />
    </div>
  );
}
