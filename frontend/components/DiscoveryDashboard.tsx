"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  AtsProvider,
  Company,
  DashboardStats,
  DiscoveryRun,
  Job,
  Priority,
} from "@/lib/api";
import { CompanyCard } from "./CompanyCard";
import { MetricCard } from "./MetricCard";

const emptyStats: DashboardStats = {
  companies: 0,
  watchlisted: 0,
  jobs_found: 0,
  recruiters_found: 0,
  messages_ready: 0,
  messages_sent: 0,
  replies: 0,
  referrals: 0,
  interviews: 0,
};

async function fetchDashboardData() {
  const [companies, jobs, stats, runs] = await Promise.all([
    api.companies(),
    api.jobs(),
    api.stats(),
    api.discoveryRuns(5),
  ]);
  return { companies, jobs, stats, runs };
}

export function DiscoveryDashboard() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<DashboardStats>(emptyStats);
  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [location, setLocation] = useState("Bangalore");
  const [priority, setPriority] = useState<Priority>("HIGH");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchDashboardData();
      setCompanies(data.companies);
      setJobs(data.jobs);
      setStats(data.stats);
      setRuns(data.runs);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the dashboard.");
    }
  }, []);

  useEffect(() => {
    let active = true;
    void fetchDashboardData()
      .then((data) => {
        if (!active) return;
        setCompanies(data.companies);
        setJobs(data.jobs);
        setStats(data.stats);
        setRuns(data.runs);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Could not load the dashboard.");
      });
    return () => {
      active = false;
    };
  }, []);

  const watchlist = useMemo(
    () => companies.filter((company) => company.is_watchlisted),
    [companies],
  );
  const suggestions = useMemo(
    () => companies.filter((company) => company.source === "AI" && !company.is_watchlisted),
    [companies],
  );
  const latestRun = runs[0];

  async function submitCompany(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.addCompany({
        name: name.trim(),
        website: website.trim() || undefined,
        location: location.trim() || undefined,
        priority,
      });
      setName("");
      setWebsite("");
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add the company.");
    } finally {
      setBusy(false);
    }
  }

  async function updateCompany(id: number, payload: { priority?: Priority; is_watchlisted?: boolean }) {
    setError(null);
    try {
      await api.updateCompany(id, payload);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update the company.");
    }
  }

  async function removeCompany(id: number) {
    setError(null);
    try {
      await api.removeCompany(id);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not remove the company.");
    }
  }

  async function discover() {
    setBusy(true);
    setError(null);
    try {
      await api.discover(5);
      await load();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "AI discovery is unavailable. Your watchlist still works.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function syncJobs() {
    setBusy(true);
    setError(null);
    try {
      await api.syncJobs();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not sync live jobs.");
    } finally {
      setBusy(false);
    }
  }

  async function saveAtsSource(companyId: number, provider: AtsProvider, slug: string) {
    setError(null);
    try {
      await api.saveAtsSource(companyId, provider, slug);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not connect the job board.");
    }
  }

  async function removeAtsSource(companyId: number) {
    setError(null);
    try {
      await api.removeAtsSource(companyId);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not disconnect the job board.");
    }
  }

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#" aria-label="RahulGPT dashboard">
          <span className="brand-mark">R</span>
          <span>
            Rahul<span>GPT</span>
          </span>
        </a>
        <nav aria-label="Primary navigation">
          <a className="active" href="#discovery">
            Discovery
          </a>
          <a href="#jobs">Jobs</a>
          <a href="#recruiters">Recruiters</a>
          <a href="#outreach">Outreach</a>
        </nav>
        <div className="profile-pill">RR</div>
      </header>

      <section className="hero" id="discovery">
        <div>
          <p className="eyebrow">Wednesday intelligence brief</p>
          <h1>Find the roles worth chasing.</h1>
          <p className="hero__copy">
            Your target companies stay in focus. AI adds new possibilities; you decide what enters
            the pipeline.
          </p>
        </div>
        <div className="hero__actions">
          <button className="button button--primary" onClick={syncJobs} disabled={busy}>
            <span aria-hidden="true">↻</span> {busy ? "Working…" : "Sync live jobs"}
          </button>
          <button className="button button--secondary" onClick={discover} disabled={busy}>
            Find AI companies
          </button>
          {latestRun && (
            <span className={`run-status run-status--${latestRun.status.toLowerCase()}`}>
              Last run: {latestRun.status.replaceAll("_", " ").toLowerCase()} ·{" "}
              {latestRun.jobs_found} new jobs
            </span>
          )}
        </div>
      </section>

      {error && (
        <div className="notice" role="alert">
          <span>!</span>
          <p>{error}</p>
          <button onClick={() => setError(null)} aria-label="Dismiss notification">
            ×
          </button>
        </div>
      )}

      <section className="metrics" aria-label="Pipeline metrics">
        <MetricCard label="Target companies" value={stats.watchlisted} accent />
        <MetricCard label="Jobs found" value={stats.jobs_found} />
        <MetricCard label="Recruiters found" value={stats.recruiters_found} />
        <MetricCard label="Messages ready" value={stats.messages_ready} />
        <MetricCard label="Replies" value={stats.replies} />
      </section>

      <section className="content-grid">
        <div className="content-main">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Always checked</p>
              <h2>My watchlist</h2>
            </div>
            <span>{watchlist.length} companies</span>
          </div>

          <form className="add-company" onSubmit={submitCompany}>
            <div className="field field--wide">
              <label htmlFor="company-name">Company</label>
              <input
                id="company-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Sarvam AI"
                required
              />
            </div>
            <div className="field field--wide">
              <label htmlFor="company-website">Website</label>
              <input
                id="company-website"
                type="url"
                value={website}
                onChange={(event) => setWebsite(event.target.value)}
                placeholder="https://…"
              />
            </div>
            <div className="field">
              <label htmlFor="company-location">Location</label>
              <select
                id="company-location"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
              >
                <option>Bangalore</option>
                <option>Gurgaon</option>
                <option>Mumbai</option>
                <option>Remote</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="company-priority">Priority</label>
              <select
                id="company-priority"
                value={priority}
                onChange={(event) => setPriority(event.target.value as Priority)}
              >
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>
            <button className="button button--dark" disabled={busy}>
              + Add company
            </button>
          </form>

          <div className="company-grid">
            {watchlist.map((company) => (
              <CompanyCard
                key={company.id}
                company={company}
                onPriorityChange={(nextPriority) =>
                  updateCompany(company.id, { priority: nextPriority })
                }
                onRemove={() => removeCompany(company.id)}
                onAtsSave={(provider, slug) => saveAtsSource(company.id, provider, slug)}
                onAtsRemove={() => removeAtsSource(company.id)}
              />
            ))}
            {watchlist.length === 0 && (
              <div className="empty-state">
                <strong>Your watchlist is empty.</strong>
                <p>Add the first company above. It will be checked on every discovery run.</p>
              </div>
            )}
          </div>

          <div className="section-heading section-heading--spaced">
            <div>
              <p className="eyebrow">New possibilities</p>
              <h2>AI suggestions</h2>
            </div>
            <span>Verify before applying</span>
          </div>

          <div className="company-grid">
            {suggestions.map((company) => (
              <CompanyCard
                key={company.id}
                company={company}
                onAddToWatchlist={() =>
                  updateCompany(company.id, { is_watchlisted: true, priority: "MEDIUM" })
                }
              />
            ))}
            {suggestions.length === 0 && (
              <div className="empty-state">
                <strong>No AI suggestions yet.</strong>
                <p>
                  Add an OpenAI API key locally, then run discovery. Manual watchlist features do
                  not need a key.
                </p>
              </div>
            )}
          </div>
        </div>

        <aside id="jobs">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Last 24 hours</p>
              <h2>Today&apos;s jobs</h2>
            </div>
            <span>{jobs.length}</span>
          </div>
          <div className="job-list">
            {jobs.map((job) => (
              <article className="job-card" key={job.id}>
                <p>{job.company.name}</p>
                <h3>{job.title}</h3>
                <span>{job.location}</span>
                <a href={job.url} target="_blank" rel="noreferrer">
                  View role <span aria-hidden="true">↗</span>
                </a>
              </article>
            ))}
            {jobs.length === 0 && (
              <div className="empty-state empty-state--aside">
                <strong>No jobs stored yet.</strong>
                <p>Connect a company&apos;s ATS board, then sync live jobs.</p>
              </div>
            )}
          </div>

          <div className="profile-summary">
            <p className="eyebrow">RahulGPT profile</p>
            <h3>What the ranking agent optimizes for</h3>
            <div className="tag-cloud">
              <span>AI Product</span>
              <span>Founder&apos;s Office</span>
              <span>Strategy</span>
              <span>Consumer</span>
              <span>Bangalore first</span>
              <span>High ownership</span>
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
