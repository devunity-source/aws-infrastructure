// Single place for everything you will want to change.
export const SITE = {
  name: 'Protocloud Reviews',
  tagline: 'Honest picks for laptops, keyboards and the gadgets on your desk',
  // Shown after the site name in the home page <title>.
  homeTitle: 'Tech Buying Guides for Developers',
  description:
    'Tech gadget reviews and buying guides. Best laptops, keyboards, monitors and desk accessories, picked by engineers who spend all day at a desk.',
  url: 'https://protocloudsolutions.com/blog',
  // Legal operator, shown only in the privacy policy and copyright line.
  legalName: 'Protocloud Solutions',
  locale: 'en_US',
  author: 'Protocloud Reviews',
  email: 'hello@protocloudreviews.com', // change to the inbox you actually monitor
  twitter: '@protocloudreviews',
  ogImage: '/images/og-default.png',
  logo: '/images/logo.png',
};

// Every guide is reviewed by this person before it goes live (shown in the post header and JSON-LD).
export const REVIEWER = {
  name: 'Rakan Khaled',
  image: '/images/rakan-khaled.jpg',
};

// Google AdSense. Replace the placeholder with your real publisher ID (ca-pub-XXXXXXXXXXXXXXXX).
// It must match the ID in public/ads.txt. Set ENABLED to false to ship an ad-free build.
export const ADSENSE = {
  ENABLED: true,
  CLIENT: 'ca-pub-XXXXXXXXXXXXXXXX',
  // Create these units in the AdSense dashboard and paste the slot IDs here.
  SLOTS: {
    inArticle: '0000000001', // "In-article" format
    sidebar: '0000000002', // 300x600 or responsive display
    footer: '0000000003', // responsive display
  },
  AUTO_ADS: false, // true lets Google place extra ads automatically
};

// Amazon Associates tracking ID.
export const AFFILIATE = {
  AMAZON_TAG: 'protocloudsol-20',
  DISCLOSURE:
    'Protocloud Reviews is reader-supported. When you buy through links on this page we may earn an affiliate commission at no extra cost to you.',
};

// Google Analytics / Tag Manager from the main site. Replace or blank out.
export const ANALYTICS = {
  GTM_ID: 'GTM-MPKQBLJG',
  GA4_ID: 'G-2GGCFXYL86',
};

export const CATEGORIES = {
  laptops: { label: 'Laptops', blurb: 'Work machines, ultrabooks and developer rigs.' },
  desktops: { label: 'Desktops', blurb: 'Prebuilt gaming and workstation towers.' },
  keyboards: { label: 'Keyboards', blurb: 'Mechanical, low-profile and ergonomic boards.' },
  mice: { label: 'Mice & Input', blurb: 'Mice, trackpads and pointing devices.' },
  monitors: { label: 'Monitors', blurb: 'Displays for coding, design and everything between.' },
  audio: { label: 'Audio', blurb: 'Headphones, earbuds and desk speakers.' },
  gadgets: { label: 'Gadgets', blurb: 'Docks, chargers, wearables and desk extras.' },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;

// The site lives under a base path (/blog). Build every internal link and asset URL through these
// helpers so the base is applied in one place. Paths are written without the base: url('/about').
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Base-prefixed path for internal links and assets: url('/about') -> '/blog/about', url('/') -> '/blog'. */
export function url(path = '/'): string {
  if (/^[a-z]+:/i.test(path) || path.startsWith('#')) return path;
  if (BASE && (path === BASE || path.startsWith(`${BASE}/`))) return path;
  const p = path.startsWith('/') ? path : `/${path}`;
  return p === '/' ? BASE || '/' : `${BASE}${p}`;
}

/** Absolute URL on the public site: absUrl('/about') -> 'https://protocloudsolutions.com/blog/about'. */
export function absUrl(path = '/'): string {
  if (/^[a-z]+:/i.test(path)) return path;
  return new URL(url(path), SITE.url).toString().replace(/\/$/, '');
}

/** The .webp sibling of a .png/.jpg image path, for <picture><source>. */
export function webpOf(path: string): string {
  return path.replace(/\.(png|jpe?g)$/i, '.webp');
}

/** Anchor id used for a product card and the picks table. */
export function productId(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

export function amazonUrl(asinOrSearch: string): string {
  if (/^[A-Z0-9]{10}$/.test(asinOrSearch)) {
    return `https://www.amazon.com/dp/${asinOrSearch}?tag=${AFFILIATE.AMAZON_TAG}`;
  }
  return `https://www.amazon.com/s?k=${encodeURIComponent(asinOrSearch)}&tag=${AFFILIATE.AMAZON_TAG}`;
}
