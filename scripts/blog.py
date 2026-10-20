#!/usr/bin/env python3
"""DynastyMath blog generator (imported by build_pages.py; stdlib only).

Source:  content/blog/*.md  - front matter (key: value lines between '---' lines) + markdown body.
Output:  blog/index.html, blog/<slug>/index.html, blog/feed.xml  (all marked with a .generated file).

Front matter keys: title, slug, date (YYYY-MM-DD), updated (optional), description (100-160 chars), answer (one-paragraph direct answer, inline markdown),
lede (optional), tags (comma separated), data_as_of (YYYY-MM-DD, the date the numbers in the article are baked from), cta_label / cta_href (optional, site-relative like /trade-analyzer/).
Body markdown subset: ## / ### headings, paragraphs, **bold**, *italic*, `code`, [text](/site-path/ or https://...), - and 1. lists, pipe tables, ---.
A '## Frequently asked questions' section ('### Question' + answer paragraphs) also becomes FAQPage JSON-LD.
Internal links are written root-relative ('/dynasty-value-bo-nix/') and rewritten to the site's relative style; a link to a page that no longer
exists is rendered as plain text with a warning (so a daily data refresh can never break the build or leave a dead link).
The author is always 'DynastyMath Staff'."""
import json, html, pathlib, re, datetime, shutil
E = html.escape
AUTHOR = 'DynastyMath Staff'

def parse_front(text):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', text, re.S)
    if not m: raise ValueError('missing front matter')
    meta = {}
    for ln in m.group(1).split('\n'):
        if ':' in ln and not ln.startswith('#'):
            k, v = ln.split(':', 1); meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2)

def fmt_date(d, long=True): return datetime.date.fromisoformat(d).strftime('%B %-d, %Y' if long else '%b %-d, %Y')

class Renderer:
    def __init__(self, root, pre):
        self.root, self.pre, self.warn = root, pre, []
    def exists(self, path):
        seg = path.strip('/').split('/')[0] if path.strip('/') else ''
        if not seg: return True
        return (self.root / seg / 'index.html').exists() or (self.root / seg).is_file()
    def inline(self, s):
        s = E(s, quote=False)
        s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(?<![*\w])\*([^*\s][^*]*)\*(?!\w)', r'<em>\1</em>', s)
        def link(m):
            txt, href = m.group(1), html.unescape(m.group(2))
            if href.startswith('http'): return f'<a href="{E(href)}" rel="noopener">{txt}</a>'
            if href.startswith('/'):
                path = href.split('#')[0].split('?')[0]
                if not self.exists(path): self.warn.append(f'broken internal link {href} (rendered as text)'); return txt
                return f'<a href="{E(self.pre + href.lstrip("/"))}">{txt}</a>'
            return m.group(0)
        return re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link, s)
    def md(self, text):
        L = text.split('\n'); out = []; para = []; i = 0
        def flush():
            if para: out.append('<p>' + self.inline(' '.join(x.strip() for x in para)) + '</p>'); para.clear()
        while i < len(L):
            ln = L[i]
            if not ln.strip(): flush(); i += 1; continue
            h = re.match(r'^(#{2,4})\s+(.*)$', ln)
            if h:
                flush(); n = len(h.group(1)); t = h.group(2).strip()
                sid = re.sub('[^a-z0-9]+', '-', t.lower()).strip('-')[:60]
                out.append(f'<h{n} id="{sid}">{self.inline(t)}</h{n}>'); i += 1; continue
            if re.match(r'^-{3,}\s*$', ln): flush(); out.append('<hr>'); i += 1; continue
            if ln.lstrip().startswith('|') and i + 1 < len(L) and re.match(r'^\s*\|[\s:|-]+\|\s*$', L[i + 1]):
                flush(); cells = lambda r: [c.strip() for c in r.strip().strip('|').split('|')]
                head = cells(ln); i += 2; rows = []
                while i < len(L) and L[i].lstrip().startswith('|'): rows.append(cells(L[i])); i += 1
                lft = ' style="text-align:left"'
                out.append('<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th scope="col"{lft if j == 0 else ""}>{self.inline(c)}</th>' for j, c in enumerate(head)) + '</tr></thead><tbody>'
                           + ''.join('<tr>' + ''.join(f'<td{lft if j == 0 else ""}>{self.inline(c)}</td>' for j, c in enumerate(r)) + '</tr>' for r in rows) + '</tbody></table></div>')
                continue
            lm = re.match(r'^\s*([-*]|\d+\.)\s+(.*)$', ln)
            if lm:
                flush(); tagn = 'ol' if lm.group(1)[0].isdigit() else 'ul'; items = []
                while i < len(L) and (mm := re.match(r'^\s*([-*]|\d+\.)\s+(.*)$', L[i])):
                    items.append(mm.group(2)); i += 1
                    while i < len(L) and L[i].startswith('  ') and L[i].strip() and not re.match(r'^\s*([-*]|\d+\.)\s+', L[i]): items[-1] += ' ' + L[i].strip(); i += 1
                out.append(f'<{tagn}>' + ''.join(f'<li>{self.inline(x)}</li>' for x in items) + f'</{tagn}>'); continue
            para.append(ln); i += 1
        flush(); return '\n'.join(out)

