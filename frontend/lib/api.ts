export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type CompanySource = "USER" | "AI";

export interface Company {
  id: number;
  name: string;
  website: string | null;
  industry: string | null;
  location: string | null;
  source: CompanySource;
  priority: Priority;
  is_watchlisted: boolean;
  funding_score: number;
  hiring_score: number;
  ai_score: number;
  location_score: number;
  role_match_score: number;
  total_score: number;
  score_reason: string | null;
  last_checked: string | null;
  created_at: string;
}

export interface Job {
  id: number;
  company_id: number;
  title: string;
  location: string;
  url: string;
  source: string;
  status: string;
  posted_at: string | null;
  discovered_at: string;
  company: Company;
}

export interface DashboardStats {
  companies: number;
  watchlisted: number;
  jobs_found: number;
  recruiters_found: number;
  messages_ready: number;
  messages_sent: number;
  replies: number;
  referrals: number;
  interviews: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  companies: () => request<Company[]>("/api/companies"),
  jobs: () => request<Job[]>("/api/jobs?today_only=true"),
  stats: () => request<DashboardStats>("/api/dashboard/stats"),
  addCompany: (payload: {
    name: string;
    website?: string;
    location?: string;
    priority: Priority;
  }) =>
    request<Company>("/api/companies", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateCompany: (id: number, payload: Partial<Pick<Company, "priority" | "is_watchlisted">>) =>
    request<Company>(`/api/companies/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  removeCompany: (id: number) =>
    request<void>(`/api/companies/${id}`, {
      method: "DELETE",
    }),
  discover: (count = 5) =>
    request<Company[]>("/api/discovery/suggest", {
      method: "POST",
      body: JSON.stringify({ count }),
    }),
};

