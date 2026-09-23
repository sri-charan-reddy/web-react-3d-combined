/**
 * Last-resort boundary so a render fault in one panel doesn't blank the whole
 * mission-control view with no explanation.
 */
import { Component, type ErrorInfo, type PropsWithChildren, type ReactNode } from 'react';

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<PropsWithChildren, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[dashboard] render fault', error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="fatal" role="alert">
        <h1>Mission Control failed to render</h1>
        <p>{error.message}</p>
        <button type="button" className="btn btn--primary" onClick={() => this.setState({ error: null })}>
          Retry
        </button>
      </div>
    );
  }
}
