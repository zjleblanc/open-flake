import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { UserPreferencesProvider } from "./settings/UserPreferencesContext";
import {
  applyColorScheme,
  applyLayoutDensity,
  DEFAULT_USER_PREFERENCES,
} from "./settings/userPreferences";
import { App } from "./App";
import favicon from "./assets/images/open_flake_sm.png";
import "./theme/global.css";

applyLayoutDensity(DEFAULT_USER_PREFERENCES.layoutDensity);
applyColorScheme(DEFAULT_USER_PREFERENCES.colorScheme);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

const faviconLink = document.createElement("link");
faviconLink.rel = "icon";
faviconLink.type = "image/png";
faviconLink.href = favicon;
document.head.appendChild(faviconLink);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <UserPreferencesProvider>
            <App />
          </UserPreferencesProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
