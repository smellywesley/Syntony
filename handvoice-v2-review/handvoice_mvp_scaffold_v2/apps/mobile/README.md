# Mobile protocol module

The files in `src/protocol` are framework-neutral TypeScript and can be used from React Native screens, hooks, or a native recorder bridge.

The recorder itself should be native because cue and active-window timing must use a monotonic platform clock rather than a JavaScript timer.
