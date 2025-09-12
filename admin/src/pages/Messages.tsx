import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMessages,
  getMessage,
  upsertMessage,
  deleteMessage,
  BotMessage,
} from '../api/messages';
import { useNotifications } from '../store/notifications';
import { useForm } from 'react-hook-form';

/**
 * Message templates page allows administrators to view and edit bot
 * messages keyed by a string.  Each message consists of arbitrary
 * JSON content (commonly ``content`` and ``buttons``).  Users can
 * create new messages, edit existing ones and delete templates.
 */
const MessagesPage: React.FC = () => {
  const { addNotification } = useNotifications();
  const queryClient = useQueryClient();
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [isEditOpen, setEditOpen] = useState(false);
  const [isCreateOpen, setCreateOpen] = useState(false);

  // Fetch list of messages
  const { data: messages, isLoading } = useQuery<BotMessage[], Error>(
    ['messages'],
    getMessages,
    {
      onError: (err) => addNotification(err.message, 'error'),
    },
  );

  // Fetch single message when editing
  const { data: editingMessage, refetch: refetchMessage } = useQuery<BotMessage, Error>(
    ['message', selectedKey],
    () => {
      if (!selectedKey) throw new Error('No key');
      return getMessage(selectedKey);
    },
    {
      enabled: false,
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );

  // Mutation for upsert
  const upsertMutation = useMutation(
    (variables: { key: string; data: BotMessage }) => upsertMessage(variables.key, variables.data),
    {
      onSuccess: () => {
        addNotification('Message saved', 'success');
        queryClient.invalidateQueries(['messages']);
        if (selectedKey) queryClient.invalidateQueries(['message', selectedKey]);
      },
      onError: (err) => addNotification((err as Error).message, 'error'),
    },
  );
  // Delete mutation
  const deleteMutation = useMutation((key: string) => deleteMessage(key), {
    onSuccess: () => {
      addNotification('Message deleted', 'success');
      queryClient.invalidateQueries(['messages']);
    },
    onError: (err) => addNotification((err as Error).message, 'error'),
  });

  // Form state for create/edit
  const { register, handleSubmit, reset, setValue, formState: { errors } } = useForm<{
    key: string;
    content: string;
    buttons: string;
  }>({
    defaultValues: { key: '', content: '', buttons: '' },
  });

  // Populate form when editing
  useEffect(() => {
    if (isEditOpen && selectedKey) {
      refetchMessage().then((res) => {
        const msg = res.data;
        if (msg) {
          setValue('key', selectedKey);
          const content = (msg as any).content ?? '';
          const buttons = (msg as any).buttons ? JSON.stringify((msg as any).buttons, null, 2) : '';
          setValue('content', content);
          setValue('buttons', buttons);
        }
      });
    } else {
      reset();
    }
  }, [isEditOpen, selectedKey, reset, refetchMessage, setValue]);

  const onSubmit = async (data: { key: string; content: string; buttons: string }) => {
    try {
      const payload: BotMessage = { content: data.content };
      if (data.buttons) {
        try {
          payload.buttons = JSON.parse(data.buttons);
        } catch (e) {
          addNotification('Invalid JSON in buttons', 'error');
          return;
        }
      }
      await upsertMutation.mutateAsync({ key: data.key, data: payload });
      setEditOpen(false);
      setCreateOpen(false);
    } catch (err) {
      // error handled by mutation
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">Bot Messages</h2>
      <div className="flex justify-end">
        <button
          onClick={() => {
            setSelectedKey(null);
            setCreateOpen(true);
          }}
          className="px-3 py-2 bg-blue-600 text-white rounded-md text-sm"
        >
          New Message
        </button>
      </div>
      {/* List */}
      <div className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Key</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Content</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider dark:text-gray-300">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 dark:bg-gray-900 dark:divide-gray-700">
            {isLoading ? (
              <tr>
                <td colSpan={3} className="p-4 text-center">Loading…</td>
              </tr>
            ) : messages && messages.length > 0 ? (
              messages.map((msg: any, idx) => {
                // Each message should include a key; fallback to index string
                const key = msg.key ?? String(idx);
                const content = msg.content ?? JSON.stringify(msg);
                return (
                  <tr key={key} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 font-mono">{key}</td>
                    <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 truncate max-w-xs" title={typeof content === 'string' ? content : JSON.stringify(content)}>
                      {typeof content === 'string' ? content.slice(0, 80) : JSON.stringify(content).slice(0, 80)}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
                      <button
                        onClick={() => {
                          setSelectedKey(key);
                          setEditOpen(true);
                        }}
                        className="px-2 py-1 rounded-md bg-yellow-600 text-white text-xs mr-2"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('Delete this message?')) deleteMutation.mutate(key);
                        }}
                        className="px-2 py-1 rounded-md bg-red-600 text-white text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={3} className="p-4 text-center text-gray-500 dark:text-gray-400">No messages found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* Create/Edit Modal */}
      {(isCreateOpen || isEditOpen) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg max-w-lg w-full p-6">
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">
              {isEditOpen ? `Edit Message ${selectedKey}` : 'New Message'}
            </h3>
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Key</label>
                <input
                  type="text"
                  {...register('key', { required: true })}
                  disabled={isEditOpen}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                />
                {errors.key && <p className="text-sm text-red-600 mt-1">Key is required</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Content</label>
                <textarea
                  {...register('content', { required: true })}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  rows={4}
                />
                {errors.content && <p className="text-sm text-red-600 mt-1">Content is required</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Buttons (JSON)</label>
                <textarea
                  {...register('buttons')}
                  className="w-full border border-gray-300 dark:border-gray-700 rounded-md px-2 py-1 text-sm bg-white dark:bg-gray-900"
                  rows={3}
                  placeholder='[{"text": "Button", "callback_data": "action"}]'
                />
              </div>
              <div className="flex justify-end space-x-2 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    reset();
                    setEditOpen(false);
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

export default MessagesPage;