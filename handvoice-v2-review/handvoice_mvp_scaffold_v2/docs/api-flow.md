# Executable API workflow

```mermaid
sequenceDiagram
    participant App as Capture App
    participant API as FastAPI
    participant Media as Local Controlled Media Root
    participant DB as PostgreSQL

    App->>API: POST /v1/participants + API key
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
    API->>API: Derive hand/audio events and features
    API->>DB: Persist recording, events and features
    API-->>App: analyzed_synchronously
    App->>API: GET /sessions/{id}/report
    API-->>App: Hand DTC, speech DTC and exploratory coupling
    App->>API: GET /sessions/{id}/visualization
    API-->>App: Synchronized hand/DDK timeline
```

## Repeat rule

`POST /v1/task-instances/{id}/repeat` creates repetition 2 only when repetition 1 is already accepted. The initial session never creates six recordings automatically.

## Security boundary

The validation prototype uses one configured API key, bounded uploads, generated storage keys and a contained local media root. It is not a multi-tenant production authorization model.
