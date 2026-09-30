import { useMemo } from 'react';
import './ActivityHeatmap.css';

const CELL_SIZE = 11;
const CELL_GAP = 3;
const LEFT_LABEL_WIDTH = 24;
const TOP_LABEL_HEIGHT = 16;
const DEFAULT_WEEKS = 52;
/** Fixed seed so the sample dataset looks the same on every render/refresh. */
const DATA_SEED = 1337;

const MONTH_NAMES = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

/** Row index (0 = Sunday) -> label shown to the left of the grid, GitHub-style. */
const DAY_LABEL_ROWS: Record<number, string> = { 1: 'Mon', 3: 'Wed', 5: 'Fri' };

interface DayActivity {
  date: Date;
  count: number;
  level: number;
  isFuture: boolean;
}

/** Deterministic PRNG (mulberry32) so the demo dataset is stable across renders. */
function createRandom(seed: number): () => number {
  let state = seed;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Generates a stable, GitHub-style sample activity dataset ending on the current week. */
function generateActivityColumns(weeks: number): DayActivity[][] {
  const random = createRandom(DATA_SEED);
  const today = startOfDay(new Date());
  const currentWeekStart = new Date(today);
  currentWeekStart.setDate(today.getDate() - today.getDay());
  const startDate = new Date(currentWeekStart);
  startDate.setDate(currentWeekStart.getDate() - (weeks - 1) * 7);

  const days: DayActivity[] = [];
  let maxCount = 0;
  for (let i = 0; i < weeks * 7; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + i);
    const isFuture = date > today;
    let count = 0;
    if (!isFuture) {
      const dow = date.getDay();
      const weekdayFactor = dow === 0 || dow === 6 ? 0.4 : 1;
      const roll = random();
      if (roll > 0.24) {
        const intensity = random();
        count = Math.round(intensity * intensity * 13 * weekdayFactor);
        if (roll > 0.88) {
          count += Math.round(random() * 5);
        }
      }
    }
    maxCount = Math.max(maxCount, count);
    days.push({ date, count, level: 0, isFuture });
  }

  for (const day of days) {
    if (day.count <= 0 || maxCount <= 0) {
      day.level = 0;
    } else {
      const ratio = day.count / maxCount;
      day.level = ratio > 0.75 ? 4 : ratio > 0.5 ? 3 : ratio > 0.25 ? 2 : 1;
    }
  }

  const columns: DayActivity[][] = [];
  for (let w = 0; w < weeks; w++) {
    columns.push(days.slice(w * 7, w * 7 + 7));
  }
  return columns;
}

/** Label shown above the first week-column of each new month, GitHub-style. */
function computeMonthLabels(columns: DayActivity[][]): (string | null)[] {
  let lastMonth = -1;
  return columns.map((column, index) => {
    const month = column[0].date.getMonth();
    if (index === 0 || month !== lastMonth) {
      lastMonth = month;
      return MONTH_NAMES[month];
    }
    return null;
  });
}

function formatTooltip(day: DayActivity): string {
  const label = day.date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
  if (day.count === 0) return `No activity on ${label}`;
  return `${day.count} ${day.count === 1 ? 'event' : 'events'} on ${label}`;
}

interface ActivityHeatmapProps {
  /** Number of weekly columns to render. Defaults to 52 (one year, GitHub-style). */
  weeks?: number;
}

export function ActivityHeatmap({ weeks = DEFAULT_WEEKS }: ActivityHeatmapProps) {
  const columns = useMemo(() => generateActivityColumns(weeks), [weeks]);
  const monthLabels = useMemo(() => computeMonthLabels(columns), [columns]);
  const totalCount = useMemo(
    () => columns.reduce((sum, column) => sum + column.reduce((s, day) => s + day.count, 0), 0),
    [columns],
  );

  const gridWidth = weeks * (CELL_SIZE + CELL_GAP) - CELL_GAP;
  const gridHeight = 7 * (CELL_SIZE + CELL_GAP) - CELL_GAP;
  const totalWidth = LEFT_LABEL_WIDTH + gridWidth;
  const totalHeight = TOP_LABEL_HEIGHT + gridHeight;

  return (
    <div className="activity-heatmap">
      <svg
        className="activity-heatmap-svg"
        viewBox={`0 0 ${totalWidth} ${totalHeight}`}
        role="img"
        aria-label={`Instance activity heatmap: ${totalCount} events over the last ${weeks} weeks`}
      >
        {Object.entries(DAY_LABEL_ROWS).map(([row, label]) => (
          <text
            key={label}
            className="activity-heatmap-day-label"
            x={LEFT_LABEL_WIDTH - 6}
            y={TOP_LABEL_HEIGHT + Number(row) * (CELL_SIZE + CELL_GAP) + CELL_SIZE - 2}
            textAnchor="end"
          >
            {label}
          </text>
        ))}
        {columns.map((column, c) => (
          <g key={column[0].date.toISOString()}>
            {monthLabels[c] && (
              <text
                className="activity-heatmap-month-label"
                x={LEFT_LABEL_WIDTH + c * (CELL_SIZE + CELL_GAP)}
                y={TOP_LABEL_HEIGHT - 5}
              >
                {monthLabels[c]}
              </text>
            )}
            {column.map((day, r) => (
              <rect
                key={day.date.toISOString()}
                className={
                  day.isFuture
                    ? 'activity-heatmap-cell activity-heatmap-cell--future'
                    : `activity-heatmap-cell activity-heatmap-cell--${day.level}`
                }
                x={LEFT_LABEL_WIDTH + c * (CELL_SIZE + CELL_GAP)}
                y={TOP_LABEL_HEIGHT + r * (CELL_SIZE + CELL_GAP)}
                width={CELL_SIZE}
                height={CELL_SIZE}
                rx={2}
              >
                {!day.isFuture && <title>{formatTooltip(day)}</title>}
              </rect>
            ))}
          </g>
        ))}
      </svg>
      <div className="activity-heatmap-legend">
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((level) => (
          <span
            key={level}
            className={`activity-heatmap-legend-swatch activity-heatmap-legend-swatch--${level}`}
          />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}
