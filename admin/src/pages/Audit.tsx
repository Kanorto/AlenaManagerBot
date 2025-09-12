import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ColumnDef,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  flexRender,
} from '@tanstack/react-table';
import { AuditLog, AuditQueryParams, getAuditLogs } from '../api/audit';
import { useNotifications } from '../store/notifications';

/**
 * Audit logs page displays a paginated and sortable table of system actions.
 * Administrators can filter by user, object type, action and date range.
 * A CSV export button allows downloading all filtered results (limited to 500 rows)
 * for offline review.  Only super‑administrators should access this page.
 */
const AuditPage: React.FC = () => {
  const { addNotification } = useNotifications();

  // Pagination and sorting state
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sorting, setSorting] = useState<SortingState>([]);

  // Filter state
  const [userIdFilter, setUserIdFilter] = useState('');
  const [objectTypeFilter, setObjectTypeFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [startDateFilter, setStartDateFilter] = useState('');
  const [endDateFilter, setEndDateFilter] = useState('');

  // Compute API query parameters based on state
  const queryParams = useMemo(() => {
    const params: AuditQueryParams = {
      limit: pageSize,
      offset: pageIndex * pageSize,
    };
    // Sorting is client-side only; API does not support ordering, so we don't include it.
    if (userIdFilter) {
      const parsed = parseInt(userIdFilter, 10);
      if (!isNaN(parsed)) params.user_id = parsed;
    }
    if (objectTypeFilter) params.object_type = objectTypeFilter;
    if (actionFilter) params.action = actionFilter;
    if (startDateFilter) params.start_date = startDateFilter;
    if (endDateFilter) params.end_date = endDateFilter;
    return params;
  }, [pageSize, pageIndex, userIdFilter, objectTypeFilter, actionFilter, startDateFilter, endDateFilter]);

  // Fetch audit logs
  const {
    data: logs,
    error,
    isLoading,
  } = useQuery<AuditLog[], Error>({
    queryKey: ['auditLogs', queryParams],
    queryFn: () => getAuditLogs(queryParams),
    keepPreviousData: true,
    onError: (err) => {
      addNotification(err.message, 'error');
    },
  });

  // Determine if there is a next page (approximate)
  const hasNextPage = logs ? logs.length === pageSize : false;

  // Define table columns.  We anticipate typical fields but fall back to a JSON
  // string for unknown fields on each row.  Sorting is performed client-side.
  const columns = useMemo<ColumnDef<AuditLog>[]>(() => {
    return [
      {
        accessorFn: (row) => (row as any).id,
        id: 'id',
        header: 'ID',
        cell: (info) => String(info.getValue<number | string>() ?? '—'),
      },
      {
        accessorFn: (row) => (row as any).user_id,
        id: 'user_id',
        header: 'User ID',
        cell: (info) => {
          const v = info.getValue<number | null | undefined>();
          return v ?? '—';
        },
      },
      {
        accessorFn: (row) => (row as any).object_type,
        id: 'object_type',
        header: 'Object Type',
        cell: (info) => String(info.getValue<string>() ?? '—'),
      },
      {
        accessorFn: (row) => (row as any).object_id,
        id: 'object_id',
        header: 'Object ID',
        cell: (info) => {
          const v = info.getValue<number | null | undefined>();
          return v ?? '—';
        },
      },
      {
        accessorFn: (row) => (row as any).action,
        id: 'action',
        header: 'Action',
        cell: (info) => String(info.getValue<string>() ?? '—'),
      },
      {
        accessorFn: (row) => (row as any).timestamp,
        id: 'timestamp',
        header: 'Timestamp',
        cell: (info) => {
          const ts = info.getValue<string>();
          // Format the timestamp as local date/time if valid
          const date = ts ? new Date(ts) : null;
          return date && !isNaN(date.getTime())
            ? date.toLocaleString()
            : ts ?? '—';
        },
      },
      {
        accessorFn: (row) => (row as any).details,
        id: 'details',
        header: 'Details',
        cell: (info) => {
          const value = info.getValue<any>();
          if (!value) return '—';
          // Stringify JSON details with safe fallback and truncate long strings
          let text: string;
          try {
            text = JSON.stringify(value);
          } catch (e) {
            text = String(value);
          }
          return text.length > 60 ? `${text.slice(0, 60)}…` : text;
        },
      },
    ];
  }, []);

  // Configure TanStack table
  const table = useReactTable({
    data: logs ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    // We perform client-side sorting using TanStack when sorting state changes
  });

  /**
   * Export the current filtered logs to CSV.  This fetches up to 500
   * records matching the current filters and downloads a CSV file.
   */
  const handleExportCsv = async () => {
    try {
      // Copy current filters but override limit/offset to fetch up to 500 rows
      const exportParams: AuditQueryParams = { ...queryParams, limit: 500, offset: 0 };
      const rows = await getAuditLogs(exportParams);
      if (!rows || rows.length === 0) {
        addNotification('No audit logs to export for the selected filters.', 'info');
        return;
      }
      // Assemble CSV header from known fields
      const headers = ['id', 'user_id', 'object_type', 'object_id', 'action', 'timestamp', 'details'];
      const csvLines = [headers.join(',')];
      rows.forEach((row) => {
        const values = headers.map((key) => {
          let v: any = (row as any)[key];
          if (v === null || v === undefined) return '';
          // If value is object, stringify
          if (typeof v === 'object') {
            try {
              v = JSON.stringify(v);
            } catch (e) {
              v = String(v);
            }
          }
          // Escape double quotes and wrap in quotes if needed
          const s = String(v).replace(/"/g, '""');
          return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s}"` : s;
        });
        csvLines.push(values.join(','));
      });
      const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'audit_logs.csv';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      addNotification('Audit logs exported successfully.', 'success');
    } catch (err: any) {
      addNotification(err?.message || 'Failed to export audit logs.', 'error');
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Audit Logs</h2>
      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label htmlFor="userId" className="block text-sm font-medium mb-1">
            User ID
          </label>
          <input
            id="userId"
            type="number"
            min="1"
            value={userIdFilter}
            onChange={(e) => {
              setUserIdFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
            placeholder="Any"
          />
        </div>
        <div>
          <label htmlFor="objectType" className="block text-sm font-medium mb-1">
            Object Type
          </label>
          <select
            id="objectType"
            value={objectTypeFilter}
            onChange={(e) => {
              setObjectTypeFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          >
            <option value="">All</option>
            <option value="event">Event</option>
            <option value="booking">Booking</option>
            <option value="payment">Payment</option>
            <option value="review">Review</option>
            <option value="support">Support</option>
            <option value="user">User</option>
            <option value="role">Role</option>
            <option value="message">Message</option>
            <option value="faq">FAQ</option>
            <option value="setting">Setting</option>
            {/* Additional object types may be present; users can leave blank for all */}
          </select>
        </div>
        <div>
          <label htmlFor="action" className="block text-sm font-medium mb-1">
            Action
          </label>
          <select
            id="action"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          >
            <option value="">All</option>
            <option value="create">Create</option>
            <option value="update">Update</option>
            <option value="delete">Delete</option>
          </select>
        </div>
        <div>
          <label htmlFor="startDate" className="block text-sm font-medium mb-1">
            Start Date
          </label>
          <input
            id="startDate"
            type="date"
            value={startDateFilter}
            onChange={(e) => {
              setStartDateFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label htmlFor="endDate" className="block text-sm font-medium mb-1">
            End Date
          </label>
          <input
            id="endDate"
            type="date"
            value={endDateFilter}
            onChange={(e) => {
              setEndDateFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={handleExportCsv}
          className="ml-auto px-4 py-2 text-sm font-medium bg-primary text-white rounded-md disabled:opacity-50"
        >
          Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    scope="col"
                    className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider cursor-pointer select-none"
                    onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getIsSorted() ? (
                      <span className="ml-1">
                        {header.column.getIsSorted() === 'asc' ? '▲' : '▼'}
                      </span>
                    ) : null}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center">
                  Loading audit logs…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-red-600 dark:text-red-400">
                  Failed to load audit logs.
                </td>
              </tr>
            ) : logs && logs.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-gray-500 dark:text-gray-400">
                  No audit logs found.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-2 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600 dark:text-gray-400">
          Page {pageIndex + 1}
        </div>
        <div className="space-x-2">
          <button
            className="px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm disabled:opacity-50"
            onClick={() => setPageIndex((p) => Math.max(p - 1, 0))}
            disabled={pageIndex === 0}
          >
            Previous
          </button>
          <button
            className="px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm disabled:opacity-50"
            onClick={() => setPageIndex((p) => p + 1)}
            disabled={!hasNextPage}
          >
            Next
          </button>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPageIndex(0);
            }}
            className="px-2 py-1 border border-gray-300 dark:border-gray-700 rounded-md text-sm"
          >
            {[10, 25, 50, 100].map((size) => (
              <option key={size} value={size}>
                Show {size}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
};

export default AuditPage;