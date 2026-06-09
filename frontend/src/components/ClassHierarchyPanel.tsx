import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

function parseClassPath(sysClassPath: string | undefined): string[] {
  if (!sysClassPath) return [];
  return sysClassPath.split("/").filter(Boolean);
}

function fallbackPath(className: string): string[] {
  if (!className) return [];
  return ["cmdb", "cmdb_ci", className];
}

function humanizeClassName(name: string): string {
  const trimmed = name.replace(/^cmdb_ci_?/, "").replace(/_/g, " ").trim();
  return trimmed || name;
}

interface ClassHierarchyPanelProps {
  className: string;
  sysClassPath?: string;
}

export function ClassHierarchyPanel({ className, sysClassPath }: ClassHierarchyPanelProps) {
  const { data } = useQuery({
    queryKey: ["cmdb-class-schema", className],
    queryFn: () => api.getCmdbClassSchema(className),
    enabled: !!className,
    retry: false,
    throwOnError: false,
  });

  const schema = data?.result;

  const inheritancePath = useMemo(() => {
    if (schema?.registered && schema.inheritance_path?.length) {
      return schema.inheritance_path;
    }
    const fromPath = parseClassPath(sysClassPath);
    if (fromPath.length) return fromPath;
    if (schema?.inheritance_path?.length) return schema.inheritance_path;
    return fallbackPath(className);
  }, [schema, sysClassPath, className]);

  if (!className) return null;

  return (
    <div className="class-hierarchy-panel">
      <ol className="class-hierarchy-tree" aria-label="Class inheritance hierarchy">
        {inheritancePath.map((name, index) => {
          const isCurrent = name === className;
          return (
            <li
              key={`${name}-${index}`}
              className={`class-hierarchy-node${isCurrent ? " class-hierarchy-node--current" : ""}`}
            >
              <span className="class-hierarchy-marker" aria-hidden="true" />
              <div className="class-hierarchy-node-content">
                <code className="class-hierarchy-name">{name}</code>
                {isCurrent && <span className="class-hierarchy-badge">current</span>}
                {isCurrent && (
                  <span className="class-hierarchy-subtitle">{humanizeClassName(name)}</span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
