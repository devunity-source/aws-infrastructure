import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';
import tailwindcss from '@tailwindcss/vite';

// Served from the root of digitalapricot.io. protocloudsolutions.com/blog/* 301s here
// (deploy/protocloud-blog.conf on the old domain).
export default defineConfig({
  site: 'https://digitalapricot.io',
  trailingSlash: 'never',
  build: { format: 'file' },
  redirects: {
    '/best-budget-gaming-mice': '/best-mice-for-gaming-and-work',
  },
  integrations: [
    mdx(),
    // Search and tag pages are noindex, so keep them out of the sitemap too.
    sitemap({ filter: (page) => !/^https:\/\/digitalapricot\.io\/(search|tags\/)/.test(page) }),
  ],
  vite: { plugins: [tailwindcss()] },
});
