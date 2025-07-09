import Chart from "react-apexcharts";
import { ApexOptions } from "apexcharts";
type Props = {
    present: number;
    absent: number;
    total: number;
};
export default function PieChartOne({ present, absent, total }: Props) {
    const options: ApexOptions = {
        legend: {
            show: true,
            position: "top",
            horizontalAlign: "left",
        },
        colors: ["#4CAF50", "#F44336"],
        chart: {
            fontFamily: "Outfit, sans-serif",
            height: 310,
            type: "pie",
            toolbar: {
                show: false,
            },
        },
        dataLabels: {
            enabled: true,
        },
        tooltip: {
            enabled: true,
        },
        labels: ["Present", "Absent"],
    };

    // Example data: 80 present, 20 absent (total 100 employees)
    const series = [present/total, absent/total];

    return (
        <div className="max-w-full overflow-x-auto custom-scrollbar">
            <div id="pieChartOne" className="min-w-[300px]">
                <Chart options={options} series={series} type="pie" height={310} />
                <div className="text-center mt-2 font-semibold">
                    Total Employees: {total}
                </div>
            </div>
        </div>
    );
}
