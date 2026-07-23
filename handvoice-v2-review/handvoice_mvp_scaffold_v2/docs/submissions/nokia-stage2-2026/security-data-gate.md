# Security and external-data gate

**Current authorization:** synthetic and prerecorded non-personal demo material
only. The prototype is not approved to collect participant or health data.

The following controls must be implemented and verified before any external
participant recording:

- Enforce `Operator.study_id` on participant, session, task, report and media
  access; the global bootstrap operator remains local-demo only.
- Associate every upload with an operator/study and enforce pending-storage and
  request quotas.
- Define a short raw-media retention period, withdrawal deletion workflow,
  verified expiry and encrypted/protected storage.
- Run startup and scheduled cleanup for stale partial, incoming and unreferenced
  processing objects, with durable failure alerts.
- Serve physical phones through HTTPS or trusted secure-device forwarding;
  never bind the current bearer-authenticated HTTP service directly to a LAN.
- Obtain institutional privacy, consent and ethics/governance approval.

Controls already present for the local demonstrator include high-entropy
bootstrap-key generation and minimum length, loopback-only binding, bounded
uploads, contained storage paths, exclusive upload claims, deterministic
rejection cleanup, ignored capture directories and hidden credentials by
default in the launcher.

Exit criterion: a security re-review verifies every item above and the
institutional owner signs off before the first participant recording.
