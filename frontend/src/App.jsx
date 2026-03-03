import { useState, useMemo, useEffect } from "react";
import ReactMarkdown from "react-markdown";

const defaultQuery = "Give a summary of your work experience.";
const STORAGE_KEY = "profile_bot_messages";

const getAskEndpoint = () => {
  const base = (import.meta.env.VITE_API_BASE_URL || "").trim();
  if (!base) {
    return "/ask/stream";
  }

  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  return `${normalizedBase}/ask/stream`;
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
    
    const nextMessages = [...messages, { role: "user", content: query }];
    setMessages(nextMessages);
    
    let accumulatedResponse = "";
    
    try {
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

      // Handle streaming response
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const finalizeStream = () => {
        const updatedMessages = [
          ...nextMessages,
          { role: "assistant", content: accumulatedResponse }
        ];
        setMessages(updatedMessages);
        setQuery("");
        setIsLoading(false);
      };

      const handleSseData = (data) => {
        if (data === "[DONE]") {
          finalizeStream();
          return true;
        }
        if (data.startsWith("Error: ")) {
          setError(data);
          setIsLoading(false);
          return true;
        }

        accumulatedResponse += data;
        setAnswer(accumulatedResponse);
        return false;
      };

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split(/\r?\n\r?\n/);
        buffer = events.pop() ?? "";

        for (const event of events) {
          const lines = event.split(/\r?\n/);
          const dataLines = [];

          for (const line of lines) {
            if (line.startsWith("data:")) {
              dataLines.push(line.replace(/^data:\s?/, ""));
            } else if (line.trim() !== "") {
              dataLines.push(line);
            }
          }

          if (!dataLines.length) {
            continue;
          }

          const data = dataLines.join("\n");
          if (handleSseData(data)) {
            return;
          }
        }
      }

      if (buffer.trim() !== "") {
        const lines = buffer.split(/\r?\n/);
        const dataLines = [];

        for (const line of lines) {
          if (line.startsWith("data:")) {
            dataLines.push(line.replace(/^data:\s?/, ""));
          } else if (line.trim() !== "") {
            dataLines.push(line);
          }
        }

        if (dataLines.length) {
          handleSseData(dataLines.join("\n"));
        }
      }
    } catch (err) {
      console.error("Fetch failed:", err);
      setError("Failed to connect to the backend");
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
            {isLoading ? "Streaming..." : "Ask"}
          </button>
        </form>

        {error && <p className="error">Error: {error}</p>}

        {answer && (
          <section className="response">
            <h2>Response</h2>
            <div className="response-content">
              {typeof answer === "string" ? (
                <ReactMarkdown className="markdown-content">
                  {answer}
                </ReactMarkdown>
              ) : (
                <pre>{JSON.stringify(answer, null, 2)}</pre>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
