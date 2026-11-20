import Button from "../../components/ui/button/Button";

type Props = {
  page: number;
  numPages: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
};

/** Page numbers to show: the first, the last, and two either side of the
 *  current page, with gaps marked by null. */
const pageList = (page: number, numPages: number): (number | null)[] => {
  const pages: (number | null)[] = [];
  for (let n = 1; n <= numPages; n++) {
    if (n === 1 || n === numPages || Math.abs(n - page) <= 2) {
      pages.push(n);
    } else if (pages[pages.length - 1] !== null) {
      pages.push(null);
    }
  }
  return pages;
};

/** "Showing 11–20 of 31" with Previous / page numbers / Next, under a table. */
const TablePagination = ({ page, numPages, total, pageSize, onChange }: Props) => {
  if (total <= 0) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <div className="mt-4 flex flex-col items-center justify-between gap-3 border-t border-gray-100 pt-4 sm:flex-row dark:border-gray-800">
      <span className="text-xs text-gray-500 dark:text-gray-400">
        Showing {first}–{last} of {total}
      </span>
      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="xs" variant="outline" onClick={() => onChange(page - 1)} disabled={page <= 1}>
          Previous
        </Button>
        {pageList(page, numPages).map((n, i) =>
          n === null ? (
            <span key={`gap-${i}`} className="px-1 text-xs text-gray-400">
              …
            </span>
          ) : (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              aria-current={n === page ? "page" : undefined}
              className={`min-w-8 rounded-lg px-2 py-1 text-xs font-medium ${
                n === page
                  ? "bg-brand-500 text-white"
                  : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/[0.05]"
              }`}
            >
              {n}
            </button>
          )
        )}
        <Button
          size="xs"
          variant="outline"
          onClick={() => onChange(page + 1)}
          disabled={page >= numPages}
        >
          Next
        </Button>
      </div>
    </div>
  );
};

export default TablePagination;
