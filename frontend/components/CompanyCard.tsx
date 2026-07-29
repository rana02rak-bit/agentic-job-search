import type { Company, Priority } from "@/lib/api";

interface CompanyCardProps {
  company: Company;
  onPriorityChange?: (priority: Priority) => void;
  onRemove?: () => void;
  onAddToWatchlist?: () => void;
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
}: CompanyCardProps) {
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
        {company.source === "AI" && <span className="source-badge">AI find</span>}
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
      )}
    </article>
  );
}
