import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import type { User } from "./api";

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(() => !!localStorage.getItem("token"));

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      return;
    }

    api.auth
      .me()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("token");
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const response = await api.auth.login({ username: email, password });
    localStorage.setItem("token", response.access_token);
    localStorage.setItem("refresh_token", response.refresh_token);
    setUser(response.user);
  };

  const register = async (name: string, email: string, password: string) => {
    await api.auth.register({ name, email, password });
    // Don't auto-login - user needs to wait for approval
  };

  const logout = () => {
    api.auth.logout();
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        isAdmin: user?.role === "admin",
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
