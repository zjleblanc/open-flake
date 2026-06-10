function parseClassPath(sysClassPath: string | undefined): string[] {
  if (!sysClassPath) return [];
  return sysClassPath.split("/").filter(Boolean);
}

function fallbackPath(className: string): string[] {
  if (!className) return [];
  return ["cmdb", "cmdb_ci", className];
}

export function isOrderedSubsequence(shorter: string[], longer: string[]): boolean {
  if (!shorter.length) return true;
  let index = 0;
  for (const segment of longer) {
    if (segment === shorter[index]) index += 1;
    if (index === shorter.length) return true;
  }
  return index === shorter.length;
}

export function normalizeInheritancePath(className: string, path: string[]): string[] {
  const trimmed = path.filter(Boolean);
  if (!trimmed.length) return [];

  const classIndex = trimmed.lastIndexOf(className);
  if (classIndex >= 0) return trimmed.slice(0, classIndex + 1);
  return [...trimmed, className];
}

function pickLongestCompatiblePath(paths: string[][]): string[] {
  const valid = paths.filter((path) => path.length > 0);
  if (!valid.length) return [];

  const sorted = [...valid].sort((a, b) => b.length - a.length);
  for (const candidate of sorted) {
    const compatible = sorted.every(
      (path) =>
        path === candidate ||
        isOrderedSubsequence(path, candidate) ||
        isOrderedSubsequence(candidate, path)
    );
    if (compatible) return candidate;
  }

  return sorted[0];
}

export function resolveInheritancePath(
  className: string,
  options: {
    schemaPath?: string[];
    sysClassPath?: string;
  }
): string[] {
  if (!className) return [];

  const candidates = [
    options.schemaPath?.length
      ? normalizeInheritancePath(className, options.schemaPath)
      : undefined,
    parseClassPath(options.sysClassPath).length
      ? normalizeInheritancePath(className, parseClassPath(options.sysClassPath))
      : undefined,
  ].filter((path): path is string[] => !!path?.length && path[path.length - 1] === className);

  if (!candidates.length) return fallbackPath(className);
  return pickLongestCompatiblePath(candidates);
}