def faq_pairs(body):
    m = re.search(r'^##\s+(?:Frequently asked questions|FAQ)\s*$(.*?)(?=^##\s[^#]|\Z)', body, re.S | re.M | re.I)
    if not m: return []
    pairs = []
    for q in re.split(r'^###\s+', m.group(1), flags=re.M)[1:]:
        head, _, ans = q.partition('\n'); ans = ' '.join(ans.split())
        if head.strip() and ans: pairs.append((head.strip(), ans))
    return pairs

def plain(md_text): return re.sub(r'\s+', ' ', re.sub(r'\*+|`|\[([^\]]+)\]\([^)]*\)', lambda m: m.group(1) or '', md_text)).strip()

def load_articles(root):
    arts = []
    for f in sorted((root / 'content' / 'blog').glob('*.md')):
        meta, body = parse_front(f.read_text())
        for k in ('title', 'slug', 'date', 'description', 'answer'):
            if not meta.get(k): raise ValueError(f'{f.name}: missing front matter "{k}"')
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', meta['slug']): raise ValueError(f'{f.name}: bad slug')
        meta['_body'] = body; meta['_file'] = f.name; arts.append(meta)
    slugs = [a['slug'] for a in arts]
    if len(set(slugs)) != len(slugs): raise ValueError('duplicate blog slugs')
    return sorted(arts, key=lambda a: (a['date'], a['slug']), reverse=True)

def cards(arts, pre, n=None):
    return '<div class="guide-grid">' + ''.join(f'<a class="gcard" href="{pre}blog/{a["slug"]}/"><span class="gtag">{E(fmt_date(a["date"], False))}</span><b>{E(a["title"])}</b><span>{E(a["description"][:130])}</span></a>' for a in arts[:n]) + '</div>'

