# Digital Apricot website audit

**Stronger evidence. Easier buying decisions.**

Audit of https://digitalapricot.io, 5 November 2026. Source: `docs/Digital-Apricot-Website-Audit-v3.pptx`
(9 slides). The audit had no analytics or commercial results to work from, so it covers what the
site shows, not how it performs.

## Summary

The brand is strong. The next investment belongs in the buying guides.

1. **Keep the visual identity.** Distinctive logo, warm colours, readable typography and a memorable
   retro motif.
2. **Strengthen the purchase decision.** Back recommendations with sources, comparison details and
   precise product links.

## What already works

| Strength | Detail |
|---|---|
| A clear audience | Developers and people who spend their working day at a desk. |
| Clear recommendations | Quick picks, pros and cons, contents links and concise explanations. |
| Transparent research | The About page explains that guides rely on research rather than lab testing. |
| Useful SEO foundations | Canonical metadata, social previews, sitemap and article structured data. |

Pages checked: [/about](https://digitalapricot.io/about), [robots.txt](https://digitalapricot.io/robots.txt),
[sitemap](https://digitalapricot.io/sitemap-index.xml),
[best laptops for developers](https://digitalapricot.io/best-laptops-for-developers).

## Four fixes with the clearest immediate value

All four are top priority (level 1).

| # | Observed issue | Recommended change |
|---|---|---|
| 1 | The newsletter form submits to `mailto:` | Connect a signup service with a confirmation flow |
| 2 | Research claims have no source links | Cite the specifications and reviews behind each pick |
| 3 | Purchase buttons open Amazon searches | Link exact models, or label search links accurately |
| 4 | The mouse guide has no photos of the individual mice | Add your own or licensed product photos |

Evidence: all five purchase links in the laptop guide and two in the mouse guide were Amazon
searches. The newsletter form's action was `mailto:hello@digitalapricot.io?subject=Subscribe`.

## The mouse guide needs better comparison evidence

Page: [best mice for gaming and work](https://digitalapricot.io/best-mice-for-gaming-and-work)

1. **A comparison table near the top.** Show weight, connection, buttons, battery life and who each
   mouse suits.
2. **Product photos beside each pick.** Help readers recognise the hardware and compare shapes
   before they leave the article.
3. **Sources beside factual claims.** Link specifications and reviews. Date figures that change, such
   as owner review counts.

Google's guidance on [writing high-quality reviews](https://developers.google.com/search/docs/specialty/ecommerce/write-high-quality-reviews)
asks for original evidence, useful comparisons, measurements and supporting resources. Use licensed
images. AI illustrations don't show hands-on experience.

## Engineering experience can set the content apart

Advice is useful when it names specific working conditions.

1. **Developer laptops:** container workloads, sustained builds, Linux support and exact memory
   configurations.
2. **Docks and desk equipment:** whether monitors wake reliably, which display combinations work, and
   operating-system limitations.

Document equipment you actually own, and keep research-based recommendations clearly labelled as
research. These are suggested editorial directions, not claims that the site has run these tests.
Add a reviewer biography with verifiable professional experience.

## Navigation and freshness need small refinements

1. **Search relevance.** Searching "mouse" returned the productivity guide but not the gaming mouse
   guide.
2. **Homepage length.** 27 article cards come before the category section and the newsletter.
   Show a shorter, curated selection.
3. **Freshness and reviewer identity.** Show meaningful update dates, and link a detailed reviewer
   biography.

Also from the notes:
- The homepage's latest cards show publication dates, while the sampled articles showed November
  updates.
- Cut down the repeated category navigation.
- Give the hero one clear main route into the content.

## Technical foundations pass basic checks

| Verified | Still to measure |
|---|---|
| Robots and sitemap respond successfully | Google indexing and Search Console |
| Unknown URLs return HTTP 404 | Mobile layouts and accessibility |
| Sample article images load (heroes about 91 KB and 112 KB) | Core Web Vitals |
| Article, Breadcrumb and ItemList markup | Consent and analytics behaviour |
| Affiliate links carry `rel="sponsored"` | Purchase and signup events |

This audit does not give a performance score, a conversion rate or a privacy-compliance verdict.

## 30-day action plan

A proposed order and rough time windows, not a delivery commitment or a forecast.

| Days 1–7 | Days 8–14 | Days 15–30 |
|---|---|---|
| Fix newsletter signup | Upgrade the mouse guide | Improve two more guides |
| Replace ambiguous purchase links | Add sources and product photos | Simplify homepage discovery |
| Correct search matching | Publish a reviewer biography | Check tracking and the mobile experience |

**Success checks:** confirmed signups, relevant search results, links to the exact products, and
recommendations backed by sources.

---

## Where each item stands in the code (checked 5 November 2026)

Not part of the presentation. These notes record what the repo shows, so each item has a starting point.

| Item | Current state | Where |
|---|---|---|
| Newsletter | Confirmed. The form posts to `mailto:`, and a comment in the file says so. | `src/components/Newsletter.astro` |
| Purchase links | Confirmed. The SEO agent's audit flags 14 guides with Amazon search links. The webcam guide is the only one with ASINs for every pick. | `products[].asin` in each post |
| Search "mouse" | Confirmed. Search is a plain substring match on title, description, category and tags, so "mouse" doesn't match "Mice". Fix: match singular and plural forms and synonyms, or add tags such as `mouse`. | `src/pages/search.astro` |
| Homepage length | Confirmed. After the featured post and three cards, every other post is listed (`rest.slice(3)`). | `src/pages/index.astro` |
| Reviewer biography | No bio page yet. The reviewer's name and photo come from `REVIEWER`. | `src/lib/site.ts`, `src/pages/about.astro` |
| Product photos | The mouse guide has only its hero illustration. | `src/content/posts/best-mice-for-gaming-and-work.mdx` |
| Click tracking | Product button clicks go to GA4 as `affiliate_click`, and the weekly run imports them. | `src/layouts/Base.astro`, `seo-agent` `ga4` command |
| Consent | No consent banner yet. Configure Google's consent message in AdSense > Privacy & messaging before ads run in the EEA or UK. | AdSense |

## Progress

- **Days 1–7 (in progress, 5 November 2026):**
  - Newsletter signup goes through Buttondown with double opt-in. It stays hidden until `NEWSLETTER.BUTTONDOWN_USERNAME` is set.
  - Search links are labelled "Search on Amazon", with a tooltip naming the search.
  - Search folds plurals and synonyms, requires every word to match, ranks title matches first, and supports `?q=`.
  - Still open: replacing the 14 guides' search links with exact ASINs.
- **Days 8–14 (in progress, 6 November 2026):**
  - The mouse guide has a comparison table near the top (weight, connection, buttons, battery, who it suits).
    It scrolls sideways on phones with the pick column pinned.
  - Every card except the Lamzu links its sources. Specs were checked against the makers' pages, which corrected
    several: the Lamzu's 4K dongle is sold separately, the Viper's battery figure only holds at 1,000 Hz, the
    M612 weighs about 150 g with its cable and uses a PixArt 3104. Undated owner review counts were removed.
  - Product cards can show a photo (`image`, `imageAlt`), but none are added yet. They need own or licensed photos.
  - A reviewer page at `/reviewers/<slug>` (with ProfilePage and Person markup) is built and goes live once
    `REVIEWER.bio` is filled in. Until then, bylines link to /about.
  - Still open: the Lamzu source (its site rate-limits automated requests), product photos, and the reviewer's details.
