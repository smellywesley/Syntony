# Executable API workflow

```mermaid
sequenceDiagram
    participant App as Capture App
    participant API as FastAPI
    participant Media as Local Controlled Media Root
    participant DB as PostgreSQL

    App->>API: POST /v1/participants + operator bearer key
    API->>DB: Create pseudonymous participant
    App->>API: POST /v1/sessions
    API->>DB: Lock participant and allocate unique session number
    API-->>App: Three first-pass task instances
    App->>App: Capture 15-second A/V + local hand landmarks
    App->>API: POST /v1/media with synchronized media
    API->>Media: Store under generated contained key + SHA-256
    API-->>App: Media key and checksum
    App->>API: POST /task-instances/{id}/measure
    API->>Media: Resolve contained storage key
    API->>Media: Verify SHA-256 and ffprobe A/V tracks
    API->>API: Derive events, features and deterministic QC
    alt Quality accepted
        API->>DB: Persist recording, events and features
        API-->>App: accepted + quality metrics
    else Retry or review needed
        API->>Media: Delete rejected upload safely
        API-->>App: Structured reason codes; task remains pending
    end
    App->>API: GET /sessions/{id}/report
    API-->>App: Hand DTC, speech DTC and exploratory coupling
    App->>API: GET /sessions/{id}/visualization
    API-->>App: Synchronized hand/DDK timeline
```

## Repeat rule

`POST /v1/task-instances/{id}/repeat` creates repetition 2 only when repetition 1 is already accepted. The initial session never creates six recordings automatically.

## Security boundary

Every `/v1` route requires a hashed, revocable operator/site key. The participant
never enters a credential. Bounded uploads, generated storage keys and a
contained local media root protect the competition demo, but this remains a
local engineering prototype rather than clinical production authorization.
