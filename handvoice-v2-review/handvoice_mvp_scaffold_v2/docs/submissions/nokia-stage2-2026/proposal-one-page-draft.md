# HandVoice — A Synchronized Motor–Speech Check for Older Adults

## Problem Definition & Context

Older adults with difficulty in hand dexterity, speech rhythm or multitasking are often observed through separate manual and speech activities in community rehabilitation. Yet daily activities, such as speaking while handling medication or preparing food, demand both systems simultaneously. Separate observations and free-text notes provide no shared timeline, making change hard to compare and potentially missing difficulty under combined load. HandVoice targets trained staff supporting adults aged 65+ in community rehabilitation or ageing-care settings. It provides a brief, repeatable functional measurement; it does not diagnose disease or recommend treatment.

## Goals & Strategic Approach

The goal is to determine whether one standard smartphone can provide a usable, repeatable view of motor–speech performance during a staff-assisted visit. A proposed 12-week, 30-participant feasibility pilot targets at least 85% protocol completion, at least 80% usable sessions, median operator time of five minutes or less, and exact agreement with a predefined 30-case quality benchmark. Repeatability and agreement with human-annotated events will also be measured. Missing a threshold triggers refinement, not a clinical claim.

## Innovation & System Integration

Each participant completes three 15-second recordings: right index–thumb tapping, repeated `/pa-ta-ka/`, and both simultaneously with equal priority. On-device MediaPipe computer vision tracks 21 hand landmarks while deterministic audio analysis places candidate speech events on the same clock. HandVoice displays within-person motor and exploratory speech dual-task contrasts, an aligned timeline, and recording-quality evidence. Its novelty is one synchronized capture showing how both rhythms change together. A trained staff member obtains consent, guides the seated participant and reviews the result. Technical failure permits one repeat only if the participant remains comfortable; limited performance goes to human review. A qualified professional chooses repeat observation or an existing assessment pathway. No disease score or autonomous clinical decision is produced.

## Feasibility & Execution Plan

Weeks 1–2: confirm workflow, wording, stop criteria, privacy and reference annotations with rehabilitation and speech professionals. Weeks 3–5: validate quality, accessibility and latency on three representative test smartphones against 30 benchmark cases. Weeks 6–9: after institutional approval and informed consent, train two staff and run the 30-participant pilot using pseudonymous codes and minimum data. Weeks 10–12: analyse completion, quality, operator time, repeatability and annotation agreement; then issue a go/refine/stop decision. The tested prototype already supports the three-task path, synchronized report, controlled retries and offline demonstration, limiting new work to validation and supervised deployment.

## Impact & Expected Outcomes

The pilot involves 30 older adults, trains two staff and produces 90 first-pass recordings. Success means at least 24 participants yield a usable synchronized session during a routine visit, every rejected capture has a precise reason, and performance is reviewable without specialist hardware or automated diagnosis. Measures are completion, usable-session rate, staff time, participant stops/retries, device reliability and annotation agreement. Passing the thresholds supports a low-equipment community measurement study; broader healthcare-impact claims require a clinically governed trial.

## Budget & Resource Overview

Estimated 12-week pilot budget: **SGD 13,200**—clinical and speech review, SGD 4,800; participant reimbursement, SGD 1,500 (30 × SGD 50); device testing, SGD 1,200; secure hosting/data controls, SGD 1,000; accessibility and staff training, SGD 2,000; operations, SGD 1,500; and 10% contingency, SGD 1,200. Existing smartphones and the open-source prototype are reused; quotations will be confirmed before deployment.
