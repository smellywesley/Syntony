# Architecture decisions

## ADR-001: One synchronized MP4

Audio and video share a media timeline so event-level coupling is technically defensible.

## ADR-002: Modular monolith first

The MVP uses one API and asynchronous processing workers. Splitting every pipeline into network microservices would increase operational failure modes before throughput justifies it.

## ADR-003: Deterministic measurement first

Motor and speech features remain independently auditable. Neural classifiers are excluded from the MVP.

## ADR-004: Feature-family quality gates

A recording can be usable for timing while unusable for absolute intensity. Quality is not collapsed into one pass/fail bit.

## ADR-005: Coupling requires a null model

Temporal coincidence is compared with circular-shift permutations to reduce false interpretation of chance alignment.
