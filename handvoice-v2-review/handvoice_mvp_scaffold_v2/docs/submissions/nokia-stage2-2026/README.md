# Nokia Stage 2 2026 — controlled submission package

**Status:** draft; not yet safe to submit.

This folder separates measured engineering evidence from proposed pilot claims.
No interview, clinician decision, device result, budget quote or older-adult
outcome is treated as complete until its checklist row has an owner, date and
source.

## Gate order

1. `requirements-checklist.md`
2. `problem-validation.md`
3. `claims-register.md` and `novelty-matrix.md`
4. `device-qc-latency-evidence.md`
5. `security-data-gate.md`
6. `stage3-pilot-budget.md`
7. `proposal-one-page-draft.md`
8. `video-script.md`
9. `red-team-checklist.md` and `submission-checklist.md`

## One-page proposal artifacts

- `Nokia_Stage2_HandVoice_One_Page_Proposal.docx` — Aptos 12 pt,
  single-spaced; Microsoft Word verified one page.
- `Nokia_Stage2_HandVoice_One_Page_Proposal.pdf` — one page with embedded
  Aptos and Aptos Bold fonts; visually inspected.
- `proposal-one-page-final-v2.md` — canonical evidence-integrated source for
  the current DOCX and PDF; expands the three 20%-weighted judging sections.
- `Nokia_Stage2_HandVoice_One_Page_Proposal_v3.*` — current versioned
  artifacts with the fully itemised six-category budget restored.
- `Stage-2_Case_Guidelines.pdf` — archived primary requirements source.

The Stage 2 implementation remains an engineering-validation prototype. It
does not diagnose, screen for or predict Parkinson's disease or any other
condition.

## Rebuild the controlled proposal artifacts

```powershell
python -m pip install -e ".[documents]"
python .\scripts\generate_submission_documents.py
```

The generator fails if the draft is outside 550-650 words or the review PDF is
not exactly one page. The final Aptos PDF export and visual inspection remain a
submission-machine gate.
