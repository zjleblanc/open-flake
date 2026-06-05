import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { BreadcrumbItem } from "./Breadcrumbs";

export interface PageHeaderState {
  breadcrumbs: BreadcrumbItem[];
  badge?: ReactNode;
  actions?: ReactNode;
}

interface PageHeaderContextValue {
  header: PageHeaderState;
  setPageHeader: (state: PageHeaderState) => void;
  clearPageHeader: () => void;
}

const EMPTY_HEADER: PageHeaderState = { breadcrumbs: [] };

const PageHeaderContext = createContext<PageHeaderContextValue | null>(null);

function breadcrumbsEqual(a: BreadcrumbItem[], b: BreadcrumbItem[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((item, i) => item.label === b[i].label && item.to === b[i].to);
}

export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [header, setHeader] = useState<PageHeaderState>(EMPTY_HEADER);

  const setPageHeader = useCallback((state: PageHeaderState) => {
    setHeader((prev) => {
      if (
        breadcrumbsEqual(prev.breadcrumbs, state.breadcrumbs) &&
        prev.badge === state.badge &&
        prev.actions === state.actions
      ) {
        return prev;
      }
      return state;
    });
  }, []);

  const clearPageHeader = useCallback(() => {
    setHeader((prev) =>
      prev.breadcrumbs.length === 0 && !prev.badge && !prev.actions ? prev : EMPTY_HEADER
    );
  }, []);

  const value = useMemo(
    () => ({ header, setPageHeader, clearPageHeader }),
    [header, setPageHeader, clearPageHeader]
  );

  return <PageHeaderContext.Provider value={value}>{children}</PageHeaderContext.Provider>;
}

export function usePageHeaderContext(): PageHeaderContextValue {
  const ctx = useContext(PageHeaderContext);
  if (!ctx) throw new Error("usePageHeaderContext must be used within PageHeaderProvider");
  return ctx;
}

/** Register breadcrumbs and optional toolbar actions for the sticky top navbar. */
export function usePageHeader({ breadcrumbs, badge, actions }: PageHeaderState) {
  const { setPageHeader, clearPageHeader } = usePageHeaderContext();
  const breadcrumbKey = JSON.stringify(breadcrumbs);
  const breadcrumbsRef = useRef(breadcrumbs);
  breadcrumbsRef.current = breadcrumbs;

  useLayoutEffect(() => {
    setPageHeader({ breadcrumbs: breadcrumbsRef.current, badge, actions });
  }, [breadcrumbKey, badge, actions, setPageHeader]);

  useEffect(() => {
    return () => clearPageHeader();
  }, [clearPageHeader]);
}
