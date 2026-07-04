"use client";

import { useEffect, type ReactNode } from "react";
import { useChatStore } from "@/store/useChatStore";

interface DirectionalLayoutSwitcherProps {
  children: ReactNode;
}

export function DirectionalLayoutSwitcher({ children }: DirectionalLayoutSwitcherProps) {
  const direction = useChatStore((s) => s.workspace.direction);

  useEffect(() => {
    document.documentElement.dir = direction;
    return () => {
      document.documentElement.dir = "ltr";
    };
  }, [direction]);

  return (
    <div className={direction === "rtl" ? "font-sans-rtl" : "font-sans-ltr"}>
      {children}
    </div>
  );
}
