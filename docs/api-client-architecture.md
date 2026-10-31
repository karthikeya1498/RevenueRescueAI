# API Client Architecture — Phase 2.5

## 1. Overview and Design Principles
To prevent individual React components from making ad-hoc `fetch()` calls or duplicating authentication header injection, all HTTP communication in RevenueRescueAI is centralized within a reusable, strongly-typed API client module located at [`frontend/src/api.ts`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/frontend/src/api.ts).

### Key Architectural Tenets:
1. **Centralized Authentication Injection**: Bearer tokens are stored in `localStorage` under a standard key (`rr_access_token`) and automatically appended to the `Authorization` header on all protected requests.
2. **Single Point of Base URL Configuration**: Reads from `import.meta.env.VITE_API_BASE_URL` with fallback to `http://localhost:8000`.
3. **Strict TypeScript Typing**: Every API call returns a typed Promise (`DashboardMetricsResponse`, `CaseListResponse`, etc.), ensuring compile-time safety across UI components.
4. **Uniform Error Handling**: Non-2xx HTTP responses parse RFC-7807 structured JSON bodies and throw structured `Error` objects with informative user-facing messages.

---

## 2. API Client Structure & Methods

```typescript
// frontend/src/api.ts Architecture Outline

export interface ApiClientConfig {
  baseUrl: string;
}

export class ApiClient {
  private baseUrl: string;

  // Token Management
  public setToken(token: string | null): void;
  public getToken(): string | null;

  // Generic Request Dispatcher
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T>;

  // Health APIs
  public async getHealth(): Promise<{ status: string; uptime_seconds?: number }>;
  public async getReadiness(): Promise<{ status: string; database: string }>;

  // Authentication & User Profile
  public async getCurrentUser(): Promise<UserProfile>;
  public async login(credentials: LoginRequest): Promise<AuthTokenResponse>;

  // Dashboard Aggregates
  public async getDashboardMetrics(): Promise<DashboardMetricsResponse>;
  public async getRevenueTrend(days?: number): Promise<RevenueTrendResponse>;
  public async getWorkflowDistribution(): Promise<Record<string, number>>;

  // Recovery Cases
  public async getCases(params?: {
    state?: string;
    page?: number;
    limit?: number;
  }): Promise<CaseListResponse>;
  public async getCaseDetail(caseId: string): Promise<CaseDetailResponse>;
}

export const api = new ApiClient();
```

---

## 3. Usage Pattern in React Components

```tsx
import React, { useEffect, useState } from "react";
import { api, DashboardMetricsResponse } from "./api";

export const MetricsSummaryCard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetricsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    api.getDashboardMetrics()
      .then((data) => {
        if (isMounted) {
          setMetrics(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => { isMounted = false; };
  }, []);

  if (loading) return <div className="skeleton-card" />;
  if (error) return <div className="error-card">{error}</div>;

  return (
    <div className="metric-card">
      <span className="label">Recovered Revenue</span>
      <span className="value">
        ${((metrics?.recovered_amount_minor || 0) / 100).toLocaleString()}
      </span>
    </div>
  );
};
```
