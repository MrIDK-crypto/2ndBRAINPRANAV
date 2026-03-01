'use client'

import { useEffect, useRef } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import './product.css'

function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) e.target.classList.add('visible') }),
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    )
    ref.current?.querySelectorAll('.reveal').forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])
  return ref
}

export default function ProductPage() {
  const rootRef = useReveal()

  return (
    <div className="product-root" ref={rootRef}>
      {/* ═══ Nav ═══ */}
      <nav className="nav">
        <Link href="/" className="nav-logo">
          <Image src="/owl.png" alt="2nd Brain" width={32} height={32} className="nav-logo-img" />
          <span className="nav-logo-text">2nd Brain</span>
        </Link>
        <div className="nav-links">
          <Link href="/#features">features</Link>
          <Link href="/#integrations">integrations</Link>
          <Link href="/product" style={{ color: 'var(--ink)' }}>product</Link>
          <Link href="/#pricing">pricing</Link>
        </div>
        <div className="nav-cta">
          <Link href="/login" className="btn-ghost">log in</Link>
          <Link href="/signup" className="btn-solid btn-accent">get started</Link>
        </div>
      </nav>

      {/* ═══ Hero ═══ */}
      <section className="product-hero">
        <div className="product-hero-content reveal">
          <span className="product-tag">product</span>
          <h1 className="product-h1">
            the <em>complete</em> knowledge<br />
            transfer platform
          </h1>
          <p className="product-subtitle">
            from ingestion to insight in four steps. connect your tools, let ai classify and index everything, then search with precision and fill knowledge gaps automatically.
          </p>
          <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link href="/signup" className="btn-solid btn-accent btn-lg">start free trial</Link>
            <Link href="/#pricing" className="btn-ghost btn-lg">view pricing</Link>
          </div>
        </div>
      </section>

      {/* ═══ How It Works ═══ */}
      <section className="how-section">
        <div className="section-hdr reveal">
          <span className="section-tag">[ how it works ]</span>
          <h2 className="section-h2">four steps to zero knowledge loss.</h2>
          <p className="section-p">from raw data to searchable intelligence in minutes, not months.</p>
        </div>
        <div className="steps-grid">
          <div className="step-card reveal">
            <div className="step-num">step 01</div>
            <div className="step-icon">
              <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
              </svg>
            </div>
            <h3 className="step-title">connect</h3>
            <p className="step-desc">link gmail, slack, drive, box, notion, github, outlook, and more. oauth in seconds.</p>
          </div>

          <div className="step-card reveal reveal-delay-1">
            <div className="step-num">step 02</div>
            <div className="step-icon">
              <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
                <path d="M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12" />
              </svg>
            </div>
            <h3 className="step-title">ingest</h3>
            <p className="step-desc">data flows in automatically. emails, documents, messages — all parsed, chunked, and embedded.</p>
          </div>

          <div className="step-card reveal reveal-delay-2">
            <div className="step-num">step 03</div>
            <div className="step-icon">
              <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" />
              </svg>
            </div>
            <h3 className="step-title">classify</h3>
            <p className="step-desc">ai separates work from personal. review, confirm, or reject with one click. then everything gets indexed.</p>
          </div>

          <div className="step-card reveal reveal-delay-3">
            <div className="step-num">step 04</div>
            <div className="step-icon">
              <svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                <circle cx={11} cy={11} r={8} /><path d="m21 21-4.3-4.3" />
              </svg>
            </div>
            <h3 className="step-title">search</h3>
            <p className="step-desc">ask anything. get answers with citations, verified claims, and confidence scores. knowledge gaps auto-detected.</p>
          </div>
        </div>
      </section>

      {/* ═══ Feature Deep Dives ═══ */}
      <section className="feature-deep">
        {/* RAG Search */}
        <div className="feature-row reveal">
          <div className="feature-text">
            <div className="feature-badge">core engine</div>
            <h3 className="feature-h3">rag search with hallucination detection</h3>
            <p className="feature-desc">
              not just keyword matching — a full retrieval-augmented generation pipeline with multi-stage verification.
            </p>
            <ul className="feature-list">
              <li>cross-encoder reranking (ms-marco-minilm-l-12-v2)</li>
              <li>query expansion with 100+ domain acronyms</li>
              <li>mmr diversity to avoid redundant results</li>
              <li>claim extraction + source verification</li>
              <li>citation enforcement with coverage scoring</li>
              <li>freshness boost for recent documents</li>
            </ul>
          </div>
          <div className="feature-visual">
            <div className="feature-terminal">
              <div style={{ color: 'var(--ink-3)', marginBottom: 12 }}>enhanced rag pipeline</div>
              <div>
                <span style={{ color: 'var(--accent)' }}>1.</span> query: &quot;what&apos;s our roi on nicu?&quot;
              </div>
              <div>
                <span style={{ color: 'var(--accent)' }}>2.</span> expand → &quot;roi (return on investment)
              </div>
              <div>&nbsp;&nbsp;&nbsp;on nicu (neonatal intensive care unit)&quot;</div>
              <div>
                <span style={{ color: 'var(--accent)' }}>3.</span> pinecone top-k: 40 candidates
              </div>
              <div>
                <span style={{ color: 'var(--accent)' }}>4.</span> rerank → 15 relevant sources
              </div>
              <div>
                <span style={{ color: 'var(--accent)' }}>5.</span> mmr diversity: 8 unique angles
              </div>
              <div>
                <span style={{ color: 'var(--accent)' }}>6.</span> generate answer with citations
              </div>
              <div>&nbsp;</div>
              <div style={{ color: 'var(--ink-3)' }}>━━━━━━━━━━━━━━━━━━━━━━━━</div>
              <div>
                claims verified: <span style={{ color: '#22C55E' }}>5/5</span>
              </div>
              <div>
                citation coverage: <span style={{ color: '#22C55E' }}>0.92</span>
              </div>
              <div>
                confidence: <span style={{ color: '#22C55E' }}>0.94</span>
              </div>
            </div>
          </div>
        </div>

        {/* Knowledge Gaps */}
        <div className="feature-row feature-row-reverse reveal">
          <div className="feature-text">
            <div className="feature-badge">nlp engine</div>
            <h3 className="feature-h3">intelligent knowledge gap detection</h3>
            <p className="feature-desc">
              six-layer nlp architecture that finds what&apos;s missing, not just what&apos;s there. no llm calls required — pure pattern matching.
            </p>
            <ul className="feature-list">
              <li>150+ trigger patterns across 8 frame types</li>
              <li>semantic role labeling (agent, patient, cause)</li>
              <li>knowledge graph with entity normalization</li>
              <li>cross-document contradiction detection</li>
              <li>bus factor risk analysis</li>
              <li>fingerprint-based deduplication</li>
            </ul>
          </div>
          <div className="feature-visual">
            <div className="feature-terminal">
              <div style={{ color: 'var(--ink-3)', marginBottom: 12 }}>gap analysis — 6 layers</div>
              <div><span style={{ color: 'var(--accent)' }}>layer 1</span> frame extraction</div>
              <div>&nbsp;&nbsp;→ 847 frames from 120 documents</div>
              <div><span style={{ color: 'var(--accent)' }}>layer 2</span> semantic role labeling</div>
              <div>&nbsp;&nbsp;→ 312 missing agents identified</div>
              <div><span style={{ color: 'var(--accent)' }}>layer 3</span> discourse analysis</div>
              <div>&nbsp;&nbsp;→ 45 unsupported claims</div>
              <div><span style={{ color: 'var(--accent)' }}>layer 4</span> knowledge graph</div>
              <div>&nbsp;&nbsp;→ 2 bus factor risks detected</div>
              <div><span style={{ color: 'var(--accent)' }}>layer 5</span> cross-doc verification</div>
              <div>&nbsp;&nbsp;→ 3 contradictions found</div>
              <div><span style={{ color: 'var(--accent)' }}>layer 6</span> question generation</div>
              <div>&nbsp;&nbsp;→ 24 grounded questions</div>
              <div>&nbsp;</div>
              <div>quality score: <span style={{ color: '#22C55E' }}>0.87</span></div>
            </div>
          </div>
        </div>

        {/* Grant Finder */}
        <div className="feature-row reveal">
          <div className="feature-text">
            <div className="feature-badge">daily scraper</div>
            <h3 className="feature-h3">automated grant monitoring</h3>
            <p className="feature-desc">
              never miss a funding opportunity. daily scraping across five federal apis, with cross-source deduplication and smart relevance matching.
            </p>
            <ul className="feature-list">
              <li>nih reporter — 500+ results per query</li>
              <li>grants.gov with full abstracts via detail api</li>
              <li>nsf award search — all active awards</li>
              <li>sbir.gov — dod, hhs, nasa, nsf, doe</li>
              <li>cross-source dedup by normalized title</li>
              <li>rate limiting with exponential backoff</li>
            </ul>
          </div>
          <div className="feature-visual">
            <div className="feature-terminal">
              <div style={{ color: 'var(--ink-3)', marginBottom: 12 }}>daily grant scraper — celery beat</div>
              <div><span style={{ color: '#22C55E' }}>✓</span> nih reporter: 2,847 grants</div>
              <div><span style={{ color: '#22C55E' }}>✓</span> grants.gov: 1,203 opportunities</div>
              <div><span style={{ color: '#22C55E' }}>✓</span> nsf awards: 1,456 active</div>
              <div><span style={{ color: '#22C55E' }}>✓</span> sbir: 312 across 5 agencies</div>
              <div>&nbsp;</div>
              <div>total unique: <span style={{ color: 'var(--accent)' }}>4,891</span></div>
              <div>cross-source dedup: <span style={{ color: 'var(--accent)' }}>−127</span></div>
              <div>new today: <span style={{ color: '#22C55E' }}>234</span></div>
              <div>&nbsp;</div>
              <div style={{ color: 'var(--ink-3)' }}>━━━━━━━━━━━━━━━━━━━━━━━━</div>
              <div>embedded to pinecone: <span style={{ color: '#22C55E' }}>✓</span></div>
              <div>searchable via chatbot: <span style={{ color: '#22C55E' }}>✓</span></div>
              <div>next scrape: 6:00 am utc</div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Architecture ═══ */}
      <section className="arch-section">
        <div className="arch-inner">
          <div className="section-hdr reveal">
            <span className="section-tag">[ architecture ]</span>
            <h2 className="section-h2">built for scale.</h2>
            <p className="section-p">production-grade infrastructure that grows with your organization.</p>
          </div>
          <div className="arch-grid">
            <div className="arch-card reveal">
              <svg className="arch-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
              </svg>
              <h3 className="arch-name">flask + sqlalchemy</h3>
              <p className="arch-desc">python backend with postgresql in production, jwt auth, per-tenant data isolation, and comprehensive api.</p>
            </div>
            <div className="arch-card reveal reveal-delay-1">
              <svg className="arch-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                <rect x={2} y={3} width={20} height={14} rx={2} /><path d="M8 21h8M12 17v4" />
              </svg>
              <h3 className="arch-name">next.js 14 frontend</h3>
              <p className="arch-desc">react 18 + typescript + tailwind css. responsive design, real-time chat interface, and integration dashboards.</p>
            </div>
            <div className="arch-card reveal reveal-delay-2">
              <svg className="arch-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                <circle cx={12} cy={12} r={10} /><path d="M12 2a14.5 14.5 0 000 20 14.5 14.5 0 000-20M2 12h20" />
              </svg>
              <h3 className="arch-name">pinecone + azure openai</h3>
              <p className="arch-desc">vector embeddings with text-embedding-3-large (1536d), namespace isolation per tenant, gpt-5 for generation.</p>
            </div>
            <div className="arch-card reveal reveal-delay-1">
              <svg className="arch-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              <h3 className="arch-name">aws ecs fargate</h3>
              <p className="arch-desc">containerized deployment with auto-scaling. github actions ci/cd. rds postgresql. cloudwatch monitoring.</p>
            </div>
            <div className="arch-card reveal reveal-delay-2">
              <svg className="arch-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                <path d="M4 14a1 1 0 01-.78-1.63l9.9-10.2a.5.5 0 01.86.46l-1.92 6.02A1 1 0 0013 10h7a1 1 0 01.78 1.63l-9.9 10.2a.5.5 0 01-.86-.46l1.92-6.02A1 1 0 0011 14z" />
              </svg>
              <h3 className="arch-name">celery + redis</h3>
              <p className="arch-desc">background task processing for syncs, embeddings, and daily grant scraping. beat scheduler for periodic jobs.</p>
            </div>
            <div className="arch-card reveal reveal-delay-3">
              <svg className="arch-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
                <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" /><circle cx={9} cy={7} r={4} /><path d="M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
              </svg>
              <h3 className="arch-name">multi-tenant isolation</h3>
              <p className="arch-desc">jwt-only auth, per-tenant pinecone namespaces, tier-based rate limits, and comprehensive audit logging.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Security ═══ */}
      <section className="security-section">
        <div className="section-hdr reveal">
          <span className="section-tag">[ security ]</span>
          <h2 className="section-h2">enterprise-grade protection.</h2>
          <p className="section-p">your data is isolated, encrypted, and audited at every layer.</p>
        </div>
        <div className="security-grid">
          <div className="security-card reveal">
            <svg className="security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
              <rect x={3} y={11} width={18} height={11} rx={2} /><path d="M7 11V7a5 5 0 0110 0v4" />
            </svg>
            <div>
              <h3 className="security-name">jwt authentication</h3>
              <p className="security-desc">bcrypt password hashing, refresh token rotation, session management, and no header spoofing vectors.</p>
            </div>
          </div>
          <div className="security-card reveal reveal-delay-1">
            <svg className="security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <div>
              <h3 className="security-name">tenant isolation</h3>
              <p className="security-desc">data partitioned by tenant at every layer — database, vector store, file storage, and api access.</p>
            </div>
          </div>
          <div className="security-card reveal reveal-delay-2">
            <svg className="security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
              <path d="M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2" /><circle cx={9} cy={7} r={4} /><line x1={19} y1={8} x2={19} y2={14} /><line x1={22} y1={11} x2={16} y2={11} />
            </svg>
            <div>
              <h3 className="security-name">rate limiting</h3>
              <p className="security-desc">tier-based rate limits per tenant. free, starter, professional, and enterprise tiers with configurable thresholds.</p>
            </div>
          </div>
          <div className="security-card reveal reveal-delay-3">
            <svg className="security-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" /><path d="M16 13H8M16 17H8M10 9H8" />
            </svg>
            <div>
              <h3 className="security-name">audit logging</h3>
              <p className="security-desc">every api call, data access, and configuration change logged with timestamp, user, tenant, and action details.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ CTA ═══ */}
      <section className="cta-section">
        <div className="cta-inner reveal">
          <h2 className="cta-h2">ready to preserve your team&apos;s knowledge?</h2>
          <p className="cta-p">start for free. no credit card required. connect your first integration in under 60 seconds.</p>
          <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link href="/signup" className="btn-solid btn-accent btn-lg">get started free</Link>
            <a href="mailto:team@2ndbrain.ai" className="btn-ghost btn-lg">contact sales</a>
          </div>
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
          <Link href="/#features">features</Link>
          <Link href="/#integrations">integrations</Link>
          <Link href="/product">product</Link>
          <Link href="/#pricing">pricing</Link>
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
