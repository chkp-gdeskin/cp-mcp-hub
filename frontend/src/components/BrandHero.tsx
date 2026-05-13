/**
 * Brand-aligned hero panel used on unauthenticated screens.
 *
 * Per Check Point brand guidelines: Brand Berry should be the dominant color
 * on first-impression surfaces. Curves echo the "approachability" motif from
 * the guide's logo description; the burst shape echoes "intelligence and
 * innovation bursting forth." Strictly 2D, minimal gradient, no Check Point
 * logo or proprietary patterns (which require brand-request approval).
 */
export function BrandHero() {
  return (
    <div className="relative hidden md:flex flex-col justify-between overflow-hidden bg-berry text-white p-10 lg:p-14">
      {/* Decorative SVG — abstract curves & burst */}
      <svg
        className="absolute inset-0 w-full h-full opacity-95 pointer-events-none"
        viewBox="0 0 800 1000"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden
      >
        <defs>
          <linearGradient id="berry-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="hsl(var(--berry))" />
            <stop offset="100%" stopColor="hsl(var(--berry-dark))" />
          </linearGradient>
          <radialGradient id="burst-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.18)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
        </defs>
        <rect width="800" height="1000" fill="url(#berry-gradient)" />

        {/* Large slow curve — approachability */}
        <path
          d="M -100 700 Q 200 400 500 600 T 1100 500"
          stroke="rgba(255,255,255,0.18)"
          strokeWidth="2"
          fill="none"
        />
        <path
          d="M -100 800 Q 250 520 550 720 T 1100 640"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="2"
          fill="none"
        />
        <path
          d="M -100 900 Q 280 660 580 840 T 1100 800"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="2"
          fill="none"
        />

        {/* Concentric rings — intelligence motif */}
        <circle cx="640" cy="220" r="240" fill="url(#burst-glow)" />
        <circle cx="640" cy="220" r="120" stroke="rgba(255,255,255,0.22)" strokeWidth="1.5" fill="none" />
        <circle cx="640" cy="220" r="180" stroke="rgba(255,255,255,0.14)" strokeWidth="1.5" fill="none" />
        <circle cx="640" cy="220" r="240" stroke="rgba(255,255,255,0.08)" strokeWidth="1.5" fill="none" />

        {/* Small dots — innovation burst */}
        <g fill="rgba(255,255,255,0.55)">
          <circle cx="640" cy="220" r="4" />
          <circle cx="580" cy="180" r="2" />
          <circle cx="710" cy="190" r="2.5" />
          <circle cx="690" cy="290" r="2" />
          <circle cx="560" cy="260" r="1.8" />
        </g>
      </svg>

      <div className="relative z-10 max-w-lg">
        <div className="text-xs uppercase tracking-[0.2em] text-white/80 font-medium">Check Point</div>
        <div className="text-sm text-white/90 mt-1">MCP Hub</div>
      </div>

      <div className="relative z-10 max-w-lg">
        <h1 className="text-3xl lg:text-4xl font-bold leading-tight tracking-tight">
          We make our world a safer place to live and work.
        </h1>
        <p className="mt-4 text-white/85 text-sm lg:text-base leading-relaxed max-w-md">
          A self-hosted control plane for Check Point's Model Context Protocol servers — connect
          enterprise security data to your AI workflows.
        </p>
        <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 text-xs uppercase tracking-[0.18em] text-white/70 font-medium">
          <span>Trustworthy</span>
          <span aria-hidden>·</span>
          <span>Intelligent</span>
          <span aria-hidden>·</span>
          <span>Relentless</span>
          <span aria-hidden>·</span>
          <span>Approachable</span>
          <span aria-hidden>·</span>
          <span>Innovative</span>
        </div>
      </div>
    </div>
  );
}
