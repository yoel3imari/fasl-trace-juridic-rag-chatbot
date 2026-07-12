"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ChevronDown, LogOut } from "lucide-react";
import { createClient } from "@/lib/supabase";

const pathLabels: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/workspace": "Workspace",
  "/settings": "Settings",
};

function getBreadcrumb(pathname: string): string {
  if (pathname === "/") return "Home";
  return pathLabels[pathname] ?? "Unknown";
}

export function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const breadcrumb = getBreadcrumb(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setUserEmail(data.user?.email ?? null);
    });
  }, []);

  const handleSignOut = useCallback(async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }, [router]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [menuOpen]);

  return (
    <header className="h-12 border-b border-sidebar-border bg-sidebar flex items-center justify-between px-4 shrink-0">
      <div className="text-sm text-sidebar-foreground/70">{breadcrumb}</div>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex items-center gap-2.5 rounded-md px-2 py-1 transition-colors hover:bg-sidebar-accent/50"
        >
          <div className="w-6 h-6 rounded-full bg-cyan-500 flex items-center justify-center text-[10px] font-semibold text-white select-none">
            {(userEmail ?? "U")[0].toUpperCase()}
          </div>
          <span className="text-sm text-sidebar-foreground/80">{userEmail ?? "User"}</span>
          <ChevronDown className="w-3.5 h-3.5 text-sidebar-foreground/40" />
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-full z-50 mt-1 min-w-[160px] overflow-hidden rounded-lg border border-border bg-popover py-1 shadow-lg">
            {userEmail && (
              <div className="px-3 py-2 text-xs text-muted-foreground border-b border-border">
                {userEmail}
              </div>
            )}
            <button
              type="button"
              onClick={() => {
                setMenuOpen(false);
                handleSignOut();
              }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-foreground transition-colors hover:bg-muted"
            >
              <LogOut className="size-3.5 text-muted-foreground" />
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
