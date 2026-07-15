"use server";

import { cookies } from "next/headers";
import { createClient } from "@/lib/supabase-server";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

export async function signOut() {
  const supabase = await createClient();

  // Revoke the session server-side
  await supabase.auth.signOut();

  // Manually clear ALL Supabase auth cookies.
  // The @supabase/ssr applyServerStorage callback can fail to clear cookies
  // in some server action contexts, so we brute-force clear any sb-* cookie.
  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();

  for (const cookie of allCookies) {
    if (cookie.name.startsWith("sb-")) {
      cookieStore.set(cookie.name, "", {
        path: "/",
        maxAge: 0,
        expires: new Date(0),
      });
    }
  }

  revalidatePath("/", "layout");
  redirect("/login");
}
