"use client";

import type { Session, User } from "@supabase/supabase-js";
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { createClient } from "@/lib/supabase/client";

type AuthSessionContextValue = {
  isLoading: boolean;
  session: Session | null;
  user: User | null;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

/**
 * Keeps the browser UI in step with the Supabase Auth session. This is only
 * presentation state; protected backend requests still validate the bearer
 * token with Supabase before returning private data.
 */
export function AuthSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();
    let mounted = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;

      setSession(data.session);
      setIsLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        if (!mounted) return;

        setSession(nextSession);
        setIsLoading(false);
      },
    );

    return () => {
      mounted = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  const value = useMemo(
    () => ({
      isLoading,
      session,
      user: session?.user ?? null,
    }),
    [isLoading, session],
  );

  return (
    <AuthSessionContext.Provider value={value}>
      {children}
    </AuthSessionContext.Provider>
  );
}

export function useAuthSession() {
  const value = useContext(AuthSessionContext);

  if (!value) {
    throw new Error("useAuthSession must be used within AuthSessionProvider");
  }

  return value;
}
