import React, { useMemo, useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ColumnDef,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
  flexRender,
} from '@tanstack/react-table';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Mailing,
  getMailings,
  createMailing,
  updateMailing,
  deleteMailing,
  sendMailing,
  getMailingLogs,
  MailingLog,
} from '../api/mailings';
import { useNotifications } from '../store/notifications';

/**
 * Form schema for creating or editing a mailing.  Users must provide
 * a title and content.  Optional fields include filters (JSON
 * string), scheduled_at (datetime-local string) and messengers (comma
 * separated).  Validation is handled by zod and react-hook-form.
 */
const mailingSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  content: z.string().min(1, 'Content is required'),
  filters: z.string().optional().nullable(),
  scheduled_at: z.string().optional().nullable(),
  messengers: z.string().optional().nullable(),
});
type MailingFormData = z.infer<typeof mailingSchema>;

/**
 * The Mailings page displays a paginated list of mailing campaigns and
 * allows administrators to create, edit, delete and send them.  A
 * secondary modal shows delivery logs for a mailing.  Pagination and
 * sorting parameters are passed to the backend where supported.
 */
const MailingsPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  // Table sorting and pagination state.  sortBy/order map to API params.
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  // Modal state for create/edit forms
  const [isCreateOpen, setCreateOpen] = useState(false);
  const [isEditOpen, setEditOpen] = useState(false);
  const [editingMailing, setEditingMailing] = useState<Mailing | null>(null);

  // State for viewing logs
  const [isLogsOpen, setLogsOpen] = useState(false);
  const [logsMailingId, setLogsMailingId] = useState<number | null>(null);
  const [logsPageIndex, setLogsPageIndex] = useState(0);
  const logsPageSize = 50;

  // Compute API sort parameters from tanstack sorting state.  We only
  // support sorting by created_at or scheduled_at; fall back to
  // undefined when unsorted.
  const sort_by = useMemo(() => {
    if (sorting.length === 0) return undefined;
    const colId = sorting[0].id;
    return colId === 'scheduled_at' || colId === 'created_at' ? colId : undefined;
  }, [sorting]);
  const order = useMemo(() => {
    if (sorting.length === 0) return undefined;
    return sorting[0].desc ? 'desc' : 'asc';
  }, [sorting]);

  // Fetch paginated mailings from the API
  const {
    data: mailings,
    isLoading,
    error,
  } = useQuery<Mailing[], Error>(
    ['mailings', { pageIndex, pageSize, sort_by, order }],
    () =>
      getMailings({
        limit: pageSize,
        offset: pageIndex * pageSize,
        sort_by: sort_by ?? undefined,
        order: order ?? undefined,
      }),
    {
      keepPreviousData: true,
      onError: (err) => addNotification(err.message, 'error'),
    },
  );

  // Mutations for create, update, delete and send operations
  const createMutation = useMutation((data: MailingFormData) => {
    // Transform form data to API payload
    const payload: any = {
      title: data.title,
      content: data.content,
    };
    if (data.filters) {
      try {
        payload.filters = JSON.parse(data.filters);
      } catch {
        payload.filters = null;
      }
    }
    if (data.scheduled_at) {
      payload.scheduled_at = new Date(data.scheduled_at).toISOString();
    }
    if (data.messengers) {
      const arr = data.messengers
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      payload.messengers = arr.length > 0 ? arr : null;
    }
    return createMailing(payload);
  }, {
    onSuccess: () => {
      addNotification('Mailing created', 'success');
      queryClient.invalidateQueries(['mailings']);
    },
    onError: (err: any) => addNotification(err.message, 'error'),
  });

  const updateMutation = useMutation(
    (variables: { id: number; data: MailingFormData }) => {
      const { id, data } = variables;
      const payload: any = {};
      if (data.title !== undefined) payload.title = data.title;
      if (data.content !== undefined) payload.content = data.content;
      if (data.filters !== undefined) {
        if (data.filters) {
          try {
            payload.filters = JSON.parse(data.filters);
          } catch {
            payload.filters = null;
          }
        } else {
          payload.filters = null;
        }
      }
      if (data.scheduled_at !== undefined) {
        payload.scheduled_at = data.scheduled_at
          ? new Date(data.scheduled_at).toISOString()
          : null;
      }
      if (data.messengers !== undefined) {
        if (data.messengers) {
          const arr = data.messengers
            .split(',')
            .map((s) => s.trim())
            .filter((s) => s.length > 0);
          payload.messengers = arr.length > 0 ? arr : null;
        } else {
          payload.messengers = null;
        }
      }
      return updateMailing(id, payload);
    },
    {
      onSuccess: () => {
        addNotification('Mailing updated', 'success');
        queryClient.invalidateQueries(['mailings']);
      },
      onError: (err: any) => addNotification(err.message, 'error'),
    },
  );

  const deleteMutation = useMutation((id: number) => deleteMailing(id), {
    onSuccess: () => {
      addNotification('Mailing deleted', 'success');
      queryClient.invalidateQueries(['mailings']);
    },
    onError: (err: any) => addNotification(err.message, 'error'),
  });

  const sendMutation = useMutation((id: number) => sendMailing(id), {
    onSuccess: (count: number) => {
      addNotification(`Mailing sent to ${count} recipient(s)`, 'success');
      queryClient.invalidateQueries(['mailings']);
    },
    onError: (err: any) => addNotification(err.message, 'error'),
  });

  // Logs query; only run when logs modal open
  const {
    data: logs,
    isLoading: logsLoading,
  } = useQuery<MailingLog[], Error>(
    ['mailingLogs', { mailingId: logsMailingId, logsPageIndex }],
    () => {
      if (!logsMailingId) return Promise.resolve([]);
      return getMailingLogs(logsMailingId, {
        limit: logsPageSize,
        offset: logsPageIndex * logsPageSize,
      });
    },
    {
      enabled: isLogsOpen && logsMailingId != null,
      keepPreviousData: true,
      onError: (err) => addNotification(err.message, 'error'),
    },
  );

  // Form handling for create/edit
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<MailingFormData>({
    resolver: zodResolver(mailingSchema),
    defaultValues: {
      title: '',
      content: '',
      filters: '',
      scheduled_at: '',
      messengers: '',
    },
  });

  // Populate form when editing
  useEffect(() => {
    if (isEditOpen && editingMailing) {
      setValue('title', editingMailing.title);
      setValue('content', editingMailing.content);
      setValue('filters', editingMailing.filters ? JSON.stringify(editingMailing.filters, null, 2) : '');
      setValue('scheduled_at', editingMailing.scheduled_at ? new Date(editingMailing.scheduled_at).toISOString().slice(0, 16) : '');
      setValue('messengers', editingMailing.messengers ? editingMailing.messengers.join(', ') : '');
    } else {
      reset();
    }
  }, [isEditOpen, editingMailing, reset, setValue]);

  // Internal submit handler
  const onSubmit = async (data: MailingFormData) => {
    if (isEditOpen && editingMailing) {
      await updateMutation.mutateAsync({ id: editingMailing.id, data });
    } else {
      await createMutation.mutateAsync(data);
    }
    setCreateOpen(false);
    setEditOpen(false);
  };

  // Define table columns
  const columns = useMemo<ColumnDef<Mailing>[]>(() => [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: (info) => info.getValue<number>(),
    },
    {
      accessorKey: 'title',
      header: 'Title',
      cell: (info) => info.getValue<string>(),
    },
    {
      accessorKey: 'created_at',
      header: 'Created At',
      cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      accessorKey: 'scheduled_at',
      header: 'Scheduled At',
      cell: (info) => {
        const val = info.getValue<string | null>();
        return val ? new Date(val).toLocaleString() : '—';
      },
    },
    {
      accessorKey: 'messengers',
      header: 'Messengers',
      cell: (info) => {
        const arr = info.getValue<string[] | null>();
        return arr && arr.length > 0 ? arr.join(', ') : '—';
      },
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const mailing = row.original;
        return (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setEditingMailing(mailing);
                setEditOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs"
            >
              Edit
            </button>
            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this mailing?')) {
                  deleteMutation.mutate(mailing.id);
                }
              }}
              className="px-2 py-1 rounded-md bg-red-600 text-white text-xs"
            >
              Delete
            </button>
            <button
              onClick={() => {
                if (confirm('Send this mailing now?')) {
                  sendMutation.mutate(mailing.id);
                }
              }}
              className="px-2 py-1 rounded-md bg-green-700 text-white text-xs"
            >
              Send
            </button>
            <button
              onClick={() => {
                setLogsMailingId(mailing.id);
                setLogsPageIndex(0);
                setLogsOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-blue-700 text-white text-xs"
            >
              Logs
            </button>
          </div>
        );
      },
    },
  ], [deleteMutation, sendMutation]);

  const table = useReactTable({
    data: mailings ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    manualSorting: true,
  });

  const hasNextPage = (mailings?.length ?? 0) === pageSize; // naive

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Mailings</h2>
      <div className="flex justify-between items-center">
        <button
          onClick={() => {
            setEditingMailing(null);
            setCreateOpen(true);
          }}
          className="px-3 py-2 bg-blue-600 text-white rounded-md text-sm"
        >
          New Mailing
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
                <td colSpan={columns.length} className="p-4 text-center">
                  Loading...
                </td>
              </tr>
            ) : mailings && mailings.length > 0 ? (
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
                  No mailings found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* Pagination controls */}
      <div className="flex justify-between items-center pt-2">
        <div className="text-sm">
          Page {pageIndex + 1}
        </div>
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

      {/* Create/Edit Modal */}
      {(isCreateOpen || isEditOpen) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-lg w-full p-6">
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">
              {isEditOpen ? 'Edit Mailing' : 'New Mailing'}
            </h3>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Title
                </label>
                <input
                  type="text"
                  {...register('title')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.title && <p className="text-sm text-red-600 mt-1">{errors.title.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Content
                </label>
                <textarea
                  {...register('content')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  rows={4}
                />
                {errors.content && <p className="text-sm text-red-600 mt-1">{errors.content.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Filters (JSON)
                </label>
                <textarea
                  {...register('filters')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  rows={3}
                  placeholder='{"event_id": 1, "is_paid": true}'
                />
                {errors.filters && <p className="text-sm text-red-600 mt-1">{errors.filters.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Scheduled At
                </label>
                <input
                  type="datetime-local"
                  {...register('scheduled_at')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.scheduled_at && <p className="text-sm text-red-600 mt-1">{errors.scheduled_at.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Messengers (comma separated)
                </label>
                <input
                  type="text"
                  {...register('messengers')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  placeholder="telegram,vk"
                />
                {errors.messengers && <p className="text-sm text-red-600 mt-1">{errors.messengers.message}</p>}
              </div>
              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    reset();
                    setCreateOpen(false);
                    setEditOpen(false);
                  }}
                  className="px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
                >
                  {isEditOpen ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {isLogsOpen && logsMailingId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-2xl w-full p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold dark:text-gray-100">Mailing Logs (ID {logsMailingId})</h3>
              <button
                onClick={() => {
                  setLogsOpen(false);
                }}
                className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                ✕
              </button>
            </div>
            {logsLoading ? (
              <p className="text-center">Loading logs…</p>
            ) : logs && logs.length > 0 ? (
              <div className="max-h-96 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-md">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">ID</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">User</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Status</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Sent At</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Error</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-900 dark:divide-gray-700">
                    {logs.map((log) => (
                      <tr key={log.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                        <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{log.id}</td>
                        <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{log.user_id}</td>
                        <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{log.status}</td>
                        <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{new Date(log.sent_at).toLocaleString()}</td>
                        <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{log.error_message ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-center text-gray-500 dark:text-gray-400">No logs found.</p>
            )}
            {/* Logs pagination */}
            <div className="flex justify-between items-center mt-4">
              <div className="text-sm">Page {logsPageIndex + 1}</div>
              <div className="space-x-2">
                <button
                  onClick={() => setLogsPageIndex((p) => Math.max(p - 1, 0))}
                  disabled={logsPageIndex === 0}
                  className="px-2 py-1 text-sm border rounded-md disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setLogsPageIndex((p) => p + 1)}
                  disabled={logs && logs.length < logsPageSize}
                  className="px-2 py-1 text-sm border rounded-md disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MailingsPage;