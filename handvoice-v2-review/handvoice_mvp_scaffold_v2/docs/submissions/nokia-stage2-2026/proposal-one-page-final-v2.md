# HandVoice — A Synchronized Motor–Speech Check for Older Adults

## Problem Definition & Context

Community rehabilitation staff often observe older adults’ hand dexterity, speech rhythm and multitasking through separate activities. Yet daily actions—speaking while handling medication, preparing food or following instructions—load movement and speech simultaneously. Separate notes have no shared clock, making change difficult to compare and potentially missing combined-load difficulty. **Evidence of scale:** Singapore’s MOH (5 March 2026) calls the country “super-aged”; by 2030, one in four Singaporeans will be 65+, one in four of those seniors will be 80+, and seniors use eight times as much hospital care as younger people. WHO’s *Ageing and health* (2025) projects the global 60+ population will grow from 1.0 billion in 2020 to 2.1 billion by 2050. Without scalable measurement, this access and documentation gap expands with the ageing caseload. HandVoice targets measurement—not diagnosis or treatment.

## Goals & Strategic Approach

HandVoice will test whether one smartphone can produce a usable, repeatable motor–speech measurement during a five-minute staff-assisted visit. The strategy combines three fixed tasks, within-person baselines, deterministic quality control and human interpretation. A 12-week, 30-participant pilot uses predefined completion, quality, latency, repeatability and annotation-agreement gates. Missing a gate triggers refinement or stopping—not a clinical claim.

## Innovation & System Integration

Participants record 15 seconds each of right index–thumb tapping, repeated `/pa-ta-ka/`, and both with equal priority. On-device MediaPipe tracks 21 hand landmarks; deterministic audio timestamps speech events on the same clock. HandVoice renders direction-aware motor and exploratory speech dual-task contrasts on one aligned timeline. Novelty combines simultaneous motor–speech loading, within-person comparison, synchronized explainability and transparent `accept/retry/review` evidence from one ordinary phone. **Technical precedent:** Li et al. (2024; doi:10.1002/dad2.70025) tested 20 phones; 90.3% of video and 98.3% of audio frequency results were within ±1 Hz of reference instruments. Their 31-person healthy-adult study supports component technology, not HandVoice’s clinical validity. Integration stays human-governed: staff obtain consent, position the participant, permit one comfort-dependent retry and review the timeline; qualified professionals retain follow-up decisions. Processing is reproducible without a cloud LLM. No disease score, treatment recommendation or autonomous clinical action is produced.

## Feasibility & Execution Plan

**Weeks 1–2 — Protocol gate:** rehabilitation and speech professionals confirm wording, stop criteria, annotations, privacy and the action a result may support. **Weeks 3–5 — Engineering gate:** three phones must achieve 100% expected `accept/retry/review` decisions on 30 benchmark cases, ≤20% rejection of known-good captures and p95 report latency ≤10 seconds. **Weeks 6–9 — Supervised pilot:** after institutional approval and consent, two trained staff run 30 seated older adults using pseudonymous codes, minimum data and participant-controlled stopping. **Weeks 10–12 — Decision gate:** analyse completion, usability, staff time, retries/stops, repeatability and annotation agreement; issue a go/refine/stop decision. The prototype already implements the tasks, synchronized report, controlled retries and offline demonstration; remaining work is governance and validation.

## Impact & Expected Outcomes

The pilot involves 30 older adults, trains two staff and produces 90 first-pass recordings. Success requires ≥85% completion, ≥80% usable sessions (at least 24 participants), median operator time ≤5 minutes, a precise reason for every rejection and reviewable results without specialist hardware. Older adults gain structured, low-burden measurement using familiar equipment; staff gain comparable records and recovery guidance; services learn whether a five-minute community workflow can scale. Success justifies a clinically governed multi-site study. It does not establish diagnosis, treatment benefit, hospital-use reduction or improved quality of life.

## Budget & Resource Overview

| Cost item | SGD | Cost item | SGD |
|---|---:|---|---:|
| Clinical and SLP review | 4,800 | Participant reimbursement (30 × 50) | 1,500 |
| Three-phone device validation | 1,200 | Secure hosting and data controls | 1,000 |
| Accessibility and two-staff training | 2,000 | Materials, local travel and operations | 1,500 |
| **Subtotal** | **12,000** | **Contingency (10%)** | **1,200** |
| **Total 12-week pilot budget** |  |  | **13,200** |
