import { useState } from "react";
import { Lock, User, ShieldCheck, AlertCircle } from "lucide-react";
import { toast } from "react-hot-toast";
import { loginUser } from "../api";

export default function Login({ onLoginSuccess, onCancel }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const res = await loginUser(username, password);
      if (res && res.status === "success") {
        toast.success("Authenticated as Shop Owner!");
        onLoginSuccess(res);
      } else {
        setError("Invalid username or password");
        toast.error("Invalid username or password");
      }
    } catch (err) {
      const msg = err.response?.data?.detail || "Authentication failed. Check credentials.";
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-bg-base/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
      <div className="w-full max-w-md bg-bg-panel border border-border-panel rounded-2xl shadow-2xl overflow-hidden p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 bg-accent-primary/10 text-accent-primary rounded-xl flex items-center justify-center mx-auto border border-accent-primary/20">
            <ShieldCheck size={26} />
          </div>
          <h2 className="text-2xl font-light tracking-tight text-text-primary">Shop Owner Login</h2>
          <p className="text-xs text-text-secondary">Authenticate to access the inventory and product management portal.</p>
        </div>

        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs flex items-center gap-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wider text-text-secondary">Username</label>
            <div className="relative flex items-center">
              <User size={16} className="absolute left-3 text-text-secondary" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="w-full bg-bg-base border border-border-panel text-text-primary rounded-xl pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-primary transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium uppercase tracking-wider text-text-secondary">Password</label>
            <div className="relative flex items-center">
              <Lock size={16} className="absolute left-3 text-text-secondary" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-bg-base border border-border-panel text-text-primary rounded-xl pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:border-accent-primary transition-colors"
              />
            </div>
          </div>

          <div className="pt-2 flex items-center gap-3">
            {onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="flex-1 py-2.5 border border-border-panel text-text-secondary rounded-xl text-sm font-medium hover:text-text-primary hover:bg-border-panel/30 transition-colors cursor-pointer"
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 py-2.5 bg-accent-primary text-bg-base rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
            >
              {isSubmitting ? "Authenticating..." : "Login"}
            </button>
          </div>
        </form>

        <div className="text-center pt-2 border-t border-border-panel/50">
          <p className="text-[11px] text-text-secondary">Default credentials: <code className="text-accent-primary bg-border-panel/40 px-1.5 py-0.5 rounded font-mono">admin / password123</code></p>
        </div>
      </div>
    </div>
  );
}
