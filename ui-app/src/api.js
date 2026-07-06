import { getToken, setToken } from "./auth.js";

const BASE = import.meta.env.VITE_CONVERSATION_API || "http://localhost:8000";

// The App registers a callback so it can force re-login when the token expires.
let onAuthExpired = null;
export function setOnAuthExpired(fn) {
  onAuthExpired = fn;
}

function authHeaders(extra = {}) {
  const token = getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function handle(res) {
  if (res.status === 401) {
    setToken("");
    if (onAuthExpired) onAuthExpired();
    throw new Error("Your session expired — please sign in again.");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} ${text}`.trim());
  }
  return res.json();
}

// Both calls block until Genie has finished and return the fully-resolved
// answer: { conversation_id, message_id, status, done, answer_text, sql, result, error }

export async function startConversation(question) {
  const res = await fetch(`${BASE}/conversations`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ question }),
  });
  return handle(res);
}

export async function sendFollowUp(conversationId, question) {
  const res = await fetch(
    `${BASE}/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ question }),
    }
  );
  return handle(res);
}

// --- History ---

export async function listConversations() {
  const res = await fetch(`${BASE}/conversations`, { headers: authHeaders() });
  return handle(res);
}

export async function getConversation(conversationId) {
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    headers: authHeaders(),
  });
  return handle(res);
}

export async function deleteConversation(conversationId) {
  const res = await fetch(`${BASE}/conversations/${conversationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handle(res);
}
