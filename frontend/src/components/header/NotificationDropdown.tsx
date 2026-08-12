import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Dropdown } from "../ui/dropdown/Dropdown";
import axios from "../../api/axios";

type Notification = {
  id: number;
  category: string;
  event: string;
  title: string;
  message?: string;
  link?: string | null;
  related_id?: number | null;
  is_read: boolean;
  created_at: string;
};

// How often to re-check while the tab is open, so an approval that happens
// mid-session appears without a reload.
const POLL_MS = 60_000;

// sessionStorage key: the panel auto-opens once per browser session, i.e. on
// login, rather than every time the header remounts on navigation.
const POPUP_SHOWN_KEY = "ismo:notifications:popupShown";

const eventStyles: Record<string, { dot: string; label: string }> = {
  approved: { dot: "bg-success-500", label: "Approved" },
  rejected: { dot: "bg-error-500", label: "Rejected" },
  awaiting_approval: { dot: "bg-warning-500", label: "Needs approval" },
};

/** "3 minutes ago" style, from a "YYYY-MM-DD HH:MM:SS" server timestamp. */
const relativeTime = (value: string) => {
  // Treated as local time — the API sends server-local timestamps (USE_TZ is
  // off), so parsing as UTC would shift them.
  const then = new Date(value.replace(" ", "T"));
  const seconds = Math.floor((Date.now() - then.getTime()) / 1000);

  if (Number.isNaN(seconds)) return value;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} d ago`;
  return then.toLocaleDateString();
};

export default function NotificationDropdown() {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const autoOpened = useRef(false);

  const erpId = (() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}").erpid;
    } catch {
      return undefined;
    }
  })();

  const fetchNotifications = useCallback(
    async (openIfUnread = false) => {
      if (!erpId) return;
      setLoading(true);
      try {
        const response = await axios.get(`/notifications/get/${erpId}/`);
        const list: Notification[] = response.data.notifications ?? [];
        setItems(list);
        setUnreadCount(response.data.unread_count ?? 0);

        // The "pop up as he logs in" behaviour: open the panel once per
        // session if anything is unread.
        if (
          openIfUnread &&
          !autoOpened.current &&
          (response.data.unread_count ?? 0) > 0 &&
          !sessionStorage.getItem(POPUP_SHOWN_KEY)
        ) {
          autoOpened.current = true;
          sessionStorage.setItem(POPUP_SHOWN_KEY, "1");
          setIsOpen(true);
        }
      } catch (error) {
        // A notification failure must never disrupt the page.
        console.error("Error fetching notifications:", error);
      } finally {
        setLoading(false);
      }
    },
    [erpId]
  );

  useEffect(() => {
    fetchNotifications(true);
    const timer = setInterval(() => fetchNotifications(false), POLL_MS);
    return () => clearInterval(timer);
  }, [fetchNotifications]);

  const openNotification = async (notification: Notification) => {
    setIsOpen(false);

    // Mark read optimistically so the badge responds immediately; the request
    // is scoped by erp_id server side.
    if (!notification.is_read) {
      setItems((prev) =>
        prev.map((n) => (n.id === notification.id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((count) => Math.max(0, count - 1));
      try {
        await axios.post("/notifications/mark-read/", {
          id: notification.id,
          erp_id: erpId,
        });
      } catch (error) {
        console.error("Error marking notification read:", error);
      }
    }

    if (notification.link) navigate(notification.link);
  };

  const markAllRead = async () => {
    if (!erpId || unreadCount === 0) return;
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
    try {
      await axios.post("/notifications/mark-all-read/", { erp_id: erpId });
    } catch (error) {
      console.error("Error marking all read:", error);
    }
  };

  if (!erpId) return null;

  return (
    <div className="relative">
      <button
        aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
        className="relative flex items-center justify-center text-gray-500 transition-colors bg-white border border-gray-200 rounded-full dropdown-toggle hover:text-gray-700 h-11 w-11 hover:bg-gray-100 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white"
        onClick={() => setIsOpen((open) => !open)}
      >
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 z-10 flex h-4 min-w-4 items-center justify-center rounded-full bg-error-500 px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
            <span className="absolute inline-flex w-full h-full bg-error-400 rounded-full opacity-75 animate-ping" />
          </span>
        )}
        <svg
          className="fill-current"
          width="20"
          height="20"
          viewBox="0 0 20 20"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            fillRule="evenodd"
            clipRule="evenodd"
            d="M10.75 2.29248C10.75 1.87827 10.4143 1.54248 10 1.54248C9.58583 1.54248 9.25004 1.87827 9.25004 2.29248V2.83613C6.08266 3.20733 3.62504 5.9004 3.62504 9.16748V14.4591H3.33337C2.91916 14.4591 2.58337 14.7949 2.58337 15.2091C2.58337 15.6234 2.91916 15.9591 3.33337 15.9591H4.37504H15.625H16.6667C17.0809 15.9591 17.4167 15.6234 17.4167 15.2091C17.4167 14.7949 17.0809 14.4591 16.6667 14.4591H16.375V9.16748C16.375 5.9004 13.9174 3.20733 10.75 2.83613V2.29248ZM14.875 14.4591V9.16748C14.875 6.47509 12.6924 4.29248 10 4.29248C7.30765 4.29248 5.12504 6.47509 5.12504 9.16748V14.4591H14.875ZM8.00004 17.7085C8.00004 18.1228 8.33583 18.4585 8.75004 18.4585H11.25C11.6643 18.4585 12 18.1228 12 17.7085C12 17.2943 11.6643 16.9585 11.25 16.9585H8.75004C8.33583 16.9585 8.00004 17.2943 8.00004 17.7085Z"
            fill="currentColor"
          />
        </svg>
      </button>

      <Dropdown
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        className="absolute -right-[240px] mt-[17px] flex max-h-[480px] w-[350px] flex-col rounded-2xl border border-gray-200 bg-white p-3 shadow-theme-lg dark:border-gray-800 dark:bg-gray-dark sm:w-[380px] lg:right-0"
      >
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-gray-100 dark:border-gray-700">
          <h5 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            Notifications
            {unreadCount > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                {unreadCount} unread
              </span>
            )}
          </h5>
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-xs font-medium text-brand-500 hover:text-brand-600 dark:text-brand-400"
            >
              Mark all read
            </button>
          )}
        </div>

        <ul className="flex flex-col overflow-y-auto custom-scrollbar">
          {loading && items.length === 0 && (
            <li className="px-2 py-6 text-sm text-center text-gray-500 dark:text-gray-400">
              Loading...
            </li>
          )}

          {!loading && items.length === 0 && (
            <li className="px-2 py-6 text-sm text-center text-gray-500 dark:text-gray-400">
              You have no notifications.
            </li>
          )}

          {items.map((notification) => {
            const style =
              eventStyles[notification.event] ?? {
                dot: "bg-gray-400",
                label: notification.event,
              };
            return (
              <li key={notification.id}>
                <button
                  onClick={() => openNotification(notification)}
                  className={`flex w-full gap-3 rounded-lg border-b border-gray-100 p-3 text-left hover:bg-gray-100 dark:border-gray-800 dark:hover:bg-white/5 ${
                    notification.is_read ? "" : "bg-brand-50/60 dark:bg-brand-500/10"
                  }`}
                >
                  <span
                    className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-gray-800 dark:text-white/90">
                      {notification.title}
                    </span>
                    {notification.message && (
                      <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">
                        {notification.message}
                      </span>
                    )}
                    <span className="mt-1 flex items-center gap-2 text-[11px] text-gray-400 dark:text-gray-500">
                      <span>{style.label}</span>
                      <span>·</span>
                      <span>{relativeTime(notification.created_at)}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </Dropdown>
    </div>
  );
}
