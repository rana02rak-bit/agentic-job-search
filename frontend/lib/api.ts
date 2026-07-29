export type Priority = "HIGH" | "MEDIUM" | "LOW";
export type CompanySource = "USER" | "AI";
export type AtsProvider = "GREENHOUSE" | "LEVER" | "ASHBY";

export interface AtsSource {
  id: number;
  company_id: number;
  provider: AtsProvider;
  slug: string;
  enabled: boolean;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
}

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
  ats_source: AtsSource | null;
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

export interface DiscoverySourceRun {
  id: number;
  ats_source_id: number;
  status: string;
  jobs_seen: number;
  jobs_matched: number;
  jobs_created: number;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DiscoveryRun {
  id: number;
  status: string;
  companies_checked: number;
  suggestions_created: number;
  jobs_found: number;
  error: string | null;
  started_at: string;
  completed_at: string | null;
  source_runs: DiscoverySourceRun[];
}

export interface Recruiter {
  id: number;
  company_id: number;
  name: string;
  email: string | null;
  email_status: string | null;
  linkedin_url: string | null;
  source: string;
  external_id: string | null;
  designation: string | null;
  activity: string | null;
  mutuals: number;
  reply_probability: number | null;
  is_shortlisted: boolean;
  shortlisted_job_id: number | null;
  created_at: string;
}

export interface CandidateProfile {
  id: number;
  name: string;
  resume_text: string;
  positioning: string | null;
  updated_at: string;
}

export interface OutreachMessage {
  id: number;
  recruiter_id: number;
  job_id: number;
  subject: string | null;
  recipient_email: string | null;
  body: string;
  rationale: string | null;
  status: "DRAFT" | "APPROVED" | "SENDING" | "SENT" | "REPLIED" | "REJECTED";
  delivery_mode: string;
  delivery_error: string | null;
  provider_message_id: string | null;
  provider_thread_id: string | null;
  generated_at: string;
  approved_at: string | null;
  sent_at: string | null;
  replied_at: string | null;
  recruiter: Recruiter;
  job: Job;
}

export interface DeliveryCapabilities {
  automatic_linkedin_send: boolean;
  mode: string;
  connectsafely_configured: boolean;
  account_connected: boolean;
  account_name: string | null;
  daily_limit: number;
  sent_today: number;
  reason: string | null;
}

export interface IntegrationStatus {
  ai_provider: string;
  ai_configured: boolean;
  gemini_configured: boolean;
  openai_configured: boolean;
  connectsafely_configured: boolean;
  connectsafely_account_connected: boolean;
  connectsafely_account_name: string | null;
  connectsafely_error: string | null;
  ready_for_contact_discovery: boolean;
  ready_for_linkedin_sending: boolean;
  missing: string[];
}

export interface ContactDiscoveryResult {
  company_id: number;
  discovered: number;
  stored: number;
  skipped_duplicates: number;
  people: Recruiter[];
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
  allJobs: () => request<Job[]>("/api/jobs"),
  stats: () => request<DashboardStats>("/api/dashboard/stats"),
  discoveryRuns: (limit = 5) =>
    request<DiscoveryRun[]>(`/api/discovery/runs?limit=${limit}`),
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
  discover: (count = 5, autoShortlist = false) =>
    request<Company[]>("/api/discovery/suggest", {
      method: "POST",
      body: JSON.stringify({
        count,
        auto_shortlist: autoShortlist,
        minimum_score: 35,
      }),
    }),
  syncJobs: () =>
    request<DiscoveryRun>("/api/discovery/sync", {
      method: "POST",
    }),
  saveAtsSource: (companyId: number, provider: AtsProvider, slug: string) =>
    request<AtsSource>(`/api/companies/${companyId}/ats-source`, {
      method: "PUT",
      body: JSON.stringify({ provider, slug }),
    }),
  removeAtsSource: (companyId: number) =>
    request<void>(`/api/companies/${companyId}/ats-source`, {
      method: "DELETE",
    }),
  recruiters: () => request<Recruiter[]>("/api/recruiters"),
  addRecruiter: (payload: {
    company_id: number;
    name: string;
    email?: string;
    linkedin_url?: string;
    designation?: string;
    activity?: string;
    mutuals?: number;
  }) =>
    request<Recruiter>("/api/recruiters", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  discoverRecruiters: (payload: {
    company_id: number;
    job_id?: number;
    limit: number;
  }) =>
    request<ContactDiscoveryResult>("/api/recruiters/discover", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  shortlistRecruiter: (id: number, jobId?: number) =>
    request<Recruiter>(`/api/recruiters/${id}/shortlist`, {
      method: "POST",
      body: JSON.stringify({ job_id: jobId }),
    }),
  removeRecruiterShortlist: (id: number) =>
    request<void>(`/api/recruiters/${id}/shortlist`, {
      method: "DELETE",
    }),
  profile: () => request<CandidateProfile>("/api/outreach/profile"),
  saveProfile: (payload: { name: string; resume_text: string; positioning?: string }) =>
    request<CandidateProfile>("/api/outreach/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  outreachMessages: () => request<OutreachMessage[]>("/api/outreach/messages"),
  outreachCapabilities: () =>
    request<DeliveryCapabilities>("/api/outreach/capabilities"),
  integrationStatus: () =>
    request<IntegrationStatus>("/api/integrations/status"),
  generateOutreach: (payload: {
    recruiter_id: number;
    job_id: number;
    extra_context?: string;
  }) =>
    request<OutreachMessage>("/api/outreach/messages", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  editOutreach: (id: number, subject: string, body: string) =>
    request<OutreachMessage>(`/api/outreach/messages/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ subject, body }),
    }),
  approveOutreach: (id: number) =>
    request<{
      message: OutreachMessage;
      linkedin_url: string;
      automatic_send_available: boolean;
    }>(
      `/api/outreach/messages/${id}/approve`,
      { method: "POST" },
    ),
  autoSendOutreach: (id: number) =>
    request<OutreachMessage>(`/api/outreach/messages/${id}/send`, {
      method: "POST",
    }),
  markOutreachSent: (id: number) =>
    request<OutreachMessage>(`/api/outreach/messages/${id}/mark-sent`, {
      method: "POST",
    }),
  markOutreachReplied: (id: number) =>
    request<OutreachMessage>(`/api/outreach/messages/${id}/mark-replied`, {
      method: "POST",
    }),
};
