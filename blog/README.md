# Protocloud Gear

Tech gadget blog for Protocloud Solutions, monetised with Google AdSense and Amazon affiliate links.
Static site built with [Astro](https://astro.build), Tailwind CSS 4 and MDX. Theme tokens are lifted
from protocloudsolutions.com (navy `hsl(222 47% 6%)`, blue `hsl(217 91% 60%)`, cyan accent, Space Grotesk).

Served at `https://blog.protocloudsolutions.com` from the same nginx box as the main site.

## Before you go live

Three placeholders to replace, all in one place:

| What | Where | Looks like |
|---|---|---|
| AdSense publisher ID | `src/lib/site.ts` (`ADSENSE.CLIENT`) and `public/ads.txt` | `ca-pub-1234567890123456` / `pub-1234567890123456` |
| AdSense ad unit slot IDs | `src/lib/site.ts` (`ADSENSE.SLOTS`) | 10-digit numbers from the AdSense "Ads > By ad unit" page |
| Amazon Associates tag | `src/lib/site.ts` (`AFFILIATE.AMAZON_TAG`) | `yourname-20` |

Ads do not render while the publisher ID is still the placeholder, so a dev build never ships broken tags.
The GA4 and GTM IDs from the main site are already wired in `ANALYTICS`; blank them out if you want separate properties.

## Local development

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # outputs to dist/
npm run check      # type check
```

## Writing a post

Add a file to `src/content/posts/`, for example `best-webcams.mdx`. The filename becomes the URL.

```mdx
---
title: "The Best Webcams for Remote Work"
description: "Under 170 characters, this is the meta description and card blurb."
pubDate: 2026-10-15
category: gadgets          # laptops | keyboards | mice | monitors | audio | gadgets
tags: [webcam, remote-work]
heroImage: /images/webcams.jpg   # optional, 1200x630 works for both hero and OG
featured: false
products:
  - name: "Insta360 Link 2"
    pick: "Best overall"
    asin: "B0DBLMM6RW"      # optional, falls back to an Amazon search link
    specs: ["4K", "Gimbal"]
    pros: ["..."]
    cons: ["..."]
---
import ProductCard from '../../components/ProductCard.astro';
import AdSlot from '../../components/AdSlot.astro';

Intro paragraph.

<ProductCard index={0} {...frontmatter.products[0]} />

Body text about the first pick.

<AdSlot slot="inArticle" format="fluid" layout="in-article" />
```

The `products` list drives the "at a glance" table at the top of the article and each `<ProductCard>` renders
the affiliate button with `rel="nofollow sponsored"`. Set `draft: true` to keep a post out of the build.

Specs and product availability in the seed articles were written in October 2026 and should be
spot-checked against current listings before publishing. Prices are deliberately left out of the copy;
the "Check price" button sends readers to the live listing.

## Deploy

### One-off from your machine

```bash
DEPLOY_HOST=ubuntu@your-server ./deploy/deploy.sh
```

### Server setup (once)

```bash
sudo mkdir -p /var/www/blog.protocloudsolutions.com
sudo cp deploy/blog-static.conf /etc/nginx/snippets/
sudo cp deploy/nginx-blog.conf /etc/nginx/sites-available/blog.protocloudsolutions.com
sudo ln -s /etc/nginx/sites-available/blog.protocloudsolutions.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d blog.protocloudsolutions.com
```

Add an `A` record for `blog` pointing at the server's IP first so certbot can validate.

### Automatic on push

`.github/workflows/deploy-blog.yml` builds and rsyncs on every push to `main` that touches `blog/`.
Repository secrets it needs:

- `BLOG_DEPLOY_HOST`: server hostname or IP
- `BLOG_DEPLOY_USER`: ssh user with write access to the web root
- `BLOG_DEPLOY_SSH_KEY`: private key for that user
- `BLOG_DEPLOY_PATH`: optional, defaults to `/var/www/blog.protocloudsolutions.com`

## AdSense approval checklist

Google reviews the site before serving ads. What they look for, and what is already handled:

- [x] Privacy policy that mentions the DoubleClick cookie and opt-out links (`/privacy`)
- [x] About and contact pages (`/about`, `/contact`)
- [x] `ads.txt` served as plain text at the root
- [x] Mobile layout, fast load, no layout shift from ads (slots reserve height)
- [ ] 15 to 20 substantial original articles. Eight are here. Keep publishing before applying.
- [ ] Domain live on HTTPS for a few weeks with some real traffic
- [ ] EU consent message configured in AdSense > Privacy & messaging (required for EEA/UK visitors)

Once approved, create three ad units (in-article, display for sidebar, display for footer) and paste the
slot IDs into `src/lib/site.ts`. Flip `AUTO_ADS` to `true` if you want Google to place extra units.
