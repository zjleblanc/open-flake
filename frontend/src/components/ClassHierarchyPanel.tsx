import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { resolveInheritancePath } from '../utils/resolveInheritancePath';

interface ClassHierarchyPanelProps {
  className: string;
  sysClassPath?: string;
}

export function ClassHierarchyPanel({ className, sysClassPath }: ClassHierarchyPanelProps) {
  const { data } = useQuery({
    queryKey: ['cmdb-class-schema', className],
    queryFn: () => api.getCmdbClassSchema(className),
    enabled: !!className,
    retry: false,
    throwOnError: false,
  });

  const schema = data?.result;

  const inheritancePath = useMemo(() => {
    const path = resolveInheritancePath(className, {
      schemaPath: schema?.inheritance_path,
      sysClassPath,
    });
    return path.filter((name) => name !== 'cmdb');
  }, [schema, sysClassPath, className]);

  if (!className) return null;

  return (
    <div className="class-hierarchy-panel">
      <ol
        id="ci-class-hierarchy"
        className="class-hierarchy-tree"
        aria-label="Class inheritance hierarchy"
      >
        {inheritancePath.map((name, index) => {
          const isCurrent = name === className;
          return (
            <li
              key={`${name}-${index}`}
              className={`class-hierarchy-node${isCurrent ? ' class-hierarchy-node--current' : ''}`}
            >
              <span className="class-hierarchy-marker" aria-hidden="true" />
              <div className="class-hierarchy-node-content">
                <code className="class-hierarchy-name">{name}</code>
                {isCurrent && <span className="class-hierarchy-badge">current</span>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
