"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";

import { getMyAgentProfile } from "@/lib/agent-api";
import { createClient } from "@/lib/supabase/client";

type AvatarVariant = "male" | "female" | "neutral";

const figureAssets: Record<
  AvatarVariant,
  { profile: string; suit: string; label: string }
> = {
  neutral: {
    profile: "/images/hero-profile-mannequin.png",
    suit: "/images/hero-profile-suit.png",
    label: "A 3D passport profile figure",
  },
  male: {
    profile: "/images/hero-profile-male.png",
    suit: "/images/hero-profile-male-suit.png",
    label: "A verified male 3D passport profile figure",
  },
  female: {
    profile: "/images/hero-profile-female.png",
    suit: "/images/hero-profile-female-suit.png",
    label: "A verified female 3D passport profile figure",
  },
};

export default function HeroProfileFigure() {
  const [variant, setVariant] = useState<AvatarVariant>("neutral");
  const assets = figureAssets[variant];

  useEffect(() => {
    let active = true;
    let requestId = 0;
    const supabase = createClient();

    async function loadVariantForSession(session: Session | null) {
      const currentRequest = ++requestId;

      // The anonymous, faceless profile is always the first state. It also
      // remains the fallback for accounts without an approved identity yet.
      if (active) setVariant("neutral");
      if (!session) return;

      try {
        const profile = await getMyAgentProfile();

        if (
          active &&
          currentRequest === requestId &&
          (profile.avatar_variant === "male" ||
            profile.avatar_variant === "female")
        ) {
          setVariant(profile.avatar_variant);
        }
      } catch {
        // A new account may not have an agent profile yet. The neutral figure
        // remains the intentional fallback until identity approval completes.
      }
    }

    void supabase.auth.getSession().then(({ data }) => {
      void loadVariantForSession(data.session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      void loadVariantForSession(session);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  return (
    <div
      className="hero-figure"
      tabIndex={0}
      role="img"
      aria-label={`${assets.label} that changes into a suited professional on hover or focus`}
    >
      <div className="hero-figure__halo" aria-hidden="true" />
      <div className="hero-figure__portrait" key={variant}>
        <Image
          className="hero-figure__image hero-figure__image--profile"
          src={assets.profile}
          alt=""
          fill
          priority
          sizes="(max-width: 760px) 80vw, 43vw"
        />
        <Image
          className="hero-figure__image hero-figure__image--suit"
          src={assets.suit}
          alt=""
          fill
          priority
          sizes="(max-width: 760px) 80vw, 43vw"
        />
      </div>
      <p className="hero-figure__hint">Hover to suit up</p>
      <div className="hero-figure__card" aria-hidden="true">
        <span>
          {variant === "neutral" ? "Passport profile" : "Verified profile"}
        </span>
        <strong>SM / 001</strong>
      </div>
    </div>
  );
}
