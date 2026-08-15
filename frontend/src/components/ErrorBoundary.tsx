import { Component, type ErrorInfo, type ReactNode } from 'react';
import { FetchErrorView } from './FetchErrorView';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Top-level safety net for render-time failures caused by unreachable APIs or
 * other unhandled errors. Falls back to FetchErrorView so the user sees the
 * "contact your administrator" message instead of a blank screen.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled application error', error, info);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return <FetchErrorView error={this.state.error} onRetry={this.handleRetry} />;
    }
    return this.props.children;
  }
}
