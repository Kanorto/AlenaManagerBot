import { create } from 'zustand';

/**
 * Notification interface used by the notifications store.  Each
 * notification has a unique id, a message and a type.  Types can
 * be extended in the future (e.g. success, warning) to change
 * styling accordingly.
 */
export interface Notification {
  id: number;
  message: string;
  type: 'error' | 'success' | 'info';
}

interface NotificationState {
  notifications: Notification[];
  addNotification: (message: string, type: Notification['type']) => void;
  removeNotification: (id: number) => void;
}

// Zustand store for global notifications.  Notifications are
// automatically removed after 5 seconds when added.
export const useNotifications = create<NotificationState>((set, get) => ({
  notifications: [],
  addNotification: (message: string, type) => {
    const id = Date.now();
    set((state) => ({
      notifications: [...state.notifications, { id, message, type }],
    }));
    // Remove the notification after 5 seconds.
    setTimeout(() => {
      get().removeNotification(id);
    }, 5000);
  },
  removeNotification: (id: number) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    }));
  },
}));