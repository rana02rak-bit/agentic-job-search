interface MetricCardProps {
  label: string;
  value: number;
  accent?: boolean;
}

export function MetricCard({ label, value, accent = false }: MetricCardProps) {
  return (
    <article className={`metric-card ${accent ? "metric-card--accent" : ""}`}>
      <span>{label}</span>
      <strong>{value.toString().padStart(2, "0")}</strong>
    </article>
  );
}

