import { Snowfall } from './Snowfall';
import './ErrorPage.css';

interface FetchErrorViewProps {
  error?: unknown;
  onRetry?: () => void;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Failed to fetch';
}

/**
 * Shown when the app cannot reach the server (network failure, unhandled render
 * error, etc). Reuses the Snowfall animation but keeps a serious tone, unlike
 * NotFoundPage, since this indicates a real operational problem.
 */
export function FetchErrorView({ error, onRetry }: FetchErrorViewProps) {
  function handleRetry() {
    if (onRetry) {
      onRetry();
    } else {
      window.location.reload();
    }
  }

  return (
    <div className="error-page">
      <Snowfall />
      <div className="error-page-content">
        <p className="error-page-eyebrow">Connection Error</p>
        <h1 className="error-page-title">Something went wrong</h1>
        <p className="error-page-subtitle">Contact your OpenFlake administrator.</p>
        <pre className="error-page-code">
          <code>{getErrorMessage(error)}</code>
        </pre>
        <div className="error-page-actions">
          <button type="button" className="btn btn-primary" onClick={handleRetry}>
            Retry
          </button>
        </div>
      </div>
    </div>
  );
}
