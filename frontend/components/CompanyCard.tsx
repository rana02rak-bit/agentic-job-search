import { FormEvent, useState } from "react";
import type { AtsProvider, Company, Priority } from "@/lib/api";

interface CompanyCardProps {
  company: Company;
  onPriorityChange?: (priority: Priority) => void;
  onRemove?: () => void;
  onAddToWatchlist?: () => void;
  onAtsSave?: (provider: AtsProvider, slug: string) => Promise<void>;
  onAtsRemove?: () => Promise<void>;
}

const priorityLabels: Record<Priority, string> = {
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

export function CompanyCard({
  company,
  onPriorityChange,
  onRemove,
  onAddToWatchlist,
  onAtsSave,
  onAtsRemove,
}: CompanyCardProps) {
  const [provider, setProvider] = useState<AtsProvider>(
    company.ats_source?.provider ?? "GREENHOUSE",
  );
  const [slug, setSlug] = useState(company.ats_source?.slug ?? "");
  const [saving, setSaving] = useState(false);

  async function saveSource(event: FormEvent) {
    event.preventDefault();
    if (!slug.trim() || !onAtsSave) return;
    setSaving(true);
    try {
      await onAtsSave(provider, slug.trim());
    } finally {
      setSaving(false);
    }
  }

  async function removeSource() {
    if (!onAtsRemove) return;
    setSaving(true);
    try {
      await onAtsRemove();
      setSlug("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="company-card">
      <div className="company-card__top">
        <div className="company-monogram" aria-hidden="true">
          {company.name.slice(0, 1).toUpperCase()}
        </div>
        <div>
          <h3>{company.name}</h3>
          <p>
            {[company.industry, company.location].filter(Boolean).join(" · ") ||
              "Details pending"}
          </p>
        </div>
        {company.ats_source?.enabled ? (
          <span className="source-badge">{company.ats_source.provider}</span>
        ) : (
          company.source === "AI" && <span className="source-badge">AI find</span>
        )}
      </div>

      {!company.is_watchlisted ? (
        <>
          <div className="score-line">
            <span>Fit score</span>
            <strong>{company.total_score}/50</strong>
          </div>
          <div className="score-track" aria-label={`Fit score ${company.total_score} out of 50`}>
            <span style={{ width: `${company.total_score * 2}%` }} />
          </div>
          <p className="company-card__reason">
            {company.score_reason ?? "Review this company against your target profile."}
          </p>
          <button className="button button--secondary button--full" onClick={onAddToWatchlist}>
            Add to watchlist
          </button>
        </>
      ) : (
        <>
          <div className="company-card__actions">
            <label>
              Priority
              <select
                value={company.priority}
                onChange={(event) => onPriorityChange?.(event.target.value as Priority)}
              >
                {Object.entries(priorityLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <button className="text-button" onClick={onRemove}>
              Remove
            </button>
          </div>
          <details className="ats-config">
            <summary>
              {company.ats_source?.enabled ? "Job board connected" : "Connect ATS job board"}
            </summary>
            <form onSubmit={saveSource}>
              <select
                aria-label="ATS provider"
                value={provider}
                onChange={(event) => setProvider(event.target.value as AtsProvider)}
              >
                <option value="GREENHOUSE">Greenhouse</option>
                <option value="LEVER">Lever</option>
                <option value="ASHBY">Ashby</option>
              </select>
              <input
                aria-label="ATS board slug"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="Board slug"
                pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
                required
              />
              <button className="button button--mini" disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </form>
            <p>
              {company.ats_source?.enabled && company.ats_source.last_error
                ? `Last sync failed: ${company.ats_source.last_error}`
                : "Use the company identifier from its public careers URL."}
            </p>
            {company.ats_source?.enabled && (
              <button className="text-button" onClick={removeSource} disabled={saving}>
                Disconnect board
              </button>
            )}
          </details>
        </>
      )}
    </article>
  );
}
