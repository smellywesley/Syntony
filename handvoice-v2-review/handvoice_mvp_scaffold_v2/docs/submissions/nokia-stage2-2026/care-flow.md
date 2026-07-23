# Proposed care flow and human governance

```mermaid
flowchart LR
    A["Trained staff starts pseudonymous session"] --> B["Older adult performs 3 guided tasks"]
    B --> C["Deterministic capture-quality gate"]
    C -->|Accept| D["Motor/speech measures and synchronized timeline"]
    C -->|Retry| B
    C -->|Review needed| E["Staff stops or recaptures"]
    D --> F["Qualified reviewer considers measurements with other information"]
    F --> G["Human decides follow-up; HandVoice gives no diagnosis"]
```

## Authority boundary

- The software may accept, reject or flag recording quality using versioned rules.
- It may calculate measurements and display limitations.
- It may not diagnose, triage, recommend treatment, alter thresholds or override a human.
- A future language model may rephrase an already-decided retry instruction only
  after it beats fixed templates on a golden evaluation set.

**Workflow validation status:** OPEN — confirm operator, reviewer and downstream
action through `problem-validation.md` before submission.
