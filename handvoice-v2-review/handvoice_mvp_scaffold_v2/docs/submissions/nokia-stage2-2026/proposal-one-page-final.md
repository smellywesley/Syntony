# HandVoice — A Synchronized Motor–Speech Check for Older Adults

## Problem Definition & Context

Older adults with difficulty in hand dexterity, speech rhythm or multitasking are often observed through separate manual and speech activities in community rehabilitation. Yet daily activities—speaking while handling medication, preparing food or following instructions—demand both systems simultaneously. Separate observations and free-text notes provide no shared timeline, making change hard to compare and potentially missing difficulty under combined load. Scale makes this urgent: Singapore’s MOH (5 March 2026) calls the country “super-aged”; by 2030, one in four Singaporeans will be 65+, one in four of those seniors will be 80+, and seniors use eight times as much hospital care as younger people. WHO’s *Ageing and health* (2025) projects the global 60+ population will grow from 1.0 billion in 2020 to 1.4 billion by 2030 and 2.1 billion by 2050. Expanding caseloads consume finite professional time and constrain structured-review access. HandVoice targets brief, repeatable measurement—not diagnosis or treatment.

## Goals & Strategic Approach

The goal is to test whether one smartphone can provide a usable, repeatable view of motor–speech performance during a staff-assisted visit. A 12-week, 30-participant feasibility pilot targets at least 85% protocol completion, at least 80% usable sessions, median operator time of five minutes or less, and 100% correct accept/retry/review decisions on a predefined 30-case quality benchmark. Repeatability and agreement with human-annotated events will also be measured. Missing a threshold triggers refinement, not a clinical claim.

## Innovation & System Integration

Each participant completes three 15-second recordings: right index–thumb tapping, repeated `/pa-ta-ka/`, and both simultaneously with equal priority. On-device MediaPipe computer vision tracks 21 hand landmarks while deterministic audio analysis places candidate speech events on the same clock. HandVoice displays within-person motor and exploratory speech dual-task contrasts, an aligned timeline, and recording-quality evidence. Its innovation is one synchronized capture showing how both rhythms change together. Li et al. (2024; doi:10.1002/dad2.70025) validated component motor and speech frequencies across 20 smartphones: 90.3% of video and 98.3% of audio results were within ±1 Hz of reference instruments. Their 31-person healthy-adult study supports technical feasibility, not HandVoice’s clinical validity. Staff guide a seated participant; one technical retry is allowed only while comfortable, and qualified professionals retain all follow-up decisions. No disease score or autonomous clinical decision is produced.

## Feasibility & Execution Plan

Weeks 1–2: confirm workflow, stop criteria, privacy and annotations with rehabilitation and speech professionals. Weeks 3–5: validate quality, accessibility and latency on three smartphones against 30 benchmark cases. Weeks 6–9: after institutional approval and consent, train two staff and run the pilot using pseudonymous codes and minimum data. Weeks 10–12: analyse completion, quality, time, repeatability and annotation agreement; then issue a go/refine/stop decision. The tested prototype already supports the three tasks, synchronized report, controlled retries and offline demonstration; remaining work is validation and supervised deployment.

## Impact & Expected Outcomes

The pilot involves 30 older adults, trains two staff and produces 90 first-pass recordings. Success means at least 24 usable synchronized sessions, a precise reason for every rejected capture, and results reviewable without specialist hardware or automated diagnosis. Measures are completion, usable-session rate, staff time, stops/retries, device reliability and annotation agreement. Passing these thresholds justifies a larger clinically governed study; it does not establish improved health outcomes.

## Budget & Resource Overview

| Category | Basis | SGD |
|---|---|---:|
| Clinical and SLP review | Protocol, safety and annotation review | 4,800 |
| Participant reimbursement | 30 participants × SGD 50 | 1,500 |
| Technology and data safeguards | Three-phone validation, hosting and access controls | 2,200 |
| Accessibility, training and operations | Usability checks, two staff, materials and local travel | 3,500 |
| **Total (including 10% contingency)** | **SGD 12,000 subtotal + SGD 1,200; devices/prototype reused** | **13,200** |
