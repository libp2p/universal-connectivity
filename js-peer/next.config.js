/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  reactStrictMode: true,
  productionBrowserSourceMaps: true,
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
