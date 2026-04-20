import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase browser client for Next.js App Router.
 * Uses @supabase/ssr for proper cookie-based auth handling.
 *
 * Environment variables are prefixed with NEXT_PUBLIC_ for client-side access.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
