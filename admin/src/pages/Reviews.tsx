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
import { Review, getReviews, deleteReview, moderateReview } from '../api/reviews';
import { useNotifications } from '../store/notifications';

/**
 * Reviews page lists user feedback for events and allows administrators to
 * approve, reject or delete reviews.  Filters by approval status are
 * provided.  Pagination and sorting parameters are passed to the API.
 */
const ReviewsPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  // Filters and pagination
  const [approvedFilter, setApprovedFilter] = useState<string>('all');
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  // Derive API parameters
  const approvedParam = useMemo(() => {
    if (approvedFilter === 'approved') return true;
    if (approvedFilter === 'pending') return false;
    return undefined;
  }, [approvedFilter]);
  const sort_by = sorting.length > 0 ? sorting[0].id : undefined;
  const order = sorting.length > 0 && sorting[0].desc ? 'desc' : 'asc';

  // Fetch reviews
  const {
    data: reviews,
    isLoading,
  } = useQuery<Review[], Error>(
    ['reviews', { approvedParam, pageIndex, pageSize, sort_by, order }],
    () =>
      getReviews({
        approved: approvedParam ?? undefined,
        limit: pageSize,
        offset: pageIndex * pageSize,
        sort_by: sort_by ?? undefined,
        order: sort_by ? order : undefined,
      }),
    {
      keepPreviousData: true,
      onError: (err) => addNotification(err.message, 'error'),
    },
  );

  // Mutations
  const deleteMutation = useMutation((id: number) => deleteReview(id), {
    onSuccess: () => {
      addNotification('Review deleted', 'success');
      queryClient.invalidateQueries(['reviews']);
    },
    onError: (err) => addNotification((err as Error).message, 'error'),
  });
  const moderateMutation = useMutation(
    (variables: { id: number; approved: boolean }) => moderateReview(variables.id, variables.approved),
    {
      onSuccess: () => {
        addNotification('Review moderated', 'success');
        queryClient.invalidateQueries(['reviews']);
      },
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  // Table columns
  const columns = useMemo<ColumnDef<Review>[]>(() => [
    { accessorKey: 'id', header: 'ID', cell: (info) => info.getValue<number>() },
    { accessorKey: 'user_id', header: 'User', cell: (info) => info.getValue<number>() },
    { accessorKey: 'event_id', header: 'Event', cell: (info) => info.getValue<number>() },
    { accessorKey: 'rating', header: 'Rating', cell: (info) => info.getValue<number>() },
    { accessorKey: 'comment', header: 'Comment', cell: (info) => info.getValue<string | null>() || '—' },
    {
      accessorKey: 'approved',
      header: 'Approved',
      cell: (info) => (info.getValue<boolean>() ? 'Yes' : 'No'),
    },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const review = row.original;
        return (
          <div className="flex gap-2">
            <button
              onClick={() => moderateMutation.mutate({ id: review.id, approved: true })}
              disabled={review.approved}
              className="px-2 py-1 rounded-md bg-green-600 text-white text-xs disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => moderateMutation.mutate({ id: review.id, approved: false })}
              disabled={!review.approved}
              className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs disabled:opacity-50"
            >
              Reject
            </button>
            <button
              onClick={() => {
                if (confirm('Delete this review?')) deleteMutation.mutate(review.id);
              }}
              className="px-2 py-1 rounded-md bg-red-600 text-white text-xs"
            >
              Delete
            </button>
          </div>
        );
      },
    },
  ], [deleteMutation, moderateMutation]);

  const table = useReactTable({
    data: reviews ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    manualSorting: true,
  });
  const hasNextPage = (reviews?.length ?? 0) === pageSize;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Reviews</h2>
      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Approved</label>
          <select
            value={approvedFilter}
            onChange={(e) => {
              setApprovedFilter(e.target.value);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
          >
            <option value="all">All</option>
            <option value="approved">Approved</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>
      {/* Reviews table */}
      <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    colSpan={header.colSpan}
                    className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300"
                  >
                    {header.isPlaceholder ? null : (
                      <div
                        className={
                          header.column.getCanSort()
                            ? 'cursor-pointer select-none flex items-center'
                            : undefined
                        }
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {{ asc: ' ▲', desc: ' ▼' }[header.column.getIsSorted() as string] ?? null}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-900 dark:divide-gray-700">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="p-4 text-center">Loading…</td>
              </tr>
            ) : reviews && reviews.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="p-4 text-center text-gray-500 dark:text-gray-400">
                  No reviews found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* Pagination */}
      <div className="flex justify-between items-center pt-2">
        <div className="text-sm">Page {pageIndex + 1}</div>
        <div className="space-x-2">
          <button
            onClick={() => setPageIndex((p) => Math.max(p - 1, 0))}
            disabled={pageIndex === 0}
            className="px-2 py-1 text-sm border rounded-md disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => setPageIndex((p) => p + 1)}
            disabled={!hasNextPage}
            className="px-2 py-1 text-sm border rounded-md disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default ReviewsPage;