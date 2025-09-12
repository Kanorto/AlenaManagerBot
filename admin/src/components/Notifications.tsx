import React from 'react';
import { useNotifications } from '../store/notifications';

/**
 * Notifications component renders transient messages at the bottom
 * right of the screen.  It subscribes to the notifications store
 * and displays each notification with styling based on its type.
 */
const Notifications: React.FC = () => {
  const { notifications } = useNotifications();

  if (notifications.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 space-y-2 z-50">
      {notifications.map((n) => {
        let bgColor = 'bg-blue-600';
        if (n.type === 'error') bgColor = 'bg-red-600';
        if (n.type === 'success') bgColor = 'bg-green-600';
        return (
          <div
            key={n.id}
            className={`${bgColor} text-white px-4 py-2 rounded shadow-lg`}
          >
            {n.message}
          </div>
        );
      })}
    </div>
  );
};

export default Notifications;