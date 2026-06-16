import { createClient } from 'microcms-js-sdk';

const serviceDomain = process.env.MICROCMS_SERVICE_DOMAIN;
const apiKey = process.env.MICROCMS_API_KEY;

if (!serviceDomain) {
  console.warn('MICROCMS_SERVICE_DOMAIN is not set in env variables. Using dummy fallback.');
}
if (!apiKey) {
  console.warn('MICROCMS_API_KEY is not set in env variables. Using dummy fallback.');
}

// createClient requires both parameters. During build time in Vercel before env vars are configured,
// we must provide dummy fallbacks so it doesn't throw and crash the build.
export const client = createClient({
  serviceDomain: serviceDomain || 'dummy',
  apiKey: apiKey || 'dummy',
});

