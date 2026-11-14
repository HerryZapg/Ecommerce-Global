"use client";

import { useState } from "react";

export default function AdminChatPage() {
  const [message, setMessage] = useState("Stock bajo en SKU-99");
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    setLoading(true);
    setOutput("");

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!res.body) {
      setOutput("No stream");
      setLoading(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let text = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      text += decoder.decode(value);
      setOutput(text);
    }

    setLoading(false);
  }

  return (
    <main style={{ padding: 24, display: "grid", gap: 12, maxWidth: 900 }}>
      <h1>Chat IA</h1>
      <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={4} />
      <button onClick={send} disabled={loading}>
        {loading ? "Enviando..." : "Enviar"}
      </button>
      <pre style={{ whiteSpace: "pre-wrap" }}>{output}</pre>
    </main>
  );
}

