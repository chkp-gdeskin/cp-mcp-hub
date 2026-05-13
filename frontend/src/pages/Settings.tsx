import { useEffect, useState } from "react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CopyButton } from "@/components/CopyButton";

export function Settings() {
  const [token, setToken] = useState<string | null>(null);
  const [rotatedAt, setRotatedAt] = useState<string | null>(null);
  const [info, setInfo] = useState<{ version: string; manifest_version: string; manifest_generated_at: string; server_count: number } | null>(null);
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [showPwModal, setShowPwModal] = useState(false);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState(false);

  useEffect(() => {
    void (async () => {
      const [t, i] = await Promise.all([api.getToken(), api.systemInfo()]);
      setToken(t.token);
      setRotatedAt(t.rotated_at);
      setInfo(i);
    })();
  }, []);

  async function doRotate() {
    setConfirmRotate(false);
    const r = await api.rotateToken();
    setToken(r.token);
    setRotatedAt(r.rotated_at);
  }

  async function doChangePw(e: React.FormEvent) {
    e.preventDefault();
    setPwError(null);
    if (newPw.length < 12) { setPwError("min 12 characters"); return; }
    try {
      await api.changePassword(oldPw, newPw);
      setPwSuccess(true);
      setOldPw(""); setNewPw("");
      setTimeout(() => { setPwSuccess(false); setShowPwModal(false); }, 1500);
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "failed");
    }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>SSE bearer token</CardTitle>
          <CardDescription>This token authorizes access to all enabled MCP servers.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 items-center">
            <code className="flex-1 truncate bg-muted px-2 py-1 rounded text-xs font-mono">{token ?? ""}</code>
            <CopyButton value={token} label="Copy bearer token" />
          </div>
          {rotatedAt && <p className="text-xs text-muted-foreground">Last rotated: {new Date(rotatedAt).toLocaleString()}</p>}
          <Button variant="destructive" onClick={() => setConfirmRotate(true)}>Rotate token</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Admin password</CardTitle>
          <CardDescription>Single admin user in v1.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => setShowPwModal(true)}>Change password</Button>
        </CardContent>
      </Card>

      {info && (
        <Card>
          <CardHeader>
            <CardTitle>System</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <Row k="Image version" v={info.version} />
            <Row k="Manifest version" v={info.manifest_version} />
            <Row k="Manifest generated" v={new Date(info.manifest_generated_at).toLocaleString()} />
            <Row k="Servers in manifest" v={String(info.server_count)} />
          </CardContent>
        </Card>
      )}

      <Dialog open={confirmRotate} onOpenChange={setConfirmRotate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rotate SSE bearer token?</DialogTitle>
            <DialogDescription>
              This will invalidate the old token immediately and briefly restart all running servers. MCP clients will need to update their token.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmRotate(false)}>Cancel</Button>
            <Button variant="destructive" onClick={doRotate}>Rotate</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showPwModal} onOpenChange={setShowPwModal}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change password</DialogTitle>
          </DialogHeader>
          <form className="space-y-3" onSubmit={doChangePw}>
            <div className="space-y-1.5">
              <Label htmlFor="op">Current password</Label>
              <Input id="op" type="password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="np">New password (min 12)</Label>
              <Input id="np" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} minLength={12} required />
            </div>
            {pwError && <p className="text-sm text-destructive">{pwError}</p>}
            {pwSuccess && <p className="text-sm text-success">Password updated.</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowPwModal(false)}>Cancel</Button>
              <Button type="submit">Update</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2 border-b last:border-0 py-1">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono text-xs">{v}</span>
    </div>
  );
}
