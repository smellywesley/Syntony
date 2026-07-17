export interface CaptureTiming {
  preRollMs: number;
  activeMs: number;
  postRollMs: number;
}

export const MVP_TIMING: CaptureTiming = {
  preRollMs: 2_000,
  activeMs: 10_000,
  postRollMs: 3_000,
};

export interface NativeCueSchedule {
  recordingStartNs: bigint;
  activeStartNs: bigint;
  activeEndNs: bigint;
  recordingEndNs: bigint;
}

export function buildCueSchedule(recordingStartNs: bigint, timing = MVP_TIMING): NativeCueSchedule {
  const msToNs = (ms: number): bigint => BigInt(ms) * 1_000_000n;
  const activeStartNs = recordingStartNs + msToNs(timing.preRollMs);
  const activeEndNs = activeStartNs + msToNs(timing.activeMs);
  return {
    recordingStartNs,
    activeStartNs,
    activeEndNs,
    recordingEndNs: activeEndNs + msToNs(timing.postRollMs),
  };
}
