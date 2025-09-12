import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ColumnDef,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  flexRender,
} from '@tanstack/react-table';
import {
  Payment,
  getPayments,
  confirmPayment,
  deletePayment,
  PaymentsQueryParams,
} from '../api/payments';
import { useNotifications } from '../store/notifications';

/**
 * Payments management page.  Displays a paginated, sortable list of
 * payments.  Administrators can filter by provider and status,
 * confirm pending payments and delete payments.  Server-side
 * pagination and sorting are driven via query parameters.
 */
const PaymentsPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  // Pagination and sorting state
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([]);

  // Filter state
  const [providerFilter, setProviderFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [eventIdFilter, setEventIdFilter] = useState('');

  // Derive API parameters from state
  const queryParams = useMemo(() => {
    const params: PaymentsQueryParams = {
      limit: pageSize,
      offset: pageIndex * pageSize,
    };
    if (sorting[0]) {
      params.sort_by = sorting[0].id;
      params.order = sorting[0].desc ? 'desc' : 'asc';
    }
    if (providerFilter) params.provider = providerFilter;
    if (statusFilter) params.status = statusFilter;
    if (eventIdFilter) params.event_id = Number(eventIdFilter);
    return params;
  }, [pageSize, pageIndex, sorting, providerFilter, statusFilter, eventIdFilter]);

  // Fetch payments from API
  const {
    data: payments,
    error,
    isLoading,
  } = useQuery<Payment[], Error>({
    queryKey: ['payments', queryParams],
    queryFn: () => getPayments(queryParams),
    keepPreviousData: true,
    onError: (err) => addNotification(err.message, 'error'),
  });

  // Confirm mutation
  const confirmMutation = useMutation((id: number) => confirmPayment(id), {
    onSuccess: () => {
      addNotification('Payment confirmed', 'success');
      queryClient.invalidateQueries(['payments']);
    },
    onError: (err: Error) => addNotification(err.message, 'error'),
  });

  // Delete mutation
  const deleteMutation = useMutation((id: number) => deletePayment(id), {
    onSuccess: () => {
      addNotification('Payment deleted', 'success');
      queryClient.invalidateQueries(['payments']);
    },
    onError: (err: Error) => addNotification(err.message, 'error'),
  });

  // Determine if there is a next page (approximate)
  const hasNextPage = payments ? payments.length === pageSize : false;

  // Table columns
  const columns = useMemo<ColumnDef<Payment>[]>(() => [
    { accessorKey: 'id', header: 'ID', cell: (info) => info.getValue<number>() },
    { accessorKey: 'user_id', header: 'User ID', cell: (info) => info.getValue<number>() ?? '—' },
    { accessorKey: 'event_id', header: 'Event ID', cell: (info) => info.getValue<number>() ?? '—' },
    { accessorKey: 'amount', header: 'Amount', cell: (info) => info.getValue<number>().toFixed(2) },
    { accessorKey: 'currency', header: 'Currency', cell: (info) => info.getValue<string>() },
    { accessorKey: 'provider', header: 'Provider', cell: (info) => info.getValue<string>() ?? '—' },
    { accessorKey: 'status', header: 'Status', cell: (info) => info.getValue<string>() ?? '—' },
    {
      accessorKey: 'created_at',
      header: 'Created At',
      cell: (info) => {
        const dt = info.getValue<string>();
        return new Date(dt).toLocaleString();
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const payment = row.original as Payment;
        const isPending = payment.status === 'pending' || payment.status === null || payment.status === undefined;
        return (
          <div className="flex gap-2">
            {isPending && (
              <button
                onClick={() => confirmMutation.mutate(payment.id)}
                className="px-2 py-1 rounded-md bg-green-600 text-white text-xs"
              >
                Confirm
              </button>
            )}
            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this payment?')) {
                  deleteMutation.mutate(payment.id);
                }
              }}
              className="px-2 py-1 rounded-md bg-red-600 text-white text-xs"
            >
              Delete
            </button>
          </div>
        );
      },
    },
  ], [confirmMutation, deleteMutation]);

  // Configure table
  const table = useReactTable({
    data: payments ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: true,
    manualPagination: true,
  });

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Payments</h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label htmlFor="provider" className="block text-sm font-medium mb-1">
            Provider
          </label>
          <select
            id="provider"
            value={providerFilter}
            onChange={(e) => {
              setProviderFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          >
            <option value="">All</option>
            <option value="yookassa">YooKassa</option>
            <option value="support">Support</option>
            <option value="cash">Cash</option>
          </select>
        </div>
        <div>
          <label htmlFor="status" className="block text-sm font-medium mb-1">
            Status
          </label>
          <select
            id="status"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="refunded">Refunded</option>
          </select>
        </div>
        <div>
          <label htmlFor="eventId" className="block text-sm font-medium mb-1">
            Event ID
          </label>
          <input
            id="eventId"
            type="number"
            min="1"
            value={eventIdFilter}
            onChange={(e) => {
              setEventIdFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
            placeholder="Any"
          />
        </div>
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
                  Loading payments…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-red-600 dark:text-red-400">
                  Failed to load payments.
                </td>
              </tr>
            ) : payments && payments.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-gray-500 dark:text-gray-400">
                  No payments found.
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
            {[10, 25, 50].map((size) => (
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

export default PaymentsPage;