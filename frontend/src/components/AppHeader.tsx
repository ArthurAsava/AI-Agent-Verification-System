"use client";

import Link from "next/link";
import { useRef, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

import { useAuthSession } from "@/components/AuthSessionProvider";
import { createClient } from "@/lib/supabase/client";

type AppHeaderProps = {
  showOverviewLink?: boolean;
  authenticatedHref?: string;
  authenticatedLabel?: string;
};

type AuthUser = {
  email?: string | null;
  user_metadata?: Record<string, unknown>;
};

function initialsForUser(user: AuthUser | null | undefined) {
  // This is presentation-only; user metadata is never used for authorization.
  const metadataName =
    user?.user_metadata?.full_name ?? user?.user_metadata?.name;
  const source =
    typeof metadataName === "string" && metadataName.trim()
      ? metadataName
      : user?.email?.split("@")[0] ?? "User";
  const parts = source.match(/[A-Za-z]+/g) ?? [];

  const [firstPart, secondPart] = parts;
  if (firstPart && secondPart) {
    return `${firstPart.charAt(0)}${secondPart.charAt(0)}`.toUpperCase();
  }

  return (firstPart ?? "U").slice(0, 2).toUpperCase();
}

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
  authenticatedHref,
  authenticatedLabel,
}: AppHeaderProps) {
  const router = useRouter();
  const profileMenuRef = useRef<HTMLDetailsElement>(null);
  const { session, user } = useAuthSession();
  const [signingOut, setSigningOut] = useState(false);
  const canReturn = useSyncExternalStore(
    subscribeToBrowserHistory,
    canReturnInBrowser,
    cannotReturnOnServer,
  );

  const isAuthenticated = Boolean(session);
  const userInitials = initialsForUser(user as AuthUser | null);

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

  async function handleSignOut() {
    setSigningOut(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signOut({ scope: "local" });

    if (error) {
      setSigningOut(false);
      window.alert(`We could not sign you out: ${error.message}`);
      return;
    }

    profileMenuRef.current?.removeAttribute("open");
    router.replace("/");
    router.refresh();
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
          <>
            {authenticatedHref && authenticatedLabel && (
              <Link
                className="button button--dark button--small"
                href={authenticatedHref}
              >
                {authenticatedLabel}
              </Link>
            )}
            <details className="profile-menu" ref={profileMenuRef}>
              <summary
                className="profile-menu__trigger"
                aria-label="Open account menu"
              >
                <span aria-hidden="true">{userInitials}</span>
              </summary>
              <div className="profile-menu__panel">
                <Link href="/dashboard">My dashboard</Link>
                <button
                  type="button"
                  onClick={() => void handleSignOut()}
                  disabled={signingOut}
                >
                  {signingOut ? "Signing out…" : "Sign out"}
                </button>
                <Link href="/security">Security</Link>
              </div>
            </details>
          </>
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
