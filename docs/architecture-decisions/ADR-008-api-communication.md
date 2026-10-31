# ADR-008: API Communication — RESTful Contracts & Real-Time WebSockets

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Senior Full-Stack Engineer, Principal Architect  

---

## 1. Context
The frontend dashboard requires low-latency updates for live recovery cases, agent decision traces, and evaluation progress, while external/simulator webhook sources send discrete event notifications.

## 2. Problem
Which communication protocols should govern client-to-server and provider-to-server interactions?

## 3. Options Considered
1. **Pure REST with Polling:** Standard HTTP GET polling every 2–5 seconds from the browser.
2. **GraphQL:** Flexible client-specified query schemas with GraphQL subscriptions.
3. **Hybrid REST + Real-Time WebSocket Streaming:** RESTful endpoints for CRUD/command operations and persistent WebSockets for live event broadcasting.
4. **gRPC-Web:** Protocol buffers over HTTP/2.

## 4. Decision
We choose **RESTful JSON Contracts paired with a Real-Time WebSocket Stream (`/api/v1/ws/realtime`)**.

## 5. Reasons
- **Industry Standard for Fintech:** REST with Pydantic v2 schemas is universal, easy to debug in browser network tabs, and supported by all payment gateways for webhook delivery.
- **Low-Latency Dashboard Updates:** A lightweight WebSocket connection pushes state changes, trace steps, and evaluation metrics to the frontend in real time, eliminating wasteful HTTP polling.
- **Zero GraphQL Overhead:** GraphQL introduces complex query parsing, caching difficulties, N+1 query risks, and unnecessary schema compilation layers for an application with fixed dashboard views.
- **Automatic Documentation:** FastAPI generates OpenAPI (Swagger) documentation automatically for all REST routes.

## 6. Trade-offs & Consequences
- **Positive:** Intuitive for junior engineers, instant UI responsiveness, clean separation of commands (REST) and events (WebSocket).
- **Negative:** WebSocket connections require reconnection handling on the client side (implemented with exponential backoff in `frontend/src/realtime.ts`).

## 7. Reconsideration Conditions
Re-evaluate Server-Sent Events (SSE) if corporate firewalls block bidirectional WebSocket handshakes.
