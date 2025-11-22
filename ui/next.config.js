/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  // Use relative assets so Electron file:// loads pick them up without a web server.
  assetPrefix: './',
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
}

module.exports = nextConfig
