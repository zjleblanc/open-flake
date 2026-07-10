export type DateDisplayFormat = 'raw' | 'local';
export type LayoutDensity = 'comfortable' | 'compact';
export type ColorScheme = 'dark' | 'light' | 'system';
export type ResolvedTheme = 'dark' | 'light';

export interface UserPreferences {
  dateDisplayFormat: DateDisplayFormat;
  layoutDensity: LayoutDensity;
  sidebarExpanded: boolean;
  colorScheme: ColorScheme;
}

export interface UserPreferencesApi {
  date_display_format: DateDisplayFormat;
  layout_density: LayoutDensity;
  sidebar_expanded: boolean;
  color_scheme: ColorScheme;
}

export const DEFAULT_USER_PREFERENCES: UserPreferences = {
  dateDisplayFormat: 'raw',
  layoutDensity: 'comfortable',
  sidebarExpanded: true,
  colorScheme: 'dark',
};

const LEGACY_PREFS_KEY = 'openflake.userPreferences';
const LEGACY_SIDEBAR_KEY = 'openflake.sidebar.expanded';

const VALID_COLOR_SCHEMES = new Set<ColorScheme>(['dark', 'light', 'system']);

export function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function resolveTheme(colorScheme: ColorScheme): ResolvedTheme {
  if (colorScheme === 'system') return getSystemTheme();
  return colorScheme;
}

export function fromApiPreferences(
  api: Partial<UserPreferencesApi> | null | undefined,
): UserPreferences {
  return {
    dateDisplayFormat:
      api?.date_display_format === 'local' ? 'local' : DEFAULT_USER_PREFERENCES.dateDisplayFormat,
    layoutDensity:
      api?.layout_density === 'compact' ? 'compact' : DEFAULT_USER_PREFERENCES.layoutDensity,
    sidebarExpanded:
      typeof api?.sidebar_expanded === 'boolean'
        ? api.sidebar_expanded
        : DEFAULT_USER_PREFERENCES.sidebarExpanded,
    colorScheme:
      api?.color_scheme && VALID_COLOR_SCHEMES.has(api.color_scheme)
        ? api.color_scheme
        : DEFAULT_USER_PREFERENCES.colorScheme,
  };
}

export function toApiPreferences(preferences: UserPreferences): UserPreferencesApi {
  return {
    date_display_format: preferences.dateDisplayFormat,
    layout_density: preferences.layoutDensity,
    sidebar_expanded: preferences.sidebarExpanded,
    color_scheme: preferences.colorScheme,
  };
}

export function readLegacyPreferences(): Partial<UserPreferences> | null {
  const partial: Partial<UserPreferences> = {};
  let hasLegacy = false;

  try {
    const raw = localStorage.getItem(LEGACY_PREFS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<UserPreferences>;
      if (parsed.dateDisplayFormat === 'local' || parsed.dateDisplayFormat === 'raw') {
        partial.dateDisplayFormat = parsed.dateDisplayFormat;
        hasLegacy = true;
      }
      if (parsed.layoutDensity === 'compact' || parsed.layoutDensity === 'comfortable') {
        partial.layoutDensity = parsed.layoutDensity;
        hasLegacy = true;
      }
    }

    const sidebar = localStorage.getItem(LEGACY_SIDEBAR_KEY);
    if (sidebar === 'true' || sidebar === 'false') {
      partial.sidebarExpanded = sidebar === 'true';
      hasLegacy = true;
    }
  } catch {
    return null;
  }

  return hasLegacy ? partial : null;
}

export function clearLegacyPreferences(): void {
  localStorage.removeItem(LEGACY_PREFS_KEY);
  localStorage.removeItem(LEGACY_SIDEBAR_KEY);
}

export function applyLayoutDensity(density: LayoutDensity): void {
  document.documentElement.dataset.layoutDensity = density;
}

export function applyColorScheme(colorScheme: ColorScheme): () => void {
  const root = document.documentElement;

  const apply = () => {
    const resolved = resolveTheme(colorScheme);
    root.dataset.theme = resolved;
    root.dataset.colorScheme = colorScheme;
  };

  apply();

  if (colorScheme !== 'system') {
    return () => {};
  }

  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const onChange = () => apply();
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
