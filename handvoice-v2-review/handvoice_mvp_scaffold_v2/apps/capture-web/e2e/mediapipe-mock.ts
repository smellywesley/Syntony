const landmarks = Array.from({ length: 21 }, (_, index) => ({
  x: 0.45 + (index % 5) * 0.02,
  y: 0.45 + Math.floor(index / 5) * 0.02,
  z: 0,
}));

export const FilesetResolver = {
  async forVisionTasks(): Promise<Record<string, never>> {
    return {};
  },
};

export class HandLandmarker {
  static async createFromOptions(): Promise<HandLandmarker> {
    return new HandLandmarker();
  }

  detectForVideo(): {
    landmarks: Array<typeof landmarks>;
    handedness: Array<Array<{ categoryName: string; score: number }>>;
  } {
    return {
      landmarks: [landmarks],
      // MediaPipe labels the unmirrored rear-camera image anatomically opposite;
      // production physicalHandedness() normalizes this to the participant's right hand.
      handedness: [[{ categoryName: "Left", score: 0.99 }]],
    };
  }

  close(): void {
    // The production application owns cleanup; the mock keeps it observable and deterministic.
  }
}
