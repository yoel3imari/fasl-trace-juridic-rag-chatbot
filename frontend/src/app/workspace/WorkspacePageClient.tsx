"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { WorkspaceLayout } from "@/components/features/workspace";
import { DirectionalLayoutSwitcher } from "@/components/features/workspace/DirectionalLayoutSwitcher";
import type { User, SupabaseClient } from "@supabase/supabase-js";

export function WorkspacePageClient() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const supabaseRef = useRef<SupabaseClient | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabaseRef.current = supabase;
    let cancelled = false;

    supabase.auth
      .getSession()
      .then(({ data: { session } }) => {
        if (cancelled) return;
        if (!session) {
          router.replace("/login");
        } else {
          setUser(session.user);
        }
        setAuthChecked(true);
      })
      .catch(() => {
        if (!cancelled) {
          setAuthChecked(true);
        }
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.replace("/login");
      } else {
        setUser(session.user);
      }
    });

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, [router]);

  if (!authChecked || !user) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-900">
        <div className="text-slate-400 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <DirectionalLayoutSwitcher>
      <WorkspaceLayout />
    </DirectionalLayoutSwitcher>
  );
}
