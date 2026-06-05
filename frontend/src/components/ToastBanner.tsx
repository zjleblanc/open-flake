import { useEffect } from "react";

interface ToastBannerProps {
  message: string;
  type: "success" | "error";
  onDismiss: () => void;
  durationMs?: number;
}

export function ToastBanner({
  message,
  type,
  onDismiss,
  durationMs = 3000,
}: ToastBannerProps) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(timer);
  }, [message, type, durationMs, onDismiss]);

  return (
    <div className={`toast-banner toast-banner-${type}`} role="status">
      {message}
    </div>
  );
}
