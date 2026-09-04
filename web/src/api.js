export async function fetchOptions() {
  const response = await fetch("/api/models");
  if (!response.ok) throw new Error("Không đọc được cấu hình model");
  return response.json();
}

/** POST /api/ask and hand every NDJSON event to onEvent as it arrives. */
export async function streamAsk(body, onEvent, signal) {
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) throw new Error(`Backend lỗi (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line));
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}
