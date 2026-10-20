# Qlynk REST API v1 - reference

Base URL: `https://qlynk.eu/api/v1` (override with the `QLYNK_API_URL` environment variable).
Public documentation: https://qlynk.eu/docs/api.php

## Authentication and quotas

- Header `Authorization: Bearer <key>` on every request; JSON bodies with `Content-Type: application/json`.
- Keys are created at https://qlynk.eu/api-keys.php and shown once. Missing, malformed or revoked key: `401`.
- Daily quota per account (all keys together), renewed at midnight: Free 50 requests, Pro 10,000.
  Headers on each answer: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix time).
  Over quota: `429` with `Retry-After` (seconds) and a body `{ "limit", "window": "day", "retry_after" }`. Refused requests do not count.
- Plan limits also apply (`403`): Free accounts can have 10 active links at a time (deleting one frees its slot; a link disabled by moderation cannot be deleted and keeps its slot) plus a daily cap that also counts deleted links; `custom_code` (choosing or changing the ending) and `expires_at` are reserved to Pro.

## Answer format

Success: `{ "success": true, "data": ... }`. Error: `{ "success": false, "error": "message", "code": "stable_code" }`. The message follows the request language (English by default); test `code` (for example `pro_required`, `link_limit_reached`, `link_not_found`, `invalid_url`), never the message text.
Codes: 200/201 success, 400 invalid request, 401 key, 403 not yours or plan limit, 404 not found, 405 method, 429 quota, 500 server, 503 API turned off.

## Links

| Method | Path | Notes |
|---|---|---|
| POST | `/urls` | Body: `url` (required), `custom_code` (max 50, Pro only), `title` (255), `description` (1000), `is_indexed` (bool), `category_id` (int or null), `expires_at` (`YYYY-MM-DD` or date-time, Pro). Returns 201. |
| GET | `/urls` | Query: `category_id` (int, or `none` for uncategorised), `include_children=0` to exclude sub-categories. Returns `{ total, urls[] }`, newest first. |
| GET | `/urls/{code}` | One link. |
| PATCH or PUT | `/urls/{code}` | Only the fields sent change. `url`, `custom_code`, `title`, `description`, `is_indexed`, `category_id` (null = uncategorised), `expires_at` (null = none). |
| DELETE | `/urls/{code}` | Permanent. |

Link object: `short_code`, `short_url`, `original_url`, `title`, `description`, `is_indexed`, `category_id`, `expires_at`, `app` (name of the mobile app the link opens, or null), `created_at`.

## Categories

| Method | Path | Notes |
|---|---|---|
| GET | `/categories` | `{ total, categories[] }` with `id`, `parent_id`, `name`, `color`, `icon`, `position`, `link_count`. |
| GET | `/categories/{id}` | One category. |
| POST | `/categories` | `name` (required), `parent_id` (a top-level category; two levels at most), `color` (`#RRGGBB`), `icon`, `position`. |
| PATCH or PUT | `/categories/{id}` | Only the fields sent change. `parent_id: null` moves it to the top level. |
| DELETE | `/categories/{id}` | Links are kept (they become uncategorised); sub-categories move to the top level. |

## Statistics

`GET /stats/{code}?period=day|week|month|year|all` (default `all`).

Answer: `period`, `period_days`, `history_limited` (true when the free plan shortened the period to 30 days), `timezone` (Europe/Paris), `total_clicks`, `unique_visitors`, `app_opens`, `qr_scans`, `filtered_hits` (bots, link previews, prefetches, repeats, owner), `last_click`, `clicks_by_date[] {date, clicks}` newest first, `devices {mobile, tablet, desktop}`, `top_countries[] {country, code, clicks}`, `top_browsers[]`, `top_os[]`, `top_referrers[] {domain, clicks}`.

There is no endpoint for totals across all links: `scripts/qlynk.py summary` calls `/stats/{code}` once per link.

## QR codes

There is no QR endpoint. `scripts/qlynk.py qr` computes the QR code locally (`scripts/qr.py`) for `https://qlynk.eu/<code>?qr=1`; the `qr=1` parameter makes Qlynk count the visit as a QR scan.

Link status: each link in `GET /urls` and `GET /urls/{code}` has `status` (`active` or `paused`) and `paused_at`. A paused link (Free account over its active-link limit, 7 days after a Pro plan ended) answers HTTP 423 to visitors and does not count toward the active-link limit; it is reactivated automatically when the account is Pro again.
