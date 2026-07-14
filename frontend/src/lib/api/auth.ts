import { createClient } from '@/lib/supabase';

/**
 * Get the current Supabase session access token for API authentication.
 * Returns null if no session exists.
 *
 * Uses getSession() first (reads from cookies), then falls back to
 * getUser() (validates with auth server) — the middleware proves
 * getUser() works even when cookies aren't synced to document.cookie.
 */
export async function getAuthToken(): Promise<string | null> {
  const supabase = createClient();

  // Try getSession first — fast, reads local cookies
  const { data: sessionData, error: sessionError } = await supabase.auth.getSession();
  if (!sessionError && sessionData.session?.access_token) {
    return sessionData.session.access_token;
  }

  // Fallback: getUser() contacts the auth server and sets the session
  const { data: userData, error: userError } = await supabase.auth.getUser();
  if (userError || !userData.user) {
    return null;
  }

  // After getUser() succeeds, the session should be available
  const { data: refreshedSession } = await supabase.auth.getSession();
  return refreshedSession.session?.access_token ?? null;
}

/**
 * Get the current user's email for display purposes.
 */
export async function getUserEmail(): Promise<string | null> {
  const supabase = createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) {
    return null;
  }
  return data.user.email ?? null;
}
