import { useNavigate } from "react-router-dom";
import { LogIn, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib";
import { PublicSearchPanel } from "@/components/PublicSearchPanel";

export default function LandingPage() {
    const { login, isAuthenticated, isLoading: authLoading } = useAuth();
    const navigate = useNavigate();

    const handleLogin = () => {
        if (isAuthenticated) {
            navigate("/dashboard");
        } else {
            login();
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <div className="relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-background to-background" />

                <div className="relative max-w-5xl mx-auto px-4 pt-16 pb-8">
                    <div className="text-center mb-12">
                        <div className="flex items-center justify-center gap-3 mb-4">
                            <div className="p-2 rounded-xl bg-primary/10">
                                <svg className="h-12 w-12 text-emerald-400" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M16 8v6" />
                                    <path d="M16 14L10 19" />
                                    <path d="M16 14L22 19" />
                                    <circle cx="16" cy="14" r="2.5" fill="currentColor" stroke="none" />
                                    <circle cx="10" cy="19" r="1.5" fill="currentColor" stroke="none" />
                                    <circle cx="22" cy="19" r="1.5" fill="currentColor" stroke="none" />
                                    <path d="M12 23h8" strokeOpacity="0.8" />
                                    <path d="M16 19v3" />
                                    <path d="M14 20l2 2 2-2" fill="none" />
                                    <path d="M21 7l-1 3h2l-2 3" className="text-emerald-300" stroke="currentColor" strokeWidth="1.5" fill="none" />
                                </svg>
                            </div>
                        </div>
                        <h1 className="text-4xl font-bold text-gradient mb-4">DNO Crawler</h1>
                        <p className="text-lg text-muted-foreground max-w-lg mx-auto">
                            Search for German network operator data by address or coordinates.
                            Quick lookup without an account.
                        </p>
                    </div>

                    <PublicSearchPanel errorClassName="mt-6" resultClassName="mt-6" />

                    <Card className="mt-8 border-dashed">
                        <CardContent className="p-6 text-center">
                            <LogIn className="w-10 h-10 mx-auto text-primary mb-4" />
                            <h2 className="text-xl font-semibold mb-2">
                                {isAuthenticated ? "Go to Dashboard" : "Login to Access More"}
                            </h2>
                            <p className="text-muted-foreground mb-6">
                                {isAuthenticated
                                    ? "You're already logged in. Access the full dashboard to manage DNOs and import data."
                                    : "Sign in to view full data, manage DNOs, trigger data imports, and access the admin dashboard."
                                }
                            </p>
                            <Button
                                onClick={handleLogin}
                                size="lg"
                                className="gap-2"
                                disabled={authLoading}
                            >
                                {authLoading ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <LogIn className="w-4 h-4" />
                                )}
                                {isAuthenticated ? "Open Dashboard" : "Login with Zitadel"}
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
