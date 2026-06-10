import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  DEFAULT_USER_PREFERENCES,
  loadUserPreferences,
  saveUserPreferences,
  type DateDisplayFormat,
  type UserPreferences,
} from "./userPreferences";

interface UserPreferencesContextValue {
  preferences: UserPreferences;
  dateDisplayFormat: DateDisplayFormat;
  setDateDisplayFormat: (format: DateDisplayFormat) => void;
}

const UserPreferencesContext = createContext<UserPreferencesContextValue | null>(null);

export function UserPreferencesProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<UserPreferences>(loadUserPreferences);

  const setDateDisplayFormat = useCallback((dateDisplayFormat: DateDisplayFormat) => {
    setPreferences((current) => {
      const next = { ...current, dateDisplayFormat };
      saveUserPreferences(next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({
      preferences,
      dateDisplayFormat: preferences.dateDisplayFormat,
      setDateDisplayFormat,
    }),
    [preferences, setDateDisplayFormat]
  );

  return (
    <UserPreferencesContext.Provider value={value}>{children}</UserPreferencesContext.Provider>
  );
}

export function useUserPreferences(): UserPreferencesContextValue {
  const context = useContext(UserPreferencesContext);
  if (!context) {
    return {
      preferences: DEFAULT_USER_PREFERENCES,
      dateDisplayFormat: DEFAULT_USER_PREFERENCES.dateDisplayFormat,
      setDateDisplayFormat: () => {},
    };
  }
  return context;
}
