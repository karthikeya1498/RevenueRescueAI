# ADR-010: Deployment Approach — Containerized Docker Compose

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** DevOps Engineer, Principal Software Architect  

---

## 1. Context
RevenueRescueAI must transition reliably from a developer's local laptop to staging and production environments without "works on my machine" discrepancies.

## 2. Problem
What is the minimum practical deployment topology that satisfies production reliability, isolation, and security without unnecessary cloud infrastructure costs?

## 3. Options Considered
1. **Bare Metal / Virtual Machine Manual Deploy:** Installing Python, Node, and Postgres directly on a VM.
2. **Kubernetes (EKS / GKE) Cluster:** Complex container orchestration with Helm charts and service meshes.
3. **Containerized Multi-Stage Docker Compose:** Multi-stage Dockerfiles for backend and frontend, orchestrated via a single declarative `docker-compose.yml`.
4. **Serverless (AWS Lambda / Vercel):** Distributed functions with API Gateway.

## 4. Decision
We choose **Containerized Multi-Stage Docker Compose** for staging/single-host production, paired with native local virtual environments for day-to-day development.

## 5. Reasons
- **Zero Configuration Drift:** The `docker-compose.yml` orchestrates the exact versions of Python 3.11/3.14, FastAPI, and PostgreSQL 16 Alpine, matching production environment variables and networking.
- **Cost Conscious:** Runs on a standard $10–$20/month cloud virtual private server (VPS) or local machine without incurring hundreds of dollars in Kubernetes control-plane fees.
- **Fast Startup & Healthchecks:** Postgres healthcheck ensures the backend container starts only after the database is ready to accept connections.
- **Interview Defensibility:** Demonstrates that the team avoids premature overengineering (Kubernetes) while adhering to professional containerization standards.

## 6. Trade-offs & Consequences
- **Positive:** Single-command startup (`docker compose up --build`), reproducible builds, isolated persistent volume (`postgres-data`).
- **Negative:** Horizontal auto-scaling across multiple cloud availability zones is manual rather than automated.

## 7. Reconsideration Conditions
Re-evaluate Kubernetes or managed container platforms (AWS ECS / Google Cloud Run) if application traffic requires automated multi-region scaling and high-availability multi-node clustering.
