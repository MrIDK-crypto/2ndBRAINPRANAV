'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import './landing.css'

/* ════════════════════════════════════════════
   2nd Brain — Landing Page
   Synthetic Sciences design language
   ════════════════════════════════════════════ */

function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible')
          }
        })
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    )
    const el = ref.current
    if (el) {
      el.querySelectorAll('.reveal').forEach((child) => observer.observe(child))
    }
    return () => observer.disconnect()
  }, [])
  return ref
}

export default function LandingPage() {
  const rootRef = useReveal()

  const smoothScroll = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault()
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="landing-root" ref={rootRef}>
      {/* ═══ Navigation ═══ */}
      <nav className="nav">
        <Link href="/" className="nav-logo">
          <Image src="/owl.png" alt="2nd Brain" width={32} height={32} className="nav-logo-img" />
          <span className="nav-logo-text">2nd Brain</span>
        </Link>
        <div className="nav-links">
          <a href="#features" onClick={(e) => smoothScroll(e, 'features')}>features</a>
          <a href="#integrations" onClick={(e) => smoothScroll(e, 'integrations')}>integrations</a>
          <Link href="/product">product</Link>
          <a href="#pricing" onClick={(e) => smoothScroll(e, 'pricing')}>pricing</a>
        </div>
        <div className="nav-cta">
          <Link href="/login" className="btn-ghost">log in</Link>
          <Link href="/signup" className="btn-solid btn-accent">get started</Link>
        </div>
      </nav>

      {/* ═══ Hero ═══ */}
      <section className="hero">
        <div className="hero-bg" />
        <div className="hero-grid" />

        <div className="hero-content reveal">
          <span className="hero-tag">ai-powered knowledge transfer</span>
          <h1 className="hero-h1">
            never lose<br />
            organizational <em>knowledge</em>
          </h1>
          <p className="hero-p">
            capture emails, documents, and messages from every team. make it all searchable with ai. identify knowledge gaps before they become problems.
          </p>
          <div className="hero-cta">
            <Link href="/signup" className="btn-solid btn-accent btn-lg">get started free</Link>
            <div className="install-box">
              <code>pip install 2nd-brain</code>
              <button className="copy-btn" aria-label="copy" onClick={() => navigator.clipboard.writeText('pip install 2nd-brain')}>
                <svg width={13} height={13} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <rect x={9} y={9} width={13} height={13} rx={0} />
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div className="hero-mockup reveal reveal-delay-2">
          <div className="mockup-frame">
            <div className="mockup-titlebar">
              <div className="mockup-dots">
                <span className="dot-close" />
                <span className="dot-min" />
                <span className="dot-max" />
              </div>
              <span className="mockup-title">~/2nd-brain &mdash; zsh</span>
            </div>
            <div className="mockup-terminal">
              <div><span className="t-prompt">~ $</span> <span className="t-cmd">2brain connect --gmail --slack</span></div>
              <div>&nbsp;</div>
              <div><span className="t-dim">connecting integrations...</span></div>
              <div><span className="t-green">✓</span> <span className="t-dim">gmail connected (1,847 emails synced)</span></div>
              <div><span className="t-green">✓</span> <span className="t-dim">slack connected (12 channels synced)</span></div>
              <div>&nbsp;</div>
              <div><span className="t-prompt">~ $</span> <span className="t-cmd">2brain search &quot;Q4 product roadmap&quot;</span></div>
              <div>&nbsp;</div>
              <div><span className="t-dim">searching 2,847 documents...</span></div>
              <div><span className="t-green">✓</span> <span className="t-dim">found 14 relevant sources (0.94 relevance)</span></div>
              <div><span className="t-green">✓</span> <span className="t-dim">generating answer with citations...</span></div>
              <div>&nbsp;</div>
              <div><span className="t-prompt">~ $</span> <span className="t-cmd">2brain gaps --analyze</span></div>
              <div>&nbsp;</div>
              <div><span className="t-green">✓</span> <span className="t-dim">12 knowledge gaps identified across 5 topics</span></div>
              <div><span className="t-green">✓</span> <span className="t-dim">targeted questions generated</span></div>
              <div>&nbsp;</div>
              <div><span className="t-prompt">&gt;</span> <span className="term-cursor" /></div>
            </div>
          </div>
        </div>
      </section>

      <div className="divider" />

      {/* ═══ Stats ═══ */}
      <div className="stats-bar">
        <div className="stat-item reveal">
          <div className="stat-num">15+</div>
          <div className="stat-label">integrations</div>
        </div>
        <div className="stat-item reveal reveal-delay-1">
          <div className="stat-num">2,847</div>
          <div className="stat-label">documents indexed</div>
        </div>
        <div className="stat-item reveal reveal-delay-2">
          <div className="stat-num">0.97</div>
          <div className="stat-label">search accuracy</div>
        </div>
        <div className="stat-item reveal reveal-delay-3">
          <div className="stat-num">24/7</div>
          <div className="stat-label">grant monitoring</div>
        </div>
      </div>

      {/* ═══ Features ═══ */}
      <section className="section" id="features">
        <div className="section-hdr reveal">
          <span className="section-tag">[ features ]</span>
          <h2 className="section-h2">6 core capabilities. one platform.</h2>
          <p className="section-p">from ingestion to insight, every step of knowledge management is covered. connect your tools and let ai do the heavy lifting.</p>
        </div>
        <div className="agent-grid">
          {/* 01 Smart Search — wide */}
          <div className="agent-card agent-card-wide reveal">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={100} cy={100} r={16} fill="var(--accent)" stroke="none" opacity={0.15} />
              <circle cx={100} cy={100} r={4} fill="currentColor" />
              <circle cx={100} cy={100} r={50} strokeDasharray="4 6" opacity={0.5} />
              <circle cx={100} cy={100} r={80} strokeDasharray="1 8" opacity={0.3} />
              <path d="M100 100 L140 60" strokeWidth={1.5} />
              <path d="M100 100 L150 120" strokeWidth={1.5} />
              <path d="M100 100 L60 140" strokeWidth={1.5} />
              <path d="M100 100 L40 80" strokeWidth={1.5} />
              <path d="M100 100 L90 30" strokeWidth={1.5} />
              <circle cx={140} cy={60} r={6} fill="var(--accent)" />
              <circle cx={150} cy={120} r={8} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={60} cy={140} r={10} fill="var(--accent)" opacity={0.4} stroke="none" />
              <circle cx={40} cy={80} r={5} fill="currentColor" />
              <circle cx={90} cy={30} r={7} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">01 <span className="bento-tag">core</span></span>
              <h3 className="bento-name">smart search</h3>
              <p className="bento-desc">ask any question in natural language. ai searches your entire knowledge base — emails, docs, messages — and returns precise answers with source citations.</p>
            </div>
          </div>

          {/* 02 Classification */}
          <div className="agent-card reveal reveal-delay-1">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={100} cy={100} r={50} strokeDasharray="8 8" />
              <path d="M100 20 L100 50 M100 150 L100 180 M20 100 L50 100 M150 100 L180 100" strokeWidth={2} />
              <circle cx={100} cy={100} r={25} fill="var(--accent)" stroke="none" opacity={0.15} />
              <circle cx={100} cy={100} r={8} fill="currentColor" />
              <path d="M100 30 A 70 70 0 0 1 170 100" strokeWidth={2} stroke="var(--accent)" />
              <path d="M170 100 L160 90 M170 100 L180 90" strokeWidth={2} stroke="var(--accent)" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">02</span>
              <h3 className="bento-name">classification</h3>
              <p className="bento-desc">ai-powered document classification separates work from personal content. review, confirm, or reject classifications with one click.</p>
            </div>
          </div>

          {/* 03 Integrations — wide */}
          <div className="agent-card agent-card-wide reveal reveal-delay-2">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <path d="M40 100 Q 70 20 100 100 T 160 100" strokeWidth={2} />
              <path d="M40 100 Q 70 180 100 100 T 160 100" strokeWidth={2} stroke="var(--accent)" />
              <line x1={55} y1={70} x2={55} y2={130} strokeWidth={1.5} opacity={0.6} />
              <line x1={85} y1={40} x2={85} y2={160} strokeWidth={1.5} opacity={0.6} />
              <line x1={115} y1={40} x2={115} y2={160} strokeWidth={1.5} opacity={0.6} />
              <line x1={145} y1={70} x2={145} y2={130} strokeWidth={1.5} opacity={0.6} />
              <circle cx={100} cy={100} r={14} fill="var(--accent)" stroke="none" opacity={0.15} />
              <circle cx={40} cy={100} r={6} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={160} cy={100} r={6} fill="var(--accent)" stroke="none" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">03 <span className="bento-tag">auto</span></span>
              <h3 className="bento-name">integrations</h3>
              <p className="bento-desc">connect gmail, slack, box, google drive, notion, github, outlook, and onedrive. data syncs automatically, classified by ai, and indexed for instant retrieval.</p>
            </div>
          </div>

          {/* 04 Knowledge Gaps */}
          <div className="agent-card reveal reveal-delay-1">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={50} y={30} width={100} height={140} rx={2} strokeWidth={2} />
              <path d="M50 50 L150 50" strokeWidth={1} />
              <line x1={70} y1={70} x2={130} y2={70} strokeLinecap="round" />
              <line x1={70} y1={90} x2={120} y2={90} strokeLinecap="round" />
              <line x1={70} y1={110} x2={130} y2={110} strokeLinecap="round" />
              <line x1={70} y1={130} x2={100} y2={130} strokeLinecap="round" />
              <rect x={65} y={80} width={60} height={20} fill="var(--accent)" stroke="none" opacity={0.12} rx={4} />
              <path d="M140 120 L160 100 L170 110 L150 130 Z" fill="var(--paper)" stroke="currentColor" strokeWidth={1.5} />
              <path d="M140 120 L130 135 L150 130 Z" fill="currentColor" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">04</span>
              <h3 className="bento-name">knowledge gaps</h3>
              <p className="bento-desc">automatically identifies missing documentation and undocumented processes. generates targeted questions, accepts text or voice answers.</p>
            </div>
          </div>

          {/* 05 Grant Finder */}
          <div className="agent-card reveal">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={30} y={50} width={140} height={100} rx={6} strokeWidth={2} />
              <line x1={30} y1={75} x2={170} y2={75} strokeWidth={1.5} />
              <circle cx={45} cy={62} r={3} fill="currentColor" />
              <circle cx={58} cy={62} r={3} fill="currentColor" opacity={0.5} />
              <circle cx={71} cy={62} r={3} fill="currentColor" opacity={0.3} />
              <path d="M50 95 L65 110 L50 125" strokeWidth={2.5} stroke="var(--accent)" strokeLinecap="round" strokeLinejoin="round" />
              <line x1={80} y1={125} x2={95} y2={125} strokeWidth={2.5} />
              <circle cx={100} cy={100} r={35} fill="var(--accent)" stroke="none" opacity={0.06} />
              <line x1={50} y1={140} x2={80} y2={140} strokeLinecap="round" opacity={0.5} />
              <line x1={90} y1={140} x2={150} y2={140} strokeLinecap="round" opacity={0.3} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">05</span>
              <h3 className="bento-name">grant finder</h3>
              <p className="bento-desc">daily automated scraping from nih reporter, grants.gov, nsf, and sbir. thousands of grants indexed and searchable through your ai assistant.</p>
            </div>
          </div>

          {/* 06 Multi-tenant — wide */}
          <div className="agent-card agent-card-wide reveal reveal-delay-1">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={75} y={40} width={50} height={30} rx={6} strokeWidth={2} fill="var(--paper)" />
              <rect x={30} y={110} width={40} height={26} rx={4} fill="var(--paper)" />
              <rect x={130} y={110} width={40} height={26} rx={4} fill="var(--paper)" />
              <rect x={80} y={150} width={40} height={26} rx={4} fill="var(--paper)" />
              <path d="M100 70 L100 90 L50 90 L50 110" strokeWidth={1.5} strokeLinejoin="round" />
              <path d="M100 70 L100 90 L150 90 L150 110" strokeWidth={1.5} strokeLinejoin="round" />
              <path d="M50 136 L50 163 L80 163" strokeWidth={1.5} strokeDasharray="3 3" />
              <path d="M150 136 L150 163 L120 163" strokeWidth={1.5} strokeDasharray="3 3" />
              <circle cx={100} cy={55} r={25} fill="var(--accent)" stroke="none" opacity={0.08} />
              <path d="M90 55 L95 60 L110 45" stroke="var(--accent)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">06</span>
              <h3 className="bento-name">multi-tenant</h3>
              <p className="bento-desc">enterprise-grade isolation. each organization gets its own secure data partition, user management, and audit trail. soc 2 ready architecture.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Showcase 1 — AI Search ═══ */}
      <section className="showcase">
        <div className="showcase-art" aria-hidden="true" />
        <div className="showcase-inner reveal">
          <div className="showcase-text">
            <h2 className="showcase-h2">search everything. find anything.</h2>
            <p className="showcase-p">
              ask a question in plain english. 2nd brain searches across all your connected sources — emails, documents, slack messages, drive files — and returns a precise answer with source citations. powered by rag with cross-encoder reranking and hallucination detection.
            </p>
          </div>
          <div className="showcase-screenshot">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 2, color: 'var(--ink-2)', position: 'relative', zIndex: 1 }}>
              <div><span style={{ color: 'var(--ink-3)' }}>query:</span> &quot;what was decided about the Q4 roadmap?&quot;</div>
              <div>&nbsp;</div>
              <div><span style={{ color: 'var(--accent)' }}>→</span> searching 2,847 documents...</div>
              <div><span style={{ color: 'var(--accent)' }}>→</span> reranking 14 candidates...</div>
              <div><span style={{ color: '#9CB896' }}>✓</span> 5 sources verified</div>
              <div>&nbsp;</div>
              <div style={{ color: 'var(--ink)' }}>based on the Q4 planning email [source 1]</div>
              <div style={{ color: 'var(--ink)' }}>and slack discussion [source 2], the team</div>
              <div style={{ color: 'var(--ink)' }}>decided to prioritize mobile-first...</div>
              <div>&nbsp;</div>
              <div><span style={{ color: 'var(--ink-3)' }}>confidence:</span> <span style={{ color: '#9CB896' }}>0.94</span></div>
              <div><span style={{ color: 'var(--ink-3)' }}>claims verified:</span> 5/5</div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Cloud Cards ═══ */}
      <div className="cloud-grid" id="capabilities">
        <div className="cloud-card reveal">
          <svg className="cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <circle cx={11} cy={11} r={8} /><path d="m21 21-4.3-4.3" />
          </svg>
          <h3 className="cloud-name">rag search engine</h3>
          <p className="cloud-desc">cross-encoder reranking, query expansion with 100+ acronyms, mmr diversity, and hallucination detection built in.</p>
        </div>
        <div className="cloud-card reveal reveal-delay-1">
          <svg className="cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <rect x={2} y={3} width={20} height={14} rx={2} /><path d="M8 21h8" /><path d="M12 17v4" />
          </svg>
          <h3 className="cloud-name">smart classification</h3>
          <p className="cloud-desc">every ingested document is automatically classified as work or personal using gpt-5. review and confirm with bulk actions.</p>
        </div>
        <div className="cloud-card reveal reveal-delay-2">
          <svg className="cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />
          </svg>
          <h3 className="cloud-name">knowledge gap detection</h3>
          <p className="cloud-desc">150+ nlp patterns detect missing docs, bus-factor risks, and contradictions. generates targeted questions to fill gaps.</p>
        </div>
        <div className="cloud-card reveal reveal-delay-3">
          <svg className="cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" />
          </svg>
          <h3 className="cloud-name">grant monitoring</h3>
          <p className="cloud-desc">daily scraping from nih reporter, grants.gov, nsf, and sbir. thousands of grants auto-indexed and searchable via chatbot.</p>
        </div>
        <div className="cloud-card reveal reveal-delay-4">
          <svg className="cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" /><circle cx={9} cy={7} r={4} /><path d="M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
          </svg>
          <h3 className="cloud-name">multi-tenant isolation</h3>
          <p className="cloud-desc">jwt auth, per-tenant data partitions, pinecone namespace isolation, and tier-based rate limiting.</p>
        </div>
        <div className="cloud-card reveal reveal-delay-5">
          <svg className="cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
            <path d="m15.5 7.5 2.3 2.3a1 1 0 0 1 0 1.4l-2.3 2.3" /><path d="m8.5 16.5-2.3-2.3a1 1 0 0 1 0-1.4l2.3-2.3" /><path d="m21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
          <h3 className="cloud-name">video training</h3>
          <p className="cloud-desc">auto-generate onboarding videos from your knowledge base with ai scripts, text-to-speech, and visual slides.</p>
        </div>
      </div>

      {/* ═══ Showcase 2 — Knowledge Preservation ═══ */}
      <section className="showcase showcase-reverse">
        <div className="showcase-art showcase-art-2" aria-hidden="true" />
        <div className="showcase-inner reveal">
          <div className="showcase-text">
            <h2 className="showcase-h2">your team&apos;s knowledge, always accessible.</h2>
            <p className="showcase-p">
              when someone leaves, their knowledge stays. every email, document, and conversation is preserved, searchable, and ready for the next person who needs it. no more &ldquo;ask john, he knows.&rdquo;
            </p>
          </div>
          <div className="showcase-screenshot">
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.8, color: 'var(--ink-2)', position: 'relative', zIndex: 1 }}>
              <div style={{ color: 'var(--ink-3)', marginBottom: 8 }}>knowledge gap analysis</div>
              <div>▸ <span style={{ color: 'var(--accent)' }}>bus factor risk</span>: sarah manages deployments,</div>
              <div>&nbsp;&nbsp;monitoring, and incident response alone</div>
              <div>&nbsp;</div>
              <div>▸ <span style={{ color: 'var(--accent)' }}>missing rationale</span>: &ldquo;we switched from</div>
              <div>&nbsp;&nbsp;redis to memcached&rdquo; — no reason documented</div>
              <div>&nbsp;</div>
              <div>▸ <span style={{ color: 'var(--accent)' }}>implicit process</span>: &ldquo;the usual deploy</div>
              <div>&nbsp;&nbsp;steps&rdquo; referenced but never written down</div>
              <div>&nbsp;</div>
              <div style={{ color: 'var(--ink-3)' }}>━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
              <div>gaps found: <span style={{ color: '#9CB896' }}>12</span> | questions: <span style={{ color: '#9CB896' }}>24</span></div>
              <div>quality score: <span style={{ color: '#9CB896' }}>0.87</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Integrations ═══ */}
      <section className="isg-section" id="integrations">
        <div className="section-hdr reveal">
          <span className="section-tag">[ integrations ]</span>
          <h2 className="section-h2">connect everything. miss nothing.</h2>
          <p className="section-p">15+ integrations with the tools your team already uses. data flows in automatically.</p>
        </div>
        <div className="isg-grid">
          <div className="isg-card reveal">
            <div className="isg-visual">
              <div className="logo-bubble" style={{ top: '20%', left: '15%', animationDelay: '0s' }}>
                <img src="/gmail.png" alt="Gmail" />
              </div>
              <div className="logo-bubble" style={{ top: '30%', right: '20%', animationDelay: '1s' }}>
                <img src="/slack.png" alt="Slack" />
              </div>
              <div className="logo-bubble" style={{ bottom: '25%', left: '35%', animationDelay: '2s' }}>
                <img src="/outlook.png" alt="Outlook" />
              </div>
              <div className="logo-bubble" style={{ top: '50%', right: '35%', animationDelay: '0.5s' }}>
                <img src="/notion.png" alt="Notion" />
              </div>
            </div>
            <div className="isg-content">
              <h3 className="isg-title">communication</h3>
              <p className="isg-desc">gmail, slack, outlook, and email forwarding. every conversation captured and classified automatically.</p>
            </div>
          </div>

          <div className="isg-card reveal reveal-delay-1">
            <div className="isg-visual">
              <div className="logo-bubble" style={{ top: '20%', left: '20%', animationDelay: '0.3s' }}>
                <img src="/gdrive.png" alt="Google Drive" />
              </div>
              <div className="logo-bubble" style={{ top: '40%', right: '15%', animationDelay: '1.5s' }}>
                <img src="/box.png" alt="Box" />
              </div>
              <div className="logo-bubble" style={{ bottom: '20%', left: '40%', animationDelay: '0.8s' }}>
                <img src="/notion.png" alt="Notion" />
              </div>
              <div className="logo-bubble" style={{ bottom: '35%', right: '30%', animationDelay: '2.2s' }}>
                <img src="/github.png" alt="GitHub" />
              </div>
            </div>
            <div className="isg-content">
              <h3 className="isg-title">documents &amp; code</h3>
              <p className="isg-desc">google drive, box, notion, github, onedrive, google docs, sheets, slides, excel, and powerpoint.</p>
            </div>
          </div>

          <div className="isg-card reveal reveal-delay-2">
            <div className="isg-visual">
              <div className="logo-bubble" style={{ top: '25%', left: '25%', animationDelay: '0.6s' }}>
                <img src="/zotero.webp" alt="Zotero" />
              </div>
              <div className="logo-bubble" style={{ top: '35%', right: '25%', animationDelay: '1.8s' }}>
                <img src="/pubmed.png" alt="PubMed" />
              </div>
              <div className="logo-bubble" style={{ bottom: '30%', left: '35%', animationDelay: '1.2s' }}>
                <img src="/googlescholar.png" alt="Google Scholar" />
              </div>
            </div>
            <div className="isg-content">
              <h3 className="isg-title">research</h3>
              <p className="isg-desc">zotero, pubmed, and google scholar. keep your citations and references searchable alongside everything else.</p>
            </div>
          </div>

          <div className="isg-card reveal reveal-delay-3">
            <div className="isg-visual">
              <svg viewBox="0 0 800 200" fill="none" stroke="currentColor" strokeWidth={1.5} style={{ width: '100%', height: '100%', opacity: 0.4 }} preserveAspectRatio="xMidYMid slice">
                <path d="M0 100 Q 200 0 400 100 T 800 100" strokeWidth={2} stroke="var(--accent)" opacity={0.3} />
                <path d="M0 100 Q 200 200 400 100 T 800 100" strokeWidth={2} opacity={0.1} />
                <circle cx={100} cy={75} r={4} fill="var(--accent)" stroke="none" />
                <circle cx={300} cy={125} r={6} fill="currentColor" stroke="none" />
                <circle cx={500} cy={75} r={5} fill="var(--accent)" stroke="none" />
                <circle cx={700} cy={125} r={4} fill="currentColor" stroke="none" />
              </svg>
            </div>
            <div className="isg-content">
              <h3 className="isg-title">zero-config deployment</h3>
              <p className="isg-desc">deploy on any cloud in minutes. sqlite for development, postgresql for production. multi-tenant isolation out of the box.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Pricing ═══ */}
      <section className="pricing-section" id="pricing">
        <div className="pricing-wrap">
          <div className="section-hdr reveal">
            <span className="section-tag">[ pricing ]</span>
            <h2 className="section-h2">simple, transparent pricing.</h2>
            <p className="section-p">transparent pricing for teams of every size. all plans include unlimited integrations and ai-powered search.</p>
          </div>
          <div className="pricing-row">
            <div className="pricing-card reveal">
              <div className="pricing-hdr">
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                  <path d="M12 5v14" /><path d="M5 12h14" />
                </svg>
                <span className="label">starter</span>
              </div>
              <div className="pricing-price">
                <span className="price-amt">$29</span><span className="price-per">/user/mo</span>
              </div>
              <div className="pricing-desc">for small teams getting started.</div>
              <ul className="pricing-list">
                <li>up to 10 users</li>
                <li>all 15+ integrations</li>
                <li>ai-powered search &amp; classification</li>
                <li>knowledge gap analysis</li>
                <li>automatic indexing</li>
                <li>email support</li>
              </ul>
              <Link href="/signup" className="btn-ghost btn-full">get started</Link>
            </div>

            <div className="pricing-card pricing-featured reveal reveal-delay-1">
              <div className="pricing-hdr">
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth={1.5} strokeLinecap="round">
                  <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
                </svg>
                <span className="label">growth</span>
                <div className="pricing-tag">most popular</div>
              </div>
              <div className="pricing-price">
                <span className="price-amt">$79</span><span className="price-per">/user/mo</span>
              </div>
              <div className="pricing-desc">for growing organizations.</div>
              <ul className="pricing-list">
                <li>up to 50 users</li>
                <li>everything in starter</li>
                <li>priority sync &amp; indexing</li>
                <li>grant monitoring &amp; alerts</li>
                <li>advanced analytics dashboard</li>
                <li>priority support</li>
              </ul>
              <Link href="/signup" className="btn-solid btn-accent btn-full">get growth</Link>
            </div>

            <div className="pricing-card reveal reveal-delay-2">
              <div className="pricing-hdr">
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <rect x={2} y={7} width={20} height={14} rx={2} /><path d="M16 7V5a4 4 0 00-8 0v2" />
                </svg>
                <span className="label">enterprise</span>
              </div>
              <div className="pricing-price">
                <span className="price-amt">custom</span>
              </div>
              <div className="pricing-desc">for enterprises with complex needs.</div>
              <ul className="pricing-list">
                <li>unlimited users</li>
                <li>everything in growth</li>
                <li>dedicated success manager</li>
                <li>custom integrations &amp; connectors</li>
                <li>on-premise or private cloud</li>
                <li>sla guarantees &amp; audit logs</li>
              </ul>
              <a href="mailto:team@2ndbrain.ai" className="btn-ghost btn-full">contact us</a>
            </div>
          </div>
          <p className="pricing-note">all plans include all integrations &middot; ai search &middot; document classification &middot; knowledge gaps</p>
        </div>
      </section>

      {/* ═══ Footer ═══ */}
      <footer className="footer-dark">
        <div className="footer-hero reveal">
          <div className="footer-logo-wrap">
            <Image src="/owl.png" alt="2nd Brain" width={36} height={36} className="footer-logo-img" />
            <div className="footer-wordmark">2nd Brain</div>
          </div>
          <p className="footer-tagline">ai-powered knowledge transfer for enterprises.</p>
          <Link href="/signup" className="btn-footer">get started</Link>
        </div>
        <nav className="footer-nav">
          <a href="#features" onClick={(e) => smoothScroll(e, 'features')}>features</a>
          <a href="#integrations" onClick={(e) => smoothScroll(e, 'integrations')}>integrations</a>
          <Link href="/product">product</Link>
          <a href="#pricing" onClick={(e) => smoothScroll(e, 'pricing')}>pricing</a>
          <Link href="/terms">terms</Link>
          <Link href="/privacy">privacy</Link>
        </nav>
        <div className="footer-bottom">
          <span>&copy; 2026 2nd brain inc.</span>
          <div className="footer-bottom-links">
            <a href="mailto:team@2ndbrain.ai">email</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
