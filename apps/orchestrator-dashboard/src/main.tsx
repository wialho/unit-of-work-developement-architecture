import React, { FormEvent, useState } from "react";
import { createRoot } from "react-dom/client";
import { CreateWorkflowRunResponse, createWorkflowRun } from "./api";
import "./styles.css";

function App() {
  const [sourceRef, setSourceRef] = useState("PROJ-123");
  const [title, setTitle] = useState("Add greeting endpoint");
  const [description, setDescription] = useState("Create a simple endpoint that returns a greeting.");
  const [result, setResult] = useState<CreateWorkflowRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);

    try {
      const response = await createWorkflowRun({
        source_type: "dashboard",
        source_ref: sourceRef,
        ticket: {
          title,
          description,
          acceptance_criteria: ["Workflow run is accepted by orchestrator"]
        }
      });
      setResult(response);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  return (
    <main>
      <h1>Workflow Orchestrator</h1>
      <p>Dashboard shell for creating workflow runs through the orchestrator service.</p>

      <form onSubmit={onSubmit}>
        <label>
          Source Reference
          <input value={sourceRef} onChange={(event) => setSourceRef(event.target.value)} />
        </label>
        <label>
          Title
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label>
          Description
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <button type="submit">Create Workflow Run</button>
      </form>

      {error && <section className="error">Failed to create workflow run: {error}</section>}
      {result && (
        <section>
          <h2>Workflow Created</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
