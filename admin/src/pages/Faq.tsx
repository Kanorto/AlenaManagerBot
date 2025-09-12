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
import { Faq, getFaqs, createFaq, updateFaq, deleteFaq } from '../api/faqs';
import { useNotifications } from '../store/notifications';

/** Schema for creating or editing FAQ entries. */
const faqSchema = z.object({
  question_short: z.string().min(1, 'Short question is required'),
  question_full: z.string().optional().nullable(),
  answer: z.string().min(1, 'Answer is required'),
  position: z
    .preprocess((v) => (v === '' || v === null || v === undefined ? undefined : parseInt(v as string, 10)), z.number().int().nonnegative().optional())
    .optional(),
});
type FaqFormData = z.infer<typeof faqSchema>;

/** FAQ page allows administrators to manage frequently asked questions.  A
 * paginated table displays all entries and modals support create and
 * edit operations.  Attachments are not currently supported. */
const FaqPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  // Modal state
  const [isModalOpen, setModalOpen] = useState(false);
  const [editingFaq, setEditingFaq] = useState<Faq | null>(null);

  // Fetch FAQs
  const {
    data: faqs,
    isLoading,
  } = useQuery<Faq[], Error>(
    ['faqs', { pageIndex, pageSize }],
    () => getFaqs({ limit: pageSize, offset: pageIndex * pageSize }),
    {
      keepPreviousData: true,
      onError: (err) => addNotification(err.message, 'error'),
    },
  );

  // Mutations
  const createMutation = useMutation((data: FaqFormData) => createFaq(data), {
    onSuccess: () => {
      addNotification('FAQ created', 'success');
      queryClient.invalidateQueries(['faqs']);
    },
    onError: (err) => addNotification((err as Error).message, 'error'),
  });
  const updateMutation = useMutation(
    (variables: { id: number; data: FaqFormData }) => updateFaq(variables.id, variables.data),
    {
      onSuccess: () => {
        addNotification('FAQ updated', 'success');
        queryClient.invalidateQueries(['faqs']);
      },
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );
  const deleteMutation = useMutation((id: number) => deleteFaq(id), {
    onSuccess: () => {
      addNotification('FAQ deleted', 'success');
      queryClient.invalidateQueries(['faqs']);
    },
    onError: (err) => addNotification((err as Error).message, 'error'),
  });

  // Form hook
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<FaqFormData>({ resolver: zodResolver(faqSchema) });

  useEffect(() => {
    if (isModalOpen && editingFaq) {
      setValue('question_short', editingFaq.question_short);
      setValue('question_full', editingFaq.question_full ?? '');
      setValue('answer', editingFaq.answer);
      setValue('position', editingFaq.position);
    } else {
      reset();
    }
  }, [isModalOpen, editingFaq, reset, setValue]);

  const onSubmit = async (data: FaqFormData) => {
    if (editingFaq) {
      await updateMutation.mutateAsync({ id: editingFaq.id, data });
    } else {
      await createMutation.mutateAsync(data);
    }
    setModalOpen(false);
    setEditingFaq(null);
  };

  // Table columns
  const columns = useMemo<ColumnDef<Faq>[]>(() => [
    { accessorKey: 'id', header: 'ID', cell: (info) => info.getValue<number>() },
    { accessorKey: 'question_short', header: 'Question', cell: (info) => info.getValue<string>() },
    {
      accessorKey: 'position',
      header: 'Position',
      cell: (info) => info.getValue<number>(),
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => {
        const faq = row.original;
        return (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setEditingFaq(faq);
                setModalOpen(true);
              }}
              className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs"
            >
              Edit
            </button>
            <button
              onClick={() => {
                if (confirm('Delete this FAQ entry?')) deleteMutation.mutate(faq.id);
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
    data: faqs ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualPagination: true,
    manualSorting: true,
  });
  const hasNextPage = (faqs?.length ?? 0) === pageSize;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">FAQs</h2>
      <div className="flex justify-end">
        <button
          onClick={() => {
            setEditingFaq(null);
            setModalOpen(true);
          }}
          className="px-3 py-2 bg-blue-600 text-white rounded-md text-sm"
        >
          New FAQ
        </button>
      </div>
      {/* Table */}
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
            ) : faqs && faqs.length > 0 ? (
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
                  No FAQ entries found.
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
      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-lg w-full p-6">
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">
              {editingFaq ? 'Edit FAQ' : 'New FAQ'}
            </h3>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Short Question</label>
                <input
                  type="text"
                  {...register('question_short')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.question_short && <p className="text-sm text-red-600 mt-1">{errors.question_short.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Full Question</label>
                <input
                  type="text"
                  {...register('question_full')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.question_full && <p className="text-sm text-red-600 mt-1">{errors.question_full.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Answer</label>
                <textarea
                  {...register('answer')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  rows={4}
                />
                {errors.answer && <p className="text-sm text-red-600 mt-1">{errors.answer.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Position</label>
                <input
                  type="number"
                  min="0"
                  {...register('position')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.position && <p className="text-sm text-red-600 mt-1">{errors.position.message}</p>}
              </div>
              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setModalOpen(false);
                    setEditingFaq(null);
                    reset();
                  }}
                  className="px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
                >
                  {editingFaq ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default FaqPage;