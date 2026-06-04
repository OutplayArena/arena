import { Component } from "react";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 px-6">
          <h2 className="text-lg font-extrabold text-ink">Something went wrong</h2>
          <p className="text-sm text-muted text-center max-w-md">
            {this.state.error.message || "An unexpected error occurred."}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="px-5 py-2 rounded-input bg-accent text-white text-sm font-extrabold"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
