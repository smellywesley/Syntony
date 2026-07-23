# Final submission checklist

## Evidence

- [ ] Competition portal/email requirements reverified and archived.
- [ ] Problem gate passed; anonymous interview evidence recorded.
- [ ] Clinician/SLP decisions recorded or fallback claim limits applied.
- [ ] Claims register has no unsupported submission wording.
- [ ] Device/QC/latency table contains measured, reproducible results.
- [ ] Budget contains dated sources and a 10% contingency.
- [ ] `security-data-gate.md` is closed before any participant recording.

## Proposal

- [ ] Exactly one page after PDF export.
- [ ] Aptos Body 12 pt, single spacing and clear six-section headings.
- [ ] Every number is measured, sourced, estimated or proposed.
- [ ] No “first-ever”, diagnosis, screening, clinical accuracy or efficacy claim.
- [ ] PDF fonts embed correctly; links and characters render without mojibake.

## Video

- [ ] Runtime 2:50–3:00 and organiser file requirements satisfied.
- [ ] Captions, readable units and non-diagnostic boundary visible.
- [ ] No credential, real identifier or unapproved personal media shown.
- [ ] Known-good and QC-retry moments are prerecorded.
- [ ] File plays offline on a second machine; backup copy exists.

## Technical handoff

- [ ] Python suite, browser tests/build, synthetic validation and compose config pass.
- [ ] `scripts/start_demo.ps1` succeeds twice from a clean Docker-capable machine.
- [ ] `/health` and `/capture/` return 200 without internet after image build.
- [ ] Three-device compatibility claim matches the devices actually tested.
