# How to add an article

An article is one file. Drop it in `src/content/posts/` and the filename becomes the URL,
so `best-webcams.mdx` publishes at `/best-webcams`.

## Skeleton

```mdx
---
title: "The Best Webcams for Remote Work"
description: "Under 170 characters. This is the meta description and the card blurb."
pubDate: 2026-10-15
category: gadgets
tags: [webcam, remote-work]
featured: false
products:
  - name: "Insta360 Link 2"
    pick: "Best overall"
    asin: "B0DBLMM6RW"
    specs: ["4K sensor", "Gimbal tracking"]
    pros: ["Looks dramatically better than any laptop camera"]
    cons: ["Overkill if you sit still"]
  - name: "Logitech MX Brio"
    pick: "Best value"
    specs: ["4K", "Fixed lens"]
    pros: ["Simple, reliable"]
    cons: ["No tracking"]
---
import ProductCard from '../../components/ProductCard.astro';
import AdSlot from '../../components/AdSlot.astro';

Intro paragraph. Why this category matters and how you picked.

## How we picked

Your criteria.

<ProductCard index={0} {...frontmatter.products[0]} />

Two or three paragraphs about the first product.

<AdSlot slot="inArticle" format="fluid" layout="in-article" />

<ProductCard index={1} {...frontmatter.products[1]} />

Paragraphs about the second product.

## The short version

- One line per pick.
```

## Frontmatter fields

| Field | Required | Notes |
|---|---|---|
| `title` | yes | Page title and H1 |
| `description` | yes | Max 170 characters. Meta description and card blurb |
| `pubDate` | yes | `YYYY-MM-DD`. Posts sort newest first |
| `category` | yes | One of `laptops`, `keyboards`, `mice`, `monitors`, `audio`, `gadgets`. Anything else fails the build |
| `tags` | no | Lowercase, hyphenated. Each tag gets its own page at `/tags/<tag>` |
| `products` | no | Drives the "Our picks at a glance" table and the product cards |
| `heroImage` | no | Path under `public/`, e.g. `/images/webcams.jpg`. 1200 by 630 works for both the hero and social sharing |
| `heroAlt` | no | Alt text for the hero image |
| `featured` | no | `true` puts the post in the big homepage hero card. Otherwise the newest post takes that spot |
| `updatedDate` | no | Shows an "Updated" date on the article and in structured data |
| `draft` | no | `true` keeps the post out of the build while you work on it |

## Product entries

Each item in `products` takes:

- `name` (required): the product name as shown on the card
- `pick` (required): the label, e.g. "Best overall", "Best value"
- `asin` (optional): Amazon ASIN. With it, the button links straight to the product. Without it, the button runs an Amazon search for the name. Your affiliate tag is appended either way
- `specs`, `pros`, `cons` (optional): lists of short strings

Write the product list once in the frontmatter. Each `<ProductCard index={N} {...frontmatter.products[N]} />` in the body pulls from it, and the glance table at the top of the article is generated from it automatically.

## Body

- `## Headings` build the table of contents. It appears once there are three or more
- `<AdSlot slot="inArticle" format="fluid" layout="in-article" />` places an ad. One per article in the body is enough; the layout adds another after the content and one in the sidebar
- Plain `.md` works if you do not need product cards or inline ads. Skip the import lines
- Leave prices out of the copy. They go stale fast, and the "Check price" button sends readers to the live listing

## Workflow

```bash
cd protocloud-reviews
npm run dev          # live preview at http://localhost:4321 while you write
npm run build        # catches schema errors before you push
git add . && git commit -m "Add webcams guide" && git push
```

Once the branch is merged into `main`, every push that touches `protocloud-reviews/` triggers the deploy
workflow and the article goes live. Until then, run `./deploy/deploy.sh` by hand.

## Checklist before publishing

- [ ] Description is under 170 characters
- [ ] Category is one of the six valid values
- [ ] Product names and specs checked against current listings
- [ ] No prices in the copy
- [ ] `npm run build` passes
