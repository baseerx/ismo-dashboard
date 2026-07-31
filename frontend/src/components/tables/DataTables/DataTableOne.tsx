import  { useState,useEffect, useRef } from "react";
import { flushSync } from "react-dom";
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  flexRender,
  ColumnDef,
} from "@tanstack/react-table";
import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import * as XLSX from "xlsx";

interface EnhancedDataTableProps<T extends object> {
  data: T[];
    columns: ColumnDef<T, any>[];
    fromdate?: string;
  todate?: string;
  onEdit?: (row: T) => void;
  onDelete?: (id: any) => void;
  getExportHeaders?: () => string[];
  getExportRows?: (data: T[]) => any[][];
  idKey?: keyof T;
  /** Show a Print button. The caller must wrap the table in a `print-area`
   *  element, otherwise the global print stylesheet keeps it off the paper. */
  printable?: boolean;
}

const EnhancedDataTable = <T extends object>({
  data,
    columns,
    fromdate,
    todate,
  getExportHeaders,
  getExportRows,
  printable = false,
}: EnhancedDataTableProps<T>) => {
    const [globalFilter, setGlobalFilter] = useState("");
    const [tableData, setTableData] = useState<T[]>([]);
    // Page size / theme captured while a print dialog is open, restored after.
    const printRestore = useRef<{ pageSize: number; wasDark: boolean } | null>(
      null
    );
    
    
  useEffect(() => {
   setTableData(data);
  }, [data])
  
  const table = useReactTable({
    data: tableData,
    columns,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageIndex: 0,
        pageSize: 15, // 👈 Show 20 records by default
      },
    },
  });

const exportToExcel = () => {
  const wsData = [
    ["Independent System & Market Operator (ISMO)"],
    ["Attendance Report" + (fromdate ? " (from: " + fromdate + ", to: " + todate + ")" : "")],
    [], // empty row for spacing
    getExportHeaders ? getExportHeaders() : Object.keys(tableData[0] || {}),
    ...(getExportRows
      ? getExportRows(tableData)
      : tableData.map((row) => Object.values(row))),
  ];

  const worksheet = XLSX.utils.aoa_to_sheet(wsData);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Data");
  XLSX.writeFile(workbook, "attendance_report.xlsx");
};

const exportToPDF = () => {
  const doc = new jsPDF();

  // Add custom multi-line header
  doc.setFontSize(12);
  doc.text("Independent System & Market Operator (ISMO)", 14, 15);
  doc.text("Attendance Report" + (fromdate ? " (from: " + fromdate + ", to: " + todate + ")" : ""), 14, 23);

  autoTable(doc, {
    startY: 30,
    head: [
      getExportHeaders ? getExportHeaders() : Object.keys(tableData[0] || {}),
    ],
    body: getExportRows
      ? getExportRows(tableData)
      : tableData.map((row) => Object.values(row)),
  });

  doc.save("attendance_report.pdf");
};

// The browser prints what is on screen, so before the dialog opens the
// paginated view has to be widened to every matching row — otherwise only the
// current page of 15 reaches the paper — and the dark palette has to go, since
// white-on-white is unreadable in print.
const expandForPrint = () => {
  if (printRestore.current) return; // already opened up for this dialog

  const root = document.documentElement;
  const wasDark = root.classList.contains("dark");
  if (wasDark) root.classList.remove("dark");

  printRestore.current = {
    pageSize: table.getState().pagination.pageSize,
    wasDark,
  };

  // Synchronous so the extra rows are in the DOM by the time the browser
  // snapshots the page for printing.
  flushSync(() => {
    table.setPageIndex(0);
    table.setPageSize(Math.max(table.getFilteredRowModel().rows.length, 1));
  });
};

const restoreAfterPrint = () => {
  const saved = printRestore.current;
  if (!saved) return;
  printRestore.current = null;
  table.setPageSize(saved.pageSize);
  if (saved.wasDark) document.documentElement.classList.add("dark");
};

// Covers Ctrl+P and the browser menu as well as the Print button.
useEffect(() => {
  if (!printable) return;
  window.addEventListener("beforeprint", expandForPrint);
  window.addEventListener("afterprint", restoreAfterPrint);
  return () => {
    window.removeEventListener("beforeprint", expandForPrint);
    window.removeEventListener("afterprint", restoreAfterPrint);
  };
});

const handlePrint = () => {
  expandForPrint(); // browsers that never fire `beforeprint`
  window.print();
};


  return (
    <div className="p-6 space-y-4 bg-white rounded-xl shadow border border-gray-200">
      <div className="no-print flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
        <input
          type="text"
          placeholder="Search..."
          value={globalFilter ?? ""}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="w-full sm:w-64 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring focus:border-blue-400"
        />
        <div className="flex gap-2">
          {printable && (
            <button
              onClick={handlePrint}
              disabled={tableData.length === 0}
              className="bg-brand-500 hover:bg-brand-600 text-white px-4 py-2 rounded text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              Print
            </button>
          )}
          <button
            onClick={exportToExcel}
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded text-sm"
          >
            Export Excel
          </button>
          <button
            onClick={exportToPDF}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded text-sm"
          >
            Export PDF
          </button>
        </div>
      </div>

          <div className="overflow-x-auto">
        
        <table className="print-report min-w-full table-auto border-collapse">
          <thead className="bg-gray-100 text-sm text-gray-700">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="border px-4 py-2 text-left">
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="text-sm text-gray-800">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50">
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className={`border px-4 py-2 ${
                      (cell.column.columnDef.meta as any)?.getTdClassName?.(
                        cell.getValue()
                      ) ?? ""
                    }`}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="no-print flex justify-between items-center text-sm">
        <div>
          Page {table.getState().pagination.pageIndex + 1} of{" "}
          {table.getPageCount()}
        </div>
        <div className="space-x-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1 rounded border border-gray-300 bg-white disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1 rounded border border-gray-300 bg-white disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default EnhancedDataTable;
