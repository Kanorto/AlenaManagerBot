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
  SupportTicket,
  SupportMessage,
  getTickets,
  deleteTicket,
  getTicketWithMessages,
  replyToTicket,
  updateTicketStatus,
  createTicket,
} from '../api/support';
import { useNotifications } from '../store/notifications';

/**
 * Schema for creating or replying to a support ticket.  Subject is
 * required when creating a new ticket.  The reply form uses only the
 * content field.
 */
const ticketCreateSchema = z.object({
  subject: z.string().min(1, 'Subject is required'),
  content: z.string().min(1, 'Content is required'),
});
type TicketCreateData = z.infer<typeof ticketCreateSchema>;

const replySchema = z.object({
  content: z.string().min(1, 'Message cannot be empty'),
});
type ReplyData = z.infer<typeof replySchema>;

/**
 * Support page lists open support tickets and allows administrators
 * to view details, reply, update status or delete tickets.  Users may
 * also create new tickets.  Messages are displayed in a modal with a
 * simple thread view.
 */
const SupportPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  // Filters and pagination
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  // Modal state
  const [isViewOpen, setViewOpen] = useState(false);
  const [activeTicketId, setActiveTicketId] = useState<number | null>(null);
  const [isCreateOpen, setCreateOpen] = useState(false);

  // Fetch tickets
  const {
    data: tickets,
    isLoading: ticketsLoading,
  } = useQuery<SupportTicket[], Error>(
    ['tickets', { statusFilter, pageIndex, pageSize, sorting }],
    () =>
      getTickets({
        status: statusFilter ?? undefined,
        limit: pageSize,
        offset: pageIndex * pageSize,
        sort_by: sorting[0]?.id ?? undefined,
        order: sorting[0]?.desc ? 'desc' : 'asc',
      }),
    {
      keepPreviousData: true,
      onError: (err) => addNotification(err.message, 'error'),
    },
  );

  // Mutation definitions
  const deleteMutation = useMutation((id: number) => deleteTicket(id), {
    onSuccess: () => {
      addNotification('Ticket deleted', 'success');
      queryClient.invalidateQueries(['tickets']);
    },
    onError: (err) => addNotification((err as Error).message, 'error'),
  });

  const replyMutation = useMutation(
    (variables: { id: number; data: ReplyData }) => replyToTicket(variables.id, { content: variables.data.content }),
    {
      onSuccess: () => {
        addNotification('Reply sent', 'success');
        // Refetch messages for the active ticket
        if (activeTicketId) {
          queryClient.invalidateQueries(['ticket', activeTicketId]);
        }
      },
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  const statusMutation = useMutation(
    (variables: { id: number; status: string }) => updateTicketStatus(variables.id, variables.status),
    {
      onSuccess: () => {
        addNotification('Status updated', 'success');
        queryClient.invalidateQueries(['tickets']);
        if (activeTicketId) queryClient.invalidateQueries(['ticket', activeTicketId]);
      },
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  const createMutation = useMutation((data: TicketCreateData) => createTicket(data), {
    onSuccess: () => {
      addNotification('Ticket created', 'success');
      queryClient.invalidateQueries(['tickets']);
    },
    onError: (err) => addNotification((err as Error).message, 'error'),
  });

  // Fetch active ticket with messages when view modal open
  const {
    data: ticketWithMessages,
    isLoading: ticketLoading,
  } = useQuery<{ ticket: SupportTicket; messages: SupportMessage[] }, Error>(
    ['ticket', activeTicketId],
    () => {
      if (activeTicketId == null) return Promise.reject('No ticket');
      return getTicketWithMessages(activeTicketId);
    },
    {
      enabled: isViewOpen && activeTicketId != null,
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  // Form hooks for reply and create
  const {
    register: registerReply,
    handleSubmit: handleReplySubmit,
    reset: resetReply,
    formState: { errors: replyErrors },
  } = useForm<ReplyData>({ resolver: zodResolver(replySchema) });

  const {
    register: registerCreate,
    handleSubmit: handleCreateSubmit,
    reset: resetCreate,
    formState: { errors: createErrors },
  } = useForm<TicketCreateData>({ resolver: zodResolver(ticketCreateSchema) });

  // Table columns
  const columns = useMemo<ColumnDef<SupportTicket>[]>(() => [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: (info) => info.getValue<number>(),
    },
    {
      accessorKey: 'subject',
      header: 'Subject',
      cell: (info) => info.getValue<string>() || '—',
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: (info) => info.getValue<string>(),
    },
    {
      accessorKey: 'created_at',
      header: 'Created',
      cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      accessorKey: 'updated_at',
      header: 'Updated',
      cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const ticket = row.original;
        return (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setActiveTicketId(ticket.id);
                setViewOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-blue-600 text-white text-xs"
            >
              View
            </button>
            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this ticket?')) {
                  deleteMutation.mutate(ticket.id);
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
  ], [deleteMutation]);

  const table = useReactTable({
    data: tickets ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    manualSorting: true,
  });

  const hasNextPage = (tickets?.length ?? 0) === pageSize;

  // Submit handlers
  const onReplySubmit = async (data: ReplyData) => {
    if (!activeTicketId) return;
    await replyMutation.mutateAsync({ id: activeTicketId, data });
    resetReply();
  };
  const onCreateSubmit = async (data: TicketCreateData) => {
    await createMutation.mutateAsync(data);
    resetCreate();
    setCreateOpen(false);
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Support Tickets</h2>
      {/* Filters and actions */}
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Status
          </label>
          <select
            value={statusFilter ?? ''}
            onChange={(e) => {
              const val = e.target.value;
              setStatusFilter(val ? val : null);
              setPageIndex(0);
            }}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
          >
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="px-3 py-2 bg-blue-600 text-white rounded-md text-sm"
        >
          New Ticket
        </button>
      </div>
      {/* Tickets table */}
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
            {ticketsLoading ? (
              <tr>
                <td colSpan={columns.length} className="p-4 text-center">
                  Loading…
                </td>
              </tr>
            ) : tickets && tickets.length > 0 ? (
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
                  No tickets found.
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
      {/* View Ticket Modal */}
      {isViewOpen && activeTicketId != null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-3xl w-full p-6 flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold dark:text-gray-100">Ticket #{activeTicketId}</h3>
              <button
                onClick={() => {
                  setViewOpen(false);
                  setActiveTicketId(null);
                  resetReply();
                }}
                className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              >
                ✕
              </button>
            </div>
            {ticketLoading ? (
              <p className="text-center">Loading ticket…</p>
            ) : ticketWithMessages ? (
              <div className="flex flex-col space-y-4 flex-1 overflow-hidden">
                <div>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    <strong>Subject:</strong> {ticketWithMessages.ticket.subject || '—'}
                  </p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    <strong>Status:</strong> {ticketWithMessages.ticket.status}
                  </p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    <strong>Created:</strong> {new Date(ticketWithMessages.ticket.created_at).toLocaleString()}
                  </p>
                  <p className="text-sm text-gray-700 dark:text-gray-300">
                    <strong>Updated:</strong> {new Date(ticketWithMessages.ticket.updated_at).toLocaleString()}
                  </p>
                </div>
                {/* Status update */}
                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Change status:</label>
                  <select
                    value={ticketWithMessages.ticket.status}
                    onChange={(e) => {
                      const newStatus = e.target.value;
                      statusMutation.mutate({ id: ticketWithMessages.ticket.id, status: newStatus });
                    }}
                    className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  >
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>
                {/* Message thread */}
                <div className="flex-1 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-md p-2">
                  {ticketWithMessages.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`mb-3 p-2 rounded-md ${
                        msg.sender_role === 'admin' ? 'bg-blue-100 dark:bg-blue-900' : 'bg-gray-100 dark:bg-gray-800'
                      }`}
                    >
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {msg.sender_role} • {new Date(msg.created_at).toLocaleString()}
                      </div>
                      <div className="text-sm text-gray-700 dark:text-gray-200 whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    </div>
                  ))}
                </div>
                {/* Reply form */}
                <form onSubmit={handleReplySubmit(onReplySubmit)} className="space-y-2 pt-2">
                  <textarea
                    {...registerReply('content')}
                    className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                    rows={3}
                    placeholder="Type your reply…"
                  />
                  {replyErrors.content && <p className="text-sm text-red-600">{replyErrors.content.message}</p>}
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
                    >
                      Send Reply
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <p className="text-center text-gray-500 dark:text-gray-400">Ticket not found.</p>
            )}
          </div>
        </div>
      )}
      {/* Create Ticket Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">New Support Ticket</h3>
            <form onSubmit={handleCreateSubmit(onCreateSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Subject
                </label>
                <input
                  type="text"
                  {...registerCreate('subject')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {createErrors.subject && <p className="text-sm text-red-600 mt-1">{createErrors.subject.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Content
                </label>
                <textarea
                  {...registerCreate('content')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  rows={4}
                />
                {createErrors.content && <p className="text-sm text-red-600 mt-1">{createErrors.content.message}</p>}
              </div>
              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    resetCreate();
                    setCreateOpen(false);
                  }}
                  className="px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SupportPage;