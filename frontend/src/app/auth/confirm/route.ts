import type { EmailOtpType } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

function safeNextPath(value: string | null): string {
  if (value?.startsWith("/") && !value.startsWith("//")) {
    return value;
  }

  return "/dashboard";
}

/**
 * Exchanges either supported Supabase email-confirmation credential for a
 * cookie-backed session, then starts the Verity registration journey.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const destination = request.nextUrl.clone();
  const next = safeNextPath(searchParams.get("next"));

  destination.pathname = next;
  destination.search = "";

  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const supabase = await createClient();

  const error = code
    ? (await supabase.auth.exchangeCodeForSession(code)).error
    : tokenHash && type
      ? (await supabase.auth.verifyOtp({ token_hash: tokenHash, type })).error
      : new Error("The confirmation link is incomplete or has expired.");

  if (error) {
    destination.pathname = "/login";
    destination.searchParams.set("confirmation", "failed");
    return NextResponse.redirect(destination);
  }

  destination.searchParams.set("confirmed", "1");
  return NextResponse.redirect(destination);
}
