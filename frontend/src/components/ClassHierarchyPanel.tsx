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
  const { data, isLoading, isError } = useQuery({
    queryKey: ["cmdb-class-schema", className],
    queryFn: () => api.getCmdbClassSchema(className),
    enabled: !!className,
    retry: false,
  });

  const schema = data?.result;

  const inheritancePath = useMemo(() => {
    if (schema?.inheritance_path?.length) return schema.inheritance_path;
    const fromPath = parseClassPath(sysClassPath);
    if (fromPath.length) return fromPath;
    return fallbackPath(className);
  }, [schema, sysClassPath, className]);

  const fieldStats = useMemo(() => {
    if (!schema?.fields) return null;
    let native = 0;
    let inherited = 0;
    for (const field of schema.fields) {
      if (field.origin === "Native") native += 1;
      else inherited += 1;
    }
    return { native, inherited };
  }, [schema]);

  if (!className) return null;

  return (
    <div className="class-hierarchy-panel">
      {isLoading && <p className="text-muted text-sm">Loading class schema…</p>}
      {!isLoading && isError && (
        <p className="class-hierarchy-notice text-muted text-sm">
          Class is not registered in the schema registry. Showing path from the record.
        </p>
      )}
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
      {fieldStats && (
        <p className="class-hierarchy-stats text-muted text-sm">
          {fieldStats.native} native · {fieldStats.inherited} inherited fields
        </p>
      )}
    </div>
  );
}