def build(root, S, gen, genh):
    """Writes the blog; returns the list of article metas (newest first). Warnings are printed, never fatal for dead links."""
    url, name = S['url'], S['name']; tpl = S['template']
    arts = load_articles(root)
    if not arts: return []
    org = S['org']; author = {'@type': 'Organization', 'name': AUTHOR, 'url': url + 'about.html'}
    rss_link = f'<link rel="alternate" type="application/rss+xml" title="{name} blog" href="__PRE__blog/feed.xml">'
    def page(slug, depth, title, desc, h1, lede, answer, body, ld, eyebrow, crumb_nav, cta=('Check your trade', 'trade-analyzer/', ''), cta_text='Check any trade with players and picks.'):
        t = tpl
        t = t.replace('<a href="../guides/">Guides</a> › <span aria-current="page">__NAV__</span>', '<a href="../blog/">Blog</a> › <span aria-current="page">__NAV__</span>')
        t = re.sub(r'__SECTION__ · Updated <time datetime="__UPD__">__UPDH__</time>', eyebrow, t)
        t = t.replace('<link rel="alternate" type="text/plain"', rss_link.replace('__PRE__', '../') + '<link rel="alternate" type="text/plain"', 1)
        ldj = json.dumps({'@context': 'https://schema.org', '@graph': ld}, ensure_ascii=False).replace('</', '<\\/')
        for k, v in [('__LD__', ldj), ('__TITLE__', E(title)), ('__DESC__', E(desc)), ('__H1__', E(h1)), ('__LEDE__', lede), ('__ANSWER__', answer), ('__BODY__', body), ('__NAV__', E(crumb_nav)),
                     ('__CTAL__', E(cta[0])), ('__CTAQ__', cta[1]), ('__CTAA__', cta[2]), ('__CTAT__', E(cta_text)), ('__SLUG__', slug)]:
            t = t.replace(k, v)
        t = re.sub(r'(<a class="btn" href="[^"#]*)#"', r'\1"', t)
        if depth == 2: t = re.sub(r'url\(\.\./', 'url(../../', re.sub(r'(href|src|data-root)="\.\./', r'\1="../../', t))
        d = root / slug; d.mkdir(parents=True, exist_ok=True); (d / 'index.html').write_text(t); (d / '.generated').write_text('')
    (root / 'blog').mkdir(exist_ok=True)
    made = []
    for a in arts:
        slug = 'blog/' + a['slug']; u = url + slug + '/'
        r = Renderer(root, '../'); body_md = a['_body'].strip()  # '../' here: page() prefixes every '../' once more for depth-2 pages
        faqs = faq_pairs(body_md); body = r.md(body_md)
        for w in r.warn: print(f'WARNING blog/{a["slug"]}: {w}')
        words = len(re.sub(r'<[^>]+>', ' ', body).split())
        a['_words'] = words
        asof = a.get('data_as_of') or a['date']
        by = f'<p class="hint"><strong>By {AUTHOR}</strong> · Published <time datetime="{a["date"]}">{fmt_date(a["date"])}</time>' + (f' · Updated <time datetime="{a["updated"]}">{fmt_date(a["updated"])}</time>' if a.get('updated') and a['updated'] != a['date'] else '') + f' · Numbers as of {fmt_date(asof)} · {max(1, round(words / 220))} min read</p>'
        others = [x for x in arts if x['slug'] != a['slug']][:3]
        more = ('<h2>More from the blog</h2><ul>' + ''.join(f'<li><a href="../blog/{x["slug"]}/">{E(x["title"])}</a></li>' for x in others) + '</ul>') if others else ''
        note = f'<p class="hint">Numbers as of {fmt_date(asof)}. Live values move daily, so check the linked pages for today’s. Fantasy football is for fun. This is data, not betting advice.</p>'
        crumbs = [{'@type': 'ListItem', 'position': 1, 'name': name, 'item': url}, {'@type': 'ListItem', 'position': 2, 'name': 'Blog', 'item': url + 'blog/'}, {'@type': 'ListItem', 'position': 3, 'name': a['title'], 'item': u}]
        post = {'@type': ['BlogPosting', 'Article'], 'headline': a['title'][:110], 'description': a['description'], 'url': u, 'mainEntityOfPage': u, 'datePublished': a['date'], 'dateModified': a.get('updated') or a['date'],
                'author': author, 'publisher': org, 'image': url + 'og.png', 'inLanguage': 'en-US', 'wordCount': words, 'articleSection': 'Fantasy football', 'isPartOf': {'@type': 'Blog', 'name': f'{name} blog', 'url': url + 'blog/'}}
        if a.get('tags'): post['keywords'] = a['tags']
        ld = [post, {'@type': 'BreadcrumbList', 'itemListElement': crumbs}]
        if faqs: ld.append({'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': ans}} for q, ans in faqs]})
        cta_href = a.get('cta_href') or '/trade-analyzer/'
        cta = (a.get('cta_label') or 'Check your trade', cta_href.lstrip('/'), '')
        page(slug, 2, a['title'], a['description'], a['title'], r.inline(a['lede']) if a.get('lede') else E(a['description']), r.inline(a['answer']),
             by + body + more + note, ld, f'Blog · <time datetime="{a["date"]}">{fmt_date(a["date"])}</time>', a['title'][:48], cta=cta, cta_text=a.get('cta_text') or 'Price any deal, players and picks, 1QB or superflex.')
        made.append(slug)
    # index
    blog_ld = [{'@type': 'Blog', 'name': f'{name} blog', 'url': url + 'blog/', 'description': 'Dynasty and redraft fantasy football articles: trade targets, rookie risers and start/sit calls.', 'publisher': org,
                'blogPost': [{'@type': 'BlogPosting', 'headline': a['title'][:110], 'url': url + 'blog/' + a['slug'] + '/', 'datePublished': a['date'], 'author': author} for a in arts]},
               {'@type': 'BreadcrumbList', 'itemListElement': [{'@type': 'ListItem', 'position': 1, 'name': name, 'item': url}, {'@type': 'ListItem', 'position': 2, 'name': 'Blog', 'item': url + 'blog/'}]}]
    ib = '<p>Number-first reads on dynasty trade targets, rookie movers and weekly lineup calls. Every article shows the date of its numbers. Follow along with the <a href="feed.xml">RSS feed</a>.</p>' + cards(arts, '../') + \
         '<h2>Run your own numbers</h2><ul><li><a href="../trade-analyzer/">Dynasty trade analyzer</a></li><li><a href="../dynasty-buy-low-sell-high/">Dynasty buy-low and sell-high targets</a></li><li><a href="../rest-of-season-rankings/">Rest of season rankings</a></li><li><a href="../start-sit/">Start/sit tool</a></li></ul>'
    page('blog', 1, f'Fantasy Football Blog: Dynasty & Redraft | {name}', f'Dynasty and redraft fantasy football articles: trade targets, rookie risers and start/sit calls, with fresh numbers every day. From {AUTHOR}.', f'{name} blog', 'Trade targets, rookie risers and start/sit calls, with the numbers.',
         'Dynasty trade targets, rookie risers, and start/sit calls, updated with fresh values every day.', ib, blog_ld, f'Blog · Latest {fmt_date(arts[0]["date"], False)}', 'Blog')
    # RSS 2.0
    def rfc(d): return datetime.datetime.fromisoformat(d + 'T12:00:00+00:00').strftime('%a, %d %b %Y %H:%M:%S +0000')
    items = ''.join(f'<item><title>{E(a["title"])}</title><link>{url}blog/{a["slug"]}/</link><guid isPermaLink="true">{url}blog/{a["slug"]}/</guid><pubDate>{rfc(a["date"])}</pubDate><dc:creator>{AUTHOR}</dc:creator>'
                    + ''.join(f'<category>{E(t.strip())}</category>' for t in (a.get('tags') or '').split(',') if t.strip()) + f'<description>{E(a["description"])}</description></item>' for a in arts)
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
            f'<title>{name} blog</title><link>{url}blog/</link><description>Dynasty and redraft fantasy football articles: trade targets, rookie risers and start/sit calls.</description><language>en-us</language>'
            f'<atom:link href="{url}blog/feed.xml" rel="self" type="application/rss+xml"/><lastBuildDate>{rfc(arts[0].get("updated") or arts[0]["date"])}</lastBuildDate><generator>DynastyMath build_pages.py</generator>' + items + '</channel></rss>\n')
    (root / 'blog' / 'feed.xml').write_text(feed)
    # stale article folders
    keep = {a['slug'] for a in arts}
    for d in (root / 'blog').iterdir():
        if d.is_dir() and (d / '.generated').exists() and d.name not in keep: shutil.rmtree(d)
    (root / 'blog' / '.generated').write_text('')
    return arts
