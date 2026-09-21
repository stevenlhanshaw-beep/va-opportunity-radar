# VA Opportunity Radar

Mobile-first prototype for turning Virginia public procurement and project data into useful local business intelligence.

## Product layers
- **Spend Signals** — eVA procurement / purchase-order activity.
- **Open Opportunities** — only records explicitly supported as active solicitations.
- **Project Signals** — permits and related public project records.

The first procurement target is Virginia's **eVA Procurement Data 2026**. Purchase-order history is not labeled as an open bid.

## Publish with GitHub Pages
Upload `index.html` to the repository root. Then in GitHub open **Settings → Pages**, choose **Deploy from a branch**, select `main` and `/ (root)`, and save.

## Next build
Connect the real 2026 eVA CSV/CKAN resource, normalize order-line data, group by `Order #`, add Southwest Virginia filters, then add a genuine active-solicitation source and permit/project sources.
