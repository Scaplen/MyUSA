# MyUSA.us Google Growth Stack

Goal: use Google's search, measurement, performance, and reporting products together to grow MyUSA.us while preserving the site's official-source, no-ads, privacy-conscious approach.

## Tier 1 — Must be connected

### Google Search Console
- Domain/property ownership for `myusa.us`.
- Search performance: queries, pages, countries, devices, search appearance.
- Sitemap monitoring/submission.
- URL Inspection for important national/state/city/ZIP/weather-guide URLs.
- Indexing, Core Web Vitals, HTTPS, security/manual-action monitoring.
- Discover and Google News performance when Google makes those reports available for the site.
- Never use the Indexing API for ordinary weather pages; Google restricts it to JobPosting and BroadcastEvent-in-VideoObject use cases.

### Google Analytics 4
- Dedicated MyUSA.us web stream only.
- Reports must be filtered to the MyUSA stream; never mix HO-TEL or other sites.
- Measure page views, sessions, engaged sessions, acquisition, landing pages, ZIP search, saved-location use, alert interactions, radar interactions, trend-card views/clicks, and official-source clicks.
- Link the MyUSA GA4 web stream to the MyUSA Search Console property.

### Google tag / Tag Manager
- Use one MyUSA-specific Google tag/container.
- Centralize GA4 events and parameters.
- Avoid duplicate page_view firing.
- Use privacy/consent controls appropriate to MyUSA's legal requirements.

## Tier 2 — Search quality and performance

### PageSpeed Insights / Lighthouse
- Automated mobile and desktop tests for homepage, representative ZIPs, state pages, radar, severe, hurricane, air-quality, and Healthy Weather pages.
- Track performance, accessibility, best practices, and SEO scores.
- Treat Lighthouse lab results as diagnostics, not visitor traffic.

### Chrome UX Report (CrUX)
- Track real-user LCP, INP, CLS, TTFB and other available origin/page metrics.
- Use the 28-day rolling real-user window for release-quality decisions.
- Prefer CrUX API for field performance monitoring as Google is moving real-world data out of PageSpeed Insights API.

### Search appearance / structured data
- Maintain accurate Organization/WebSite/Breadcrumb and page-appropriate structured data.
- Use only schema supported by the actual visible page content.
- Never manufacture reviews, ratings, authors, dates, alerts, or other markup purely for rich results.

## Tier 3 — Discovery and trend intelligence

### Google Trends
- Use Trends to identify real weather/search interest by geography and time.
- Trend signals never override official NOAA/NWS/NHC/SPC/AirNow facts.
- Trend cards require official-source verification, correct geography, priority, issue time, expiration time, wording log, and lifecycle log.
- Apply for the official Google Trends API alpha; until access is granted, continue controlled Trends UI/export workflows.

### Google Discover
- No special tag is required; indexed policy-compliant content is automatically eligible.
- Favor useful, timely, people-first weather guidance with strong relevant imagery where appropriate.
- Do not create clickbait or thin trend pages solely for Discover.

### Google News
- Use only for genuine timely weather/news-style content if MyUSA develops an editorial/news layer.
- Do not turn forecast/location pages into pseudo-news articles to chase News visibility.

## Tier 4 — Reporting and data ownership

### Looker Studio
- One MyUSA dashboard combining Search Console + GA4 + operational Sheets.
- Daily overview: users, views, sessions, Google clicks/impressions, top queries/pages, trend-card performance, page health, Core Web Vitals.
- Weekly and monthly trend comparisons.

### BigQuery
- Link the MyUSA GA4 property/stream for daily raw event export when the Google Cloud project is ready.
- Use the free/sandbox path first where practical; set budgets/alerts before billable workloads.
- Keep MyUSA data separate from other projects/sites.

### Google Sheets / Drive
- Preserve searchable operational history: Search Console snapshots, trend-card lifecycle, ZIP health, release health, fixes, and weekly/monthly reports.
- Sheets are reporting/logging stores, not a replacement for GA4/Search Console source-of-truth data.

## Products intentionally not used for ranking manipulation

- Google Ads is not required for organic ranking. Keyword Planner may be used only as supplemental search-demand research if useful; paid ads never become an SEO requirement.
- AdSense is excluded because MyUSA's product rule is no ads.
- Google Business Profile is not appropriate unless MyUSA later operates a genuine eligible local business/location; never create a profile just to influence search.
- Indexing API is excluded for normal forecast/location pages.

## MCP connector tools

The `analytics_connector` exposes MyUSA-only tools for:
- GA4 property/stream details
- realtime users/views
- traffic overview
- top pages
- traffic sources
- GA4 events
- Google Search totals
- Google Search queries
- Google Search pages
- Search Console sitemaps
- URL Inspection
- PageSpeed/Lighthouse
- CrUX

## Required authorization/configuration

Environment/config values:
- `MYUSA_GA4_PROPERTY_ID=527458725`
- `MYUSA_SEARCH_CONSOLE_SITE=https://myusa.us/`
- `GOOGLE_API_KEY=<Cloud API key for CrUX/PageSpeed as needed>`

The deployed service account needs only the minimum read permissions required:
- GA4 Viewer for the MyUSA property/stream
- Search Console access to the MyUSA property
- Enabled Search Console API, Analytics Data/Admin APIs, PageSpeed Insights API, and Chrome UX Report API in the Google Cloud project

Manual Google UI links that should be completed once authorized:
1. GA4 ↔ Search Console product link for the MyUSA web stream.
2. GA4 ↔ BigQuery daily export.
3. Looker Studio data sources/dashboard.
4. Google Trends API alpha application.
5. Tag Manager/Google tag audit to ensure one MyUSA implementation and no cross-site contamination.
