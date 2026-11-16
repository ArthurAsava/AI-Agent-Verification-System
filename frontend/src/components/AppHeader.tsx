"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";

type AppHeaderProps = {
  showOverviewLink?: boolean;
};

export default function AppHeader({
  showOverviewLink = false,
}: AppHeaderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const supabase = createClient();

    void supabase.auth.getSession().then(({ data }) => {
      setIsAuthenticated(Boolean(data.session));
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, session) => setIsAuthenticated(Boolean(session)),
    );

    return () => listener.subscription.unsubscribe();
  }, []);

  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="SalesMesh home">
        <span className="brand-mark" aria-hidden="true">
          SM
        </span>
        <span>SalesMesh</span>
      </Link>

      <nav className="site-nav" aria-label="Primary navigation">
        {showOverviewLink && (
          <a href="#how-it-works">How it works</a>
        )}
        {isAuthenticated ? (
          <Link className="button button--dark button--small" href="/dashboard">
            My dashboard
          </Link>
        ) : (
          <>
            <Link className="site-nav__login" href="/login">
              Log in
            </Link>
            <Link className="button button--dark button--small" href="/signup">
              Create account
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
