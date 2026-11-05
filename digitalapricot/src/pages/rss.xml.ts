import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';
import { SITE, absUrl } from '../lib/site';

export async function GET(_context: APIContext) {
  const posts = (await getCollection('posts', ({ data }) => !data.draft)).sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
  return rss({
    title: SITE.name,
    description: SITE.description,
    site: SITE.url,
    trailingSlash: false,
    items: posts.map((p) => ({ title: p.data.title, description: p.data.description, pubDate: p.data.pubDate, link: absUrl(`/${p.id}`), categories: [p.data.category, ...p.data.tags] })),
    customData: `<language>en-us</language>`,
  });
}
