import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AnalysisSummary, getAnalysisSummary } from "./api";
import "./styles.css";

function App() {
  const [summary, setSummary] = useState<AnalysisSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAnalysisSummary()
      .then(setSummary)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Unknown error");
      });
  }, []);

  return (
    <main>
      <h1>Workflow Analysis</h1>
      <p>Dashboard shell for durable workflow, artifact, and step analytics.</p>
      {error && <section className="error">Failed to load analysis summary: {error}</section>}
      {summary && (
        <section>
          <h2>Analysis Service</h2>
          <dl>
            <dt>Status</dt>
            <dd>{summary.status}</dd>
            <dt>Note</dt>
            <dd>{summary.note}</dd>
          </dl>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
