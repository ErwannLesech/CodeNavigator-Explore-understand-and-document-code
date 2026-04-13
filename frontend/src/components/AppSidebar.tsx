import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { MessageSquare, BookOpen, Share2, FileCode2, Workflow } from "lucide-react";
import { api } from "@/lib/api";
import talanLogo from "@/assets/talan-logo.svg";

const navItems = [
  { to: "/", label: "Chat", icon: MessageSquare },
  { to: "/pipeline", label: "Pipeline", icon: Workflow },
  { to: "/docs", label: "Documentation", icon: BookOpen },
  { to: "/graph", label: "Knowledge Graph", icon: Share2 },
  { to: "/diagrams", label: "Diagrammes Mermaid", icon: FileCode2 },
];

export default function AppSidebar() {
  const location = useLocation();
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () => api.health().then(setHealthy);
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-sidebar-bg text-sidebar-fg h-screen sticky top-0">
      <div className="p-5 border-b border-sidebar-hover">
        <img src={talanLogo} alt="Talan" className="h-8 mb-3" />
        <h1 className="text-lg font-bold tracking-tight">CodeNavigator</h1>
      </div>

      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? "bg-sidebar-active text-primary-foreground"
                  : "text-sidebar-fg hover:bg-sidebar-hover"
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-sidebar-hover">
        <div className="flex items-center gap-2 text-xs text-sidebar-muted">
          <span
            className={`w-2 h-2 rounded-full ${
              healthy === null
                ? "bg-sidebar-muted"
                : healthy
                ? "bg-secondary"
                : "bg-accent"
            }`}
          />
          {healthy === null ? "Checking..." : healthy ? "Backend online" : "Backend offline"}
        </div>
      </div>
    </aside>
  );
}
