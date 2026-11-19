"use client";

import Link from "next/link";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

import { createClient } from "@/lib/supabase/client";

type AppHeaderProps = {
  showOverviewLink?: boolean;
  authenticatedHref?: string;
  authenticatedLabel?: string;
};

function subscribeToBrowserHistory(onChange: () => void) {
  window.addEventListener("popstate", onChange);
  return () => window.removeEventListener("popstate", onChange);
}

function canReturnInBrowser() {
  return window.location.pathname !== "/";
}

function cannotReturnOnServer() {
  return false;
}

export default function AppHeader({
  showOverviewLink = false,
  authenticatedHref = "/dashboard",
  authenticatedLabel = "My dashboard",
}: AppHeaderProps) {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const canReturn = useSyncExternalStore(
    subscribeToBrowserHistory,
    canReturnInBrowser,
    cannotReturnOnServer,
  );

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

  function returnToPreviousPage() {
    try {
      const previousPage = new URL(document.referrer);

      if (previousPage.origin === window.location.origin) {
        router.back();
        return;
      }
    } catch {
      // Direct visits have no usable in-app page to return to.
    }

    router.push("/");
  }

  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="Verity home">
        <span className="brand-mark" aria-hidden="true">
          V
        </span>
        <span>VERITY</span>
      </Link>

      <nav className="site-nav" aria-label="Primary navigation">
        {showOverviewLink && (
          <a href="#how-it-works">How it works</a>
        )}
        {canReturn && (
          <button
            className="site-nav__back"
            type="button"
            onClick={returnToPreviousPage}
          >
            <span aria-hidden="true">←</span> Back
          </button>
        )}
        {isAuthenticated ? (
          <Link className="button button--dark button--small" href={authenticatedHref}>
            {authenticatedLabel}
          </Link>
        ) : (
          <>
            <Link className="site-nav__login" href="/login">
              Log in
            </Link>
            <Link className="button button--dark button--small" href="/signup">
              Sign up
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
