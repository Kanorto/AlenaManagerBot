import { apiFetch } from './client';

/**
 * The messages API manages bot message templates keyed by a string.
 * Each message is stored as a JSON object with arbitrary fields
 * depending on the bot platform.  At minimum a message typically
 * contains ``content`` (string) and optional ``buttons`` (array).
 */

export type BotMessage = Record<string, unknown>;

/** List all bot message templates.  Returns an array of objects. */
export async function getMessages(): Promise<BotMessage[]> {
  const res = await apiFetch<BotMessage[]>('/api/v1/messages/');
  return res ?? [];
}

/** Retrieve a single message template by key. */
export async function getMessage(key: string): Promise<BotMessage> {
  const res = await apiFetch<BotMessage>(`/api/v1/messages/${encodeURIComponent(key)}`);
  return res!;
}

/** Create or update a message template.  The key is supplied in the
 * URL and the body contains the message content and optional
 * metadata (e.g. buttons). */
export async function upsertMessage(key: string, data: BotMessage): Promise<BotMessage> {
  const res = await apiFetch<BotMessage>(`/api/v1/messages/${encodeURIComponent(key)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
  return res!;
}

/** Delete a message template by key. */
export async function deleteMessage(key: string): Promise<void> {
  await apiFetch<void>(`/api/v1/messages/${encodeURIComponent(key)}`, {
    method: 'DELETE',
  });
}