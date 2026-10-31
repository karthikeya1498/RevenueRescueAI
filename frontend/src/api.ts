/**
 * RevenueRescueAI Frontend API Client
 *
 * Provides typed, resilient communication with the RevenueRescueAI backend.
 * Handles JWT token injection, base URL configuration, loading states, and uniform error mapping.
 */

export const API_BASE_URL =
  (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

export interface HealthResponse {
  status: string;
  service: string;
  phase: string;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  role: string;
  status: string;
  last_login_at: string | null;
}

export interface DashboardMetrics {
  currency: string;
  time_range: string;
  at_risk_revenue_minor: number;
  recovered_revenue_minor: number;
  recovery_rate_pct: string;
  case_recovery_rate_pct: string;
  total_at_risk_cases: number;
  total_recovered_cases: number;
  escalated_cases: number;
  verification_pending_cases: number;
  stopped_cases: number;
  safety_rate_pct: string;
  generated_at: string;
}

export interface RevenueTrendPoint {
  timestamp: string;
  recovered_minor: number;
  at_risk_minor: number;
}

export interface RevenueTrendResponse {
  currency: string;
  interval: string;
  points: RevenueTrendPoint[];
}

export interface WorkflowStatusDistribution {
  counts: Record<string, number>;
  total_cases: number;
  generated_at: string;
}

export interface CustomerSummary {
  id: string;
  external_customer_id: string;
  display_name: string | null;
  status: string;
}

export interface TransactionSummary {
  id: string;
  external_transaction_id: string;
  amount_minor: number;
  currency: string;
  status: string;
  occurred_at: string;
}

export interface CaseSummaryItem {
  id: string;
  case_key: string;
  customer: CustomerSummary | null;
  trigger_transaction: TransactionSummary | null;
  state: string;
  priority: number;
  attempts_count: number;
  opened_at: string;
  last_state_changed_at: string;
}

export interface PaginationMetadata {
  total: number;
  page: number;
  size: number;
  pages: number;
  has_more: boolean;
}

export interface CaseListResponse {
  items: CaseSummaryItem[];
  pagination: PaginationMetadata;
}

export interface CaseDetailResponse {
  id: string;
  case_key: string;
  customer: any;
  trigger_transaction: any;
  state: string;
  priority: number;
  version: number;
  opened_at: string;
  last_state_changed_at: string;
  closed_at: string | null;
  metadata: Record<string, any>;
  attempts_count: number;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Storage helpers for Bearer JWT token handling
 */
export function getAccessToken(): string | null {
  return localStorage.getItem('rr_access_token');
}

export function setAccessToken(token: string): void {
  localStorage.setItem('rr_access_token', token);
}

export function clearTokens(): void {
  localStorage.removeItem('rr_access_token');
  localStorage.removeItem('rr_refresh_token');
}

/**
 * Core HTTP Request Wrapper with Bearer Authorization and Uniform Error Handling
 */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const token = getAccessToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Clear expired credentials
      clearTokens();
    }
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.message || errorJson.error_code || JSON.stringify(errorJson);
    } catch {
      // Body not JSON
    }
    throw new Error(`API Error [${response.status}]: ${errorDetail}`);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Exported API Methods
// ---------------------------------------------------------------------------

export const api = {
  // 1. Health & System Status
  async checkHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/api/v1/health');
  },

  async checkReadiness(): Promise<{ status: string; dependencies: Record<string, string> }> {
    return request('/ready');
  },

  // 2. Authentication & User Profile
  async login(email: string, password: string): Promise<TokenResponse> {
    const data = await request<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    localStorage.setItem('rr_refresh_token', data.refresh_token);
    return data;
  },

  async getCurrentUser(): Promise<UserProfile> {
    return request<UserProfile>('/api/v1/users/me');
  },

  async logout(): Promise<void> {
    try {
      await request('/api/v1/auth/logout', { method: 'POST' });
    } catch {
      // Clean up client state regardless of server reachability
    } finally {
      clearTokens();
    }
  },

  // 3. Authoritative Dashboard Metrics
  async getDashboardMetrics(currency = 'USD', timeRange = 'all_time'): Promise<DashboardMetrics> {
    return request<DashboardMetrics>(
      `/api/v1/dashboard/metrics?currency=${encodeURIComponent(currency)}&time_range=${encodeURIComponent(timeRange)}`
    );
  },

  async getRevenueTrend(currency = 'USD', interval = 'day'): Promise<RevenueTrendResponse> {
    return request<RevenueTrendResponse>(
      `/api/v1/dashboard/trend?currency=${encodeURIComponent(currency)}&interval=${encodeURIComponent(interval)}`
    );
  },

  async getWorkflowStatus(): Promise<WorkflowStatusDistribution> {
    return request<WorkflowStatusDistribution>('/api/v1/dashboard/workflow-status');
  },

  // 4. Recovery Cases
  async getCases(params: {
    page?: number;
    size?: number;
    state?: string;
    customerId?: string;
  } = {}): Promise<CaseListResponse> {
    const query = new URLSearchParams();
    if (params.page) query.set('page', params.page.toString());
    if (params.size) query.set('size', params.size.toString());
    if (params.state) query.set('state', params.state);
    if (params.customerId) query.set('customer_id', params.customerId);

    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request<CaseListResponse>(`/api/v1/cases${queryString}`);
  },

  async getCaseDetail(caseId: string): Promise<CaseDetailResponse> {
    return request<CaseDetailResponse>(`/api/v1/cases/${encodeURIComponent(caseId)}`);
  },
};
