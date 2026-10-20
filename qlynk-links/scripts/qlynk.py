#!/usr/bin/env python3
"""Command line client for the Qlynk REST API (https://qlynk.eu/docs/api.php).

Standard library only. The API key is read from the QLYNK_API_KEY environment
variable (or from a file given with --key-file). It is never printed.

Examples:
  python3 qlynk.py shorten https://example.com/page --category "Clients"
  python3 qlynk.py list --search promo
  python3 qlynk.py summary --period week
  python3 qlynk.py move abc123 "Clients > Acme"
  python3 qlynk.py qr abc123 --out qr-abc123.png

Exit codes: 0 success, 1 API error, 2 usage or configuration problem,
3 key rejected (401), 4 daily quota or plan limit reached.
"""

import argparse
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API = 'https://qlynk.eu/api/v1'
USER_AGENT = 'qlynk-claude-skill/1.0'
PERIODS = ('day', 'week', 'month', 'year', 'all')


class Stop(Exception):
    """Ends the command with a message on stderr and a given exit code."""

    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# HTTP client

class Client:
    def __init__(self, key, api_url):
        self.key = key
        self.api = api_url.rstrip('/')
        self.site = self.api.rsplit('/api/', 1)[0]
        self.calls = 0
        self.remaining = None
        self.limit = None

    def request(self, method, path, body=None, query=None):
        url = self.api + path
        if query:
            url += '?' + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        data = json.dumps(body).encode('utf-8') if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Authorization', 'Bearer ' + self.key)
        req.add_header('Accept', 'application/json')
        req.add_header('User-Agent', USER_AGENT)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self._read_quota(resp.headers)
                payload = self._decode(resp.read())
                status = resp.status
        except urllib.error.HTTPError as err:
            self._read_quota(err.headers)
            payload = self._decode(err.read())
            status = err.code
        except urllib.error.URLError as err:
            raise Stop(
                'Cannot reach %s (%s). Check the internet connection. In claude.ai, code execution '
                'needs network access with the domain %s allowed (Settings > Capabilities).'
                % (self.site, err.reason, urllib.parse.urlparse(self.site).hostname), 1)
        except TimeoutError:
            raise Stop('Qlynk did not answer within 30 seconds. Try again in a moment.', 1)

        if 200 <= status < 300 and isinstance(payload, dict) and payload.get('success'):
            return payload.get('data')
        self._raise(status, payload)

    @staticmethod
    def _decode(raw):
        try:
            return json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return None

    def _read_quota(self, headers):
        if headers is None:
            return
        if headers.get('X-RateLimit-Remaining') is not None:
            self.remaining = int(headers['X-RateLimit-Remaining'])
        if headers.get('X-RateLimit-Limit') is not None:
            self.limit = int(headers['X-RateLimit-Limit'])

    def _raise(self, status, payload):
        message = payload.get('error') if isinstance(payload, dict) else None
        message = message or 'Unexpected answer from Qlynk (HTTP %d).' % status
        pro = '%s/#offres' % self.site
        if status == 401:
            raise Stop(
                'API key rejected (HTTP 401): %s\nThe key is wrong, revoked, or the account is disabled. '
                'Create a new key at %s/api-keys.php and set QLYNK_API_KEY again.' % (message, self.site), 3)
        if status == 429:
            wait = int(payload.get('retry_after', 0)) if isinstance(payload, dict) else 0
            limit = payload.get('limit') if isinstance(payload, dict) else None
            raise Stop(
                'Daily API quota reached (HTTP 429): %s\nQuota: %s requests per day, renewed at midnight '
                'in about %s. The Pro plan raises the quota to 10,000 requests per day: %s'
                % (message, limit or '?', _duration(wait), pro), 4)
        code = payload.get('code') if isinstance(payload, dict) else None
        if status == 403 and (code in ('pro_required', 'link_limit_reached') or any(w in message.lower() for w in ('offre', 'plan', 'pro', 'limit', 'limite', 'plafond'))):
            raise Stop('Plan limit (HTTP 403): %s\nSee the Pro plan: %s' % (message, pro), 4)
        if status == 503:
            raise Stop('The Qlynk API is turned off for now (HTTP 503): %s' % message, 1)
        raise Stop('Qlynk refused the request (HTTP %d): %s' % (status, message), 1)

    def short_url(self, code):
        return '%s/%s' % (self.site, code)


