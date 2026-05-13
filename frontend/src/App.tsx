import { useEffect, useState } from "react";
import { Link, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { LogOut, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Login } from "@/pages/Login";
import { ChangePassword } from "@/pages/ChangePassword";
import { Dashboard } from "@/pages/Dashboard";
import { ServerDetail } from "@/pages/ServerDetail";
import { Settings } from "@/pages/Settings";

function AuthShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (me.must_change_password) {
          navigate("/change-password", { replace: true });
        }
        setUsername(me.username);
      } catch {
        navigate("/login", { replace: true });
      } finally {
        setChecked(true);
      }
    })();
  }, [navigate]);

  if (!checked) return <div className="min-h-screen grid place-items-center text-muted-foreground">Loading…</div>;

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="border-b bg-card">
        <div className="container flex h-14 items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <ShieldCheck className="h-6 w-6 text-berry" strokeWidth={2.25} />
            <span>Check Point <span className="text-muted-foreground font-normal">MCP Hub</span></span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link
              to="/"
              className={
                "px-3 py-1.5 rounded-md transition-colors " +
                (location.pathname === "/" ? "bg-accent text-accent-foreground font-medium" : "text-muted-foreground hover:text-foreground hover:bg-muted")
              }
            >
              Servers
            </Link>
            <Link
              to="/settings"
              className={
                "px-3 py-1.5 rounded-md transition-colors inline-flex items-center gap-1.5 " +
                (location.pathname === "/settings" ? "bg-accent text-accent-foreground font-medium" : "text-muted-foreground hover:text-foreground hover:bg-muted")
              }
            >
              <SettingsIcon className="h-4 w-4" /> Settings
            </Link>
            <span className="mx-2 h-5 w-px bg-border" />
            <span className="text-muted-foreground px-2 hidden sm:inline">{username}</span>
            <Button size="sm" variant="ghost" onClick={() => api.logout().then(() => (window.location.href = "/login"))} aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </Button>
          </nav>
        </div>
      </header>
      <main className="container py-8 flex-1">
        <Outlet />
      </main>
      <footer className="border-t bg-card">
        <div className="container py-3 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-2">
          <span>
            Community tooling for{" "}
            <a className="text-berry hover:underline" href="https://github.com/CheckPointSW/mcp-servers" target="_blank" rel="noreferrer">
              CheckPointSW/mcp-servers
            </a>
            . Not an official Check Point product.
          </span>
          <span>Check Point® is a registered trademark of Check Point Software Technologies Ltd.</span>
        </div>
      </footer>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route element={<AuthShell />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/servers/:id" element={<ServerDetail />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
