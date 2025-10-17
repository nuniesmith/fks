# ADR-001: Target High-Level System Topology

Status: Draft
Date: 2025-08-19
Decision Drivers: Modularity, Observability, Code Generation, Performance Budgets, Maintainability

## Context

The FKS system spans React (frontend), Python services (API, data ingestion, strategy engine), C# (NinjaTrader integration), and assorted infrastructure (Docker Compose, scripts). Existing docs are fragmented with historical and superseded deployment notes. A unified, concise topology reference is required for ongoing refactor phases.

## Decision

Adopt a layered, service-oriented topology with explicit boundaries and code generation bridges:

- Frontend (React) -> API Gateway (Python) over HTTPS/JSON + WebSocket
- API Gateway -> Internal services via gRPC or async message bus (TBD: NATS vs Redis Streams)
- Strategy Engine exposes strategy metadata via Python decorators which feed a codegen pipeline producing C# NinjaTrader strategy stubs
- Observability plane (OpenTelemetry Collector, Prometheus) spans all runtime services
- Shared domain contracts defined once (Pydantic models / protobuf) and code-generated across language boundaries

## Topology Diagram (Textual)

```text
[ React SPA ] --HTTPS/WS--> [ API Gateway ] --gRPC/Events--> [ Data Service ]
                                           |                [ Strategy Engine ]
                                           |--Codegen JSON-->[ C# Generated Stubs (NinjaTrader) ]

[ Observability Collector ] <-- OTLP -- All Services
[ Prometheus ] <--- Metrics ---/
[ Grafana ] dashboards
```

## Consequences

- Clear separation reduces coupling and accelerates independent deploys
- Single source-of-truth for contracts enables safer evolution
- Codegen shrinks manual C# maintenance surface
- Introduces codegen & schema management overhead
- Requires investment in observability plumbing early

## Alternatives Considered

1. Keep current ad-hoc integration (Rejected: scaling & maintainability issues)
2. Monolith merge (Rejected: slows parallel work and experimentation)

## Follow-Up Tasks

- Select internal messaging (NATS vs Redis Streams benchmark)
- Define contract schema format (protobuf vs pure Pydantic + JSON schema export)
- Implement codegen MVP (see Phase 4)
- Add README diagram (mermaid) once stack stabilizes
- Integrate Python `codegen` module into CI (verify generated artifacts up-to-date)

## References

- Frontend Refactor Plan (superseded sections consolidated here)
- Multiple legacy deployment docs (archived)
