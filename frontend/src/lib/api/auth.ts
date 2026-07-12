import { createClient } from '@/lib/supabase';

/**
 * Get the current Supabase session access token for API authentication.
 * Returns null if no session exists.
 */
export async function getAuthToken(): Promise<string | null> {
  const supabase = createClient();
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) {
    return null;
  }
  return data.session.access_token;
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
