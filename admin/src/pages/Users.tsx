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
import { User, getUsers, createUser, updateUser, deleteUser } from '../api/users';
import { Role, getRoles } from '../api/roles';
import UserFormModal, { UserFormData } from '../components/UserFormModal';
import { useNotifications } from '../store/notifications';

/**
 * Users & Roles management page.  Displays a list of users and
 * allows creation, editing, deletion and role assignment.  Users are
 * fetched from the backend and displayed in a sortable table.  A
 * modal form is used for create and edit operations.  Client-side
 * filtering by email or full name is supported via a search box.
 */
const UsersPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();

  // Modal state
  const [isCreateModalOpen, setCreateModalOpen] = useState(false);
  const [isEditModalOpen, setEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);

  // Sorting state for TanStack table
  const [sorting, setSorting] = useState<SortingState>([]);
  // Pagination state (client-side because API lacks pagination)
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  // Search filter state
  const [search, setSearch] = useState('');

  // Fetch users
  const {
    data: users,
    error: usersError,
    isLoading: usersLoading,
  } = useQuery<User[], Error>({
    queryKey: ['users'],
    queryFn: getUsers,
    onError: (err) => addNotification(err.message, 'error'),
  });
  // Fetch roles
  const {
    data: roles,
    error: rolesError,
    isLoading: rolesLoading,
  } = useQuery<Role[], Error>({
    queryKey: ['roles'],
    queryFn: getRoles,
    onError: (err) => addNotification(err.message, 'error'),
  });

  // Create user mutation
  const createMutation = useMutation((data: UserFormData) => createUser(data as any), {
    onSuccess: () => {
      addNotification('User created', 'success');
      queryClient.invalidateQueries(['users']);
    },
    onError: (err: Error) => addNotification(err.message, 'error'),
  });
  // Update user mutation
  const updateMutation = useMutation(
    (variables: { id: number; data: UserFormData }) => updateUser(variables.id, variables.data as any),
    {
      onSuccess: () => {
        addNotification('User updated', 'success');
        queryClient.invalidateQueries(['users']);
      },
      onError: (err: Error) => addNotification(err.message, 'error'),
    },
  );
  // Delete user mutation
  const deleteMutation = useMutation((id: number) => deleteUser(id), {
    onSuccess: () => {
      addNotification('User deleted', 'success');
      queryClient.invalidateQueries(['users']);
    },
    onError: (err: Error) => addNotification(err.message, 'error'),
  });

  // Filter and paginate users on the client
  const filteredUsers = useMemo(() => {
    if (!users) return [];
    const lower = search.toLowerCase();
    const filtered = users.filter((u) => {
      const email = (u.email ?? '').toLowerCase();
      const name = (u.full_name ?? '').toLowerCase();
      return email.includes(lower) || name.includes(lower);
    });
    return filtered;
  }, [users, search]);

  const paginatedUsers = useMemo(() => {
    const start = pageIndex * pageSize;
    return filteredUsers.slice(start, start + pageSize);
  }, [filteredUsers, pageIndex, pageSize]);
  const hasNextPage = filteredUsers.length > (pageIndex + 1) * pageSize;

  // Table columns
  const columns = useMemo<ColumnDef<User>[]>(() => [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: (info) => info.getValue<number>(),
    },
    {
      accessorKey: 'email',
      header: 'Email',
      cell: (info) => info.getValue<string>() || '-'
    },
    {
      accessorKey: 'full_name',
      header: 'Full Name',
      cell: (info) => info.getValue<string>() || '-'
    },
    {
      id: 'role',
      header: 'Role',
      cell: ({ row }) => {
        const u = row.original as User;
        const role = roles?.find((r) => r.id === (u.role_id ?? 0));
        return role ? role.name : '—';
      },
    },
    {
      accessorKey: 'disabled',
      header: 'Disabled',
      cell: (info) => (info.getValue<boolean>() ? 'Yes' : 'No'),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const user = row.original as User;
        return (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setEditingUser(user);
                setEditModalOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs"
            >
              Edit
            </button>
            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this user?')) {
                  deleteMutation.mutate(user.id);
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
  ], [roles, deleteMutation]);

  // Configure the table instance
  const table = useReactTable({
    data: paginatedUsers,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    manualSorting: true,
  });

  // Handlers for modal submissions
  const handleCreate = async (data: UserFormData) => {
    await createMutation.mutateAsync(data);
  };
  const handleEdit = async (data: UserFormData) => {
    if (editingUser) {
      await updateMutation.mutateAsync({ id: editingUser.id, data });
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Users &amp; Roles</h2>

      {/* Search and Create */}
      <div className="flex flex-wrap gap-4 items-end">
        <div>
          <label htmlFor="search" className="block text-sm font-medium mb-1">
            Search
          </label>
          <input
            id="search"
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPageIndex(0);
            }}
            placeholder="Search by email or name"
            className="border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm"
          />
        </div>
        <div className="ml-auto">
          <button
            onClick={() => setCreateModalOpen(true)}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm"
          >
            Create User
          </button>
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
            {usersLoading || rolesLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center">
                  Loading users…
                </td>
              </tr>
            ) : usersError || rolesError ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-red-600 dark:text-red-400">
                  Failed to load users.
                </td>
              </tr>
            ) : filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-4 text-center text-gray-500 dark:text-gray-400">
                  No users found.
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

      {/* Create modal */}
      <UserFormModal
        isOpen={isCreateModalOpen}
        onClose={() => setCreateModalOpen(false)}
        initialData={undefined}
        title="Create User"
        onSubmit={handleCreate}
        roles={roles}
      />
      {/* Edit modal */}
      <UserFormModal
        isOpen={isEditModalOpen}
        onClose={() => {
          setEditModalOpen(false);
          setEditingUser(null);
        }}
        initialData={editingUser ?? undefined}
        title="Edit User"
        onSubmit={handleEdit}
        roles={roles}
      />
    </div>
  );
};

export default UsersPage;