// Single place for everything you will want to change.
export const SITE = {
  name: 'Protocloud Gear',
  tagline: 'Honest picks for laptops, keyboards and the gadgets on your desk',
  description:
    'Tech gadget reviews and buying guides. Best laptops, keyboards, monitors and desk gear, tested by engineers who use them all day.',
  url: 'https://blog.protocloudsolutions.com',
  // Legal operator, shown only in the privacy policy and copyright line.
  legalName: 'Protocloud Solutions',
  locale: 'en_US',
  author: 'Protocloud Gear',
  email: 'hello@protocloudgear.com', // change to the inbox you actually monitor
  twitter: '@protocloudgear',
  ogImage: '/images/og-default.png',
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

// Amazon Associates. Replace with your tracking ID (looks like protocloud-20).
export const AFFILIATE = {
  AMAZON_TAG: 'protocloud-20',
  DISCLOSURE:
    'Protocloud Gear is reader-supported. When you buy through links on this page we may earn an affiliate commission at no extra cost to you.',
};

// Google Analytics / Tag Manager from the main site. Replace or blank out.
export const ANALYTICS = {
  GTM_ID: 'GTM-MPKQBLJG',
  GA4_ID: 'G-2GGCFXYL86',
};

export const CATEGORIES = {
  laptops: { label: 'Laptops', blurb: 'Work machines, ultrabooks and developer rigs.' },
  keyboards: { label: 'Keyboards', blurb: 'Mechanical, low-profile and ergonomic boards.' },
  mice: { label: 'Mice & Input', blurb: 'Mice, trackpads and pointing devices.' },
  monitors: { label: 'Monitors', blurb: 'Displays for coding, design and everything between.' },
  audio: { label: 'Audio', blurb: 'Headphones, earbuds and desk speakers.' },
  gadgets: { label: 'Gadgets', blurb: 'Docks, chargers, cables and desk extras.' },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;

export function amazonUrl(asinOrSearch: string): string {
  if (/^[A-Z0-9]{10}$/.test(asinOrSearch)) {
    return `https://www.amazon.com/dp/${asinOrSearch}?tag=${AFFILIATE.AMAZON_TAG}`;
  }
  return `https://www.amazon.com/s?k=${encodeURIComponent(asinOrSearch)}&tag=${AFFILIATE.AMAZON_TAG}`;
}
