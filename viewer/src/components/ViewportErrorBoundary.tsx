import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Catches errors (e.g. WebGL context creation failure) in the viewport
 * and shows a fallback so the rest of the UI stays visible.
 */
export default class ViewportErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError && this.state.error) {
      const isWebGL = this.state.error.message?.includes("WebGL");
      return (
        this.props.fallback ?? (
          <div
            className="viewport-webgl-fallback"
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              padding: 24,
              background: "var(--bg-secondary)",
              color: "var(--text-secondary)",
              fontSize: 14,
              textAlign: "center",
            }}
          >
            <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>
              {isWebGL ? "WebGL could not be initialized" : "Viewport error"}
            </div>
            <div>
              {isWebGL
                ? "Try a different browser, enable hardware acceleration, or disable software rendering."
                : this.state.error.message}
            </div>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false, error: null })}
              style={{
                marginTop: 8,
                padding: "8px 16px",
                background: "var(--accent)",
                color: "white",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Retry
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
