import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';
import tailwindcss from '@tailwindcss/vite';

// The blog is served from protocloudsolutions.com/blog. Change site/base together if it ever moves.
export default defineConfig({
  site: 'https://protocloudsolutions.com',
  base: '/blog',
  trailingSlash: 'never',
  build: { format: 'file' },
  redirects: {
    '/best-budget-gaming-mice': '/blog/best-mice-for-gaming-and-work',
  },
  integrations: [
    mdx(),
    // Search and tag pages are noindex, so keep them out of the sitemap too.
    sitemap({ filter: (page) => !/\/blog\/(search|tags\/)/.test(page) }),
  ],
  vite: { plugins: [tailwindcss()] },
});
