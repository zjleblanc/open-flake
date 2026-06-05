import type { ReactNode } from "react";

export type DetailSectionAccent = "primary" | "accent" | "info" | "success";

interface DetailSectionProps {
  title: string;
  icon: ReactNode;
  accent?: DetailSectionAccent;
  headerActions?: ReactNode;
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function DetailSection({
  title,
  icon,
  accent = "accent",
  headerActions,
  children,
  className,
  style,
}: DetailSectionProps) {
  return (
    <section
      className={`detail-section detail-section--${accent}${className ? ` ${className}` : ""}`}
      style={style}
    >
      <header className="detail-section-header">
        <span className="detail-section-icon">{icon}</span>
        <h2 className="detail-section-title">{title}</h2>
        {headerActions ? (
          <div className="detail-section-header-actions">{headerActions}</div>
        ) : null}
      </header>
      <div className="detail-section-body">{children}</div>
    </section>
  );
}
