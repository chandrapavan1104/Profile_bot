import { useState, useMemo } from "react";

const defaultQuery = "Give a summary of your work experience.";

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

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    setAnswer("");
    try {
      const response = await fetch(askEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query })
      });
    
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
    
      const data = await response.json();
      setAnswer(typeof data.response === "string" ? data.response : data.response?.result ?? "");
    } catch (err) {
      console.error("Fetch failed:", err);
      // 👇 fallback
      setAnswer("⚠️ Backend isOffline");
      setError("");
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
            placeholder="e.g. What experience does the team have with AI projects?"
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
