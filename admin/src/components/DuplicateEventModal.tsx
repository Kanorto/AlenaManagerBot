import React from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

// Schema for the duplicate event modal.  Only the new start time is
// required.  We accept a datetime-local string.
const dupSchema = z.object({
  start_time: z.string().min(1, 'Start time is required'),
});

type DupFormData = z.infer<typeof dupSchema>;

interface DuplicateEventModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (startTimeIso: string) => Promise<void>;
  title: string;
}

const DuplicateEventModal: React.FC<DuplicateEventModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  title,
}) => {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DupFormData>({ resolver: zodResolver(dupSchema) });

  const internalSubmit = handleSubmit(async (data) => {
    const iso = new Date(data.start_time).toISOString();
    await onSubmit(iso);
    onClose();
    reset();
  });

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-md w-full p-6">
        <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">{title}</h3>
        <form onSubmit={internalSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              New Start Time
            </label>
            <input
              type="datetime-local"
              {...register('start_time')}
              className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
            />
            {errors.start_time && (
              <p className="text-sm text-red-600 mt-1">{errors.start_time.message}</p>
            )}
          </div>
          <div className="flex justify-end space-x-2 pt-4">
            <button
              type="button"
              onClick={() => {
                reset();
                onClose();
              }}
              className="px-3 py-1 rounded-md border border-gray-300 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700"
            >
              Duplicate
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DuplicateEventModal;