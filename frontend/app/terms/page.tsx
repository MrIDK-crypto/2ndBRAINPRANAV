'use client'

import React from 'react'
import Link from 'next/link'

export default function TermsPage() {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#F8FAFC',
      padding: '40px 20px'
    }}>
      <div style={{
        maxWidth: '800px',
        margin: '0 auto',
        backgroundColor: 'white',
        borderRadius: '12px',
        padding: '40px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}>
        <Link href="/" style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          color: '#3B82F6',
          textDecoration: 'none',
          marginBottom: '24px',
          fontFamily: '"Work Sans", sans-serif',
          fontSize: '14px'
        }}>
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24">
            <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Home
        </Link>

        <h1 style={{
          fontFamily: '"Work Sans", sans-serif',
          fontSize: '32px',
          fontWeight: 700,
          color: '#081028',
          marginBottom: '8px'
        }}>
          Terms and Conditions
        </h1>

        <p style={{
          fontFamily: '"Work Sans", sans-serif',
          fontSize: '14px',
          color: '#6B7280',
          marginBottom: '32px'
        }}>
          Last updated: February 4, 2026
        </p>

        <div style={{
          fontFamily: '"Work Sans", sans-serif',
          fontSize: '15px',
          color: '#374151',
          lineHeight: '1.7'
        }}>
          <Section title="1. Agreement to Terms">
            <p>
              By accessing or using 2nd Brain ("the Service"), you agree to be bound by these Terms and Conditions.
              If you disagree with any part of these terms, you may not access the Service.
            </p>
          </Section>

          <Section title="2. Description of Service">
            <p>
              2nd Brain is an AI-powered knowledge management platform that helps organizations preserve,
              organize, and transfer institutional knowledge. The Service includes:
            </p>
            <ul>
              <li>Integration with third-party services (Gmail, Slack, Box, GitHub, Microsoft OneDrive)</li>
              <li>AI-powered document classification and analysis</li>
              <li>Knowledge gap identification and analysis</li>
              <li>Voice transcription and recording capabilities</li>
              <li>RAG (Retrieval-Augmented Generation) search functionality</li>
              <li>Training video generation</li>
            </ul>
          </Section>

          <Section title="3. User Accounts">
            <p>
              When you create an account with us, you must provide accurate, complete, and current information.
              You are responsible for:
            </p>
            <ul>
              <li>Maintaining the confidentiality of your account credentials</li>
              <li>All activities that occur under your account</li>
              <li>Notifying us immediately of any unauthorized access</li>
            </ul>
          </Section>

          <Section title="4. Data Collection and Processing">
            <h4>4.1 Data We Collect</h4>
            <p>When you connect third-party services, we may access and process:</p>
            <ul>
              <li><strong>Email data:</strong> Email content, attachments, sender/recipient information</li>
              <li><strong>Slack data:</strong> Messages, channels, files shared in workspaces</li>
              <li><strong>Cloud storage:</strong> Documents and files from Box or OneDrive</li>
              <li><strong>Code repositories:</strong> Source code, documentation from GitHub</li>
              <li><strong>Voice recordings:</strong> Audio transcribed for knowledge capture</li>
            </ul>

            <h4>4.2 How We Process Data</h4>
            <p>Your data is processed using:</p>
            <ul>
              <li>Azure OpenAI services for AI analysis and classification</li>
              <li>Vector embeddings for semantic search capabilities</li>
              <li>Whisper AI for voice transcription</li>
            </ul>

            <h4>4.3 Data Isolation</h4>
            <p>
              We maintain strict multi-tenant data isolation. Your organization's data is logically
              separated from other organizations and cannot be accessed by other users.
            </p>
          </Section>

          <Section title="5. Third-Party Integrations">
            <p>
              By connecting third-party services, you authorize us to access your data on those platforms
              via OAuth authentication. You represent that you have the authority to grant such access.
            </p>
            <p>
              We are not responsible for the availability, security, or practices of third-party services.
              Your use of those services is subject to their respective terms and privacy policies.
            </p>
          </Section>

          <Section title="6. AI and Machine Learning Disclosure">
            <p>
              The Service uses artificial intelligence and machine learning technologies. You acknowledge that:
            </p>
            <ul>
              <li>AI-generated content may not always be accurate or complete</li>
              <li>Document classification is automated and may require manual review</li>
              <li>Search results and recommendations are algorithmically generated</li>
              <li>Voice transcriptions may contain errors</li>
            </ul>
            <p>
              You should not rely solely on AI-generated content for critical business decisions
              without human verification.
            </p>
          </Section>

          <Section title="7. Acceptable Use">
            <p>You agree NOT to:</p>
            <ul>
              <li>Upload content that violates any laws or regulations</li>
              <li>Upload confidential information without proper authorization</li>
              <li>Attempt to access other users' data or accounts</li>
              <li>Use the Service for any illegal or unauthorized purpose</li>
              <li>Reverse engineer or attempt to extract source code</li>
              <li>Transmit malware, viruses, or harmful code</li>
              <li>Overwhelm the Service with excessive requests</li>
            </ul>
          </Section>

          <Section title="8. Intellectual Property">
            <p>
              You retain all rights to the content you upload to the Service. By using the Service,
              you grant us a limited license to process your content solely for providing the Service.
            </p>
            <p>
              The Service, including its original content, features, and functionality, is owned by
              2nd Brain and is protected by copyright, trademark, and other intellectual property laws.
            </p>
          </Section>

          <Section title="9. Limitation of Liability">
            <p>
              THE SERVICE IS PROVIDED "AS IS" WITHOUT WARRANTIES OF ANY KIND. TO THE FULLEST EXTENT
              PERMITTED BY LAW, WE SHALL NOT BE LIABLE FOR:
            </p>
            <ul>
              <li>Any indirect, incidental, special, consequential, or punitive damages</li>
              <li>Loss of profits, data, or business opportunities</li>
              <li>Errors or inaccuracies in AI-generated content</li>
              <li>Service interruptions or data loss</li>
              <li>Actions of third-party services</li>
            </ul>
          </Section>

          <Section title="10. Data Retention and Deletion">
            <p>
              You may delete your data at any time through the Service interface. Upon account
              termination or data deletion request:
            </p>
            <ul>
              <li>Your documents and content will be permanently deleted</li>
              <li>Vector embeddings will be removed from our search index</li>
              <li>Some anonymized, aggregated data may be retained for analytics</li>
            </ul>
          </Section>

          <Section title="11. Changes to Terms">
            <p>
              We reserve the right to modify these terms at any time. We will provide notice of
              significant changes via email or through the Service. Continued use after changes
              constitutes acceptance of the new terms.
            </p>
          </Section>

          <Section title="12. Termination">
            <p>
              We may terminate or suspend your account immediately, without prior notice, for conduct
              that we believe violates these Terms or is harmful to other users, us, or third parties.
            </p>
          </Section>

          <Section title="13. Governing Law">
            <p>
              These Terms shall be governed by and construed in accordance with the laws of the
              State of California, United States, without regard to its conflict of law provisions.
            </p>
          </Section>

          <Section title="14. Contact Us">
            <p>
              If you have any questions about these Terms, please contact us at:
            </p>
            <ul>
              <li>Email: pranav@use2ndbrain.com</li>
            </ul>
          </Section>
        </div>

        <div style={{
          marginTop: '40px',
          paddingTop: '24px',
          borderTop: '1px solid #E5E7EB',
          textAlign: 'center'
        }}>
          <Link href="/privacy" style={{
            color: '#3B82F6',
            textDecoration: 'none',
            fontFamily: '"Work Sans", sans-serif',
            fontSize: '14px',
            marginRight: '24px'
          }}>
            Privacy Policy
          </Link>
          <Link href="/" style={{
            color: '#3B82F6',
            textDecoration: 'none',
            fontFamily: '"Work Sans", sans-serif',
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
        color: '#081028',
        marginBottom: '12px'
      }}>
        {title}
      </h2>
      <div style={{
        color: '#374151'
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
                  color: '#1F2937',
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
