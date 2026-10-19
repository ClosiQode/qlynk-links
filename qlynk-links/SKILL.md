---
name: qlynk-links
description: Manage short links on Qlynk (qlynk.fr), the French URL shortener, through its REST API - shorten a URL, list or search links, read click statistics (per link or across all links for a day, week, month or year), put links into categories and sub-categories, edit or delete links, and make a QR code of a short link. Use this skill whenever the user mentions Qlynk or qlynk.fr, or asks to shorten a link, create a short link or a QR code for a link, count clicks or scans on their links, or organise their short links into folders/categories - including French requests such as "raccourcis ce lien", "crée le QR code", "combien de clics sur mes liens cette semaine", "range ce lien dans la catégorie X", "mes liens courts", even when they do not name Qlynk but have a QLYNK_API_KEY set.
---

# Qlynk links

Qlynk (https://qlynk.fr) shortens links, counts clicks without bots or duplicates, makes QR codes and opens links directly in the right mobile app (YouTube, Instagram, WhatsApp...). This skill drives the user's own Qlynk account through `scripts/qlynk.py`, a small Python 3 client with no dependencies.

## Setup (check first)

The script reads the API key from the `QLYNK_API_KEY` environment variable. It never prints the key.

- If a command exits with code 2 and "No API key", ask the user for their key. They create it, while logged in, at https://qlynk.fr/api-keys.php (free account; the key is shown only once).
- When the user pastes a key in the conversation, pass it for each command as `QLYNK_API_KEY='...' python3 scripts/qlynk.py ...`. Do not write it into files of their project, and do not repeat it back in your answer.
- In Claude Code, suggest a lasting setup: add `"env": {"QLYNK_API_KEY": "..."}` to `~/.claude/settings.json`, or export it in their shell profile.
- In claude.ai, code execution must be allowed to reach the internet with `qlynk.fr` in the allowed domains (Settings > Capabilities). If the script says it cannot reach qlynk.fr, explain this.

Run the script with the path where this skill is installed, for example `python3 <skill-dir>/scripts/qlynk.py <command>`. Add `--json` before the command when you need the raw data.

## Commands

| User wants | Command |
|---|---|
| Shorten a link | `shorten URL [--title T] [--code end-of-link] [--category NAME] [--create-category]` |
| Make a QR code | `qr CODE_OR_URL [--out file.png] [--svg] [--color #hex --background #hex]` |
| Clicks across all links | `summary --period day/week/month/year/all [--category NAME] [--top 10]` |
| Stats of one link | `stats CODE --period week` |
| Put a link in a category | `move CODE "Category"` or `move CODE "Parent > Child"` (`none` = uncategorised, `--create` if missing) |
| List or find links | `list [--search TEXT] [--category NAME] [--limit 50]` |
| Details of one link | `get CODE` |
| Change a link | `update CODE [--url] [--title] [--description] [--new-code] [--category] [--expires YYYY-MM-DD]` |
| Delete a link | `delete CODE --yes` (only after the user confirmed) |
| Categories | `categories`, `category-create NAME [--parent NAME]` |
| Requests left today | `quota` |

CODE is the end of the short link: for `https://qlynk.fr/promo-ete`, the code is `promo-ete`. When the user refers to a link by its destination or title ("my YouTube link"), find it with `list --search` first.

## How to handle common requests

**"Shorten this link"** - run `shorten`. Give back the short link on its own line so it is easy to copy, and mention the app it opens in when the output shows one ("Opens the app: Instagram"). Personalised links (`qlynk.fr/their-name`) are included in every plan, free too: when the user asks for a specific ending ("call it soldes-ete", "en qlynk.fr/menu"), pass `--code soldes-ete` (3 to 50 characters: letters, digits, hyphens, underscores; no accents or spaces, so turn "Soldes été" into soldes-ete). Otherwise let Qlynk pick a random code. If the ending is taken or reserved, the error suggests an alternative - offer it.

**"Make the QR code"** - run `qr` with the code of the link the user means: usually the one just created or discussed; if it is unclear, ask which link (or create it first). The QR code is computed locally, it costs no API request. It points to the short link with `?qr=1`, so scans are counted separately as QR scans in the statistics. Tell the user where the file is saved; in claude.ai, save it in the outputs folder so they can download it. PNG by default; `--svg` for print. Keep enough contrast between colour and background, or phones will not read it.

**"How many clicks this week"** - run `summary --period week`. Periods are rolling: `day` = last 24 hours, `week` = last 7 days, `month` = last 30 days, `year` = last 365 days; say so if the user may expect a calendar week. It makes one API request per link (newest 50 by default), so on a free account with many links, say how many links were counted. Answer with the total first, then the top links. For one link, use `stats CODE`.

**"Put this link in category X"** - run `categories` first when you do not know the user's categories, then `move CODE "X"`. Accents and case are ignored. If no category matches exactly, or several could fit ("Clients" vs "Clients test"), ask the user which one; add `--create` only when they clearly want a new category, so you never create a duplicate. Qlynk allows two levels: category and sub-category ("Clients > Acme").

**Deleting** is permanent (the link stops working and its statistics are lost). Run `get CODE` first, then ask the user to confirm, naming the short link and its destination; only then run `delete --yes`.

**Quota awareness** - most commands cost one or two API requests; `summary` costs one per link counted. On a free account, avoid repeating `summary` needlessly, and run `quota` if the user asks how many requests are left.

## Limits and errors

The script explains each failure on stderr. Relay the explanation in the user's language, simply.

| Exit code | Meaning | What to tell the user |
|---|---|---|
| 2 | Missing key or wrong option | Ask for the key, or fix the command. |
| 3 | Key rejected (HTTP 401) | Key wrong, revoked or account disabled: create a new key at https://qlynk.fr/api-keys.php. |
| 4 | Daily quota (HTTP 429) or plan limit (HTTP 403) | Free plan: 100 API requests per day and a monthly cap on new links; the expiry date is a Pro feature. The Pro plan (see https://qlynk.fr/#offres) gives 10,000 requests per day, unlimited links and full statistics history. Mention it once, factually, without pushing. |
| 1 | Other refusal (unknown link, address refused, code taken...) | Quote the reason given by Qlynk. |

Do not retry a 429: the quota renews at midnight and the message gives the delay. On the free plan, statistics only cover the last 30 days; the output says so when it happens.

Full API reference, fields and answers: `references/api.md` (read it only if a command above does not cover the request).