def _duration(seconds):
    if seconds <= 0:
        return 'a few hours'
    hours, minutes = divmod(int(seconds) // 60, 60)
    return '%d h %02d min' % (hours, minutes) if hours else '%d min' % max(1, minutes)


# ---------------------------------------------------------------------------
# Categories

def _norm(text):
    text = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return ' '.join(text.casefold().split())


def _split_path(name):
    for sep in ('›', '>', '/'):
        if sep in name:
            parts = [p.strip() for p in name.split(sep, 1)]
            if all(parts):
                return parts
    return [name.strip()]


def load_categories(client):
    cats = client.request('GET', '/categories')['categories']
    by_id = {c['id']: c for c in cats}
    for c in cats:
        parent = by_id.get(c['parent_id'])
        c['label'] = '%s > %s' % (parent['name'], c['name']) if parent else c['name']
    return cats


def find_category(cats, name):
    """Returns the category matching a name, an id or "Parent > Child". None if nothing matches."""
    name = str(name).strip()
    if name.isdigit():
        return next((c for c in cats if c['id'] == int(name)), None)
    parts = _split_path(name)
    if len(parts) == 2:
        parent = [c for c in cats if c['parent_id'] is None and _norm(c['name']) == _norm(parts[0])]
        if parent:
            child = [c for c in cats if c['parent_id'] == parent[0]['id'] and _norm(c['name']) == _norm(parts[1])]
            if child:
                return child[0]
    matches = [c for c in cats if _norm(c['name']) == _norm(name) or _norm(c['label']) == _norm(name)]
    if len(matches) > 1:
        raise Stop('Several categories are called "%s": %s. Use the full path, for example "%s".'
                   % (name, ', '.join(m['label'] for m in matches), matches[0]['label']), 2)
    return matches[0] if matches else None


def resolve_category(client, name, create=False):
    """Category id for a name. "none" means Uncategorised (returns None)."""
    if _norm(name) in ('none', 'aucune', 'non classes', 'uncategorized', 'uncategorised'):
        return None
    cats = load_categories(client)
    found = find_category(cats, name)
    if found:
        return found['id']
    if not create:
        names = ', '.join('"%s"' % c['label'] for c in cats) or '(no category yet)'
        raise Stop('No category called "%s". Existing categories: %s.\n'
                   'Add --create to create it.' % (name, names), 2)
    parts = _split_path(name)
    parent_id = None
    if len(parts) == 2:
        parent = find_category(cats, parts[0])
        if parent and parent['parent_id'] is not None:
            raise Stop('"%s" is already a sub-category. Qlynk allows two levels only.' % parent['label'], 2)
        parent_id = parent['id'] if parent else client.request('POST', '/categories', {'name': parts[0]})['id']
    created = client.request('POST', '/categories', {'name': parts[-1], 'parent_id': parent_id})
    print('Created category "%s" (id %d).' % (name, created['id']))
    return created['id']


# ---------------------------------------------------------------------------
# Output helpers

def show(data, as_json):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    return False


def link_line(link, cat_labels=None):
    cat = ''
    if cat_labels is not None:
        cat = '  [%s]' % cat_labels.get(link.get('category_id'), 'Uncategorised')
    title = ('  "%s"' % link['title']) if link.get('title') else ''
    paused = '  [PAUSED: does not redirect]' if link.get('status') == 'paused' else ''
    return '%s  ->  %s%s%s%s' % (link['short_url'], link['original_url'], title, cat, paused)


def describe_link(link, cat_labels):
    rows = [
        ('Short link', link['short_url']),
        ('Destination', link['original_url']),
        ('Title', link.get('title') or '-'),
        ('Category', cat_labels.get(link.get('category_id'), 'Uncategorised')),
        ('Opens the app', link.get('app') or '-'),
        ('Status', 'paused since %s (does not redirect; back to Pro or keep it active from the dashboard)' % link.get('paused_at') if link.get('status') == 'paused' else 'active'),
        ('Expires', link.get('expires_at') or 'never'),
        ('Created', link.get('created_at') or link.get('updated_at') or '-'),
    ]
    return '\n'.join('%-14s %s' % r for r in rows)


def labels(client):
    return {c['id']: c['label'] for c in load_categories(client)}


# ---------------------------------------------------------------------------
# Commands

def cmd_shorten(client, args):
    body = {'url': args.url}
    if args.code:
        body['custom_code'] = args.code
    if args.title:
        body['title'] = args.title
    if args.description:
        body['description'] = args.description
    if args.expires:
        body['expires_at'] = args.expires
    if args.no_index:
        body['is_indexed'] = False
    if args.category:
        body['category_id'] = resolve_category(client, args.category, args.create_category)
    link = client.request('POST', '/urls', body)
    if not show(link, args.json):
        print('Created: %s' % link['short_url'])
        print(describe_link(link, labels(client) if link.get('category_id') else {}))


def cmd_list(client, args):
    query = {}
    if args.category:
        cid = resolve_category(client, args.category)
        query['category_id'] = 'none' if cid is None else cid
    data = client.request('GET', '/urls', query=query)
    links = data['urls']
    if args.search:
        s = _norm(args.search)
        links = [l for l in links if s in _norm(' '.join(str(l.get(k) or '') for k in ('short_code', 'original_url', 'title', 'description')))]
    shown = links[:args.limit] if args.limit else links
    if show({'total': len(links), 'urls': shown}, args.json):
        return
    cat_labels = labels(client)
    print('%d link(s)%s, newest first:' % (len(links), ' matching' if args.search or args.category else ''))
    for link in shown:
        print('- ' + link_line(link, cat_labels))
    if len(shown) < len(links):
        print('... %d more (use --limit 0 to see all).' % (len(links) - len(shown)))


def cmd_get(client, args):
    link = client.request('GET', '/urls/' + urllib.parse.quote(args.code))
    if not show(link, args.json):
        print(describe_link(link, labels(client)))


def cmd_update(client, args):
    body = {}
    for field, value in (('url', args.url), ('custom_code', args.new_code), ('title', args.title), ('description', args.description)):
        if value is not None:
            body[field] = value
    if args.expires is not None:
        body['expires_at'] = None if _norm(args.expires) in ('none', 'never', 'jamais') else args.expires
    if args.category is not None:
        body['category_id'] = resolve_category(client, args.category, args.create_category)
    if args.index is not None:
        body['is_indexed'] = args.index == 'yes'
    if not body:
        raise Stop('Nothing to change. Give at least one option, for example --title "New title".', 2)
    link = client.request('PATCH', '/urls/' + urllib.parse.quote(args.code), body)
    if not show(link, args.json):
        print('Updated.')
        print(describe_link(link, labels(client)))


def cmd_move(client, args):
    cid = resolve_category(client, args.category, args.create)
    link = client.request('PATCH', '/urls/' + urllib.parse.quote(args.code), {'category_id': cid})
    if not show(link, args.json):
        print('%s is now in "%s".' % (link['short_url'], labels(client).get(cid, 'Uncategorised')))


def cmd_delete(client, args):
    if not args.yes:
        raise Stop('Deleting a link is permanent: it stops working and its statistics are lost. '
                   'Ask the user to confirm, then run again with --yes.', 2)
    data = client.request('DELETE', '/urls/' + urllib.parse.quote(args.code))
    if not show(data, args.json):
        print('Deleted %s.' % client.short_url(args.code))


def cmd_categories(client, args):
    cats = load_categories(client)
    if show(cats, args.json):
        return
    if not cats:
        print('No category yet. Create one with: category-create "Name"')
        return
    roots = sorted([c for c in cats if c['parent_id'] is None], key=lambda c: c['position'])
    for root in roots:
        print('- %s (id %d, %d link(s))' % (root['name'], root['id'], root['link_count']))
        for child in sorted([c for c in cats if c['parent_id'] == root['id']], key=lambda c: c['position']):
            print('    - %s (id %d, %d link(s))' % (child['name'], child['id'], child['link_count']))


def cmd_category_create(client, args):
    body = {'name': args.name}
    if args.parent:
        parent = find_category(load_categories(client), args.parent)
        if not parent:
            raise Stop('No category called "%s" to use as parent.' % args.parent, 2)
        body['parent_id'] = parent['id']
    if args.color:
        body['color'] = args.color
    cat = client.request('POST', '/categories', body)
    if not show(cat, args.json):
        print('Created category "%s" (id %d).' % (cat['name'], cat['id']))


def _stats_text(s):
    lines = [
        'Period: %s%s' % (s['period'], ' (free plan: history limited to %s days)' % s['period_days'] if s.get('history_limited') else ''),
        'Clicks: %d  |  unique visitors: %d  |  QR scans: %d  |  opened in app: %d'
        % (s['total_clicks'], s['unique_visitors'], s['qr_scans'], s['app_opens']),
        'Filtered out (bots, previews, repeats): %d' % s['filtered_hits'],
        'Last click: %s' % (s.get('last_click') or 'none yet'),
    ]
    d = s.get('devices') or {}
    if any(d.values()):
        lines.append('Devices: mobile %d, desktop %d, tablet %d' % (d.get('mobile', 0), d.get('desktop', 0), d.get('tablet', 0)))
    for key, label, field in (('top_countries', 'Countries', 'country'), ('top_referrers', 'Sources', 'domain'),
                              ('top_browsers', 'Browsers', 'browser'), ('top_os', 'Systems', 'os')):
        items = s.get(key) or []
        if items:
            lines.append('%s: %s' % (label, ', '.join('%s %d' % (i[field], i['clicks']) for i in items[:5])))
    days = s.get('clicks_by_date') or []
    if days:
        lines.append('Clicks by day (newest first): %s' % ', '.join('%s: %s' % (d.get('date'), d.get('clicks')) for d in days[:14]))
    return '\n'.join(lines)


def cmd_stats(client, args):
    s = client.request('GET', '/stats/' + urllib.parse.quote(args.code), query={'period': args.period})
    if not show(s, args.json):
        print('Statistics for %s' % client.short_url(args.code))
        print(_stats_text(s))


def cmd_summary(client, args):
    query = {}
    if args.category:
        cid = resolve_category(client, args.category)
        query['category_id'] = 'none' if cid is None else cid
    links = client.request('GET', '/urls', query=query)['urls']
    budget = len(links) if args.max == 0 else min(len(links), args.max)
    if client.remaining is not None and budget > client.remaining:
        budget = client.remaining
    rows, limited = [], False
    for link in links[:budget]:
        s = client.request('GET', '/stats/' + urllib.parse.quote(link['short_code']), query={'period': args.period})
        limited = limited or bool(s.get('history_limited'))
        rows.append({'short_url': link['short_url'], 'title': link.get('title') or '', 'original_url': link['original_url'],
                     'clicks': s['total_clicks'], 'unique_visitors': s['unique_visitors'], 'qr_scans': s['qr_scans']})
    rows.sort(key=lambda r: r['clicks'], reverse=True)
    result = {'period': args.period, 'links_counted': len(rows), 'links_total': len(links),
              'total_clicks': sum(r['clicks'] for r in rows), 'unique_visitors': sum(r['unique_visitors'] for r in rows),
              'qr_scans': sum(r['qr_scans'] for r in rows), 'history_limited': limited, 'links': rows}
    if show(result, args.json):
        return
    span = {'day': 'last 24 hours', 'week': 'last 7 days', 'month': 'last 30 days', 'year': 'last 365 days', 'all': 'all time'}[args.period]
    print('Period: %s  |  links counted: %d of %d' % (span, len(rows), len(links)))
    print('Total clicks: %d  |  unique visitors: %d  |  QR scans: %d'
          % (result['total_clicks'], result['unique_visitors'], result['qr_scans']))
    if limited:
        print('Note: free plan, statistics only cover the last days allowed by the plan.')
    if len(rows) < len(links):
        print('Note: only the %d newest links were counted (one API request per link). Use --max 0 for all.' % len(rows))
    for r in rows[:args.top]:
        print('- %5d clicks  %s  ->  %s%s' % (r['clicks'], r['short_url'], r['original_url'], ('  "%s"' % r['title']) if r['title'] else ''))


def cmd_qr(client, args):
    from qr import QrCode, hex_to_rgb  # local module next to this script

    target = args.target
    if '://' not in target:
        target = client.short_url(target.lstrip('/'))
    host = urllib.parse.urlparse(client.site).hostname
    if urllib.parse.urlparse(target).hostname == host and not args.no_track and 'qr=' not in target:
        target += ('&' if '?' in target else '?') + 'qr=1'
    try:
        code = QrCode(target, args.level)
        dark, light = hex_to_rgb(args.color), hex_to_rgb(args.background)
    except ValueError as err:
        raise Stop(str(err), 2)
    out = args.out or 'qr-%s.%s' % (target.split('://', 1)[-1].split('?')[0].rstrip('/').split('/')[-1] or 'qlynk',
                                    'svg' if args.svg else 'png')
    if out.lower().endswith('.svg'):
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write(code.to_svg(dark=args.color, light=args.background))
    else:
        with open(out, 'wb') as fh:
            fh.write(code.to_png(scale=args.scale, dark=dark, light=light))
    print('QR code saved to %s' % os.path.abspath(out))
    print('It opens: %s' % target)
    if 'qr=1' in target:
        print('Scans are counted as "QR scans" in the link statistics.')


def cmd_quota(client, args):
    client.request('GET', '/categories')
    if client.limit is None:
        print('No daily limit on this account.')
    else:
        print('Daily quota: %d requests. Left today: %d.' % (client.limit, client.remaining))


# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog='qlynk.py', description='Qlynk links from the command line.')
    p.add_argument('--json', action='store_true', help='print raw JSON')
    p.add_argument('--key-file', help='read the API key from this file instead of QLYNK_API_KEY')
    sub = p.add_subparsers(dest='command', required=True)

    s = sub.add_parser('shorten', help='create a short link')
    s.add_argument('url')
    s.add_argument('--code', help='custom end of the link (qlynk.eu/<code>)')
    s.add_argument('--title')
    s.add_argument('--description')
    s.add_argument('--category', help='category name, "Parent > Child", or id')
    s.add_argument('--create-category', action='store_true', help='create the category if missing')
    s.add_argument('--expires', help='YYYY-MM-DD (Pro plan)')
    s.add_argument('--no-index', action='store_true', help='ask search engines not to index the preview')
    s.set_defaults(func=cmd_shorten)

    s = sub.add_parser('list', help='list links, newest first')
    s.add_argument('--category', help='only this category (with its sub-categories); "none" = uncategorised')
    s.add_argument('--search', help='filter on code, destination, title or description')
    s.add_argument('--limit', type=int, default=50, help='how many to print (0 = all)')
    s.set_defaults(func=cmd_list)

    s = sub.add_parser('get', help='details of one link')
    s.add_argument('code')
    s.set_defaults(func=cmd_get)

    s = sub.add_parser('update', help='change a link (only the given fields change)')
    s.add_argument('code')
    s.add_argument('--url', help='new destination')
    s.add_argument('--new-code', help='new end of the link (the old one stops working)')
    s.add_argument('--title')
    s.add_argument('--description')
    s.add_argument('--category', help='category name, id, or "none"')
    s.add_argument('--create-category', action='store_true')
    s.add_argument('--expires', help='YYYY-MM-DD, or "none" to remove (Pro plan)')
    s.add_argument('--index', choices=('yes', 'no'))
    s.set_defaults(func=cmd_update)

    s = sub.add_parser('move', help='put a link in a category')
    s.add_argument('code')
    s.add_argument('category', help='category name, "Parent > Child", id, or "none"')
    s.add_argument('--create', action='store_true', help='create the category if missing')
    s.set_defaults(func=cmd_move)

    s = sub.add_parser('delete', help='delete a link (permanent)')
    s.add_argument('code')
    s.add_argument('--yes', action='store_true', help='confirm the deletion')
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser('categories', help='list categories and sub-categories')
    s.set_defaults(func=cmd_categories)

    s = sub.add_parser('category-create', help='create a category')
    s.add_argument('name')
    s.add_argument('--parent', help='parent category (two levels at most)')
    s.add_argument('--color', help='#RRGGBB')
    s.set_defaults(func=cmd_category_create)

    s = sub.add_parser('stats', help='statistics of one link')
    s.add_argument('code')
    s.add_argument('--period', choices=PERIODS, default='all')
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser('summary', help='clicks across all links (one request per link)')
    s.add_argument('--period', choices=PERIODS, default='week')
    s.add_argument('--category', help='only links of this category')
    s.add_argument('--max', type=int, default=50, help='newest links to count (0 = all)')
    s.add_argument('--top', type=int, default=10, help='how many links to print')
    s.set_defaults(func=cmd_summary)

    s = sub.add_parser('qr', help='make a QR code image of a short link (computed locally)')
    s.add_argument('target', help='short code (abc123) or full address')
    s.add_argument('--out', help='file name, .png or .svg')
    s.add_argument('--svg', action='store_true', help='SVG instead of PNG')
    s.add_argument('--scale', type=int, default=10, help='PNG pixels per module')
    s.add_argument('--color', default='#000000')
    s.add_argument('--background', default='#ffffff')
    s.add_argument('--level', choices=('L', 'M', 'Q', 'H'), default='M', help='error correction')
    s.add_argument('--no-track', action='store_true', help='do not add ?qr=1 (scans then count as clicks)')
    s.set_defaults(func=cmd_qr)

    s = sub.add_parser('quota', help='API requests left today')
    s.set_defaults(func=cmd_quota)
    return p


def read_key(args):
    if args.key_file:
        try:
            with open(os.path.expanduser(args.key_file), encoding='utf-8') as fh:
                return fh.read().strip()
        except OSError as err:
            raise Stop('Cannot read the key file: %s' % err, 2)
    return os.environ.get('QLYNK_API_KEY', '').strip()


def main(argv=None):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    args = build_parser().parse_args(argv)
    api_url = os.environ.get('QLYNK_API_URL', DEFAULT_API)
    try:
        key = read_key(args)
        if args.command != 'qr' and not key:
            raise Stop('No API key. Set the QLYNK_API_KEY environment variable. The key is created at '
                       'https://qlynk.eu/api-keys.php (free account) and shown only once.', 2)
        client = Client(key, api_url)
        args.func(client, args)
        if client.remaining is not None and client.remaining <= 10:
            print('Warning: only %d API requests left today.' % client.remaining, file=sys.stderr)
        return 0
    except Stop as stop:
        print(str(stop), file=sys.stderr)
        return stop.code
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
