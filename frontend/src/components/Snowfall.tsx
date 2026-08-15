import { useMemo, type CSSProperties } from 'react';
import './Snowfall.css';

const FLAKE_COUNT = 110;

type Flake = {
  left: number;
  size: number;
  duration: number;
  delay: number;
  drift: number;
  opacity: number;
};

function createFlakes(count: number): Flake[] {
  return Array.from({ length: count }, () => ({
    left: Math.random() * 100,
    size: 4 + Math.random() * 8,
    duration: 6 + Math.random() * 10,
    delay: Math.random() * -16,
    drift: -50 + Math.random() * 100,
    opacity: 0.35 + Math.random() * 0.55,
  }));
}

/** Decorative falling-snow overlay. Purely presentational — safe to drop into any error view. */
export function Snowfall() {
  const flakes = useMemo(() => createFlakes(FLAKE_COUNT), []);

  return (
    <div className="snowfall-container" aria-hidden="true">
      {flakes.map((flake, index) => (
        <span
          key={index}
          className="snowflake"
          style={
            {
              left: `${flake.left}%`,
              width: `${flake.size}px`,
              height: `${flake.size}px`,
              opacity: flake.opacity,
              animationDuration: `${flake.duration}s`,
              animationDelay: `${flake.delay}s`,
              '--snowflake-drift': `${flake.drift}px`,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
