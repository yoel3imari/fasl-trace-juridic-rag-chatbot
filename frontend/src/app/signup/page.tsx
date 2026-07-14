"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase";
import { Button } from "@/components/ui/button";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const handleSignUp = useCallback(async () => {
    const supabase = createClient();
    setLoading(true);
    setError(null);
    setConfirmed(false);

    const { data, error: signUpError } = await supabase.auth.signUp({
      email,
      password,
    });

    if (signUpError) {
      setError(signUpError.message);
      setLoading(false);
      return;
    }

    if (data.session) {
      router.push("/dashboard");
    } else {
      setConfirmed(true);
      setLoading(false);
    }
  }, [email, password, router]);

  if (confirmed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-sm mx-auto px-4">
          <div className="rounded-xl border border-border bg-sidebar p-8 shadow-lg text-center">
            <h1 className="text-xl font-semibold text-foreground">Check your email</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              We sent a confirmation link to <strong className="text-foreground">{email}</strong>.
            </p>
            <p className="mt-4 text-xs text-muted-foreground">
              <Link href="/login" className="text-cyan-500 hover:underline">
                Back to sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm mx-auto px-4">
        <div className="rounded-xl border border-border bg-sidebar p-8 shadow-lg">
          <div className="mb-8 text-center">
            <h1 className="text-xl font-semibold text-foreground">Create account</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Get started with Fasl Trace
            </p>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSignUp();
            }}
            className="flex flex-col gap-4"
          >
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-xs font-medium text-foreground/80"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-xs font-medium text-foreground/80"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                autoComplete="new-password"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500/40"
              />
            </div>

            {error && (
              <p className="text-xs text-red-400">{error}</p>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="mt-2 w-full"
            >
              {loading ? "Creating account..." : "Create account"}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="text-cyan-500 hover:underline">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
