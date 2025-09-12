import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSettings, getSetting, upsertSetting, Setting } from '../api/settings';
import { useNotifications } from '../store/notifications';
import { useForm } from 'react-hook-form';

/**
 * Settings page provides a simple key/value editor for application
 * configuration.  Each setting has a key, value and type.  Users can
 * modify existing settings or create new ones.  All operations
 * require super administrator privileges as enforced by the backend.
 */
const SettingsPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  const [isModalOpen, setModalOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);

  // Fetch settings
  const { data: settings, isLoading } = useQuery<Setting[], Error>(['settings'], getSettings, {
    onError: (err) => addNotification(err.message, 'error'),
  });

  // Fetch a single setting when editing
  const { data: editingSetting, refetch } = useQuery<Setting, Error>(
    ['setting', editingKey],
    () => {
      if (!editingKey) throw new Error('No key');
      return getSetting(editingKey);
    },
    {
      enabled: false,
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  // Mutation for upserting
  const upsertMutation = useMutation(
    (variables: { key: string; value: any; type: string }) => upsertSetting(variables.key, variables.value, variables.type),
    {
      onSuccess: () => {
        addNotification('Setting saved', 'success');
        queryClient.invalidateQueries(['settings']);
        if (editingKey) queryClient.invalidateQueries(['setting', editingKey]);
      },
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  // Form hook
  const { register, handleSubmit, reset, setValue, formState: { errors } } = useForm<{
    key: string;
    value: string;
    type: string;
  }>({ defaultValues: { key: '', value: '', type: 'string' } });

  useEffect(() => {
    if (isModalOpen && editingKey) {
      refetch().then((res) => {
        const s = res.data;
        if (s) {
          setValue('key', s.key);
          setValue('value', JSON.stringify(s.value));
          setValue('type', s.type);
        }
      });
    } else {
      reset();
    }
  }, [isModalOpen, editingKey, refetch, reset, setValue]);

  const onSubmit = async (data: { key: string; value: string; type: string }) => {
    let parsed: any;
    try {
      // Attempt to parse JSON for non-string types; strings remain as raw
      if (data.type === 'string') {
        parsed = data.value;
      } else if (data.type === 'int') {
        parsed = parseInt(data.value, 10);
      } else if (data.type === 'float') {
        parsed = parseFloat(data.value);
      } else if (data.type === 'bool') {
        parsed = data.value === 'true' || data.value === '1';
      } else {
        parsed = JSON.parse(data.value);
      }
    } catch (e) {
      addNotification('Invalid value for selected type', 'error');
      return;
    }
    await upsertMutation.mutateAsync({ key: data.key, value: parsed, type: data.type });
    setModalOpen(false);
    setEditingKey(null);
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Settings</h2>
      <div className="flex justify-end">
        <button
          onClick={() => {
            setEditingKey(null);
            setModalOpen(true);
          }}
          className="px-3 py-2 bg-blue-600 text-white rounded-md text-sm"
        >
          New Setting
        </button>
      </div>
      <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Key</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Type</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Value</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-900 dark:divide-gray-700">
            {isLoading ? (
              <tr>
                <td colSpan={4} className="p-4 text-center">Loading…</td>
              </tr>
            ) : settings && settings.length > 0 ? (
              settings.map((s) => (
                <tr key={s.key} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 font-mono">{s.key}</td>
                  <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">{s.type}</td>
                  <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 truncate max-w-xs" title={typeof s.value === 'object' ? JSON.stringify(s.value) : String(s.value)}>
                    {typeof s.value === 'object' ? JSON.stringify(s.value) : String(s.value)}
                  </td>
                  <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
                    <button
                      onClick={() => {
                        setEditingKey(s.key);
                        setModalOpen(true);
                      }}
                      className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="p-4 text-center text-gray-500 dark:text-gray-400">No settings found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-lg w-full p-6">
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">
              {editingKey ? `Edit Setting ${editingKey}` : 'New Setting'}
            </h3>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Key</label>
                <input
                  type="text"
                  {...register('key', { required: true })}
                  disabled={!!editingKey}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.key && <p className="text-sm text-red-600 mt-1">Key is required</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Type</label>
                <select
                  {...register('type', { required: true })}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                >
                  <option value="string">string</option>
                  <option value="int">int</option>
                  <option value="float">float</option>
                  <option value="bool">bool</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Value</label>
                <input
                  type="text"
                  {...register('value', { required: true })}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.value && <p className="text-sm text-red-600 mt-1">Value is required</p>}
              </div>
              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setModalOpen(false);
                    setEditingKey(null);
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
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;