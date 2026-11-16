import type { ReactNode } from "react";

import AppHeader from "@/components/AppHeader";

type AuthFrameProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

export default function AuthFrame({
  eyebrow,
  title,
  description,
  children,
}: AuthFrameProps) {
  return (
    <main className="auth-page">
      <AppHeader />

      <section className="auth-layout">
        <aside className="auth-intro" aria-hidden="true">
          <p className="section-kicker">SalesMesh identity</p>
          <p className="auth-intro__number">01</p>
          <div>
            <p className="auth-intro__label">Trusted access begins with</p>
            <p className="auth-intro__statement">a profile built for progress.</p>
          </div>
          <div className="auth-intro__stamp">Verified together</div>
        </aside>

        <section className="auth-card" aria-labelledby="auth-title">
          <p className="section-kicker">{eyebrow}</p>
          <h1 id="auth-title">{title}</h1>
          <p className="auth-card__description">{description}</p>
          {children}
        </section>
      </section>
    </main>
  );
}
