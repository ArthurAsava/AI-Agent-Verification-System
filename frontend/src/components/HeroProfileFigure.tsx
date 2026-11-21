"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { useAuthSession } from "@/components/AuthSessionProvider";
import { getMyAgentProfile } from "@/lib/agent-api";

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
  const { session } = useAuthSession();
  const signedInUserId = session?.user.id;
  const [resolvedAvatar, setResolvedAvatar] = useState<{
    userId: string;
    variant: AvatarVariant;
  } | null>(null);
  const variant =
    signedInUserId && resolvedAvatar?.userId === signedInUserId
      ? resolvedAvatar.variant
      : "neutral";
  const assets = figureAssets[variant];

  useEffect(() => {
    let active = true;

    // An account without a saved profile sex deliberately keeps the anonymous
    // mannequin. The model must never infer a person's sex from their name or
    // other unrelated account details.
    if (!signedInUserId) {
      return () => {
        active = false;
      };
    }
    const userId = signedInUserId;

    async function loadVariantForSignedInUser() {
      try {
        const profile = await getMyAgentProfile();

        if (
          active &&
          (profile.avatar_variant === "male" ||
            profile.avatar_variant === "female")
        ) {
          setResolvedAvatar({
            userId,
            variant: profile.avatar_variant,
          });
        } else if (active) {
          setResolvedAvatar({
            userId,
            variant: "neutral",
          });
        }
      } catch {
        // A newly confirmed account may not yet have a profile. Keep the
        // anonymous mannequin until a verified profile value is available.
        if (active) {
          setResolvedAvatar({
            userId,
            variant: "neutral",
          });
        }
      }
    }

    void loadVariantForSignedInUser();

    return () => {
      active = false;
    };
  }, [signedInUserId]);

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
    </div>
  );
}
