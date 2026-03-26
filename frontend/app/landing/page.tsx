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
          <a href="#features" onClick={(e) => smoothScroll(e, 'features')}>knowledge base</a>
          <a href="#research-tools" onClick={(e) => smoothScroll(e, 'research-tools')}>research tools</a>
          <a href="#integrations" onClick={(e) => smoothScroll(e, 'integrations')}>integrations</a>
          <a href="#pricing" onClick={(e) => smoothScroll(e, 'pricing')}>pricing</a>
          <div className="nav-dropdown">
            <button className="nav-dropdown-trigger">
              research tools
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <div className="nav-dropdown-menu">
              <Link href="/co-work" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Co-Researcher</span>
                  <span className="nav-dropdown-desc">AI assistant for deep research using your knowledge base</span>
                </div>
              </Link>
              <Link href="/high-impact-journal" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Journal Finder</span>
                  <span className="nav-dropdown-desc">Find the perfect journal for your manuscript</span>
                </div>
              </Link>
              <Link href="/citation-analyzer" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Citation Analyzer</span>
                  <span className="nav-dropdown-desc">Map and visualize your citation network</span>
                </div>
              </Link>
              <Link href="/protocol-optimizer" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Protocol Optimizer</span>
                  <span className="nav-dropdown-desc">Optimize protocols with AI suggestions</span>
                </div>
              </Link>
              <Link href="/competitor-finder" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Peer Labs</span>
                  <span className="nav-dropdown-desc">Discover labs working in your research area</span>
                </div>
              </Link>
              <Link href="/reproducibility-archive" className="nav-dropdown-item">
                <div>
                  <span className="nav-dropdown-label">Reproducibility Archive</span>
                  <span className="nav-dropdown-desc">Share and verify experimental reproducibility</span>
                </div>
              </Link>
            </div>
          </div>
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
          <span className="hero-tag">the knowledge transfer platform</span>
          <h1 className="hero-h1">
            your organization&apos;s<br />
            <em>second brain</em>
          </h1>
          <p className="hero-p">
            when people leave, knowledge stays. capture everything — emails, slack, documents — make it instantly searchable with ai, and transfer critical knowledge to the next generation.
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
          <div className="stat-num">100%</div>
          <div className="stat-label">knowledge retention</div>
        </div>
        <div className="stat-item reveal reveal-delay-2">
          <div className="stat-num">0.97</div>
          <div className="stat-label">search accuracy</div>
        </div>
        <div className="stat-item reveal reveal-delay-3">
          <div className="stat-num">6</div>
          <div className="stat-label">ai research tools</div>
        </div>
      </div>

      {/* ═══ Features ═══ */}
      <section className="section" id="features">
        <div className="section-hdr reveal">
          <span className="section-tag">[ knowledge base ]</span>
          <h2 className="section-h2">capture everything. lose nothing.</h2>
          <p className="section-p">connect all your tools, automatically classify and index content, and make your organization&apos;s entire knowledge searchable with ai.</p>
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

          {/* 04 Grant Finder */}
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

      {/* ═══ Research Tools ═══ */}
      <section className="section" id="research-tools">
        <div className="section-hdr reveal">
          <span className="section-tag">[ research tools ]</span>
          <h2 className="section-h2">ai tools built on your knowledge base.</h2>
          <p className="section-p">once your knowledge is connected, unlock powerful research tools that use your data to accelerate discovery.</p>
        </div>
        <div className="agent-grid">
          <div className="agent-card agent-card-wide reveal">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={100} cy={100} r={40} fill="var(--accent)" stroke="none" opacity={0.1} />
              <circle cx={100} cy={100} r={20} strokeDasharray="4 4" />
              <path d="M60 100 L30 100 M140 100 L170 100 M100 60 L100 30 M100 140 L100 170" strokeWidth={1.5} />
              <circle cx={30} cy={100} r={8} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={170} cy={100} r={8} fill="var(--accent)" />
              <circle cx={100} cy={30} r={8} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={100} cy={170} r={8} fill="var(--accent)" />
              <path d="M75 75 L60 60 M125 75 L140 60 M75 125 L60 140 M125 125 L140 140" strokeWidth={1.5} opacity={0.5} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">01 <span className="bento-tag">flagship</span></span>
              <h3 className="bento-name">co-researcher</h3>
              <p className="bento-desc">your ai research partner. ask complex questions, get answers grounded in your lab&apos;s documents, papers, and institutional knowledge. like having a senior colleague who has read everything.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-1">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={50} y={40} width={100} height={120} rx={4} />
              <path d="M70 70 L130 70 M70 90 L130 90 M70 110 L100 110" strokeWidth={2} />
              <circle cx={140} cy={140} r={25} fill="var(--accent)" stroke="none" opacity={0.15} />
              <path d="M135 135 L145 145" strokeWidth={3} stroke="var(--accent)" strokeLinecap="round" />
              <circle cx={130} cy={130} r={12} strokeWidth={2} stroke="var(--accent)" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">02</span>
              <h3 className="bento-name">journal finder</h3>
              <p className="bento-desc">paste your abstract, get ranked journal recommendations with acceptance rates, impact factors, and publication timeline estimates.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-2">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={80} cy={80} r={20} fill="var(--accent)" stroke="none" opacity={0.15} />
              <circle cx={130} cy={70} r={15} />
              <circle cx={70} cy={130} r={15} />
              <circle cx={140} cy={140} r={12} />
              <path d="M95 90 L115 80 M85 105 L75 115 M125 85 L135 125" strokeWidth={1.5} />
              <circle cx={80} cy={80} r={8} fill="currentColor" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">03</span>
              <h3 className="bento-name">citation analyzer</h3>
              <p className="bento-desc">visualize citation networks, find missing references, and discover related papers you might have missed.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-3">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={40} y={60} width={120} height={80} rx={4} />
              <path d="M60 100 L90 80 L120 100 L140 90" strokeWidth={2} stroke="var(--accent)" />
              <circle cx={90} cy={80} r={4} fill="var(--accent)" />
              <circle cx={120} cy={100} r={4} fill="var(--accent)" />
              <path d="M55 120 L145 120" strokeDasharray="4 4" opacity={0.5} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">04</span>
              <h3 className="bento-name">protocol optimizer</h3>
              <p className="bento-desc">upload your protocol, get ai-powered suggestions to improve efficiency based on published literature.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-4">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={100} cy={100} r={50} strokeDasharray="8 8" />
              <circle cx={100} cy={100} r={25} fill="var(--accent)" stroke="none" opacity={0.1} />
              <path d="M70 70 L130 130 M130 70 L70 130" strokeWidth={2} opacity={0.3} />
              <circle cx={70} cy={70} r={12} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={130} cy={70} r={12} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={100} cy={100} r={8} fill="var(--accent)" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">05</span>
              <h3 className="bento-name">peer labs</h3>
              <p className="bento-desc">discover labs working in your research area. find potential collaborators, see their publications, and identify funding opportunities.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-5">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={50} y={50} width={100} height={100} rx={4} />
              <path d="M70 85 L85 100 L130 70" strokeWidth={3} stroke="var(--accent)" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M70 120 L130 120 M70 135 L110 135" strokeWidth={1.5} opacity={0.5} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">06</span>
              <h3 className="bento-name">reproducibility archive</h3>
              <p className="bento-desc">document and share experiment outcomes — including negative results — to advance open science.</p>
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
              <div style={{ color: 'var(--ink-3)', marginBottom: 8 }}>ai-powered search</div>
              <div>▸ <span style={{ color: 'var(--accent)' }}>query</span>: &ldquo;what was the deployment process</div>
              <div>&nbsp;&nbsp;for the redis migration?&rdquo;</div>
              <div>&nbsp;</div>
              <div>▸ <span style={{ color: 'var(--accent)' }}>14 sources</span> found across emails, slack,</div>
              <div>&nbsp;&nbsp;and drive documents</div>
              <div>&nbsp;</div>
              <div>▸ <span style={{ color: 'var(--accent)' }}>confidence</span>: 0.94 — claims verified</div>
              <div>&nbsp;&nbsp;against source documents</div>
              <div>&nbsp;</div>
              <div style={{ color: 'var(--ink-3)' }}>━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
              <div>sources: <span style={{ color: '#9CB896' }}>14</span> | citations: <span style={{ color: '#9CB896' }}>8</span></div>
              <div>hallucination check: <span style={{ color: '#9CB896' }}>passed</span></div>
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
            <div className="pricing-card pricing-featured reveal">
              <div className="pricing-hdr">
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth={1.5} strokeLinecap="round">
                  <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
                </svg>
                <span className="label">lab</span>
                <div className="pricing-tag">most popular</div>
              </div>
              <div className="pricing-price">
                <span className="price-amt">$20</span><span className="price-per">/user/mo</span>
              </div>
              <div className="pricing-desc">for individual research labs.</div>
              <ul className="pricing-list">
                <li>up to 10 users</li>
                <li>all 15+ integrations</li>
                <li>ai-powered search &amp; classification</li>
                <li>co-researcher &amp; research tools</li>
                <li>email support</li>
              </ul>
              <Link href="/signup" className="btn-solid btn-accent btn-full">get lab</Link>
            </div>

            <div className="pricing-card reveal reveal-delay-1">
              <div className="pricing-hdr">
                <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                  <path d="M12 5v14" /><path d="M5 12h14" />
                </svg>
                <span className="label">department</span>
              </div>
              <div className="pricing-price">
                <span className="price-amt">$99</span><span className="price-per">/user/mo</span>
              </div>
              <div className="pricing-desc">for departments and research groups.</div>
              <ul className="pricing-list">
                <li>up to 50 users</li>
                <li>everything in lab</li>
                <li>priority sync &amp; indexing</li>
                <li>grant monitoring &amp; alerts</li>
                <li>advanced analytics dashboard</li>
                <li>priority support</li>
              </ul>
              <Link href="/signup" className="btn-ghost btn-full">get department</Link>
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
              <div className="pricing-desc">for institutions and universities.</div>
              <ul className="pricing-list">
                <li>unlimited users</li>
                <li>everything in department</li>
                <li>dedicated success manager</li>
                <li>custom integrations &amp; connectors</li>
                <li>on-premise or private cloud</li>
                <li>sla guarantees &amp; audit logs</li>
              </ul>
              <a href="mailto:team@2ndbrain.ai" className="btn-ghost btn-full">contact us</a>
            </div>
          </div>
          <p className="pricing-note">all plans include all integrations &middot; ai search &middot; document classification &middot; training videos</p>
        </div>
      </section>

      {/* ═══ Use Cases ═══ */}
      <section className="section" id="use-cases">
        <div className="section-hdr reveal">
          <span className="section-tag">[ use cases ]</span>
          <h2 className="section-h2">trusted by research teams.</h2>
          <p className="section-p">see how different research domains use 2nd brain to preserve knowledge and accelerate discovery.</p>
        </div>
        <div className="agent-grid">
          <div className="agent-card reveal">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={100} cy={80} r={30} strokeDasharray="4 4" />
              <circle cx={100} cy={80} r={15} fill="var(--accent)" stroke="none" opacity={0.2} />
              <path d="M70 130 L100 150 L130 130" strokeWidth={2} />
              <path d="M85 140 L100 150 L115 140" strokeWidth={2} stroke="var(--accent)" />
              <circle cx={70} cy={130} r={8} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={130} cy={130} r={8} fill="var(--paper)" stroke="currentColor" strokeWidth={2} />
              <circle cx={100} cy={150} r={8} fill="var(--accent)" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">biology</span>
              <h3 className="bento-name">wet lab teams</h3>
              <p className="bento-desc">capture protocols, experimental notes, and instrument data. when postdocs leave, their knowledge stays searchable for the next generation.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-1">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={50} y={50} width={100} height={100} rx={4} strokeDasharray="4 4" />
              <path d="M70 100 L90 80 L110 100 L130 70" strokeWidth={2} stroke="var(--accent)" />
              <circle cx={90} cy={80} r={4} fill="var(--accent)" />
              <circle cx={110} cy={100} r={4} fill="var(--accent)" />
              <circle cx={130} cy={70} r={4} fill="var(--accent)" />
              <path d="M70 120 L130 120 M70 135 L110 135" strokeWidth={1.5} opacity={0.5} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">chemistry</span>
              <h3 className="bento-name">synthesis labs</h3>
              <p className="bento-desc">index reaction conditions, compound libraries, and analytical results. ai helps find similar past experiments to optimize new syntheses.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-2">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <circle cx={100} cy={100} r={50} strokeDasharray="8 8" />
              <circle cx={100} cy={100} r={25} fill="var(--accent)" stroke="none" opacity={0.1} />
              <path d="M100 50 L100 150 M50 100 L150 100" strokeWidth={1.5} opacity={0.3} />
              <circle cx={100} cy={70} r={6} fill="currentColor" />
              <circle cx={130} cy={100} r={6} fill="var(--accent)" />
              <circle cx={100} cy={130} r={6} fill="currentColor" />
              <circle cx={70} cy={100} r={6} fill="var(--accent)" />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">clinical</span>
              <h3 className="bento-name">medical research</h3>
              <p className="bento-desc">consolidate patient data workflows, irb documents, and clinical protocols. ensure compliance while making institutional knowledge accessible.</p>
            </div>
          </div>

          <div className="agent-card reveal reveal-delay-3">
            <svg className="agent-svg" viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <rect x={40} y={60} width={50} height={80} rx={4} />
              <rect x={110} y={60} width={50} height={80} rx={4} />
              <path d="M90 100 L110 100" strokeWidth={2} stroke="var(--accent)" />
              <circle cx={65} cy={90} r={10} fill="var(--accent)" stroke="none" opacity={0.2} />
              <circle cx={135} cy={90} r={10} fill="var(--accent)" stroke="none" opacity={0.2} />
              <path d="M55 115 L75 115 M125 115 L145 115" strokeWidth={1.5} opacity={0.5} />
            </svg>
            <div className="agent-card-content">
              <span className="bento-num">engineering</span>
              <h3 className="bento-name">core facilities</h3>
              <p className="bento-desc">centralize equipment manuals, maintenance logs, and training materials. new staff get up to speed faster with ai-powered search.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ FAQ ═══ */}
      <section className="section" id="faq">
        <div className="section-hdr reveal">
          <span className="section-tag">[ faq ]</span>
          <h2 className="section-h2">frequently asked questions.</h2>
        </div>
        <div className="faq-grid reveal">
          <details className="faq-item">
            <summary className="faq-question">how long does it take to get started?</summary>
            <p className="faq-answer">most teams are up and running within a week. connect your integrations (gmail, slack, drive, etc.), and 2nd brain automatically indexes everything. no complex setup or data migration required.</p>
          </details>
          <details className="faq-item">
            <summary className="faq-question">what happens to my data?</summary>
            <p className="faq-answer">your data stays yours. we use enterprise-grade encryption, multi-tenant isolation, and never train ai models on your content. you can export or delete everything at any time.</p>
          </details>
          <details className="faq-item">
            <summary className="faq-question">do you offer academic pricing?</summary>
            <p className="faq-answer">yes. our lab tier at $20/user/month is designed for academic research groups. we also offer volume discounts for departments and custom pricing for university-wide deployments.</p>
          </details>
          <details className="faq-item">
            <summary className="faq-question">how does the ai search work?</summary>
            <p className="faq-answer">we use retrieval-augmented generation (rag) with cross-encoder reranking. ask questions in plain english, and 2nd brain searches your entire knowledge base, returning answers with source citations and confidence scores.</p>
          </details>
          <details className="faq-item">
            <summary className="faq-question">what integrations do you support?</summary>
            <p className="faq-answer">gmail, slack, google drive, box, notion, github, outlook, onedrive, zotero, and more. we also support email forwarding for any source and have an api for custom integrations.</p>
          </details>
          <details className="faq-item">
            <summary className="faq-question">can individual labs adopt without university approval?</summary>
            <p className="faq-answer">yes. our lab tier is designed for individual research groups. no it department involvement required. just sign up, connect your tools, and start preserving knowledge.</p>
          </details>
        </div>
      </section>

      {/* ═══ Footer ═══ */}
      <footer className="footer-dark">
        <div className="footer-hero reveal">
          <div className="footer-logo-wrap">
            <Image src="/owl.png" alt="2nd Brain" width={36} height={36} className="footer-logo-img" />
            <div className="footer-wordmark">2nd Brain</div>
          </div>
          <p className="footer-tagline">knowledge transfer + ai research tools for teams.</p>
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
