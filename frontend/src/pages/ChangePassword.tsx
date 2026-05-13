import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BrandHero } from "@/components/BrandHero";

export function ChangePassword() {
  const navigate = useNavigate();
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPw !== confirmPw) {
      setError("new passwords do not match");
      return;
    }
    if (newPw.length < 12) {
      setError("new password must be at least 12 characters");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(oldPw, newPw);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "change failed");
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
              <h2 className="text-2xl font-semibold tracking-tight">Set a new password</h2>
              <p className="text-sm text-muted-foreground mt-1">Required on first login. Minimum 12 characters.</p>
            </div>
            <div className="mb-6 md:hidden">
              <h2 className="text-xl font-semibold tracking-tight">Set a new password</h2>
              <p className="text-xs text-muted-foreground mt-1">Required on first login. Minimum 12 characters.</p>
            </div>
            <form className="space-y-4" onSubmit={submit}>
              <div className="space-y-1.5">
                <Label htmlFor="old">Current password</Label>
                <Input id="old" type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new">New password</Label>
                <Input id="new" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} minLength={12} required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="cnf">Confirm new password</Label>
                <Input id="cnf" type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} minLength={12} required />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button className="w-full" type="submit" disabled={busy}>
                {busy ? "Updating…" : "Update password"}
              </Button>
            </form>
          </div>
        </div>
        <footer className="hidden md:block px-10 lg:px-14 py-4 text-xs text-muted-foreground border-t">
          Check Point® is a registered trademark of Check Point Software Technologies Ltd.
        </footer>
      </div>
    </div>
  );
}
