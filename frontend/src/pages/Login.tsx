import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BrandHero } from "@/components/BrandHero";

export function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await api.login(username, password);
      navigate(r.must_change_password ? "/change-password" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid md:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] bg-background">
      <BrandHero />
      <div className="flex flex-col">
        <div className="md:hidden bg-berry text-white px-6 py-4 flex items-center gap-2.5">
          <ShieldCheck className="h-6 w-6" strokeWidth={2.25} />
          <span className="font-semibold tracking-tight">Check Point MCP Hub</span>
        </div>
        <div className="flex-1 grid place-items-center p-6 sm:p-10">
          <div className="w-full max-w-sm">
            <div className="mb-8 hidden md:block">
              <h2 className="text-2xl font-semibold tracking-tight">Sign in</h2>
              <p className="text-sm text-muted-foreground mt-1">Welcome back. Sign in to manage your MCP servers.</p>
            </div>
            <div className="mb-6 md:hidden">
              <h2 className="text-xl font-semibold tracking-tight">Sign in</h2>
            </div>
            <form className="space-y-4" onSubmit={submit}>
              <div className="space-y-1.5">
                <Label htmlFor="u">Username</Label>
                <Input id="u" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p">Password</Label>
                <Input id="p" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button className="w-full" type="submit" disabled={busy}>
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </form>
            <p className="text-xs text-muted-foreground mt-8">
              First time? Default credentials are <code className="font-mono">admin</code> / <code className="font-mono">admin</code>. You'll be required to change them.
            </p>
          </div>
        </div>
        <footer className="hidden md:block px-10 lg:px-14 py-4 text-xs text-muted-foreground border-t">
          Check Point® is a registered trademark of Check Point Software Technologies Ltd.
        </footer>
      </div>
    </div>
  );
}
