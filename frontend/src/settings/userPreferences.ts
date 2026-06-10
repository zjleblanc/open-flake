export type DateDisplayFormat = "raw" | "local";

export interface UserPreferences {
  dateDisplayFormat: DateDisplayFormat;
}

export const DEFAULT_USER_PREFERENCES: UserPreferences = {
  dateDisplayFormat: "raw",
};

const STORAGE_KEY = "openflake.userPreferences";

export function loadUserPreferences(): UserPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_USER_PREFERENCES;
    const parsed = JSON.parse(raw) as Partial<UserPreferences>;
    return {
      dateDisplayFormat:
        parsed.dateDisplayFormat === "local" ? "local" : "raw",
    };
  } catch {
    return DEFAULT_USER_PREFERENCES;
  }
}

export function saveUserPreferences(preferences: UserPreferences): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
}
