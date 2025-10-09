import { useState } from "react";

const defaultQuery = "Tell me about the project.";

export default function App() {
  const [query, setQuery] = useState(defaultQuery);
  const [answer, setAnswer] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await fetch("http://localhost:8003/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ query })
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      setAnswer(data.response ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
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
            <p>{answer}</p>
          </section>
        )}
      </main>
    </div>
  );
}
