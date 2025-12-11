import { useAuth } from "@/lib/use-auth";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { User, Shield, ExternalLink } from "lucide-react";

export function SettingsPage() {
  const { user, roles, avatar, openSettings } = useAuth();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Manage your account preferences
        </p>
      </div>

      {/* Profile Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Profile
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4 pb-4 border-b">
            {avatar ? (
              <img
                src={avatar}
                alt={user?.name || "Profile"}
                className="h-16 w-16 rounded-full"
              />
            ) : (
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center text-xl font-bold text-primary">
                {user?.name?.charAt(0) || user?.email?.charAt(0) || "?"}
              </div>
            )}
            <div>
              <h3 className="font-semibold text-lg">{user?.name || "Unknown"}</h3>
              <p className="text-muted-foreground">{user?.email || ""}</p>
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Roles</p>
            <div className="flex flex-wrap gap-2">
              {roles.map((role) => (
                <span
                  key={role}
                  className="inline-flex items-center rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary ring-1 ring-inset ring-primary/20"
                >
                  {role}
                </span>
              ))}
              {roles.length === 0 && (
                <span className="text-sm text-muted-foreground italic">No roles assigned</span>
              )}
            </div>
          </div>
          <div className="pt-4">
            <Button onClick={openSettings}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Manage Account in Zitadel
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Security Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Security
          </CardTitle>
          <CardDescription>Account security is managed through Zitadel</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 border border-border/50 rounded-lg bg-muted/20">
            <div>
              <p className="font-medium">Zitadel Account Settings</p>
              <p className="text-sm text-muted-foreground">
                Change password, manage sessions, and configure two-factor authentication
              </p>
            </div>
            <Button variant="outline" onClick={openSettings}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Open
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}