import Link from "next/link";

import AppHeader from "@/components/AppHeader";
import BackendStatus from "@/components/BackendStatus";
import HeroProfileFigure from "@/components/HeroProfileFigure";

const steps = [
  {
    number: "01",
    title: "Build your profile",
    copy: "Create a secure SalesMesh account and complete the details that make your identity yours.",
  },
  {
    number: "02",
    title: "Prove your identity",
    copy: "Submit the required evidence through a private, guided verification journey.",
  },
  {
    number: "03",
    title: "Move with confidence",
    copy: "Track every decision from one clear dashboard and stay ready for your next opportunity.",
  },
];

export default function Home() {
  return (
    <main className="landing-page">
      <AppHeader showOverviewLink />

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero__grain" aria-hidden="true" />
        <div className="hero__copy">
          <p className="section-kicker section-kicker--light">SalesMesh / Identity system</p>
          <h1 id="hero-title">
            Know who you&apos;re
            <span>building with.</span>
          </h1>
          <p className="hero__lede">
            A more human way to verify the people moving your business forward.
          </p>
          <div className="hero__actions">
            <Link className="button button--gold" href="/signup">
              Start your profile <span aria-hidden="true">↗</span>
            </Link>
            <a className="text-link text-link--light" href="#how-it-works">
              See how it works <span aria-hidden="true">↓</span>
            </a>
          </div>
        </div>

        <HeroProfileFigure />

        <div className="hero__footer">
          <p>Built for credible growth.</p>
          <BackendStatus />
        </div>
      </section>

      <section className="landing-intro" id="how-it-works">
        <p className="section-kicker">A clear route forward</p>
        <div className="landing-intro__grid">
          <h2>Verification that feels like momentum, not a roadblock.</h2>
          <p>
            SalesMesh brings registration, document review, and identity status
            into one considered experience—so trusted agents can get to work.
          </p>
        </div>
      </section>

      <section className="steps-section" aria-labelledby="steps-title">
        <div className="steps-section__heading">
          <p className="section-kicker">Your verification journey</p>
          <h2 id="steps-title">Three moves. One trusted profile.</h2>
        </div>
        <ol className="steps-grid">
          {steps.map((step) => (
            <li key={step.number} className="step-card">
              <span>{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.copy}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-cta">
        <p className="section-kicker section-kicker--light">Ready when you are</p>
        <h2>Make your next move a verified one.</h2>
        <Link className="button button--gold" href="/signup">
          Create your account <span aria-hidden="true">↗</span>
        </Link>
      </section>
    </main>
  );
}
