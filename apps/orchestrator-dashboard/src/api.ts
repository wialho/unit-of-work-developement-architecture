export type CreateWorkflowRunRequest = {
  source_type: string;
  source_ref: string;
  ticket: Record<string, unknown>;
};

export type CreateWorkflowRunResponse = {
  workflow_run_id: string;
  first_step_id: string;
  input_artifact_id: string;
  trace_id: string;
};

const orchestratorApiUrl = import.meta.env.VITE_ORCHESTRATOR_API_URL ?? "http://localhost:8080";

export async function createWorkflowRun(
  request: CreateWorkflowRunRequest
): Promise<CreateWorkflowRunResponse> {
  const response = await fetch(`${orchestratorApiUrl}/workflow-runs`, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    body: JSON.stringify(request)
  });
  if (!response.ok) {
    throw new Error(`Orchestrator returned ${response.status}`);
  }
  return response.json();
}
