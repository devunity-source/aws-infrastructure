# Digital Apricot

Tech buying guides at https://digitalapricot.io, monetised with Google AdSense and Amazon affiliate links.
Static site built with [Astro](https://astro.build), Tailwind CSS 4 and MDX. Burnt-apricot `#b8460f` and
leaf-green `#2e6a4c` on a warm cream surface, Space Grotesk. The mark is `src/components/ApricotMark.astro`
(also `public/favicon.svg`).

Served from the root of `digitalapricot.io` on the same nginx box as protocloudsolutions.com. It used to live
at `protocloudsolutions.com/blog`; `deploy/protocloud-blog.conf` now 301s every old URL to the new domain.

## Before you go live

Three placeholders to replace, all in one place:

| What | Where | Looks like |
|---|---|---|
| AdSense publisher ID (set: `ca-pub-9207857593393521`) | `src/lib/site.ts` (`ADSENSE.CLIENT`) and `public/ads.txt` | `ca-pub-` + 16 digits / `pub-` + 16 digits |
| AdSense ad unit slot IDs | `src/lib/site.ts` (`ADSENSE.SLOTS`) | 10-digit numbers from the AdSense "Ads > By ad unit" page |
| Amazon Associates tag | `src/lib/site.ts` (`AFFILIATE.AMAZON_TAG`) | `yourname-20` |

Ads do not render while the publisher ID is still the placeholder, so a dev build never ships broken tags.
Analytics: the site's own Google tag (`ANALYTICS.GOOGLE_TAG_ID`) sends to its own GA4 property (`ANALYTICS.GA4_ID`).

## Local development

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # outputs to dist/
npm run check      # type check
```

## Writing a post

Full guide with field reference and checklist: [post_article.md](post_article.md).

Add a file to `src/content/posts/`, for example `best-webcams.mdx`. The filename becomes the URL.

```mdx
---
title: "The Best Webcams for Remote Work"
description: "Under 170 characters, this is the meta description and card blurb."
pubDate: 2026-10-15
category: gadgets          # laptops | desktops | keyboards | mice | monitors | audio | gadgets | explainers
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
sudo install -d -o webserver -g webserver -m 755 /var/www/html/digitalapricot
sudo cp deploy/digitalapricot.io.conf /etc/nginx/sites-available/digitalapricot.io
sudo ln -s /etc/nginx/sites-available/digitalapricot.io /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d digitalapricot.io -d www.digitalapricot.io --redirect

# The old address only redirects now. The snippet stays included in protocloudsolutions.com's 443 block.
sudo cp deploy/protocloud-blog.conf /etc/nginx/snippets/
sudo nginx -t && sudo systemctl reload nginx
```

### Automatic on push

`.github/workflows/deploy-digitalapricot.yml` builds and rsyncs on every push to `main` that touches `digitalapricot/`.
Repository secrets it needs:

- `BLOG_DEPLOY_HOST`: server hostname or IP
- `BLOG_DEPLOY_USER`: ssh user that owns the blog web root (`webserver`)
- `BLOG_DEPLOY_SSH_KEY`: a key used only for deploys

The deploy key is locked down on the server. Its line in `~webserver/.ssh/authorized_keys` starts with
`restrict,command="/usr/bin/rrsync -wo /var/www/html/digitalapricot"`, so it can only write
into the site folder. It can't open a shell, read files or forward ports. rrsync treats every path as
relative to that folder, which is why the workflow uploads to `./`.

The workflow pins the server's SSH host key. If the server is rebuilt, update the `known_hosts` line in
the workflow with the output of `ssh-keyscan -t ed25519 <host>`, after checking its fingerprint.

To rotate the deploy key: generate a new one, replace its line in `authorized_keys` (keeping the
`restrict,command=...` prefix), and update the `BLOG_DEPLOY_SSH_KEY` secret.

## AdSense approval checklist

Google reviews the site before serving ads. What they look for, and what is already handled:

- [x] Privacy policy that mentions the DoubleClick cookie and opt-out links (`/privacy`)
- [x] About and contact pages (`/about`, `/contact`)
- [x] `ads.txt` served as plain text at the root
- [x] Mobile layout, fast load, no layout shift from ads (slots reserve height)
- [x] AdSense script on every page and `ads.txt` with the publisher ID. Slots without a unit ID render nothing.
- [ ] Substantial, first-hand content and a steady publishing cadence (the first review, on protocloudsolutions.com, was rejected as low value content)
- [ ] Domain live on HTTPS for a few weeks with some real traffic (live since 2026-11-05)
- [ ] EU consent message configured in AdSense > Privacy & messaging (required for EEA/UK visitors)

Once approved, create three ad units (in-article, display for sidebar, display for footer) and paste the
slot IDs into `src/lib/site.ts`. Flip `AUTO_ADS` to `true` if you want Google to place extra units.
