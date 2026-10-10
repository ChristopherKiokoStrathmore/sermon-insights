import type { CountItem } from "@/lib/workbook";

export function BarList({
  title,
  note,
  items,
  empty,
}: {
  title: string;
  note: string;
  items: CountItem[];
  empty: string;
}) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <figure className="chart">
      <figcaption>
        <h3>{title}</h3>
        <p>{note}</p>
      </figcaption>
      {items.length === 0 ? (
        <p className="chart-empty">{empty}</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.label}>
              <span className="bar-label">{item.label}</span>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${(item.count / max) * 100}%` }} />
              </span>
              <span className="bar-count">{item.count}</span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  );
}
