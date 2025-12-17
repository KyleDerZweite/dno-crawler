import { useNavigate } from "react-router-dom";
import { Home, LogIn, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib";

/**
 * LogoutPage: Shown after user logs out from Zitadel
 * 
 * - Confirmation message
 * - Button to go back to home (landing page)
 * - Button to login again
 */
export default function LogoutPage() {
    const { login } = useAuth();
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-background flex items-center justify-center p-4">
            <Card className="max-w-md w-full">
                <CardContent className="p-8 text-center">
                    <div className="p-4 rounded-full bg-success/20 w-fit mx-auto mb-6">
                        <CheckCircle2 className="w-12 h-12 text-success" />
                    </div>

                    <h1 className="text-2xl font-bold mb-2">Logged Out</h1>
                    <p className="text-muted-foreground mb-8">
                        You have been successfully logged out. Thank you for using DNO Crawler.
                    </p>

                    <div className="flex flex-col gap-3">
                        <Button
                            onClick={() => navigate("/")}
                            variant="default"
                            size="lg"
                            className="gap-2 w-full"
                        >
                            <Home className="w-4 h-4" />
                            Back to Home
                        </Button>
                        <Button
                            onClick={() => login()}
                            variant="outline"
                            size="lg"
                            className="gap-2 w-full"
                        >
                            <LogIn className="w-4 h-4" />
                            Login Again
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
