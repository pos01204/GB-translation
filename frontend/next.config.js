/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'image.idus.com',
      },
      {
        protocol: 'https',
        hostname: '*.idus.com',
      },
    ],
  },
}

module.exports = nextConfig

