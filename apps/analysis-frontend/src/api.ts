export type AnalysisSummary = {
  status: string;
  note: string;
};

const analysisApiUrl = import.meta.env.VITE_ANALYSIS_API_URL ?? "http://localhost:8081";

export async function getAnalysisSummary(): Promise<AnalysisSummary> {
  const response = await fetch(`${analysisApiUrl}/analysis/summary`);
  if (!response.ok) {
    throw new Error(`Analysis service returned ${response.status}`);
  }
  return response.json();
}
