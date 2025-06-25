import React, { useMemo, useState,useEffect } from "react";
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
  onEdit?: (row: T) => void;
  onDelete?: (id: any) => void;
  getExportHeaders?: () => string[];
  getExportRows?: (data: T[]) => any[][];
  idKey?: keyof T;
}

const EnhancedDataTable = <T extends object>({
  data,
  columns,
  onEdit,
  onDelete,
  getExportHeaders,
  getExportRows,
  idKey = "id",
}: EnhancedDataTableProps<T>) => {
    const [globalFilter, setGlobalFilter] = useState("");
    const [tableData, setTableData] = useState<T[]>([]);
    
    
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
  });

  const exportToExcel = () => {
    const worksheet = XLSX.utils.json_to_sheet(tableData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Data");
    XLSX.writeFile(workbook, "data.xlsx");
  };

  const exportToPDF = () => {
    const doc = new jsPDF();
    autoTable(doc, {
      head: [
        getExportHeaders ? getExportHeaders() : Object.keys(tableData[0] || {}),
      ],
      body: getExportRows
        ? getExportRows(tableData)
        : tableData.map((row) => Object.values(row)),
    });
    doc.save("data.pdf");
  };

  const handleEdit = (row: T) => {
    if (onEdit) onEdit(row);
  };

  const handleDelete = (id: any) => {
    if (onDelete) onDelete(id);
    else if (window.confirm("Are you sure to delete this item?")) {
      setTableData((prev) => prev.filter((item) => item[idKey] !== id));
    }
  };

  return (
    <div className="p-6 space-y-4 bg-white rounded-xl shadow border border-gray-200">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
        <input
          type="text"
          placeholder="Search..."
          value={globalFilter ?? ""}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="w-full sm:w-64 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring focus:border-blue-400"
        />
        <div className="flex gap-2">
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
        <table className="min-w-full table-auto border-collapse">
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
                  <td key={cell.id} className="border px-4 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center text-sm">
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
