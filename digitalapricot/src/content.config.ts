import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    // Full <title>/og:title when it should differ from the H1. Used verbatim, no site-name suffix added.
    seoTitle: z.string().optional(),
    description: z.string().max(170),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.enum(['laptops', 'desktops', 'keyboards', 'mice', 'monitors', 'audio', 'gadgets', 'explainers']),
    tags: z.array(z.string()).default([]),
    heroImage: z.string().optional(),
    heroAlt: z.string().optional(),
    featured: z.boolean().default(false),
    draft: z.boolean().default(false),
    // Products referenced by the post, used for the comparison table and affiliate buttons.
    products: z
      .array(
        z.object({
          name: z.string(),
          pick: z.string(), // e.g. "Best overall"
          asin: z.string().optional(), // Amazon ASIN, or leave blank to use a search link
          url: z.string().url().optional(), // direct retailer link, used instead of Amazon when set
          store: z.string().default('Amazon'), // retailer name shown on the button ("Check price at Meta")
          specs: z.array(z.string()).default([]),
          pros: z.array(z.string()).default([]),
          cons: z.array(z.string()).default([]),
          // Comparison table cells, in column order. The first product's keys name the columns.
          compare: z.record(z.string(), z.string()).optional(),
          // Where the specs and claims come from. Shown on the product card.
          sources: z.array(z.object({ label: z.string(), url: z.string().url() })).default([]),
          // Own or licensed product photo, under public/. Never a manufacturer image without permission.
          image: z.string().optional(),
          imageAlt: z.string().optional(),
        }),
      )
      .default([]),
  }),
});

export const collections = { posts };
