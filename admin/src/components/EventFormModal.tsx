import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

// Zod schema for validating event input.  All fields are required
// because both create and edit operations expect a complete
// representation of the event.  Duration and max participants must
// be positive integers.  start_time is a datetime-local string in
// the form accepted by browsers (YYYY-MM-DDTHH:mm).
const eventSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  description: z.string().optional().nullable(),
  start_time: z.string().min(1, 'Start time is required'),
  duration_minutes: z
    .preprocess((v) => (v === '' ? undefined : parseInt(v as string, 10)), z.number().int().positive()),
  max_participants: z
    .preprocess((v) => (v === '' ? undefined : parseInt(v as string, 10)), z.number().int().positive()),
  is_paid: z.boolean(),
});

export type EventFormData = z.infer<typeof eventSchema>;

interface EventFormModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Called when the modal should close */
  onClose: () => void;
  /** Initial values for the form.  When provided the form will be
   * pre-populated and used for editing.  start_time must be an ISO
   * string; it will be converted to a datetime-local value. */
  initialData?: Partial<EventFormData>;
  /** Invoked when the form is submitted with valid data */
  onSubmit: (data: EventFormData) => Promise<void>;
  /** Title shown in the modal header */
  title: string;
}

/**
 * Modal component for creating or editing an event.  Uses
 * react-hook-form and zod for validation.  The form is fully
 * controlled and calls onSubmit with typed data when valid.  The
 * modal is rendered conditionally based on isOpen.
 */
const EventFormModal: React.FC<EventFormModalProps> = ({
  isOpen,
  onClose,
  initialData,
  onSubmit,
  title,
}) => {
  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<EventFormData>({
    resolver: zodResolver(eventSchema),
    defaultValues: {
      title: '',
      description: '',
      start_time: '',
      duration_minutes: 60,
      max_participants: 10,
      is_paid: false,
    },
  });

  // Populate default values when initialData changes
  useEffect(() => {
    if (initialData) {
      // Convert ISO start time to datetime-local (strip seconds and Z)
      const dt = initialData.start_time
        ? new Date(initialData.start_time).toISOString().slice(0, 16)
        : '';
      setValue('title', initialData.title ?? '');
      setValue('description', initialData.description ?? '');
      setValue('start_time', dt);
      setValue('duration_minutes', initialData.duration_minutes ?? 60);
      setValue('max_participants', initialData.max_participants ?? 10);
      setValue('is_paid', initialData.is_paid ?? false);
    } else {
      reset();
    }
  }, [initialData, reset, setValue]);

  const internalSubmit = handleSubmit(async (data) => {
    // Convert start_time to ISO string with seconds and Z suffix
    const iso = new Date(data.start_time).toISOString();
    const payload: EventFormData = {
      ...data,
      start_time: iso,
    };
    await onSubmit(payload);
    onClose();
    // Reset form after submission to clear state
    reset();
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-md w-full p-6">
        <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">{title}</h3>
        <form
          onSubmit={internalSubmit}
          className="space-y-4"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Title
            </label>
            <input
              type="text"
              {...register('title')}
              className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
            />
            {errors.title && (
              <p className="text-sm text-red-600 mt-1">{errors.title.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <textarea
              {...register('description')}
              className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
              rows={3}
            />
            {errors.description && (
              <p className="text-sm text-red-600 mt-1">{errors.description.message}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Start Time
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
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Duration (minutes)
              </label>
              <input
                type="number"
                min="1"
                {...register('duration_minutes')}
                className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
              />
              {errors.duration_minutes && (
                <p className="text-sm text-red-600 mt-1">{errors.duration_minutes.message}</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Max Participants
              </label>
              <input
                type="number"
                min="1"
                {...register('max_participants')}
                className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
              />
              {errors.max_participants && (
                <p className="text-sm text-red-600 mt-1">{errors.max_participants.message}</p>
              )}
            </div>
          </div>
          <div className="flex items-center">
            <input
              id="isPaid"
              type="checkbox"
              {...register('is_paid')}
              className="mr-2"
            />
            <label htmlFor="isPaid" className="text-sm text-gray-700 dark:text-gray-300">
              Paid event
            </label>
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
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EventFormModal;