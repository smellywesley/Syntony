export type TaskCondition = "single" | "dual";
export type Hand = "left" | "right" | null;
export type SpeechTask = "count_backwards" | "ddk_pataka" | null;

export interface TaskDefinition {
  code: string;
  name: string;
  condition: TaskCondition;
  hand: Hand;
  speech_task: SpeechTask;
}

export interface TaskInstance extends TaskDefinition {
  id: string;
  repetition: number;
  order_index: number;
}

export type ProtocolState =
  | "CONSENT_CHECK"
  | "DEVICE_CHECK"
  | "ENVIRONMENT_CHECK"
  | "PRACTICE"
  | "READY"
  | "PRE_ROLL"
  | "ACTIVE_TASK"
  | "POST_ROLL"
  | "LOCAL_QC"
  | "REPEAT_SUGGESTED"
  | "REST"
  | "UPLOAD"
  | "COMPLETE"
  | "FAILED";

export interface ProtocolContext {
  state: ProtocolState;
  taskIndex: number;
  tasks: TaskInstance[];
  attemptByTaskId: Record<string, number>;
  lastError?: string;
}

export type ProtocolEvent =
  | { type: "CONSENT_CONFIRMED" }
  | { type: "DEVICE_OK" }
  | { type: "ENVIRONMENT_OK" }
  | { type: "PRACTICE_COMPLETE" }
  | { type: "START" }
  | { type: "PRE_ROLL_COMPLETE" }
  | { type: "ACTIVE_COMPLETE" }
  | { type: "POST_ROLL_COMPLETE" }
  | { type: "QC_ACCEPTED" }
  | { type: "QC_REPEAT" }
  | { type: "REST_COMPLETE" }
  | { type: "UPLOAD_COMPLETE" }
  | { type: "FAIL"; message: string }
  | { type: "RETRY" };
