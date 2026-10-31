# Recovery Intelligence API Reference

## 1. Endpoints Overview

| Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| **`POST`** | `/api/v1/cases/{case_id}/recommendations` | `OPERATOR`, `ADMIN` | Analyses recovery case, persists `AgentDecision`, records audit event, and returns recommendation. |
| **`GET`** | `/api/v1/cases/{case_id}/recommendations/latest` | `OPERATOR`, `ADMIN`, `AUDITOR` | Retrieves the latest recommendation formulated for this recovery case. |
| **`GET`** | `/api/v1/cases/{case_id}/recommendations` | `OPERATOR`, `ADMIN`, `AUDITOR` | Retrieves the chronological history of all recommendations formulated for this case. |
| **`POST`** | `/api/v1/recovery/decision-preview` | Public / Operator | Stateless dry-run decision simulation without writing to database or mutating state. |

---

## 2. API Specifications

### Generate AI Recommendation
- **Route**: `POST /api/v1/cases/{case_id}/recommendations`
- **Request Headers**: `Authorization: Bearer <JWT>`
- **Response Status**: `201 Created`
- **Response Model**: [`CaseRecommendationDTO`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/recommendations.py)

### Get Latest Recommendation
- **Route**: `GET /api/v1/cases/{case_id}/recommendations/latest`
- **Request Headers**: `Authorization: Bearer <JWT>`
- **Response Status**: `200 OK` (or `404 Not Found` if no recommendation generated yet)
- **Response Model**: [`CaseRecommendationDTO`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/recommendations.py)

### Get Recommendation History
- **Route**: `GET /api/v1/cases/{case_id}/recommendations`
- **Request Headers**: `Authorization: Bearer <JWT>`
- **Response Status**: `200 OK`
- **Response Model**: `List[CaseRecommendationDTO]`
