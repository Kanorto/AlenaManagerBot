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
  Event,
  getEvents,
  createEvent,
  updateEvent,
  deleteEvent,
  duplicateEvent,
} from '../api/events';
import EventFormModal, { EventFormData } from '../components/EventFormModal';
import DuplicateEventModal from '../components/DuplicateEventModal';
import BookingsDrawer from '../components/BookingsDrawer';
import { useNotifications } from '../store/notifications';

/**
 * Events management page displays a paginated, sortable list of
 * events.  Administrators can filter by paid/free status and date
 * range.  Server-side pagination and sorting are driven via query
 * parameters.  Future iterations will add actions for creating,
 * editing, duplicating and deleting events.
 */
const EventsPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  // Modals and drawer state
  const [isCreateModalOpen, setCreateModalOpen] = useState(false);
  const [isEditModalOpen, setEditModalOpen] = useState(false);
  const [isDuplicateModalOpen, setDuplicateModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<Event | null>(null);
  const [duplicateEventId, setDuplicateEventId] = useState<Event | null>(null);
  const [drawerEvent, setDrawerEvent] = useState<Event | null>(null);
  // Pagination and sorting state
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sorting, setSorting] = useState<SortingState>([]);
  // Filter state
  const [isPaidFilter, setIsPaidFilter] = useState<string>('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Derive API parameters from state
  const queryParams = useMemo(() => {
    const params: any = {
      limit: pageSize,
      offset: pageIndex * pageSize,
    };
    if (sorting[0]) {
      params.sort_by = sorting[0].id;
      params.order = sorting[0].desc ? 'desc' : 'asc';
    }
    if (isPaidFilter === 'true') params.is_paid = true;
    if (isPaidFilter === 'false') params.is_paid = false;
    if (startDate) params.date_from = startDate;
    if (endDate) params.date_to = endDate;
    return params;
  }, [pageSize, pageIndex, sorting, isPaidFilter, startDate, endDate]);

  // Fetch events from API
  const {
    data: events,
    error,
    isLoading,
  } = useQuery<Event[], Error>({
    queryKey: ['events', queryParams],
    queryFn: () => getEvents(queryParams),
    keepPreviousData: true,
    onError: (err) => addNotification(err.message, 'error'),
  });

  // Create event mutation
  const createMutation = useMutation((data: EventFormData) => createEvent(data), {
    onSuccess: () => {
      addNotification('Event created', 'success');
      queryClient.invalidateQueries(['events']);
    },
    onError: (err: Error) => addNotification(err.message, 'error'),
  });
  // Update event mutation
  const updateMutation = useMutation(
    (variables: { id: number; data: EventFormData }) => updateEvent(variables.id, variables.data),
    {
      onSuccess: () => {
        addNotification('Event updated', 'success');
        queryClient.invalidateQueries(['events']);
      },
      onError: (err: Error) => addNotification(err.message, 'error'),
    },
  );
  // Delete event mutation
  const deleteMutation = useMutation((id: number) => deleteEvent(id), {
    onSuccess: () => {
      addNotification('Event deleted', 'success');
      queryClient.invalidateQueries(['events']);
    },
    onError: (err: Error) => addNotification(err.message, 'error'),
  });
  // Duplicate event mutation
  const duplicateMutation = useMutation(
    (variables: { id: number; start_time: string }) => duplicateEvent(variables.id, variables.start_time),
    {
      onSuccess: () => {
        addNotification('Event duplicated', 'success');
        queryClient.invalidateQueries(['events']);
      },
      onError: (err: Error) => addNotification(err.message, 'error'),
    },
  );

  // Define table columns
  const columns = useMemo<ColumnDef<Event>[]>(() => [
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
      accessorKey: 'start_time',
      header: 'Start Time',
      cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
    },
    {
      accessorKey: 'duration_minutes',
      header: 'Duration (min)',
      cell: (info) => info.getValue<number>(),
    },
    {
      accessorKey: 'max_participants',
      header: 'Max Participants',
      cell: (info) => info.getValue<number>(),
    },
    {
      accessorKey: 'is_paid',
      header: 'Paid',
      cell: (info) => (info.getValue<boolean>() ? 'Yes' : 'No'),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const evt = row.original as Event;
        return (
          <div className="flex gap-2">
            <button
              onClick={() => setDrawerEvent(evt)}
              className="px-2 py-1 rounded-md bg-indigo-600 text-white text-xs"
            >
              View
            </button>
            <button
              onClick={() => {
                setEditingEvent(evt);
                setEditModalOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs"
            >
              Edit
            </button>
            <button
              onClick={() => {
                setDuplicateEventId(evt);
                setDuplicateModalOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-purple-600 text-white text-xs"
            >
              Duplicate
            </button>
            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this event?')) {
                  deleteMutation.mutate(evt.id);
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
  ], []);

  // Configure the table instance
  const table = useReactTable({
    data: events ?? [],
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: true,
    manualPagination: true,
  });

  // Calculate if there's a next page (we don't have total count so we guess)
  const hasNextPage = events ? events.length === pageSize : false;

  // Handlers for creating/editing events
  const handleCreate = async (data: EventFormData) => {
    await createMutation.mutateAsync(data);
  };
  const handleEdit = async (data: EventFormData) => {
    if (editingEvent) {
      await updateMutation.mutateAsync({ id: editingEvent.id, data });
    }
  };
  const handleDuplicate = async (start_time: string) => {
    if (duplicateEventId) {
      await duplicateMutation.mutateAsync({ id: duplicateEventId.id, start_time });
      setDuplicateEventId(null);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Events Management</h2>

      {/* Create Event button */}
      <div>
        <button
          onClick={() => setCreateModalOpen(true)}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm"
        >
          Create Event
        </button>
      </div>
      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label htmlFor="isPaid" className="block text-sm font-medium mb-1">
            Paid Status
          </label>
          <select
            id="isPaid"
            value={isPaidFilter}
            onChange={(e) => setIsPaidFilter(e.target.value)}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          >
            <option value="all">All</option>
            <option value="true">Paid</option>
            <option value="false">Free</option>
          </select>
        </div>
        <div>
          <label htmlFor="startDate" className="block text-sm font-medium mb-1">
            Start Date From
          </label>
          <input
            id="startDate"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
        <div>
          <label htmlFor="endDate" className="block text-sm font-medium mb-1">
            Start Date To
          </label>
          <input
            id="endDate"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider cursor-pointer select-none"
                      onClick={header.column.getCanSort() ? header.column.getToggleSortingHandler() : undefined}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                      {/* Sort indicator */}
                      {header.column.getIsSorted() ? (
                        <span className="ml-1">
                          {header.column.getIsSorted() === 'asc' ? '▲' : '▼'}
                        </span>
                      ) : null}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center">
                  Loading events…
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-red-600 dark:text-red-400">
                  Failed to load events.
                </td>
              </tr>
            ) : events && events.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-gray-500 dark:text-gray-400">
                  No events found.
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

      {/* Pagination controls */}
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

      {/* Create Modal */}
      <EventFormModal
        isOpen={isCreateModalOpen}
        onClose={() => setCreateModalOpen(false)}
        initialData={undefined}
        title="Create Event"
        onSubmit={handleCreate}
      />
      {/* Edit Modal */}
      <EventFormModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setEditModalOpen(false);
          setEditingEvent(null);
        }}
        initialData={editingEvent ?? undefined}
        title="Edit Event"
        onSubmit={handleEdit}
      />
      {/* Duplicate Modal */}
      <DuplicateEventModal
        isOpen={isDuplicateModalOpen}
        onClose={() => {
          setDuplicateModalOpen(false);
          setDuplicateEventId(null);
        }}
        title="Duplicate Event"
        onSubmit={handleDuplicate}
      />
      {/* Bookings Drawer */}
      {drawerEvent && (
        <BookingsDrawer
          eventId={drawerEvent.id}
          eventTitle={drawerEvent.title}
          isOpen={!!drawerEvent}
          onClose={() => setDrawerEvent(null)}
        />
      )}
    </div>
  );
};

export default EventsPage;