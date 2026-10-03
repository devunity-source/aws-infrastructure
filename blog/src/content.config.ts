import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const posts = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/posts' }),
  schema: z.object({
    title: z.string(),
    description: z.string().max(170),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    category: z.enum(['laptops', 'keyboards', 'mice', 'monitors', 'audio', 'gadgets']),
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
          specs: z.array(z.string()).default([]),
          pros: z.array(z.string()).default([]),
          cons: z.array(z.string()).default([]),
        }),
      )
      .default([]),
  }),
});

export const collections = { posts };
