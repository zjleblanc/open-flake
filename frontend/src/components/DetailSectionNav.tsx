import { useEffect, useState, type ReactNode } from "react";
import type { DetailSectionAccent } from "./DetailSection";

export interface DetailSectionNavItem {
  id: string;
  title: string;
  icon: ReactNode;
  accent?: DetailSectionAccent;
  count?: ReactNode;
}

interface DetailSectionNavProps {
  sections: DetailSectionNavItem[];
  defaultOpen?: boolean;
}

const SECTION_NAV_EXPANDED_KEY = "openflake.detail-section-nav.expanded";

function readStoredNavExpanded(defaultOpen: boolean): boolean {
  try {
    const stored = localStorage.getItem(SECTION_NAV_EXPANDED_KEY);
    if (stored === "true") return true;
    if (stored === "false") return false;
  } catch {
    // localStorage unavailable
  }
  return defaultOpen;
}

function scrollToSection(sectionId: string) {
  const element = document.getElementById(sectionId);
  if (!element) return;
  if (element instanceof HTMLDetailsElement) {
    element.open = true;
  }
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}

function ChevronLeftIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M15 18l-6-6 6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 18l6-6-6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function DetailSectionNav({ sections, defaultOpen = true }: DetailSectionNavProps) {
  const [open, setOpen] = useState(() => readStoredNavExpanded(defaultOpen));
  const [activeId, setActiveId] = useState<string | null>(sections[0]?.id ?? null);

  useEffect(() => {
    try {
      localStorage.setItem(SECTION_NAV_EXPANDED_KEY, String(open));
    } catch {
      // localStorage unavailable
    }
  }, [open]);

  useEffect(() => {
    if (sections.length === 0) return;

    const visibleSections = sections
      .map(({ id }) => document.getElementById(id))
      .filter((element): element is HTMLElement => element !== null);

    if (visibleSections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]?.target.id) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: [0, 0.25, 0.5, 1] }
    );

    visibleSections.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [sections]);

  if (sections.length === 0) return null;

  return (
    <nav
      className={`detail-section-nav${open ? "" : " detail-section-nav--collapsed"}`}
      aria-label="Page sections"
    >
      <div className={`detail-section-nav-panel${open ? "" : " detail-section-nav-panel--icons"}`}>
        <ul className="detail-section-nav-list">
          <li>
            <button
              type="button"
              className="detail-section-nav-item detail-section-nav-toggle"
              onClick={() => setOpen((value) => !value)}
              aria-label={open ? "Collapse section navigation" : "Expand section navigation"}
              aria-expanded={open}
            >
              <span className="detail-section-nav-item-icon">
                {open ? <ChevronRightIcon /> : <ChevronLeftIcon />}
              </span>
              {open ? (
                <span className="detail-section-nav-item-label">Collapse</span>
              ) : null}
            </button>
          </li>
          {sections.map((section) => (
            <li key={section.id}>
              <button
                type="button"
                className={`detail-section-nav-item detail-section-nav-item--${section.accent ?? "accent"}${activeId === section.id ? " detail-section-nav-item--active" : ""}`}
                onClick={() => scrollToSection(section.id)}
                aria-current={activeId === section.id ? "true" : undefined}
                aria-label={section.title}
                title={section.title}
              >
                <span className="detail-section-nav-item-icon">{section.icon}</span>
                <span className="detail-section-nav-item-label">{section.title}</span>
                {section.count !== undefined && section.count !== null ? (
                  <span className="detail-section-nav-item-count">{section.count}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
