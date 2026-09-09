import type { NextConfig } from 'next';

import { loadRootEnv } from './src/lib/root-env';

// The backend and this application share one environment file at the
// repository root. Next only looks inside this package, so load it here.
loadRootEnv();

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
