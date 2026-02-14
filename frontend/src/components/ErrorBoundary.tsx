import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
    /** If true, shows a compact inline error instead of full-page */
    inline?: boolean;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("ErrorBoundary caught:", error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            if (this.props.inline) {
                return (
                    <div className="flex flex-col items-center justify-center p-6 rounded-lg border border-destructive/20 bg-destructive/5">
                        <AlertTriangle className="h-6 w-6 text-destructive mb-2" />
                        <p className="text-sm text-destructive font-medium mb-1">Something went wrong</p>
                        <p className="text-xs text-muted-foreground mb-3">
                            {this.state.error?.message || "An unexpected error occurred"}
                        </p>
                        <Button variant="outline" size="sm" onClick={this.handleReset}>
                            <RefreshCw className="mr-2 h-3 w-3" /> Retry
                        </Button>
                    </div>
                );
            }

            return (
                <div className="flex flex-col items-center justify-center min-h-[50vh] p-8">
                    <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
                    <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
                    <p className="text-sm text-muted-foreground mb-4 max-w-md text-center">
                        {this.state.error?.message || "An unexpected error occurred while rendering this page."}
                    </p>
                    <div className="flex gap-3">
                        <Button variant="outline" onClick={this.handleReset}>
                            <RefreshCw className="mr-2 h-4 w-4" /> Try Again
                        </Button>
                        <Button variant="default" onClick={() => window.location.assign("/")}>
                            Go Home
                        </Button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
