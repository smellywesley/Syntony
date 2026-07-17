import type { ProtocolContext, ProtocolEvent } from "./types";

export class InvalidTransitionError extends Error {}

export function initialContext(tasks: ProtocolContext["tasks"]): ProtocolContext {
  if (tasks.length === 0) throw new Error("Protocol requires at least one task");
  return { state: "CONSENT_CHECK", taskIndex: 0, tasks, attemptByTaskId: {} };
}

export function transition(context: ProtocolContext, event: ProtocolEvent): ProtocolContext {
  if (event.type === "FAIL") return { ...context, state: "FAILED", lastError: event.message };
  if (context.state === "FAILED" && event.type === "RETRY") {
    return { ...context, state: "READY", lastError: undefined };
  }

  const next = (state: ProtocolContext["state"]): ProtocolContext => ({ ...context, state });

  switch (context.state) {
    case "CONSENT_CHECK":
      if (event.type === "CONSENT_CONFIRMED") return next("DEVICE_CHECK");
      break;
    case "DEVICE_CHECK":
      if (event.type === "DEVICE_OK") return next("ENVIRONMENT_CHECK");
      break;
    case "ENVIRONMENT_CHECK":
      if (event.type === "ENVIRONMENT_OK") return next("PRACTICE");
      break;
    case "PRACTICE":
      if (event.type === "PRACTICE_COMPLETE") return next("READY");
      break;
    case "READY":
      if (event.type === "START") {
        const task = context.tasks[context.taskIndex];
        return {
          ...context,
          state: "PRE_ROLL",
          attemptByTaskId: {
            ...context.attemptByTaskId,
            [task.id]: (context.attemptByTaskId[task.id] ?? 0) + 1,
          },
        };
      }
      break;
    case "PRE_ROLL":
      if (event.type === "PRE_ROLL_COMPLETE") return next("ACTIVE_TASK");
      break;
    case "ACTIVE_TASK":
      if (event.type === "ACTIVE_COMPLETE") return next("POST_ROLL");
      break;
    case "POST_ROLL":
      if (event.type === "POST_ROLL_COMPLETE") return next("LOCAL_QC");
      break;
    case "LOCAL_QC":
      if (event.type === "QC_REPEAT") return next("REPEAT_SUGGESTED");
      if (event.type === "QC_ACCEPTED") return next("REST");
      break;
    case "REPEAT_SUGGESTED":
      if (event.type === "RETRY") return next("READY");
      break;
    case "REST":
      if (event.type === "REST_COMPLETE") {
        const isLast = context.taskIndex >= context.tasks.length - 1;
        return isLast ? next("UPLOAD") : { ...context, state: "READY", taskIndex: context.taskIndex + 1 };
      }
      break;
    case "UPLOAD":
      if (event.type === "UPLOAD_COMPLETE") return next("COMPLETE");
      break;
    case "COMPLETE":
      break;
  }

  throw new InvalidTransitionError(`Cannot apply ${event.type} in ${context.state}`);
}
