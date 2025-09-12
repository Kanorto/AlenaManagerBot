import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Role } from '../api/roles';

// Define a zod schema for validating user input.  Email is optional to
// allow editing without modifying the address; however when
// creating a user the caller should ensure a value is supplied.
// Password is optional for edits; when present it will update the
// password.  full_name is optional and may be null.  disabled is a
// boolean flag.  role_id is optional and may be null.
const userSchema = z.object({
  email: z
    .string()
    .email('Invalid email')
    .optional()
    .nullable(),
  full_name: z.string().optional().nullable(),
  password: z.string().optional().nullable(),
  disabled: z.boolean().optional().nullable(),
  role_id: z
    .preprocess((v) => {
      // Convert empty string to undefined
      if (v === '' || v === undefined || v === null) return undefined;
      return Number(v);
    }, z.number().int().positive().optional().nullable()),
});

export type UserFormData = z.infer<typeof userSchema>;

interface UserFormModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Called when the modal should close */
  onClose: () => void;
  /** Initial values for the form.  When provided the form will be
   * pre-populated and used for editing.  */
  initialData?: Partial<UserFormData>;
  /** Invoked when the form is submitted with valid data */
  onSubmit: (data: UserFormData) => Promise<void>;
  /** Title shown in the modal header */
  title: string;
  /** List of available roles for selection.  Each role has an id
   * and name.  Optional; when omitted the role field is hidden. */
  roles?: Role[];
}

/**
 * Modal component for creating or editing a user.  Uses
 * react-hook-form and zod for validation.  The form is fully
 * controlled and calls onSubmit with typed data when valid.  The
 * modal is rendered conditionally based on isOpen.  When editing a
 * user the email and disabled fields default from initialData.  The
 * password field is always blank; if provided it will be sent to
 * the server, otherwise it is omitted.
 */
const UserFormModal: React.FC<UserFormModalProps> = ({
  isOpen,
  onClose,
  initialData,
  onSubmit,
  title,
  roles,
}) => {
  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<UserFormData>({
    resolver: zodResolver(userSchema),
    defaultValues: {
      email: '',
      full_name: '',
      password: '',
      disabled: false,
      role_id: undefined,
    },
  });

  // Populate default values when initialData changes
  useEffect(() => {
    if (initialData) {
      setValue('email', initialData.email ?? '');
      setValue('full_name', initialData.full_name ?? '');
      // Password is never prefilled
      setValue('password', '');
      setValue('disabled', initialData.disabled ?? false);
      setValue('role_id', initialData.role_id ?? undefined);
    } else {
      reset();
    }
  }, [initialData, reset, setValue]);

  const internalSubmit = handleSubmit(async (data) => {
    // For create forms ensure email and password are present.
    // initialData undefined indicates creation.
    if (!initialData) {
      if (!data.email || data.email.trim() === '') {
        // Should not reach here due to zod, but double check
        return;
      }
      if (!data.password || data.password.trim() === '') {
        // simple alert; in real app use setError
        alert('Password is required');
        return;
      }
    }
    await onSubmit({
      ...data,
      // If disabled is undefined, convert to false
      disabled: data.disabled ?? false,
    });
    onClose();
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
              Email
            </label>
            <input
              type="email"
              {...register('email')}
              className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
              disabled={!!initialData}
            />
            {errors.email && (
              <p className="text-sm text-red-600 mt-1">{errors.email.message as string}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Full Name
            </label>
            <input
              type="text"
              {...register('full_name')}
              className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
            />
            {errors.full_name && (
              <p className="text-sm text-red-600 mt-1">{errors.full_name.message as string}</p>
            )}
          </div>
          {!initialData && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Password
              </label>
              <input
                type="password"
                {...register('password')}
                className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
              />
              {errors.password && (
                <p className="text-sm text-red-600 mt-1">{errors.password.message as string}</p>
              )}
            </div>
          )}
          {roles && roles.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Role
              </label>
              <select
                {...register('role_id')}
                className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
              >
                <option value="">Unassigned</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {initialData !== undefined && (
            <div className="flex items-center">
              <input
                id="disabled"
                type="checkbox"
                {...register('disabled')}
                className="mr-2"
              />
              <label htmlFor="disabled" className="text-sm text-gray-700 dark:text-gray-300">
                Disabled
              </label>
            </div>
          )}
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
              className="px-3 py-1 rounded-md bg-blue-600 text-white text-sm"
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserFormModal;