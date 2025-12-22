import { useState, useMemo, useEffect } from "react";

const defaultQuery = "Give a summary of your work experience.";
const STORAGE_KEY = "profile_bot_messages";

const getAskEndpoint = () => {
  const base = (import.meta.env.VITE_API_BASE_URL || "").trim();
  if (!base) {
    return "/ask";
  }

  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  return `${normalizedBase}/ask`;
};

export default function App() {
  const [query, setQuery] = useState(defaultQuery);
  const [answer, setAnswer] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const askEndpoint = useMemo(getAskEndpoint, []);

  const loadMessages = () => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.warn("Failed to read messages from storage", e);
      return [];
    }
  };

  const saveMessages = (messages) => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch (e) {
      console.warn("Failed to save messages to storage", e);
    }
  };

  const [messages, setMessages] = useState(loadMessages);

  useEffect(() => {
    saveMessages(messages);
  }, [messages]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    setAnswer("");
    try {
      const nextMessages = [...messages, { role: "user", content: query }];
      const response = await fetch(askEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          messages: nextMessages
        })
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      const assistantReply =
        typeof data.response === "string"
          ? data.response
          : data.response?.result ?? JSON.stringify(data.response);

      const updatedMessages = [
        ...nextMessages,
        { role: "assistant", content: assistantReply }
      ];
      setMessages(updatedMessages);
      setAnswer(assistantReply);
      setQuery("");
    } catch (err) {
      console.error("Fetch failed:", err);
      setError("Failed to connect to the backend");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="page">
      <header className="header">
        <h1>Profile Bot</h1>
        <p>Ask a question about the knowledge base and get instant answers.</p>
      </header>

      <main className="card">
        <form onSubmit={handleSubmit} className="form">
          <label htmlFor="query" className="label">
            Your question
          </label>
          <textarea
            id="query"
            className="textarea"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            rows={4}
            placeholder="e.g. What experience do you have with AI projects?"
          />
          <button className="button" type="submit" disabled={isLoading || !query.trim()}>
            {isLoading ? "Thinking..." : "Ask"}
          </button>
        </form>

        {error && <p className="error">Error: {error}</p>}

        {answer && (
          <section className="response">
            <h2>Response</h2>
            <p>{typeof answer === "string" ? answer : JSON.stringify(answer, null, 2)}</p>
          </section>
        )}
      </main>
    </div>
  );
}
