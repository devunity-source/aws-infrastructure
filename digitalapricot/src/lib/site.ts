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

// title: the category page's <title> (the site name is added after it).
// intro: paragraphs shown above the guide list. Every claim in them comes from the guides in that
//   category, so update the intro when a guide changes its advice. Never claim hands-on testing here.
// startHere: slug of the guide to read first, linked under the intro.
export const CATEGORIES: Record<
  'laptops' | 'desktops' | 'keyboards' | 'mice' | 'monitors' | 'audio' | 'gadgets' | 'explainers',
  { label: string; blurb: string; title: string; intro: string[]; startHere?: { slug: string; label: string } }
> = {
  laptops: {
    label: 'Laptops',
    blurb: 'Work machines, ultrabooks and developer rigs.',
    title: 'Laptop Buying Guides for Developers',
    intro: [
      'A laptop for writing software has a harder day than most reviews test for: a language server, a container runtime, several browser profiles and a video call, for eight hours, without the fans screaming or the battery hitting red by mid-afternoon. Our laptop guides judge machines against that day, not against a thirty-second benchmark.',
      'Three things come up in every guide. Memory is the decision you cannot undo, because almost every thin laptop solders it to the board: 16 GB is the floor, and 32 GB is where we would aim if the budget stretches. Sustained performance matters more than peak performance, since a chip that throttles to stay cool makes a long build far slower than the benchmark suggests. And a taller 16:10 or 3:2 screen at around 160 pixels per inch or more keeps small code fonts crisp and fits more lines without scrolling.',
      'Start with the explainer on what each spec means, then move to the ranked picks. There is a separate list for students and tighter budgets, and a direct answer to the MacBook Air or MacBook Pro question. The ranked picks come from specifications, professional reviews and owner reports.',
    ],
    startHere: { slug: 'how-to-choose-a-developer-laptop', label: 'How to choose a developer laptop' },
  },
  desktops: {
    label: 'Desktops',
    blurb: 'Prebuilt gaming and workstation towers.',
    title: 'Desktop and Prebuilt PC Buying Guides',
    intro: [
      'A prebuilt desktop is the sum of its parts: a CPU, a graphics card, memory, storage, a power supply and a cooler. Each of those is a known quantity, so a tower can be judged from its parts list as long as the listing actually names them. That is how we pick. We have not tested these towers ourselves, and the guide says so.',
      'The listings we favour name their components, use a power supply rated 80+ Bronze or better, and ship with at least 16 GB of memory and an NVMe SSD. The gap between a prebuilt and the same parts bought separately is now small, which makes a prebuilt a reasonable choice if you do not want to assemble one.',
      'For engineers a gaming tower is also a useful second machine. The graphics card that runs games at 1440p also runs local AI models, and eight fast cores get through Docker builds and test suites quickly. The first upgrades worth making are usually memory, from 16 GB to 32 GB, and a second SSD.',
    ],
    startHere: { slug: 'best-prebuilt-gaming-pcs', label: 'The best prebuilt gaming PCs' },
  },
  keyboards: {
    label: 'Keyboards',
    blurb: 'Mechanical, low-profile and ergonomic boards.',
    title: 'Keyboard Buying Guides for Programmers',
    intro: [
      'A keyboard is the most used tool a programmer owns. Most buying guides lead with switches; we think that is backwards. Layout decides how your hands move all day, so choose it first. A 75 percent board keeps the function row and arrow keys in a compact body, and it is the layout most of our picks for programmers use.',
      'Switches come second, and they are simpler than the names suggest. Every traditional mechanical switch is linear, tactile or clicky. Hall effect switches work differently: a magnet and a sensor read how far down each key is at all times. A hot-swap board lets you pull switches out and push new ones in without soldering, which turns the choice into an experiment instead of a permanent decision.',
      'Hot-swap sockets, gasket mounts and PBT keycaps used to be enthusiast features and now turn up on budget boards, so there is a separate guide for those. If you have wrist pain and not just a preference, skip the standard boards and go to the ergonomic and split guide: splitting the keyboard into two halves at shoulder width is the single biggest fix.',
    ],
    startHere: { slug: 'mechanical-keyboard-switches-explained', label: 'Mechanical keyboard switches explained' },
  },
  mice: {
    label: 'Mice & Input',
    blurb: 'Mice, trackballs and pointing devices.',
    title: 'Mouse and Trackball Buying Guides',
    intro: [
      'Choose a mouse by shape before sensor. Reviewers rate the tracking highly on every mouse we recommend, so the real question is whether your hand rests on it in a neutral position or claws around it. If you have ever ended a day with a tight forearm, that is the clue.',
      'Two other things matter over a long day. Weight: a 60 g mouse causes less wrist fatigue than a 140 g one, which is the best thing gaming mice did for everyone else. And the scroll wheel, because programmers scroll constantly: a wheel that spins freely through a long file and turns notched when you want control saves real effort.',
      'We have two guides. The productivity guide covers mice built for long desk days, including a vertical mouse and a trackball. The gaming and work guide covers light mice that suit both an editor and a game, from flagship to budget. Its picks come from manufacturer specifications, professional reviews and owner reports, not our own hands-on testing, and each card links the sources behind its specs. Whichever you choose, a large cloth pad is the cheapest upgrade in the category.',
    ],
    startHere: { slug: 'best-mice-for-productivity', label: 'The best mice for programmers and long desk days' },
  },
  monitors: {
    label: 'Monitors',
    blurb: 'Desk and portable displays for coding.',
    title: 'Monitor Buying Guides for Coding',
    intro: [
      'For coding, text is the whole job. A monitor has to render small, sharp glyphs for ten hours without fatigue and fit as many lines as your eyes can handle. Two numbers decide most of that.',
      'The first is pixel density. Around 160 pixels per inch is where text starts to look like print. A 27-inch 4K panel lands at 163; a 32-inch 4K drops to 138, and you will see it in thin fonts. The second is vertical space. Code is tall, so a 3:2 or 16:10 panel shows more lines without scrolling, while an ultrawide gives you two full editors side by side. Ideally the monitor also charges your laptop over the same cable, so you never have to think about a dock.',
      'Away from the desk, a portable monitor gives you the second screen back. A good one runs from a single USB-C cable, weighs under 700 grams, and has a stand that does not collapse when you nudge the table. Check that your laptop’s USB-C port supports DisplayPort Alt Mode, and try portrait orientation for logs and documentation.',
    ],
    startHere: { slug: 'best-monitors-for-coding', label: 'The best monitors for coding' },
  },
  audio: {
    label: 'Audio',
    blurb: 'Headphones, earbuds and microphones.',
    title: 'Headphone, Earbud and Microphone Guides',
    intro: [
      'Work audio comes down to two questions: can you concentrate, and can the other person hear you? Our audio guides are split along those lines.',
      'For concentration, the noise-cancelling headphones guide gives the most weight to how each model handles voices. Low rumble is easy to cancel. Speech is hard, and it is the thing that breaks focus. Over-ear headphones cancel more, last longer per charge and are more comfortable for long sessions; earbuds go in a pocket.',
      'For being heard, the earbuds guide puts the microphone first, and looks at how each pair is reported to cope with traffic and wind, which is where most earbuds fall apart. At a desk, a USB microphone does more for how you come across than any camera. The main decision there is dynamic or condenser. A dynamic microphone picks up what is close and ignores the rest, which suits an untreated room with a mechanical keyboard, but it needs to be within a hand’s width of your mouth, so budget for a boom arm.',
    ],
    startHere: { slug: 'best-noise-cancelling-headphones-for-focus', label: 'The best noise-cancelling headphones for deep work' },
  },
  gadgets: {
    label: 'Gadgets',
    blurb: 'Docks, chargers, wearables and desk extras.',
    title: 'Desk Gadget, Dock and Wearable Guides',
    intro: [
      'This is everything on or around the desk that is not a computer, a keyboard or a screen. With most of it, the number on the box is not the number that matters.',
      'A Thunderbolt dock is limited by two things: how many watts it sends to the laptop, and how many monitors the laptop’s own chip can drive, which the dock’s port count does not change. A power bank only charges a laptop at a useful speed if a single USB-C port delivers 65 W or more, and its capacity is better read in watt-hours than milliamp-hours; about 100 Wh is the carry-on limit on most airlines. With webcams, sensor size beats resolution, and lighting matters more than either.',
      'If you are upgrading a home office, the desk setup guide gives an order to buy in, starting with a monitor arm. This category also covers wearables: smart glasses, where we explain the three different kinds and have not tested the picks ourselves, plus the Fitbit Air and the Oura ring.',
    ],
    startHere: { slug: 'remote-engineer-desk-setup-essentials', label: 'Desk setup essentials for remote engineers' },
  },
  explainers: {
    label: 'Explainers',
    blurb: 'How the tech you use every day actually works.',
    title: 'Tech Explainers',
    intro: [
      'These articles are not buying guides and carry no product picks. They explain how something works or how to do something: how to prevent phishing at work and at home, which AI roles are hiring and what skills they ask for, and how YouTube uses AI for search, recommendations and creation.',
      'Some explainers sit with the products they support, in the other categories: what laptop specs mean for developers, how mechanical keyboard switches differ, and how iPhone security actually works.',
    ],
  },
};

export type CategoryKey = keyof typeof CATEGORIES;

/** Meta description for a category page: the blurb plus the count of guides, kept under 160 characters. */
export function categoryDescription(key: CategoryKey, count: number): string {
  const c = CATEGORIES[key];
  const n = count === 1 ? '1 guide' : `${count} guides`;
  return `${c.blurb} ${n} from ${SITE.name}, picked for people who work at a desk all day.`;
}

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

// Where Google requires consent before ads and analytics cookies (EEA, UK, Switzerland). Visitors from these
// regions start with Consent Mode signals denied until they answer Google's consent message.
export const CONSENT_REGIONS = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU',
  'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'IS', 'LI', 'NO', 'GB', 'CH',
];
