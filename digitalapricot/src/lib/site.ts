// Single place for everything you will want to change.
export const SITE = {
  name: 'Digital Apricot',
  tagline: 'Honest picks for laptops, keyboards and the gadgets on your desk',
  // Shown after the site name in the home page <title>.
  homeTitle: 'Tech Buying Guides for Developers',
  description:
    'Tech gadget reviews and buying guides. Best laptops, keyboards, monitors and desk accessories, picked by engineers who spend all day at a desk.',
  url: 'https://digitalapricot.io',
  // Legal operator, shown only in the privacy policy and copyright line.
  legalName: 'Protocloud Solutions',
  locale: 'en_US',
  author: 'Digital Apricot',
  email: 'hello@digitalapricot.io', // forwarded by Namecheap email forwarding
  twitter: '', // '@handle' once the site has an X account; empty leaves the tag out
  ogImage: '/images/og-default.png',
  logo: '/images/logo.png',
};

// Every guide is reviewed by this person before it goes live (shown in the post header and JSON-LD).
// Fill in bio to publish the reviewer page at /reviewers/<slug>; until then bylines link to /about.
// Only verifiable facts: roles, years, certifications, public profiles. The audit asks for a detailed bio.
export const REVIEWER: {
  name: string;
  slug: string;
  image: string;
  jobTitle: string;
  bio: string[]; // paragraphs
  experience: { role: string; org: string; years: string }[];
  credentials: string[];
  owns: string[]; // equipment the reviewer uses day to day, for "what I actually use"
  links: { label: string; url: string }[]; // LinkedIn, GitHub, etc. Also used as schema.org sameAs.
} = {
  name: 'Rakan Khaled',
  slug: 'rakan-khaled',
  image: '/images/rakan-khaled.jpg',
  jobTitle: '',
  bio: [],
  experience: [],
  credentials: [],
  owns: [],
  links: [],
};

// Google AdSense. CLIENT must match the ID in public/ads.txt. Set ENABLED to false to ship an ad-free build.
// With CLIENT set, every page loads the AdSense script, which is what the site review needs.
export const ADSENSE = {
  ENABLED: true,
  CLIENT: 'ca-pub-9207857593393521',
  // Create these units in the AdSense dashboard (Ads > By ad unit) once the site is approved,
  // and paste their 10-digit slot IDs here. A slot left empty renders nothing.
  SLOTS: {
    inArticle: '', // "In-article" format
    sidebar: '', // 300x600 or responsive display
    footer: '', // responsive display
  },
  AUTO_ADS: false, // true lets Google place extra ads automatically
};

// Newsletter, run by Buttondown (double opt-in: subscribers confirm by email before they're added).
// USERNAME is the Buttondown newsletter username (buttondown.com/<username>). While it is empty the
// signup box is hidden rather than falling back to a mailto: form.
export const NEWSLETTER = {
  BUTTONDOWN_USERNAME: 'rakanmatouq',
};

// Amazon Associates tracking ID.
export const AFFILIATE = {
  AMAZON_TAG: 'protocloudsol-20',
  DISCLOSURE:
    'Digital Apricot is reader-supported. When you buy through links on this page we may earn an affiliate commission at no extra cost to you.',
};

// The site's own Google tag and the GA4 property it sends to (not protocloudsolutions.com's).
// Product button clicks are sent to GA4_ID explicitly.
export const ANALYTICS = {
  GOOGLE_TAG_ID: 'GTM-M7Z933TK',
  GA4_ID: 'G-TENDQPP9N8',
};

export const CATEGORIES = {
  laptops: { label: 'Laptops', blurb: 'Work machines, ultrabooks and developer rigs.' },
  desktops: { label: 'Desktops', blurb: 'Prebuilt gaming and workstation towers.' },
  keyboards: { label: 'Keyboards', blurb: 'Mechanical, low-profile and ergonomic boards.' },
  mice: { label: 'Mice & Input', blurb: 'Mice, trackpads and pointing devices.' },
  monitors: { label: 'Monitors', blurb: 'Displays for coding, design and everything between.' },
  audio: { label: 'Audio', blurb: 'Headphones, earbuds and desk speakers.' },
  gadgets: { label: 'Gadgets', blurb: 'Docks, chargers, wearables and desk extras.' },
  explainers: { label: 'Explainers', blurb: 'How the tech you use every day actually works.' },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;

// Build every internal link and asset URL through these helpers, so a base path (the site used to
// live under /blog) only ever has to be set in astro.config.mjs. Paths are written without the base: url('/about').
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

/** Base-prefixed path for internal links and assets: url('/about') -> '/about'; with base '/x', '/x/about'. */
export function url(path = '/'): string {
  if (/^[a-z]+:/i.test(path) || path.startsWith('#')) return path;
  if (BASE && (path === BASE || path.startsWith(`${BASE}/`))) return path;
  const p = path.startsWith('/') ? path : `/${path}`;
  return p === '/' ? BASE || '/' : `${BASE}${p}`;
}

/** Absolute URL on the public site: absUrl('/about') -> 'https://digitalapricot.io/about'. */
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
