const rawUrl = import.meta.env.VITE_API_BASE_URL || "";
const cleanUrl = rawUrl.replace(/\/$/, "");

const API_BASE_URL = import.meta.env.DEV
  ? (cleanUrl || "http://localhost:8000")
  : (cleanUrl.includes("localhost") ? "" : cleanUrl);

export interface ChatResponse {
  reply: string;
  session_id: string;
  sources: string[];
}

export async function sendMessage(message: string, sessionId: string | null): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) {
    const errJson = await res.json().catch(() => null);
    const detail = errJson?.detail || `Chat request failed: ${res.status}`;
    throw new Error(detail);
  }
  return res.json();
}
