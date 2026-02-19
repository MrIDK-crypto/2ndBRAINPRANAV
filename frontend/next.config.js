/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',

  // Environment variables available at runtime
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5006',
  },

  // Disable image optimization for Cloud Run (uses external URLs)
  images: {
    unoptimized: true,
  },

  // Redirect root to login so bots (Google OAuth verification) see privacy links
  async redirects() {
    return [
      {
        source: '/',
        destination: '/login',
        permanent: false,
      },
    ]
  },
}

module.exports = nextConfig
