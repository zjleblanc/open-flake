import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  applyColorScheme,
  applyLayoutDensity,
  clearLegacyPreferences,
  DEFAULT_USER_PREFERENCES,
  fromApiPreferences,
  readLegacyPreferences,
  toApiPreferences,
  type ColorScheme,
  type DateDisplayFormat,
  type LayoutDensity,
  type UserPreferences,
} from './userPreferences';

interface UserPreferencesContextValue {
  preferences: UserPreferences;
  ready: boolean;
  dateDisplayFormat: DateDisplayFormat;
  layoutDensity: LayoutDensity;
  sidebarExpanded: boolean;
  colorScheme: ColorScheme;
  pinnedNavItems: string[];
  setDateDisplayFormat: (format: DateDisplayFormat) => void;
  setLayoutDensity: (density: LayoutDensity) => void;
  setSidebarExpanded: (expanded: boolean) => void;
  setColorScheme: (scheme: ColorScheme) => void;
  setPinnedNavItems: (items: string[]) => void;
}

const UserPreferencesContext = createContext<UserPreferencesContextValue | null>(null);

export function UserPreferencesProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_USER_PREFERENCES);
  const [ready, setReady] = useState(false);
  const migratedRef = useRef(false);

  useEffect(() => {
    if (authLoading) return;

    if (!user) {
      setPreferences(DEFAULT_USER_PREFERENCES);
      setReady(true);
      migratedRef.current = false;
      return;
    }

    const activeUser = user;
    let cancelled = false;

    async function loadPreferences() {
      let next = fromApiPreferences(activeUser.preferences);

      if (!migratedRef.current) {
        const legacy = readLegacyPreferences();
        if (legacy) {
          next = { ...next, ...legacy };
          clearLegacyPreferences();
          try {
            const saved = await api.updatePreferences(toApiPreferences(next));
            next = fromApiPreferences(saved);
          } catch {
            // Keep merged local values if persistence fails.
          }
        }
        migratedRef.current = true;
      }

      if (!cancelled) {
        setPreferences(next);
        setReady(true);
      }
    }

    void loadPreferences();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading]);

  useEffect(() => {
    applyLayoutDensity(preferences.layoutDensity);
  }, [preferences.layoutDensity]);

  useEffect(() => {
    return applyColorScheme(preferences.colorScheme);
  }, [preferences.colorScheme]);

  const persistPreferences = useCallback(
    async (next: UserPreferences) => {
      if (!user) return;
      try {
        const saved = await api.updatePreferences(toApiPreferences(next));
        setPreferences(fromApiPreferences(saved));
      } catch {
        // Keep optimistic local state on failure.
      }
    },
    [user],
  );

  const setDateDisplayFormat = useCallback(
    (dateDisplayFormat: DateDisplayFormat) => {
      setPreferences((current) => {
        const next = { ...current, dateDisplayFormat };
        void persistPreferences(next);
        return next;
      });
    },
    [persistPreferences],
  );

  const setLayoutDensity = useCallback(
    (layoutDensity: LayoutDensity) => {
      setPreferences((current) => {
        const next = { ...current, layoutDensity };
        void persistPreferences(next);
        return next;
      });
    },
    [persistPreferences],
  );

  const setSidebarExpanded = useCallback(
    (sidebarExpanded: boolean) => {
      setPreferences((current) => {
        const next = { ...current, sidebarExpanded };
        void persistPreferences(next);
        return next;
      });
    },
    [persistPreferences],
  );

  const setColorScheme = useCallback(
    (colorScheme: ColorScheme) => {
      setPreferences((current) => {
        const next = { ...current, colorScheme };
        void persistPreferences(next);
        return next;
      });
    },
    [persistPreferences],
  );

  const setPinnedNavItems = useCallback(
    (pinnedNavItems: string[]) => {
      setPreferences((current) => {
        const next = { ...current, pinnedNavItems };
        void persistPreferences(next);
        return next;
      });
    },
    [persistPreferences],
  );

  const value = useMemo(
    () => ({
      preferences,
      ready,
      dateDisplayFormat: preferences.dateDisplayFormat,
      layoutDensity: preferences.layoutDensity,
      sidebarExpanded: preferences.sidebarExpanded,
      colorScheme: preferences.colorScheme,
      pinnedNavItems: preferences.pinnedNavItems,
      setDateDisplayFormat,
      setLayoutDensity,
      setSidebarExpanded,
      setColorScheme,
      setPinnedNavItems,
    }),
    [
      preferences,
      ready,
      setDateDisplayFormat,
      setLayoutDensity,
      setSidebarExpanded,
      setColorScheme,
      setPinnedNavItems,
    ],
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
      ready: true,
      dateDisplayFormat: DEFAULT_USER_PREFERENCES.dateDisplayFormat,
      layoutDensity: DEFAULT_USER_PREFERENCES.layoutDensity,
      sidebarExpanded: DEFAULT_USER_PREFERENCES.sidebarExpanded,
      colorScheme: DEFAULT_USER_PREFERENCES.colorScheme,
      pinnedNavItems: DEFAULT_USER_PREFERENCES.pinnedNavItems,
      setDateDisplayFormat: () => {},
      setLayoutDensity: () => {},
      setSidebarExpanded: () => {},
      setColorScheme: () => {},
      setPinnedNavItems: () => {},
    };
  }
  return context;
}
