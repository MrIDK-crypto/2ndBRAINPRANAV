'use client'

import React from 'react'
import Link from 'next/link'
import Image from 'next/image'

// Wellspring-Inspired Warm Design System
const warmTheme = {
  primary: '#C9A598',
  primaryHover: '#B8948A',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFE',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
}

export default function PrivacyPage() {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: warmTheme.pageBg,
      padding: '40px 20px'
    }}>
      <div style={{
        maxWidth: '800px',
        margin: '0 auto',
        backgroundColor: warmTheme.cardBg,
        borderRadius: '16px',
        padding: '40px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
        border: `1px solid ${warmTheme.border}`
      }}>
        {/* Header with logo */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '32px'
        }}>
          <Link href="/" style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '12px',
            textDecoration: 'none'
          }}>
            <Image src="/owl.png" alt="2nd Brain" width={36} height={45} style={{ objectFit: 'contain' }} />
            <span style={{
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              fontSize: '18px',
              fontWeight: 600,
              color: warmTheme.textPrimary
            }}>
              2nd Brain
            </span>
          </Link>
          <Link href="/" style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: warmTheme.primary,
            textDecoration: 'none',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontSize: '14px',
            fontWeight: 500
          }}>
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
              <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Home
          </Link>
        </div>

        <h1 style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '32px',
          fontWeight: 700,
          color: warmTheme.textPrimary,
          marginBottom: '8px'
        }}>
          Privacy Policy
        </h1>

        <p style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '14px',
          color: warmTheme.textMuted,
          marginBottom: '32px'
        }}>
          Last updated: February 4, 2026
        </p>

        <div style={{
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          fontSize: '15px',
          color: warmTheme.textSecondary,
          lineHeight: '1.7'
        }}>
          <Section title="1. Introduction">
            <p>
              2nd Brain ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy
              explains how we collect, use, disclose, and safeguard your information when you use our
              AI-powered knowledge management platform.
            </p>
          </Section>

          <Section title="2. Information We Collect">
            <h4>2.1 Account Information</h4>
            <p>When you create an account, we collect:</p>
            <ul>
              <li>Full name</li>
              <li>Email address</li>
              <li>Organization name</li>
              <li>Password (stored securely using bcrypt hashing)</li>
            </ul>

            <h4>2.2 Integration Data</h4>
            <p>When you connect third-party services, we may access:</p>
            <ul>
              <li><strong>Gmail:</strong> Email messages, attachments, sender/recipient information</li>
              <li><strong>Slack:</strong> Messages, channels, files, workspace information</li>
              <li><strong>Box:</strong> Documents, files, folder structures</li>
              <li><strong>GitHub:</strong> Repository content, code files, documentation</li>
              <li><strong>Microsoft OneDrive:</strong> Documents and files</li>
            </ul>

            <h4>2.3 Voice Data</h4>
            <p>
              When you use voice recording features, we process audio through Azure Whisper for
              transcription. Audio files are processed and not permanently stored after transcription.
            </p>

            <h4>2.4 Usage Data</h4>
            <p>We automatically collect:</p>
            <ul>
              <li>Search queries within the platform</li>
              <li>Feature usage patterns</li>
              <li>Session information</li>
              <li>Error logs for troubleshooting</li>
            </ul>
          </Section>

          <Section title="3. How We Use Your Information">
            <p>We use the collected information to:</p>
            <ul>
              <li>Provide and maintain the Service</li>
              <li>Process and classify documents using AI</li>
              <li>Generate vector embeddings for semantic search</li>
              <li>Identify knowledge gaps in your organization</li>
              <li>Generate training videos and materials</li>
              <li>Improve our AI models and services</li>
              <li>Send service-related communications</li>
              <li>Respond to support requests</li>
            </ul>
          </Section>

          <Section title="4. AI and Data Processing">
            <h4>4.1 Azure OpenAI Services</h4>
            <p>Your data is processed using Azure OpenAI services for:</p>
            <ul>
              <li>Document classification (work vs. personal)</li>
              <li>Knowledge gap analysis</li>
              <li>RAG (Retrieval-Augmented Generation) responses</li>
              <li>Content summarization</li>
            </ul>

            <h4>4.2 Data Retention in AI Systems</h4>
            <p>
              We use Azure OpenAI in a configuration where your data is not used to train
              Microsoft's models. Your prompts and completions are not retained by Azure
              beyond the immediate API call.
            </p>

            <h4>4.3 Vector Embeddings</h4>
            <p>
              Document content is converted to vector embeddings for semantic search. These
              embeddings are mathematical representations and cannot be reverse-engineered
              to recover original content.
            </p>
          </Section>

          <Section title="5. Data Sharing and Disclosure">
            <p>We do NOT sell your personal information. We may share data with:</p>
            <ul>
              <li><strong>Service Providers:</strong> Azure for AI processing, cloud hosting providers</li>
              <li><strong>Legal Requirements:</strong> When required by law or legal process</li>
              <li><strong>Business Transfers:</strong> In connection with mergers or acquisitions</li>
              <li><strong>With Your Consent:</strong> For any other purpose with your explicit permission</li>
            </ul>
          </Section>

          <Section title="6. Multi-Tenant Data Isolation">
            <p>
              2nd Brain operates as a multi-tenant platform. Your organization's data is:
            </p>
            <ul>
              <li>Logically isolated from other organizations</li>
              <li>Accessible only to authenticated users within your organization</li>
              <li>Stored with tenant-specific identifiers</li>
              <li>Never mixed with or visible to other tenants</li>
            </ul>
          </Section>

          <Section title="7. Data Security">
            <p>We implement security measures including:</p>
            <ul>
              <li>Encryption in transit (HTTPS/TLS)</li>
              <li>Secure password hashing (bcrypt)</li>
              <li>JWT-based authentication with refresh tokens</li>
              <li>OAuth 2.0 for third-party integrations</li>
              <li>Regular security assessments</li>
              <li>Access controls and audit logging</li>
            </ul>
          </Section>

          <Section title="8. Your Rights and Choices">
            <p>You have the right to:</p>
            <ul>
              <li><strong>Access:</strong> Request a copy of your data</li>
              <li><strong>Correction:</strong> Update inaccurate information</li>
              <li><strong>Deletion:</strong> Delete your data and account</li>
              <li><strong>Disconnect:</strong> Remove third-party integrations at any time</li>
              <li><strong>Export:</strong> Download your documents and data</li>
              <li><strong>Object:</strong> Opt out of certain data processing</li>
            </ul>
          </Section>

          <Section title="9. Data Retention">
            <p>We retain your data for as long as your account is active. Upon deletion:</p>
            <ul>
              <li>Personal information is deleted within 30 days</li>
              <li>Documents and content are permanently removed</li>
              <li>Vector embeddings are deleted from search indexes</li>
              <li>Backup copies are purged within 90 days</li>
              <li>Some anonymized analytics may be retained</li>
            </ul>
          </Section>

          <Section title="10. Third-Party Services">
            <p>
              When you connect external services, those services have their own privacy policies.
              We encourage you to review:
            </p>
            <ul>
              <li><strong>Google:</strong> Google Privacy Policy for Gmail integration</li>
              <li><strong>Slack:</strong> Slack Privacy Policy for workspace data</li>
              <li><strong>Box:</strong> Box Privacy Policy for cloud storage</li>
              <li><strong>GitHub:</strong> GitHub Privacy Statement for repository data</li>
              <li><strong>Microsoft:</strong> Microsoft Privacy Statement for OneDrive</li>
            </ul>
          </Section>

          <Section title="11. Children's Privacy">
            <p>
              The Service is not intended for individuals under 16 years of age. We do not
              knowingly collect personal information from children. If you believe a child
              has provided us with personal information, please contact us.
            </p>
          </Section>

          <Section title="12. International Data Transfers">
            <p>
              Your data may be processed in the United States and other countries where our
              service providers operate. We ensure appropriate safeguards are in place for
              international data transfers.
            </p>
          </Section>

          <Section title="13. Changes to This Policy">
            <p>
              We may update this Privacy Policy periodically. We will notify you of significant
              changes via email or through the Service. Continued use after changes constitutes
              acceptance of the updated policy.
            </p>
          </Section>

          <Section title="14. Contact Us">
            <p>
              For privacy-related questions or to exercise your rights, contact us at:
            </p>
            <ul>
              <li>Email: pranav@use2ndbrain.com</li>
            </ul>
          </Section>
        </div>

        <div style={{
          marginTop: '40px',
          paddingTop: '24px',
          borderTop: `1px solid ${warmTheme.border}`,
          textAlign: 'center'
        }}>
          <Link href="/terms" style={{
            color: warmTheme.primary,
            textDecoration: 'none',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontSize: '14px',
            marginRight: '24px'
          }}>
            Terms and Conditions
          </Link>
          <Link href="/" style={{
            color: warmTheme.primary,
            textDecoration: 'none',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontSize: '14px'
          }}>
            Return to Home
          </Link>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '28px' }}>
      <h2 style={{
        fontSize: '18px',
        fontWeight: 600,
        color: '#2D2D2D',
        marginBottom: '12px'
      }}>
        {title}
      </h2>
      <div style={{
        color: '#6B6B6B'
      }}>
        {React.Children.map(children, child => {
          if (React.isValidElement(child)) {
            if (child.type === 'p') {
              return React.cloneElement(child as React.ReactElement<any>, {
                style: { marginBottom: '12px', ...((child.props as any).style || {}) }
              })
            }
            if (child.type === 'ul') {
              return React.cloneElement(child as React.ReactElement<any>, {
                style: {
                  marginLeft: '20px',
                  marginBottom: '12px',
                  listStyleType: 'disc',
                  ...((child.props as any).style || {})
                }
              })
            }
            if (child.type === 'h4') {
              return React.cloneElement(child as React.ReactElement<any>, {
                style: {
                  fontSize: '15px',
                  fontWeight: 600,
                  color: '#2D2D2D',
                  marginTop: '16px',
                  marginBottom: '8px',
                  ...((child.props as any).style || {})
                }
              })
            }
          }
          return child
        })}
      </div>
    </div>
  )
}
