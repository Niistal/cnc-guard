export type Status = 'NORMAL' | 'WARNING' | 'CRITICAL' | 'UNKNOWN';
export type Reading = Record<string, number | string>;
export interface Prediction {
  status: Status; failure_score: number | null; anomaly_score: number | null;
  data_quality_status: string; explanation: string; recommended_action: string;
  model_version: string; created_at: string;
}
export interface Machine {
  id: string; name: string; area: string; simulated: boolean; source_udi: number | null;
  step: number | null; reading: Reading | null; prediction: Prediction | null;
}
export interface Session { id: number; created_at: string; state: string; cursor: number; error: string | null }
export interface Alert {
  id: number; machine_id: string; session_id: number; status: Status; created_at: string;
  acknowledged_at: string | null; prediction: Prediction; notes: { id: number; body: string }[];
}
export interface Health { status: string; models: Record<string, { ready: boolean; version: string | null }> }
export interface HistoryRow { id: number; step: number; source_udi: number; reading: Reading; prediction: Prediction }
export interface MillingRun { case: number; run: number; VB: number | null; predicted_vb: number;
  in_domain: boolean; partition: string }
export interface MillingResult { estimated_wear: number | null; unit: string; status: string;
  explanation: string; data_quality_status: string; model_version: string }
export interface Evaluation {
  model_version: string; selected_model: string; target: string;
  test: Record<string, number | number[] | Record<string, { mae: number; rows: number }>>;
  dummy_test: Record<string, number>; coverage: { accepted: number; total: number; fraction: number };
  partitions: Record<string, { rows: number; failures?: number; cases?: number[] }>;
  validation: Record<string, Record<string, number>>; global_importance?: Record<string, number>;
  groups?: Record<string, number[]>;
}
