#!/usr/bin/env python3
"""
Embodied AI News Aggregator - Live Scraping with Fallback
Fetches live data from blog sources, falls back to cached data on failure.
"""

from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, parse_qs, urlparse
import threading
import hashlib
import base64
import json
import re
import logging

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

REQUEST_TIMEOUT = 20
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

BLOG_SOURCES = [
    {"name": "Generalist AI", "url": "https://generalistai.com/assets/json/blog.json", "base_url": "https://generalistai.com", "color": "#6366f1"},
    {"name": "Physical Intelligence", "url": "https://www.pi.website/blog", "base_url": "https://www.pi.website", "color": "#8b5cf6"},
    {"name": "World Labs", "url": "https://www.worldlabs.ai/blog", "base_url": "https://www.worldlabs.ai", "color": "#ec4899"},
    {"name": "Figure", "url": "https://www.figure.ai/news", "base_url": "https://www.figure.ai", "color": "#14b8a6"},
    {"name": "Sunday Robotics", "url": "https://www.sunday.ai/journal", "base_url": "https://www.sunday.ai", "color": "#f59e0b"},
    {"name": "Skild AI", "url": "https://www.skild.ai/blogs", "base_url": "https://www.skild.ai", "color": "#ef4444"},
    {"name": "1X Technologies", "url": "https://www.1x.tech/discover", "base_url": "https://www.1x.tech", "color": "#000000"},
    {"name": "Agility Robotics", "url": "https://www.agilityrobotics.com/resources", "base_url": "https://www.agilityrobotics.com", "color": "#ff6b35"},
    {"name": "Sharpa", "url": "https://www.sharpa.com/blogs/research", "base_url": "https://www.sharpa.com", "color": "#00c853"},
    {"name": "Hexagon Robotics", "url": "https://robotics.hexagon.com/news/", "base_url": "https://robotics.hexagon.com", "color": "#0078d4"},
    {"name": "MANUS", "url": "https://www.manus-meta.com/blog", "base_url": "https://www.manus-meta.com", "color": "#1a1a1a"},
    {"name": "BeingBeyond", "url": "https://research.beingbeyond.com/", "base_url": "https://research.beingbeyond.com", "color": "#5b21b6"},
    {"name": "AGIBOT Finch", "url": "https://finch.agibot.com/research", "base_url": "https://finch.agibot.com", "color": "#d4a853"},
    {"name": "Genesis AI", "url": "https://www.genesis.ai/blog", "base_url": "https://www.genesis.ai", "color": "#2a9d8f"},
    {"name": "Ropedia", "url": "https://ropedia.com/", "base_url": "https://ropedia.com", "color": "#ccffa0"},
    {"name": "OneRobotics", "url": "https://www.onerobot.com/news", "base_url": "https://www.onerobot.com", "color": "#1e90ff"},
    {"name": "Galaxea", "url": "https://opengalaxea.github.io/G05/", "base_url": "https://opengalaxea.github.io/G05", "color": "#7c3aed"},
    {"name": "Spirit AI", "url": "https://www.spirit-ai.com/en/blog/", "base_url": "https://www.spirit-ai.com", "color": "#0ea5e9"},
    {"name": "Xiaomi Robotics", "url": "https://robotics.xiaomi.com/", "base_url": "https://robotics.xiaomi.com", "color": "#ff6900"},
    {"name": "ByteDance Seed", "url": "https://seed.bytedance.com/en/research", "base_url": "https://seed.bytedance.com", "color": "#325ab4"},
    {"name": "NVIDIA Blog", "url": "https://blogs.nvidia.com/blog/category/robotics/feed/", "base_url": "https://blogs.nvidia.com", "color": "#76b900"},
    {"name": "NVIDIA GEAR", "url": "https://research.nvidia.com/labs/gear/", "base_url": "https://research.nvidia.com", "color": "#1a7f37"},
    {"name": "X Square Robot", "url": "https://x2robot.com/en/news", "base_url": "https://x2robot.com", "color": "#0d9488"},
    {"name": "Sanctuary AI", "url": "https://www.sanctuary.ai/blog/rss.xml", "base_url": "https://www.sanctuary.ai", "color": "#c026d3"},
    {"name": "Boston Dynamics", "url": "https://bostondynamics.com/blog/", "base_url": "https://bostondynamics.com", "color": "#005288"},
    {"name": "NVIDIA Cosmos Lab", "url": "https://research.nvidia.com/labs/cosmos-lab/", "base_url": "https://research.nvidia.com", "color": "#4ade80"},
    {"name": "Agile Robots", "url": "https://www.agile-robots.com/en/news/", "base_url": "https://www.agile-robots.com", "color": "#e11d48"},
    {"name": "DexForce", "url": "https://www.dexforce.com/core.html", "base_url": "https://www.dexforce.com", "color": "#f97316"},
    {"name": "RL2 @ Georgia Tech", "url": "https://rl2.cc.gatech.edu/publications.json", "base_url": "https://rl2.cc.gatech.edu", "color": "#b3a369"},
    {"name": "Physical Superintelligence Lab", "url": "https://psi-lab.ai/research.html", "base_url": "https://psi-lab.ai", "color": "#a855f7"},
    {"name": "Dexmal", "url": "https://www.dexmal.com/research", "base_url": "https://www.dexmal.com", "color": "#00c8b4"},
    {"name": "XDOF", "url": "https://www.xdof.ai/blog", "base_url": "https://www.xdof.ai", "color": "#6c6db0"},
]

# Display companies alphabetically (A-Z) by name.
BLOG_SOURCES.sort(key=lambda s: s["name"].lower())

COMPANY_COLORS = {s["name"]: s["color"] for s in BLOG_SOURCES}

# =============================================================================
# CACHING
# =============================================================================

cache_lock = threading.RLock()
cached_posts = []
cache_timestamp = None
CACHE_DURATION = 300  # 5 minutes

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_placeholder_svg(title, company):
    """Generate an artistic placeholder SVG image based on title hash."""
    hash_obj = hashlib.md5(title.encode())
    hash_int = int(hash_obj.hexdigest()[:8], 16)

    h1 = (hash_int % 360)
    hue2 = (h1 + 30) % 360

    def hsl_to_hex(h, s=70, l=50):
        h = h / 360
        if s == 0:
            return f'#{l:02x}{l:02x}{l:02x}'
        q = l * (1 + s/100) / 100 if l < 50 else l + s - l * s / 100
        p = 2 * l - q

        def hue_to_rgb(p, q, t):
            t = t % 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p

        r = int(hue_to_rgb(p, q, h + 1/3) * 255)
        g = int(hue_to_rgb(p, q, h) * 255)
        b = int(hue_to_rgb(p, q, h - 1/3) * 255)
        return f'#{r:02x}{g:02x}{b:02x}'

    color1 = hsl_to_hex(h1, 60, 45)
    color2 = hsl_to_hex(hue2, 70, 35)
    title_short = title[:35] + "..." if len(title) > 35 else title

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:{color1};stop-opacity:1" />
          <stop offset="100%" style="stop-color:{color2};stop-opacity:1" />
        </linearGradient>
      </defs>
      <rect width="600" height="400" fill="url(#grad)"/>
      <circle cx="{100 + (hash_int % 200)}" cy="{80 + (hash_int % 100)}" r="{50 + (hash_int % 100)}" fill="{color2}" opacity="0.3"/>
      <circle cx="{300 + (hash_int % 150)}" cy="{200 + (hash_int % 80)}" r="{80 + (hash_int % 60)}" fill="{color1}" opacity="0.2"/>
      <text x="300" y="220" font-family="Arial, sans-serif" font-size="22" fill="white" text-anchor="middle">{title_short}</text>
      <text x="300" y="255" font-family="Arial, sans-serif" font-size="14" fill="white" text-anchor="middle" opacity="0.7">{company}</text>
    </svg>'''

    svg_b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{svg_b64}"


def has_real_image(post):
    """Check if post has a real image (not a placeholder SVG)."""
    image = post.get("image", "")
    return image and not image.startswith("data:image/svg")


SUMMARY_MAX_LENGTH = 220


def compress_summary(summary, max_length=SUMMARY_MAX_LENGTH):
    """Truncate an over-long summary at a word boundary and add an ellipsis."""
    if not summary or len(summary) <= max_length:
        return summary
    truncated = summary[:max_length].rstrip()
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.6:
        truncated = truncated[:last_space].rstrip()
    return truncated.rstrip('.,;:!?-\u2013\u2014') + '\u2026'


def safe_parse_date(date_str, formats):
    """Try multiple date formats, return datetime or None."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def make_request(url, timeout=None):
    """Make an HTTP request with standard headers and error handling."""
    timeout = timeout or REQUEST_TIMEOUT
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


# =============================================================================
# PER-SITE SCRAPERS
# =============================================================================

def scrape_generalist_ai(source):
    """
    Generalist AI is a client-rendered SPA, but exposes a JSON API
    at /assets/json/blog.json with all blog post metadata.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    blog_data = response.json()

    posts = []
    for item in blog_data:
        title = item.get("title", "").strip()
        slug = item.get("slug", "")
        date_str = item.get("date", "")
        description = item.get("description", "").strip()
        thumbnail = item.get("thumbnail")

        if not title or not slug:
            continue

        date = safe_parse_date(date_str, ["%Y-%m-%d"])
        url = f"{base_url}/blog/{slug}"
        image = f"{base_url}{thumbnail}" if thumbnail and thumbnail.startswith("/") else thumbnail

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": description,
            "image": image,
            "company": company,
        })

    logger.info(f"[Generalist AI] Scraped {len(posts)} posts from JSON API")
    return posts


def scrape_physical_intelligence(source):
    """
    Physical Intelligence uses Next.js App Router with SSR.
    Blog entries are <a> tags inside a timeline div with border-l class.
    Titles in div[title] with font-semibold, dates in div.text-muted-foreground.shrink-0.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    # Find all article links - they are <a> tags with href starting with /blog/ or /research/
    for entry in soup.find_all('a', href=re.compile(r'^/(blog|research)/')):
        href = entry.get('href', '')

        # Title: div with title attribute and font-semibold class
        title_el = entry.find('div', attrs={'title': True},
                              class_=lambda c: c and 'font-semibold' in c)
        if not title_el:
            continue
        title = title_el['title'].strip()
        if len(title) < 3:
            continue

        # Date: div with text-muted-foreground and shrink-0
        date_el = entry.find('div', class_=lambda c: c and 'text-muted-foreground' in c and 'shrink-0' in c)
        date_str = date_el.get_text(strip=True) if date_el else None
        date = safe_parse_date(date_str, ['%B %d, %Y']) if date_str else None

        # Summary: <p> with no-underline class, or last div.text-muted-foreground
        desc_el = entry.find('p', class_=lambda c: c and 'no-underline' in c)
        if not desc_el:
            # For research entries - look for div.text-muted-foreground that is NOT the date
            all_muted = entry.find_all('div', class_=lambda c: c and 'text-muted-foreground' in c)
            for el in all_muted:
                if 'shrink-0' not in (el.get('class') or []):
                    desc_el = el
                    break
        summary = desc_el.get_text(strip=True) if desc_el else ""

        url = f"{base_url}{href}"
        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": None,  # PI blog has no images on listing page
            "company": company,
        })

    logger.info(f"[Physical Intelligence] Scraped {len(posts)} posts")
    return posts


def scrape_world_labs(source):
    """
    World Labs uses Next.js App Router with SSR.
    Article cards are <a> tags with href containing /blog/.
    Titles in <h2>, dates in <p> with text-grey-100 class, summaries in sibling <p>.
    Images use Next.js image optimization.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '')

        # Only process blog article cards (internal or external)
        h2 = a_tag.find('h2')
        if not h2:
            continue

        title = h2.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        # Build full URL
        if href.startswith('/'):
            full_url = f"{base_url}{href}"
        else:
            full_url = href

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Date: first <p> with text-grey-100 and flex gap-2 classes
        date_p = a_tag.find('p', class_=lambda c: c and 'text-grey-100' in c)
        date_str = None
        if date_p:
            # Date is first text node (before any <span>)
            for content in date_p.contents:
                if isinstance(content, str) and content.strip():
                    date_str = content.strip()
                    break
        date = safe_parse_date(date_str, ['%B %d, %Y']) if date_str else None

        # Summary: <p> with text-grey-100 and text-sm (sibling of title h2)
        summary_p = a_tag.find('p', class_=lambda c: c and 'text-grey-100' in c and 'text-sm' in c)
        # Avoid picking up the date <p> as summary
        if summary_p and summary_p == date_p:
            summary_p = None
        summary = summary_p.get_text(strip=True) if summary_p else ""

        # Image: img with data-nimg="fill", extract raw path from Next.js optimized URL
        img = a_tag.find('img', attrs={'data-nimg': True})
        image_url = None
        if img:
            src = img.get('src', '')
            if '/_next/image' in src:
                parsed = urlparse(src)
                qs = parse_qs(parsed.query)
                if 'url' in qs:
                    raw_path = unquote(qs['url'][0])
                    image_url = f"{base_url}{raw_path}" if raw_path.startswith('/') else raw_path
            elif src.startswith('http'):
                image_url = src

        posts.append({
            "title": title,
            "url": full_url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[World Labs] Scraped {len(posts)} posts")
    return posts


def scrape_figure(source):
    """
    Figure uses Next.js SSG with Contentful CMS.
    Best approach: parse __NEXT_DATA__ JSON blob which has all article metadata.
    Falls back to HTML parsing if JSON not found.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []

    # Strategy 1: Parse __NEXT_DATA__ JSON (most reliable)
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    if next_data_script:
        try:
            next_data = json.loads(next_data_script.string)
            sections = next_data.get('props', {}).get('pageProps', {}).get('page', {}).get('sectionsCollection', {}).get('items', [])

            for section in sections:
                # Look for ArticleList section
                article_collections = []
                if 'articlePageCollection' in section:
                    article_collections.append(section['articlePageCollection'].get('items', []))
                if 'featuredArticleCollection' in section:
                    article_collections.append(section['featuredArticleCollection'].get('items', []))

                seen_slugs = set()
                for collection in article_collections:
                    for article in collection:
                        slug = article.get('slug', '')
                        if not slug or slug in seen_slugs:
                            continue
                        seen_slugs.add(slug)

                        title = article.get('articleTitle', '').strip()
                        pub_date = article.get('publicationDate', '')
                        external_url = article.get('externalArticleUrl')

                        if not title:
                            continue

                        url = external_url if external_url else f"{base_url}/news/{slug}"
                        date = safe_parse_date(pub_date, ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'])

                        # Image: prefer thumbnail, then thumbnailVideo poster
                        image = None
                        thumbnail = article.get('thumbnail')
                        if thumbnail and isinstance(thumbnail, dict):
                            image = thumbnail.get('src') or thumbnail.get('url')
                        thumbnail_video = article.get('thumbnailVideo')
                        if not image and thumbnail_video and isinstance(thumbnail_video, dict):
                            # Video thumbnail - no static image available
                            pass

                        posts.append({
                            "title": title,
                            "url": url,
                            "date": date or datetime.min,
                            "summary": "",  # No summaries on listing page
                            "image": image,
                            "company": company,
                        })

            logger.info(f"[Figure] Scraped {len(posts)} posts from __NEXT_DATA__")
            return posts
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"[Figure] Failed to parse __NEXT_DATA__: {e}, falling back to HTML")

    # Strategy 2: HTML parsing fallback
    for a_tag in soup.find_all('a', class_='article-list-item'):
        href = a_tag.get('href', '')
        if not href:
            continue

        title_el = a_tag.find('h1', class_='article-list-item__heading')
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or len(title) < 3:
            continue

        time_el = a_tag.find('time', class_='article-list-item__publication-date')
        date = None
        if time_el:
            dt_attr = time_el.get('dateTime', '')
            date = safe_parse_date(dt_attr, ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'])
            if not date:
                date = safe_parse_date(time_el.get_text(strip=True), ['%B %d, %Y'])

        url = f"{base_url}{href}" if href.startswith('/') else href

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",
            "image": None,
            "company": company,
        })

    logger.info(f"[Figure] Scraped {len(posts)} posts from HTML")
    return posts


def scrape_sunday_robotics(source):
    """
    Sunday Robotics uses Next.js App Router with Sanity CMS.
    Article cards are <a> tags with href starting with /journal/.
    Content is SSR with Tailwind utility classes (no semantic class names).
    Entries with headings are real article cards; links with only "Read article" are nav links.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for a_tag in soup.find_all('a', href=re.compile(r'^/journal/')):
        href = a_tag.get('href', '')
        if not href or href == '/journal' or href == '/journal/':
            continue

        url = f"{base_url}{href}"
        if url in seen_urls:
            continue

        # Title: require a heading element (real article cards have <h1>-<h4>)
        heading = a_tag.find(['h1', 'h2', 'h3', 'h4'])
        if not heading:
            # Skip entries without headings (nav links with just "Read article")
            continue

        title = heading.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        seen_urls.add(url)

        # Date: look for date-like text in the link's contents
        date = None
        for text in a_tag.stripped_strings:
            text = text.strip()
            parsed = safe_parse_date(text, ['%B %d, %Y', '%b %d, %Y'])
            if parsed:
                date = parsed
                break

        # Image: img inside the link
        img = a_tag.find('img')
        image_url = _extract_nextjs_image(img, base_url) if img else None

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Sunday Robotics] Scraped {len(posts)} posts")
    return posts


def scrape_skild_ai(source):
    """
    Skild AI uses Next.js App Router with SSR.
    Featured post: a.featured-post with h2 title, p.featured-meta, p.featured-excerpt.
    Regular posts: a.regular-post with h3 title, p.regular-meta, p.regular-excerpt.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    # Featured post
    featured = soup.find('a', class_='featured-post')
    if featured:
        href = featured.get('href', '')
        title_el = featured.find('h2')
        meta_el = featured.find('p', class_='featured-meta')
        excerpt_el = featured.find('p', class_='featured-excerpt')

        if title_el and href:
            title = title_el.get_text(strip=True)
            url = f"{base_url}{href}" if href.startswith('/') else href
            seen_urls.add(url)

            # Parse date from meta: "Author · Mon DD, YYYY"
            date = None
            if meta_el:
                meta_text = meta_el.get_text(strip=True)
                date_match = re.search(r'(\w{3}\s+\d{1,2},\s*\d{4})', meta_text)
                if date_match:
                    date = safe_parse_date(date_match.group(1), ['%b %d, %Y', '%B %d, %Y'])

            summary = excerpt_el.get_text(strip=True) if excerpt_el else ""

            # Image
            img = featured.find('img', class_='featured-image')
            image_url = _extract_nextjs_image(img, base_url) if img else None

            posts.append({
                "title": title,
                "url": url,
                "date": date or datetime.min,
                "summary": summary,
                "image": image_url,
                "company": company,
            })

    # Regular posts
    for post_el in soup.find_all('a', class_='regular-post'):
        href = post_el.get('href', '')
        if not href:
            continue
        url = f"{base_url}{href}" if href.startswith('/') else href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title_el = post_el.find('h3')
        meta_el = post_el.find('p', class_='regular-meta')
        excerpt_el = post_el.find('p', class_='regular-excerpt')

        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        date = None
        if meta_el:
            meta_text = meta_el.get_text(strip=True)
            date_match = re.search(r'(\w{3}\s+\d{1,2},\s*\d{4})', meta_text)
            if date_match:
                date = safe_parse_date(date_match.group(1), ['%b %d, %Y', '%B %d, %Y'])

        summary = excerpt_el.get_text(strip=True) if excerpt_el else ""

        img = post_el.find('img', class_='regular-image')
        image_url = _extract_nextjs_image(img, base_url) if img else None

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Skild AI] Scraped {len(posts)} posts")
    return posts


def _extract_nextjs_image(img_tag, base_url):
    """Extract the actual image URL from a Next.js optimized <img> tag."""
    if not img_tag:
        return None
    src = img_tag.get('src', '')
    if '/_next/image' in src:
        parsed = urlparse(src)
        qs = parse_qs(parsed.query)
        if 'url' in qs:
            raw = unquote(qs['url'][0])
            if raw.startswith('/'):
                return f"{base_url}{raw}"
            return raw
    elif src.startswith('http'):
        return src
    elif src.startswith('/'):
        return f"{base_url}{src}"
    return None



def scrape_1x_technologies(source):
    """
    1X Technologies uses Next.js Pages Router with Sanity CMS.
    Has __NEXT_DATA__ with full article data. Falls back to HTML parsing.
    Article links: a[href^="/discover/"], titles in h4, dates in span format "MON DD 'YY".
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    # Find all article links
    for a_tag in soup.find_all('a', href=re.compile(r'^/discover/')):
        href = a_tag.get('href', '')
        # Skip category links
        if '/discover/category/' in href:
            continue

        article = a_tag.find('article')
        if not article:
            continue

        url = f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Title: h4 inside article
        h4 = article.find('h4')
        title = h4.get_text(strip=True) if h4 else ""
        if not title or len(title) < 3:
            continue

        # Description: first <p> after h4
        desc_p = article.find('p')
        summary = desc_p.get_text(strip=True) if desc_p else ""

        # Date: span in the metadata div, format "MON DD 'YY"
        date = None
        meta_spans = article.find_all('span')
        for span in meta_spans:
            text = span.get_text(strip=True)
            # Match pattern like "MAR 17 '26" or "MAR 18 '25"
            date_match = re.match(r'^([A-Z]{3})\s+(\d{1,2})\s+\'(\d{2})$', text)
            if date_match:
                month_str, day, year_short = date_match.groups()
                try:
                    date = datetime.strptime(f"{month_str} {day} 20{year_short}", '%b %d %Y')
                except ValueError:
                    pass
                break

        # Image
        img = article.find('img')
        image_url = _extract_nextjs_image(img, base_url) if img else None
        # 1X uses Sanity CDN images directly in src
        if not image_url and img:
            src = img.get('src', '')
            if 'cdn.sanity.io' in src:
                # Extract clean URL from Next.js image proxy
                if '/_next/image' in src:
                    parsed = urlparse(src)
                    qs = parse_qs(parsed.query)
                    if 'url' in qs:
                        image_url = unquote(qs['url'][0])
                else:
                    image_url = src

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[1X Technologies] Scraped {len(posts)} posts")
    return posts


def scrape_agility_robotics(source):
    """
    Agility Robotics uses Webflow with CMS collections.
    Blog tiles: a.blog-tile inside div.w-dyn-item.
    Titles in h3.blog-tease-title, dates in div.blog-tease-meta,
    images in img.blog-title-image.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for tile in soup.find_all('a', class_='blog-tile'):
        href = tile.get('href', '')
        if not href:
            continue

        # Build full URL
        if href.startswith('/'):
            url = f"{base_url}{href}"
        else:
            url = href

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Title
        title_el = tile.find('h3', class_='blog-tease-title')
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        # Date and type from meta elements (can be <div> or <p> with blog-tease-meta class)
        meta_els = tile.find_all(['div', 'p'], class_='blog-tease-meta')
        date = None
        post_type = ""
        for meta in meta_els:
            text = meta.get_text(strip=True)
            # Try parsing as date
            parsed_date = safe_parse_date(text, ['%B %d, %Y', '%b %d, %Y'])
            if parsed_date:
                date = parsed_date
            else:
                post_type = text  # e.g. "Blog Post", "eBook"

        # If no date found in meta, search for date patterns in all text
        if not date:
            all_text = tile.get_text()
            date_match = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})', all_text)
            if date_match:
                date = safe_parse_date(date_match.group(1), ['%B %d, %Y'])

        # Only include blog posts and press releases, skip ebooks/videos
        if post_type and post_type.lower() in ['ebook', 'video']:
            continue

        # Image
        img = tile.find('img', class_='blog-title-image')
        image_url = None
        if img:
            src = img.get('src', '')
            if src.startswith('http'):
                image_url = src
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",  # Agility listing page has no excerpts
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Agility Robotics] Scraped {len(posts)} posts")
    return posts


def scrape_sharpa(source):
    """
    Sharpa uses a Shopify-based blog with custom web components.
    Blog posts are in <article class="sa-research-article__card"> elements.
    Titles in a.sa-research-article__card-title, dates in div.sa-research-article__card-date.
    Excerpt available via data-excerpt attribute on the article element.
    No featured images on the listing page.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for article in soup.find_all('article', class_='sa-research-article__card'):
        # Title and URL from the title link
        title_link = article.find('a', class_='sa-research-article__card-title')
        if not title_link:
            # Fallback to data-title attribute
            title = article.get('data-title', '').strip()
            if not title:
                continue
        else:
            title = title_link.get_text(strip=True)

        # URL
        href = title_link.get('href', '') if title_link else ''
        if not href:
            continue
        if href.startswith('/'):
            url = f"{base_url}{href}"
        else:
            url = href

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date from div.sa-research-article__card-date (format: "09 Mar 2026")
        date = None
        date_el = article.find('div', class_='sa-research-article__card-date')
        if date_el:
            date_text = date_el.get_text(strip=True)
            date = safe_parse_date(date_text, ['%d %b %Y'])

        # Summary from data-excerpt attribute
        summary = article.get('data-excerpt', '').strip()

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": None,  # No featured images on listing page
            "company": company,
        })

    logger.info(f"[Sharpa] Scraped {len(posts)} posts")
    return posts


def scrape_hexagon_robotics(source):
    """
    Hexagon Robotics uses WordPress + Elementor with a loop grid.
    Each post card is an elementor loop-item div containing:
    - Date in h6 heading (format: "April 22, 2026")
    - Title in h3 heading with a link
    - Image in img tag inside elementor-widget-image
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    # Each post is inside an e-loop-item div
    for item in soup.find_all('div', class_='e-loop-item'):
        # Title and URL from h3 > a
        h3 = item.find('h3', class_='elementor-heading-title')
        if not h3:
            continue
        link = h3.find('a')
        if not link:
            continue

        title = link.get_text(strip=True)
        if not title:
            continue

        href = link.get('href', '')
        if not href:
            continue
        url = href if href.startswith('http') else f"{base_url}{href}"

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date from h6 heading (format: "April 22, 2026", "March 16, 2026")
        date = None
        h6 = item.find('h6', class_='elementor-heading-title')
        if h6:
            date_text = h6.get_text(strip=True)
            date = safe_parse_date(date_text, ['%B %d, %Y', '%b %d, %Y'])

        # Image
        image_url = None
        img_widget = item.find('div', class_='elementor-widget-image')
        if img_widget:
            img = img_widget.find('img')
            if img:
                src = img.get('src', '')
                if src.startswith('http'):
                    image_url = src
                elif src.startswith('/'):
                    image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",  # Hexagon listing page has no excerpts
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Hexagon Robotics] Scraped {len(posts)} posts")
    return posts


def scrape_manus(source):
    """
    MANUS (manus-meta.com) uses Webflow CMS.
    Blog posts are in link blocks (a tags) with image, title (h2), date text, and category.
    Each post link follows pattern /blog/<slug>.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    # Find all links that point to /blog/ articles
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')

        # Only process links to blog posts (not navigation/footer links)
        if not href.startswith('/blog/') or href == '/blog' or href == '/blog/':
            continue

        # Build full URL
        url = f"{base_url}{href}"

        if url in seen_urls:
            continue

        # Must contain a heading (h2) to be a blog card, not a nav link
        h2 = link.find('h2')
        if not h2:
            continue

        title = h2.get_text(strip=True)
        if not title:
            continue

        seen_urls.add(url)

        # Date - look for text that matches date patterns within the link block
        date = None
        # The date text appears as a separate element inside the card
        for el in link.find_all(['div', 'p', 'span']):
            text = el.get_text(strip=True)
            # Try common date formats: "March 26, 2026"
            parsed = safe_parse_date(text, ['%B %d, %Y', '%b %d, %Y'])
            if parsed:
                date = parsed
                break

        # Image
        image_url = None
        img = link.find('img')
        if img:
            src = img.get('src', '')
            if src.startswith('http'):
                image_url = src
            elif src.startswith('//'):
                image_url = f"https:{src}"
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",
            "image": image_url,
            "company": company,
        })

    logger.info(f"[MANUS] Scraped {len(posts)} posts")
    return posts


def scrape_beingbeyond(source):
    """
    BeingBeyond uses Next.js with React Server Components (RSC).
    The page is client-rendered but all research paper data is embedded
    in the RSC payload within <script> tags as self.__next_f.push() calls.
    Each item has: slug, title, tldr, thumbnail, dateLabel, venue, highlight.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    html = response.text

    posts = []

    # Extract the RSC payload containing the items array
    # The data is in self.__next_f.push([1,"..."]) script blocks
    # Look for the JSON array of items with slug, title, tldr, etc.
    rsc_chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.+?)"\]\)', html)

    items = []
    for chunk in rsc_chunks:
        # Unescape the JSON string (it's double-escaped)
        try:
            unescaped = chunk.encode().decode('unicode_escape')
        except (UnicodeDecodeError, ValueError):
            continue

        # Look for the items array pattern: "items":[{...}]
        items_match = re.search(r'"items":\[(\{.*\})\]', unescaped)
        if items_match:
            try:
                items_json = '[' + items_match.group(1) + ']'
                items = json.loads(items_json)
                break
            except json.JSONDecodeError:
                continue

    for item in items:
        slug = item.get("slug", "")
        title = item.get("title", "").strip()
        tldr = item.get("tldr", "").strip()
        thumbnail = item.get("thumbnail", "")
        date_label = item.get("dateLabel", "")
        venue = item.get("venue")

        if not title or not slug:
            continue

        url = f"{base_url}/{slug}"

        # Parse date from dateLabel (format: "Apr 20, 2026")
        date = safe_parse_date(date_label, ['%b %d, %Y'])

        # Build image URL
        image_url = None
        if thumbnail:
            if thumbnail.startswith('http'):
                image_url = thumbnail
            elif thumbnail.startswith('/'):
                image_url = f"{base_url}{thumbnail}"

        # Append venue info to summary if available
        summary = tldr
        if venue and venue != "$undefined":
            summary = f"[{venue}] {tldr}" if tldr else venue

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[BeingBeyond] Scraped {len(posts)} posts from RSC payload")
    return posts


def scrape_agibot_finch(source):
    """
    AGIBOT Finch uses Next.js SSG.
    Best approach: parse __NEXT_DATA__ JSON blob which contains a researchCards
    array with id, title, description, subDesc, date, image, largeImage, href.
    Falls back to HTML parsing if JSON not found.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []

    # Strategy 1: Parse __NEXT_DATA__ JSON (most reliable)
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    if next_data_script:
        try:
            next_data = json.loads(next_data_script.string)
            cards = next_data.get('props', {}).get('pageProps', {}).get('researchCards', [])

            for card in cards:
                title = card.get('title', '').strip()
                if not title:
                    continue

                href = card.get('href', '')
                url = f"{base_url}{href}" if href.startswith('/') else href

                # Parse date (format: "Apr 30, 2026", "Jan 6, 2026")
                date_str = card.get('date', '')
                date = safe_parse_date(date_str, ['%b %d, %Y', '%B %d, %Y'])

                # Use description as primary summary, subDesc as secondary
                description = card.get('description', '').strip()
                sub_desc = card.get('subDesc', '').strip()
                summary = description if description else sub_desc

                # Image: prefer largeImage, fall back to image
                image_path = card.get('largeImage') or card.get('image')
                image_url = None
                if image_path:
                    if image_path.startswith('http'):
                        image_url = image_path
                    elif image_path.startswith('/'):
                        image_url = f"{base_url}{image_path}"

                posts.append({
                    "title": title,
                    "url": url,
                    "date": date or datetime.min,
                    "summary": summary,
                    "image": image_url,
                    "company": company,
                })

            logger.info(f"[AGIBOT Finch] Scraped {len(posts)} posts from __NEXT_DATA__")
            return posts
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"[AGIBOT Finch] Failed to parse __NEXT_DATA__: {e}, falling back to HTML")

    # Strategy 2: HTML parsing fallback
    # Research cards are <a> tags with href starting with /research/
    seen_urls = set()
    for a_tag in soup.find_all('a', href=re.compile(r'^/research/.+')):
        href = a_tag.get('href', '')
        if not href or href == '/research':
            continue

        h3 = a_tag.find('h3')
        if not h3:
            continue

        title = h3.get_text(strip=True)
        if not title or len(title) < 2:
            continue

        url = f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date: span with text-[#86909C] class
        date = None
        date_span = a_tag.find('span', class_=lambda c: c and '86909C' in c)
        if date_span:
            date = safe_parse_date(date_span.get_text(strip=True), ['%b %d, %Y', '%B %d, %Y'])

        # Summary: first <p> with text-black class
        summary = ""
        desc_p = a_tag.find('p', class_=lambda c: c and 'text-black' in c)
        if desc_p:
            summary = desc_p.get_text(strip=True)

        # Image
        img = a_tag.find('img', attrs={'data-nimg': True})
        image_url = _extract_nextjs_image(img, base_url) if img else None

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[AGIBOT Finch] Scraped {len(posts)} posts from HTML")
    return posts


def scrape_genesis_ai(source):
    """
    Genesis AI uses SvelteKit with SSR (DatoCMS backend).
    Blog articles are <a> tags with href starting with /blog/.
    Titles in <h2 class="text-article-title">, dates and categories
    in <p class="text-eyebrow"> elements. Thumbnails are Mux video
    poster images in <img class="video-thumbnail">.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for a_tag in soup.find_all('a', href=re.compile(r'^/blog/.+')):
        href = a_tag.get('href', '')
        if not href or href == '/blog' or href == '/blog/':
            continue

        # Must contain a heading (h2) to be an article card
        h2 = a_tag.find('h2', class_='text-article-title')
        if not h2:
            continue

        title = h2.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        url = f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date and category from <p class="text-eyebrow"> elements
        date = None
        eyebrows = a_tag.find_all('p', class_='text-eyebrow')
        for eyebrow in eyebrows:
            classes = eyebrow.get('class', [])
            # Skip the category tag (has color-faded class)
            if 'color-faded' in classes:
                continue
            text = eyebrow.get_text(strip=True)
            # Skip post count text like "1 posts"
            if 'post' in text.lower():
                continue
            parsed = safe_parse_date(text, ['%B %d, %Y', '%b %d, %Y'])
            if parsed:
                date = parsed
                break

        # Image: Mux video thumbnail or regular img
        image_url = None
        img = a_tag.find('img', class_='video-thumbnail')
        if not img:
            img = a_tag.find('img')
        if img:
            src = img.get('src', '')
            if src.startswith('http'):
                image_url = src
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Genesis AI] Scraped {len(posts)} posts")
    return posts


def scrape_ropedia(source):
    """
    Ropedia (ropedia.com) is a static HTML site. There is no /blog index page;
    blog posts are listed on the homepage under the "News" section.
    Each card is an <a class="card card--news"> with:
    - href to /blog/<slug>.html
    - image in .card__icon img
    - meta text in .card__meta (format: "16 Dec 2025 · Product Release")
    - title in .card__title
    - body in .card__body
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for card in soup.find_all('a', class_=lambda c: c and 'card--news' in c):
        href = card.get('href', '')
        if not href:
            continue

        url = href if href.startswith('http') else f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title_el = card.find(class_='card__title')
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        # Date from .card__meta - format: "16 Dec 2025 · Product Release"
        date = None
        meta_el = card.find(class_='card__meta')
        if meta_el:
            meta_text = meta_el.get_text(strip=True)
            # Take the part before " · "
            date_part = meta_text.split('·')[0].strip()
            date = safe_parse_date(date_part, ['%d %b %Y', '%d %B %Y'])

        body_el = card.find(class_='card__body')
        summary = body_el.get_text(strip=True) if body_el else ""

        # Image
        image_url = None
        img = card.find('img')
        if img:
            src = img.get('src', '')
            if src.startswith('http'):
                image_url = src
            elif src.startswith('//'):
                image_url = f"https:{src}"
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Ropedia] Scraped {len(posts)} posts")
    return posts


def scrape_onerobot(source):
    """
    OneRobotics (onerobot.com) is a server-rendered PHP site (layui-based).
    News list at /news with pagination via ?page=N. Each article is a <li>
    inside div.news-list > ul:
    - Link: <a href="/news/<id>">
    - Date: <div class="t1"> (format "YYYY-MM-DD")
    - Title: <div class="t2 font24">
    - Image: <img src="/uploads/..."> inside div.public-img (or div.img)
    No summaries on the listing page or detail page meta.
    Paginates through all pages (small site, ~3 pages).
    """
    company = source["name"]
    base_url = source["base_url"]

    posts = []
    seen_urls = set()
    MAX_PAGES = 10

    for page in range(1, MAX_PAGES + 1):
        url = source["url"] if page == 1 else f"{source['url']}?page={page}"
        try:
            response = make_request(url)
        except requests.exceptions.HTTPError:
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        news_list = soup.find('div', class_='news-list')
        if not news_list:
            break

        items = news_list.find_all('li')
        if not items:
            break

        page_added = 0
        for li in items:
            link = li.find('a', href=re.compile(r'^/news/\d+'))
            if not link:
                continue
            href = link.get('href', '')
            post_url = f"{base_url}{href}"
            if post_url in seen_urls:
                continue

            title_el = link.find('div', class_='t2')
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 3:
                continue

            date_el = link.find('div', class_='t1')
            date_str = date_el.get_text(strip=True) if date_el else None
            date = safe_parse_date(date_str, ['%Y-%m-%d']) if date_str else None

            image_url = None
            img_container = link.find('div', class_='public-img') or li.find('div', class_='img')
            if img_container:
                img = img_container.find('img')
                if img:
                    src = img.get('src', '')
                    if src.startswith('http'):
                        image_url = src
                    elif src.startswith('//'):
                        image_url = f"https:{src}"
                    elif src.startswith('/'):
                        image_url = f"{base_url}{src}"

            seen_urls.add(post_url)
            page_added += 1
            posts.append({
                "title": title,
                "url": post_url,
                "date": date or datetime.min,
                "summary": "",
                "image": image_url,
                "company": company,
            })

        next_link = soup.find('a', class_='next')
        has_next = bool(next_link and next_link.get('href') and 'page=' in next_link.get('href', ''))
        if not has_next or page_added == 0:
            break

    logger.info(f"[OneRobotics] Scraped {len(posts)} posts")
    return posts


def scrape_galaxea(source):
    """
    Galaxea (opengalaxea.github.io/G05) is a client-rendered React/Vite SPA
    hosted on GitHub Pages. The index.html is an empty shell; all content lives
    in a hashed JS bundle (e.g. /assets/index-<hash>.js).

    Strategy: fetch index.html, find the bundle <script src>, fetch the bundle,
    then regex-extract the embedded title, date, and abstract strings.
    The page is a single project page / technical report (one post).
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the main JS bundle referenced by the SPA shell
    bundle_url = None
    for script in soup.find_all('script', src=True):
        src = script.get('src', '')
        if '/assets/' in src and src.endswith('.js'):
            if src.startswith('http'):
                bundle_url = src
            elif src.startswith('./'):
                bundle_url = f"{base_url}/{src[2:]}"
            elif src.startswith('/'):
                bundle_url = f"https://opengalaxea.github.io{src}"
            else:
                bundle_url = f"{base_url}/{src}"
            break

    if not bundle_url:
        logger.warning(f"[Galaxea] No JS bundle found, using fallback")
        return []

    bundle = make_request(bundle_url).text

    # Title is split across JSX nodes in the bundle: the prefix
    # ("Introducing G0.5: ") sits before a <br>/<span>, and the remainder is
    # the next React `children:"..."` string. Reassemble both halves.
    title = None
    prefix_match = re.search(r'(Introducing G0\.5:\s*)"', bundle)
    if prefix_match:
        prefix = prefix_match.group(1).strip()
        rest_match = re.search(r'children:"([^"]+)"', bundle[prefix_match.end():])
        suffix = rest_match.group(1).strip() if rest_match else ""
        title = f"{prefix} {suffix}".strip() if suffix else prefix
    if not title:
        report_match = re.search(r'Galaxea G0\.5 Technical Report', bundle)
        if report_match:
            title = report_match.group(0).strip()
    if not title:
        logger.warning(f"[Galaxea] Could not extract title, using fallback")
        return []

    # Date: look for a "Month DD, YYYY" string in the bundle
    date = None
    date_match = re.search(
        r'((?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},\s*\d{4})',
        bundle)
    if date_match:
        date = safe_parse_date(date_match.group(1), ['%B %d, %Y'])

    # Summary: the abstract sentence describing the model
    summary = ""
    summary_match = re.search(
        r'A pretrained autoregressive Vision-Language-Action model[^"\'`]+',
        bundle)
    if summary_match:
        summary = summary_match.group(0).strip()

    posts = [{
        "title": title,
        "url": source["url"],
        "date": date or datetime.min,
        "summary": summary,
        "image": None,  # No static thumbnail exposed on the project page
        "company": company,
    }]

    logger.info(f"[Galaxea] Scraped {len(posts)} posts from JS bundle")
    return posts


def scrape_spirit_ai(source):
    """
    Spirit AI (千寻智能, spirit-ai.com) is a client-rendered Vite SPA. The blog
    shell HTML is empty (<div id="app">); posts are baked into a lazily-loaded
    JS chunk (assets/blogs-<hash>.js) as a `Gi=[{...}]` array of English posts.

    Strategy: index.html -> main index-<hash>.js -> blogs-<hash>.js chunk, then
    regex-extract each post object's id, title, summary, cover and date fields.
    Each post object starts with `{id:"..."`; English URLs are /en/blog/<id>.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])

    main_match = re.search(r'src="(/blog/assets/index-[^"]+\.js)"', response.text)
    if not main_match:
        logger.warning(f"[Spirit AI] No main JS bundle found, using fallback")
        return []
    main_js = make_request(f"{base_url}{main_match.group(1)}").text

    chunk_match = re.search(r'(assets/blogs-[A-Za-z0-9_-]+\.js)', main_js)
    if not chunk_match:
        logger.warning(f"[Spirit AI] No blogs chunk found, using fallback")
        return []
    chunk = make_request(f"{base_url}/blog/{chunk_match.group(1)}").text

    array_match = re.search(r'Gi=\[(.*?)\];', chunk, re.DOTALL)
    if not array_match:
        logger.warning(f"[Spirit AI] No English post array found, using fallback")
        return []
    array_body = array_match.group(1)

    posts = []
    seen_ids = set()
    for block_match in re.finditer(r'\{id:"', array_body):
        block = array_body[block_match.start():]

        id_m = re.search(r'id:"([^"]+)"', block)
        title_m = re.search(r'title:"([^"]+)"', block)
        if not id_m or not title_m:
            continue
        post_id = id_m.group(1)
        if post_id in seen_ids:
            continue
        seen_ids.add(post_id)

        summary_m = re.search(r'summary:`([^`]*)`', block)
        summary = summary_m.group(1).strip() if summary_m else ""

        date_m = re.search(r'date:"([^"]+)"', block)
        date = safe_parse_date(date_m.group(1), ['%Y-%m-%d']) if date_m else None

        cover_m = re.search(r'cover:"([^"]+)"', block)
        image = None
        if cover_m:
            cover = cover_m.group(1)
            image = cover if cover.startswith('http') else f"{base_url}{cover}"

        posts.append({
            "title": title_m.group(1).strip(),
            "url": f"{base_url}/en/blog/{post_id}",
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    logger.info(f"[Spirit AI] Scraped {len(posts)} posts from JS chunk")
    return posts


def scrape_xiaomi_robotics(source):
    """
    Xiaomi Robotics (robotics.xiaomi.com) is a Vue SSR site: blog cards are
    rendered server-side into the HTML under <section id="blog">. Each card is
    an <a class="blog-card"> with img.blog-card-image, span.blog-card-date,
    h3.blog-card-title and p.blog-card-excerpt. Cover images are absolute URLs.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for card in soup.find_all('a', class_='blog-card'):
        href = card.get('href', '')
        if not href:
            continue
        url = href if href.startswith('http') else f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title_el = card.find('h3', class_='blog-card-title')
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        date_el = card.find('span', class_='blog-card-date')
        date = safe_parse_date(date_el.get_text(strip=True), ['%b %d, %Y', '%B %d, %Y']) if date_el else None

        excerpt_el = card.find('p', class_='blog-card-excerpt')
        summary = excerpt_el.get_text(strip=True) if excerpt_el else ""

        image_url = None
        img = card.find('img', class_='blog-card-image')
        if img:
            src = img.get('src', '')
            if src.startswith('http'):
                image_url = src
            elif src.startswith('//'):
                image_url = f"https:{src}"
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Xiaomi Robotics] Scraped {len(posts)} posts")
    return posts


def _extract_js_object(text, start_index):
    """
    Extract a balanced {...} JSON object from `text` starting at the first '{'
    at/after start_index. Needed because embedded JS blobs contain '};'
    sequences inside strings/nested objects that defeat a non-greedy regex.
    Tracks string literals (single/double quotes) and escapes to find the
    matching closing brace.
    """
    brace_start = text.find('{', start_index)
    if brace_start == -1:
        return None
    depth = 0
    in_str = False
    escaped = False
    quote = ''
    for i in range(brace_start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                in_str = False
        else:
            if ch == '"' or ch == "'":
                in_str = True
                quote = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[brace_start:i + 1]
    return None


def scrape_bytedance_seed(source):
    """
    ByteDance Seed (seed.bytedance.com) is a Modern.js/React app. The research
    publication list is embedded as JSON in a `window._ROUTER_DATA = {...}`
    script. Articles live at loaderData["(locale$)/research/page"]
    ["article_list"], each with ArticleMeta (PublishDate epoch-ms, ExternalLinks,
    Journal, Thumbnail/Cover) plus ArticleSubContentZh and ArticleSubContentEn
    (each with Title, Abstract). Prefer En when populated and fall back to Zh.
    Publication links point to external destinations (mostly arXiv).
    """
    company = source["name"]
    response = make_request(source["url"])
    html = response.text

    marker = html.find('window._ROUTER_DATA')
    if marker == -1:
        logger.warning(f"[ByteDance Seed] No _ROUTER_DATA found, using fallback")
        return []

    raw = _extract_js_object(html, marker)
    if not raw:
        logger.warning(f"[ByteDance Seed] Could not extract _ROUTER_DATA JSON, using fallback")
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"[ByteDance Seed] _ROUTER_DATA JSON parse failed: {e}, using fallback")
        return []

    loader_data = data.get('loaderData', {})
    article_list = []
    for page in loader_data.values():
        if isinstance(page, dict) and page.get('article_list'):
            article_list = page['article_list']
            break

    posts = []
    seen_urls = set()
    for article in article_list:
        meta = article.get('ArticleMeta', {})
        zh_content = article.get('ArticleSubContentZh') or {}
        en_content = article.get('ArticleSubContentEn') or {}

        title = (en_content.get('Title') or zh_content.get('Title') or '').strip()
        if not title:
            continue

        # Prefer the external publication link (arXiv etc.); fall back to page
        url = None
        for link in meta.get('ExternalLinks') or []:
            link_url = link.get('Link')
            if link_url:
                url = link_url
                break
        if not url:
            url = source["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # PublishDate is epoch milliseconds
        date = None
        publish_ms = meta.get('PublishDate')
        if isinstance(publish_ms, (int, float)) and publish_ms > 0:
            date = datetime.fromtimestamp(publish_ms / 1000)

        summary = (en_content.get('Abstract') or zh_content.get('Abstract') or '').strip()
        journal = (meta.get('Journal') or '').strip()
        if journal:
            summary = f"[{journal}] {summary}" if summary else journal

        image = (meta.get('Cover') or meta.get('Thumbnail') or '').strip() or None

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    logger.info(f"[ByteDance Seed] Scraped {len(posts)} posts from _ROUTER_DATA")
    return posts


def scrape_nvidia_blog(source):
    """
    NVIDIA Blog (blogs.nvidia.com) is a WordPress site. The robotics category
    exposes a standard RSS feed (source["url"] points to .../robotics/feed/)
    which is more robust than HTML scraping: each <item> carries title, link,
    pubDate (RFC 822) and an HTML <description> excerpt, plus a Yahoo Media RSS
    <media:content url="..."> featured image. Descriptions are HTML-wrapped and
    end with a "[...]" / "[…]" read-more ellipsis that we strip.
    """
    company = source["name"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'xml')

    posts = []
    seen_urls = set()

    for item in soup.find_all('item'):
        title_el = item.find('title')
        link_el = item.find('link')
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        url = link_el.get_text(strip=True)
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)

        date = None
        pubdate_el = item.find('pubDate')
        if pubdate_el:
            date = safe_parse_date(pubdate_el.get_text(strip=True), ['%a, %d %b %Y %H:%M:%S %z'])
            # pubDate is timezone-aware; drop tzinfo so it sorts alongside the
            # naive datetimes produced by every other source and the fallback.
            if date is not None:
                date = date.replace(tzinfo=None)

        summary = ""
        desc_el = item.find('description')
        if desc_el:
            desc_text = BeautifulSoup(desc_el.get_text(), 'html.parser').get_text(strip=True)
            summary = re.sub(r'\s*\[(?:\.\.\.|…|\u2026)\]\s*$', '', desc_text).strip()

        image = None
        media = item.find('media:content') or item.find('content', recursive=True)
        if media and media.get('url'):
            image = media.get('url')
        if not image:
            enclosure = item.find('enclosure')
            if enclosure and enclosure.get('url'):
                image = enclosure.get('url')

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    logger.info(f"[NVIDIA Blog] Scraped {len(posts)} posts from RSS feed")
    return posts


def scrape_nvidia_gear(source):
    """
    NVIDIA GEAR lab (research.nvidia.com/labs/gear) is a Next.js static export.
    The publications page is client-rendered (empty in SSR HTML), but each
    individual project/blog page IS server-side rendered with a stable template:
    <article class="Home_blogPost__*"> containing a .Home_blogTitle__* heading
    and a .Home_publishDate__* date. Project routes are enumerated from the
    Next.js _buildManifest.js (e.g. /dreamgen, /egoscale, /flare, /gr00t-n1_5,
    /gr00t-n1_6); we fetch each and parse its blog article. Dates appear in
    mixed formats ("Feb 19, 2026" and "15 December 2025").
    """
    company = source["name"]
    base_url = source["base_url"]
    gear_path = "/labs/gear"

    # Known project/blog routes, used directly if route discovery via the
    # Next.js build manifest fails (the CDN occasionally rate-limits the
    # _next/static asset requests).
    known_routes = ['/dreamgen', '/egoscale', '/flare', '/gr00t-n1_5', '/gr00t-n1_6']
    skip = {'/_app', '/_error', '/_document', '/publications'}

    routes = []
    try:
        home = make_request(source["url"]).text
        build_match = re.search(r'/_next/static/([^/"]+)/_buildManifest\.js', home)
        if build_match:
            build_id = build_match.group(1)
            manifest = make_request(f"{base_url}{gear_path}/_next/static/{build_id}/_buildManifest.js").text
            for route in re.findall(r'"(/[a-zA-Z0-9_\-]+)"', manifest):
                if route in skip or route.endswith('-no-header') or route in routes:
                    continue
                routes.append(route)
    except requests.exceptions.RequestException:
        pass

    if not routes:
        routes = known_routes

    date_formats = ['%b %d, %Y', '%B %d, %Y', '%d %b %Y', '%d %B %Y']
    posts = []
    seen_urls = set()

    for route in routes:
        page_url = f"{base_url}{gear_path}{route}/"
        try:
            page_html = make_request(page_url).content
        except requests.exceptions.RequestException:
            continue

        soup = BeautifulSoup(page_html, 'html.parser')
        article = soup.find('article', class_=lambda c: c and 'blogPost' in c)
        if not article:
            continue

        title_el = soup.find(class_=lambda c: c and 'blogTitle' in c)
        if not title_el:
            continue
        # Prefer the concise document <title> over the heading, which often
        # concatenates the project name with a long subtitle.
        doc_title = soup.find('title')
        title = doc_title.get_text(strip=True) if doc_title else title_el.get_text(strip=True)
        if not title:
            continue

        if page_url in seen_urls:
            continue
        seen_urls.add(page_url)

        date = None
        date_el = soup.find(class_=lambda c: c and 'publishDate' in c)
        if date_el:
            date = safe_parse_date(date_el.get_text(strip=True), date_formats)

        # Only use still-image sources for the thumbnail; a <video> src is not
        # renderable in the <img> the UI uses, so fall back to a placeholder.
        image_url = None
        img = article.find('img')
        if img:
            src = img.get('src', '')
            if re.search(r'\.(png|jpe?g|webp|gif|svg)(\?|$)', src, re.IGNORECASE):
                if src.startswith('http'):
                    image_url = src
                elif src.startswith('//'):
                    image_url = f"https:{src}"
                elif src.startswith('/'):
                    image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": page_url,
            "date": date or datetime.min,
            "summary": "",
            "image": image_url,
            "company": company,
        })

    logger.info(f"[NVIDIA GEAR] Scraped {len(posts)} posts from project pages")
    return posts


def scrape_x_square(source):
    """
    X Square Robot (x2robot.com) is a Next.js App Router site, but the news
    list is server-side rendered into the HTML. Each post is an <a> card with a
    "border-b" class linking to /news/<id>; the title is an <h3>, the date a
    div.text-gray-500 (YYYY-MM-DD), the teaser a <p>, and the image an <img>
    (often a /_next/image?url=... proxy). English post URLs are /en/news/<id>.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for card in soup.find_all('a', href=re.compile(r'/news/[0-9a-f]{6,}')):
        href = card.get('href', '')
        h3 = card.find('h3')
        if not h3:
            continue
        title = h3.get_text(strip=True)
        if not title:
            continue

        slug = href.rstrip('/').split('/news/')[-1]
        url = f"{base_url}/en/news/{slug}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        date = None
        date_el = card.find('div', class_=lambda c: c and 'text-gray-500' in c)
        if date_el:
            date = safe_parse_date(date_el.get_text(strip=True), ['%Y-%m-%d'])

        summary = ""
        p = card.find('p')
        if p:
            summary = p.get_text(strip=True)

        image_url = None
        img = card.find('img')
        if img:
            src = img.get('src', '')
            if src.startswith('http'):
                image_url = src
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[X Square Robot] Scraped {len(posts)} posts")
    return posts


def scrape_sanctuary_ai(source):
    """
    Sanctuary AI (sanctuary.ai) runs on Squarespace, which exposes an RSS feed
    at /blog/rss.xml (source["url"]). Each <item> has title, link, pubDate
    (RFC 822), an HTML <description>, and a Squarespace <media:content> image.
    """
    company = source["name"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'xml')

    posts = []
    seen_urls = set()

    for item in soup.find_all('item'):
        title_el = item.find('title')
        link_el = item.find('link')
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        url = link_el.get_text(strip=True)
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)

        date = None
        pubdate_el = item.find('pubDate')
        if pubdate_el:
            date = safe_parse_date(pubdate_el.get_text(strip=True), ['%a, %d %b %Y %H:%M:%S %z'])
            if date is not None:
                date = date.replace(tzinfo=None)

        summary = ""
        desc_el = item.find('description')
        if desc_el:
            summary = BeautifulSoup(desc_el.get_text(), 'html.parser').get_text(strip=True)

        image = None
        media = item.find('media:content') or item.find('content')
        if media and media.get('url'):
            image = media.get('url')

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    logger.info(f"[Sanctuary AI] Scraped {len(posts)} posts from RSS feed")
    return posts


def scrape_boston_dynamics(source):
    """
    Boston Dynamics (bostondynamics.com) is WordPress, but its blog feed is
    empty; the blog listing is server-rendered instead. Each card is an
    <article class="PostAjaxFilter-card"> with a .PostAjaxFilter-card-title, a
    first <a> linking to /blog/<slug>/, and a .PostAjaxFilter-card-image whose
    CSS background-image holds the thumbnail URL. The listing exposes no dates.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for card in soup.find_all('article', class_='PostAjaxFilter-card'):
        title_el = card.find(class_='PostAjaxFilter-card-title')
        link = card.find('a', href=re.compile(r'/blog/[a-z0-9\-]+'))
        if not title_el or not link:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        href = link.get('href', '')
        url = href if href.startswith('http') else f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        image_url = None
        img_div = card.find(class_='PostAjaxFilter-card-image')
        if img_div:
            style = img_div.get('style', '')
            bg = re.search(r'url\([\'"]?([^\'")]+)[\'"]?\)', style)
            if bg:
                src = bg.group(1)
                image_url = src if src.startswith('http') else f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": datetime.min,
            "summary": "",
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Boston Dynamics] Scraped {len(posts)} posts")
    return posts


def scrape_nvidia_cosmos(source):
    """
    NVIDIA Cosmos Lab (research.nvidia.com/labs/cosmos-lab) renders its
    publication list client-side (empty in SSR HTML), but the product showcase
    is server-rendered as <div class="product-card"> entries with an
    a.product-media[href] link, an h3.product-name and a p.product-desc.
    Card media is <video>, so no still image is captured (placeholder is used).
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for card in soup.find_all(class_='product-card'):
        name_el = card.find(class_='product-name')
        link = card.find('a', href=True)
        if not name_el or not link:
            continue
        title = name_el.get_text(strip=True)
        if not title:
            continue

        href = link.get('href', '')
        if href.startswith('http'):
            url = href
        elif href.startswith('/'):
            url = f"{base_url}{href}"
        else:
            url = f"{base_url}/labs/cosmos-lab/{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        desc_el = card.find(class_='product-desc')
        summary = desc_el.get_text(strip=True) if desc_el else ""

        image_url = None
        img = card.find('img')
        if img:
            src = img.get('src', '')
            if re.search(r'\.(png|jpe?g|webp|gif|svg)(\?|$)', src, re.IGNORECASE):
                image_url = src if src.startswith('http') else f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": datetime.min,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[NVIDIA Cosmos Lab] Scraped {len(posts)} posts")
    return posts


def scrape_agile_robots(source):
    """
    Agile Robots (agile-robots.com) runs on TYPO3 with server-rendered news.
    Each card is a div.article-list-teaser-element containing an h3.title, a
    <time> element (datetime attr is ISO; visible text is DD.MM.YYYY), an
    enclosing <a> link, and an <img>. Links and images are relative and need
    the base URL prepended. The listing has no teaser summary text.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for card in soup.find_all('div', class_='article-list-teaser-element'):
        title_el = card.find('h3', class_='title') or card.find(['h2', 'h3'])
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        link = card.find('a', href=True)
        if not link:
            continue
        href = link.get('href', '')
        url = href if href.startswith('http') else f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        date = None
        time_el = card.find('time')
        if time_el:
            iso = time_el.get('datetime', '')
            date = safe_parse_date(iso[:10], ['%Y-%m-%d']) if iso else None
            if not date:
                date = safe_parse_date(time_el.get_text(strip=True), ['%d.%m.%Y'])

        image_url = None
        img = card.find('img')
        if img:
            src = img.get('src') or img.get('data-src') or ''
            if src.startswith('http'):
                image_url = src
            elif src.startswith('/'):
                image_url = f"{base_url}{src}"

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": "",
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Agile Robots] Scraped {len(posts)} posts")
    return posts


def scrape_dexforce(source):
    """
    DexForce (dexforce.com/core.html) is a static product/technology page. It
    has no press-news list, but its "Latest Research" (最新研究) section is
    server-rendered as div.core-report entries with a .report-title heading, a
    descriptive <p>, and a link to the technical report. No dates or images.
    """
    company = source["name"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    for report in soup.find_all(class_='core-report'):
        title_el = report.find(class_='report-title')
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        link = report.find('a', href=True)
        url = link.get('href', '').strip() if link else source["url"]
        if not url:
            url = source["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        summary = ""
        for p in report.find_all('p'):
            text = p.get_text(strip=True)
            if text and text != title:
                summary = text
                break

        posts.append({
            "title": title,
            "url": url,
            "date": datetime.min,
            "summary": summary,
            "image": None,
            "company": company,
        })

    logger.info(f"[DexForce] Scraped {len(posts)} posts")
    return posts


def scrape_rl2_gatech(source):
    """
    RL2 (Robot Learning and Reasoning Lab) at Georgia Tech is a static site
    that loads its publication list from /publications.json via client-side
    fetch. Each entry has: title, authors, venue, abstract, optional awards,
    a thumbnail (image or video URL relative to /assets/), and a links dict
    with paper/website/code/video keys.

    Notes:
    - The venue string ("RSS 2026", "CoRL 2025", "Robotics and Automation
      Letters (RA-L) 2022") contains the only date signal. We extract the
      4-digit year and pin the date to January 1 of that year - guessing
      conference months would be brittle. Year ordering is what the UI
      actually uses for sort, so this preserves correct chronology.
    - Each post URL prefers links.website, then links.paper, then the lab
      homepage. The lab's own SPA has no per-publication anchor.
    - Thumbnails come from /assets/<filename>. Videos cannot render in the
      UI's <img> tag (see scrape_nvidia_gear for the same constraint), so
      we only use image thumbnails and let video entries fall back to the
      generated SVG placeholder.
    """
    company = source["name"]
    base_url = source["base_url"]
    homepage = base_url + "/"
    response = make_request(source["url"])
    data = response.json()

    posts = []
    seen_urls = set()
    for pub in data.get('publications', []):
        title = (pub.get('title') or '').strip()
        if not title:
            continue

        links = pub.get('links') or {}
        url = links.get('website') or links.get('paper') or homepage
        if url.startswith('/'):
            url = base_url + url

        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Extract a 4-digit year (1990-2099) from the venue string; some
        # entries (e.g. older RA-L papers) only have the year inside the
        # awards text, so fall back to scanning those before giving up.
        venue = (pub.get('venue') or '').strip()
        awards = pub.get('awards') or []
        date = datetime.min
        year_match = re.search(r'\b(19[9]\d|20\d{2})\b', venue)
        if not year_match:
            for award in awards:
                year_match = re.search(r'\b(19[9]\d|20\d{2})\b', award)
                if year_match:
                    break
        if year_match:
            date = datetime(int(year_match.group(1)), 1, 1)

        # Summary: "[Venue] Abstract" with awards appended in brackets.
        abstract = (pub.get('abstract') or '').strip()
        summary_parts = []
        if venue:
            summary_parts.append(f"[{venue}]")
        if abstract:
            summary_parts.append(abstract)
        if awards:
            summary_parts.append(f"({', '.join(awards)})")
        summary = ' '.join(summary_parts)

        # Image thumbnails only; videos can't render in the UI's <img>.
        image_url = None
        thumb = pub.get('thumbnail') or {}
        if thumb.get('type') == 'image' and thumb.get('url'):
            thumb_path = thumb['url']
            if thumb_path.startswith('http'):
                image_url = thumb_path
            else:
                image_url = f"{base_url}/assets/{thumb_path.lstrip('/')}"

        posts.append({
            "title": title,
            "url": url,
            "date": date,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[RL2 @ Georgia Tech] Scraped {len(posts)} publications from publications.json")
    return posts


def scrape_psi_lab(source):
    """
    Physical Superintelligence Lab (psi-lab.ai) is a static HTML site. The
    /research.html page is a SPA-like shell whose research list is embedded
    as a single inline `let publications = [...]` JS array literal (not in a
    separate fetch). Each object has: name, authors, conference, webpage,
    paper, code, thumbnail.

    Notes:
    - The array is a JavaScript object literal with trailing commas, so we
      have to strip them iteratively before json.loads succeeds. We use a
      _ROUTER_DATA-style fixed-point regex pass to be safe against the
      `},\\n            ],` outer-array case.
    - The conference field ("ICLR 2026", "arXiv 2026", "ICCV 2025 Oral")
      carries the only date signal. We pull the 4-digit year and pin to
      January 1 of that year, matching scrape_rl2_gatech's approach.
    - URL prefers webpage > paper > base research page. arXiv abstract pages
      are usable directly.
    - Thumbnails are relative paths under /assets/papers/<file>.png; we
      prefix base_url. The site only serves still images here.
    - Summary is "[Conference] Authors" because the inline data has no
      abstract; authors are the most useful per-paper context available.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    html = response.text

    array_match = re.search(r'let\s+publications\s*=\s*\[(.*?)\];', html, re.DOTALL)
    if not array_match:
        logger.warning(f"[Physical Superintelligence Lab] No publications array found, using fallback")
        return []

    body = array_match.group(1)
    # Strip trailing commas before } or ] until fixed point (handles nested),
    # then drop any final comma left dangling at the end of the array body.
    prev = None
    while prev != body:
        prev = body
        body = re.sub(r',(\s*[}\]])', r'\1', body)
    body = body.rstrip().rstrip(',').rstrip()

    try:
        pubs = json.loads('[' + body + ']')
    except json.JSONDecodeError as e:
        logger.warning(f"[Physical Superintelligence Lab] JSON parse failed: {e}, using fallback")
        return []

    posts = []
    seen_urls = set()
    for pub in pubs:
        title = (pub.get('name') or '').strip()
        if not title:
            continue

        url = (pub.get('webpage') or pub.get('paper') or source['url']).strip()
        if url.startswith('/'):
            url = base_url + url
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Year is the only date signal in conference strings like "ICLR 2026"
        # or "arXiv 2026"; pin to Jan 1 of the matched year.
        conference = (pub.get('conference') or '').strip()
        date = datetime.min
        year_match = re.search(r'\b(19[9]\d|20\d{2})\b', conference)
        if year_match:
            date = datetime(int(year_match.group(1)), 1, 1)

        authors = (pub.get('authors') or '').strip()
        summary_parts = []
        if conference:
            summary_parts.append(f"[{conference}]")
        if authors:
            summary_parts.append(authors)
        summary = ' '.join(summary_parts)

        image_url = None
        thumb = (pub.get('thumbnail') or '').strip()
        if thumb:
            if thumb.startswith('http'):
                image_url = thumb
            elif thumb.startswith('/'):
                image_url = f"{base_url}{thumb}"
            else:
                image_url = f"{base_url}/{thumb}"

        posts.append({
            "title": title,
            "url": url,
            "date": date,
            "summary": summary,
            "image": image_url,
            "company": company,
        })

    logger.info(f"[Physical Superintelligence Lab] Scraped {len(posts)} publications from inline JS array")
    return posts


def scrape_dexmal(source):
    """
    Dexmal (dexmal.com) is a Vue 3 SPA. The /research route renders nothing
    server-side - the initial HTML is just an app shell that loads
    /assets/index-<hash>.js. That bundle contains BOTH:
      1. A `Km = {...}` object literal mapping semantic keys like
         `researchRealtimeVlaFlash` to arXiv URLs.
      2. An `articles:[{date, title, description, href, pinned}, ...]` array
         embedded in the i18n messages. `href` fields reference the Km map
         (e.g. `Km.researchRealtimeVlaFlash`), so we must resolve them after
         extraction.

    Notes:
    - Bundle filename is content-hashed, so we scrape the current hash from
      the shell HTML via a `src="/assets/index-<hash>.js"` regex on each call
      instead of hardcoding it.
    - Dates are formatted like "13 May 2026" (English) - we parse with
      '%d %b %Y'. If the site later switches to Chinese-first for the
      initial locale, that array will be under a zh-CN block; we currently
      target the English `articles:[...]` occurrence for stability with the
      rest of the aggregator's English UI.
    - The Km object literal uses backtick-quoted values; we extract with a
      permissive regex rather than trying to JSON-parse the whole bundle.
    """
    company = source["name"]
    base_url = source["base_url"]

    # Step 1: discover the current hashed bundle filename from the SPA shell.
    shell = make_request(source["url"]).text
    bundle_match = re.search(r'src="(/assets/index-[A-Za-z0-9_-]+\.js)"', shell)
    if not bundle_match:
        logger.warning(f"[Dexmal] Could not locate index bundle in shell HTML, using fallback")
        return []

    bundle_url = base_url + bundle_match.group(1)
    bundle = make_request(bundle_url).text

    # Step 2: build the Km link map. Entries look like `researchFoo:`https://...`,`
    km_map = {}
    for key, url in re.findall(r'(research[A-Za-z0-9_]+)\s*:\s*`([^`]+)`', bundle):
        km_map[key] = url

    # Step 3: locate the English `articles:[...]` array. It's the outermost
    # array assigned to the `articles` key inside pages.research. Do a bracket
    # walk from the opening `[` because the entries themselves contain `]`
    # inside descriptions occasionally.
    articles_start = bundle.find('articles:[')
    if articles_start < 0:
        logger.warning(f"[Dexmal] No articles:[...] block found, using fallback")
        return []

    i = articles_start + len('articles:')
    if bundle[i] != '[':
        logger.warning(f"[Dexmal] Unexpected articles block layout, using fallback")
        return []

    depth = 0
    in_backtick = False
    end = -1
    for j in range(i, len(bundle)):
        ch = bundle[j]
        if ch == '`' and bundle[j - 1] != '\\':
            in_backtick = not in_backtick
            continue
        if in_backtick:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = j
                break

    if end < 0:
        logger.warning(f"[Dexmal] Could not find end of articles array, using fallback")
        return []

    articles_body = bundle[i + 1:end]

    # Step 4: pull each `{...}` entry via a bracket walk on the body.
    entries = []
    depth = 0
    in_backtick = False
    start = -1
    for j, ch in enumerate(articles_body):
        if ch == '`' and (j == 0 or articles_body[j - 1] != '\\'):
            in_backtick = not in_backtick
            continue
        if in_backtick:
            continue
        if ch == '{':
            if depth == 0:
                start = j
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                entries.append(articles_body[start:j + 1])
                start = -1

    posts = []
    seen_urls = set()
    for entry in entries:
        def field(name):
            m = re.search(rf'\b{name}\s*:\s*`([^`]*)`', entry)
            return m.group(1) if m else None

        title = (field('title') or '').strip()
        if not title:
            continue

        description = (field('description') or '').strip()
        date_str = (field('date') or '').strip()

        # href references Km, e.g. `href:Km.researchRealtimeVlaFlash`
        href_match = re.search(r'href\s*:\s*Km\.([A-Za-z0-9_]+)', entry)
        url = None
        if href_match:
            url = km_map.get(href_match.group(1))
        if not url:
            # Fallback: sometimes href might be an inline backtick URL.
            url = field('href') or source['url']

        if url in seen_urls:
            continue
        seen_urls.add(url)

        date = safe_parse_date(date_str, ['%d %b %Y', '%d %B %Y']) or datetime.min

        posts.append({
            "title": title,
            "url": url,
            "date": date,
            "summary": compress_summary(description),
            "image": None,
            "company": company,
        })

    logger.info(f"[Dexmal] Scraped {len(posts)} research articles from JS bundle")
    return posts


def scrape_xdof(source):
    """
    XDOF (xdof.ai) uses Next.js App Router with clean SSR.
    Blog posts are rendered as <li><a href="/blog/<slug>"> cards inside
    <ul aria-label="Blog post list">. Each card contains:
    - Date in a <span> pill (format: "Jun 30, 2026")
    - Title in <h2>
    - Excerpt in <p class="text-pretty ...">
    - Category tag in a second <span> pill (e.g. "research", "releases")
    No thumbnail images on the listing page.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []
    seen_urls = set()

    # Locate the blog post list explicitly to avoid nav links.
    post_list = soup.find('ul', attrs={'aria-label': 'Blog post list'})
    candidates = post_list.find_all('a', href=True) if post_list else \
        soup.find_all('a', href=re.compile(r'^/blog/.+'))

    for a_tag in candidates:
        href = a_tag.get('href', '')
        if not href.startswith('/blog/') or href in ('/blog', '/blog/'):
            continue

        h2 = a_tag.find('h2')
        if not h2:
            continue
        title = h2.get_text(strip=True)
        if not title or len(title) < 3:
            continue

        url = f"{base_url}{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Date: first <span> whose text parses as "Mon DD, YYYY".
        date = None
        for span in a_tag.find_all('span'):
            text = span.get_text(strip=True)
            parsed = safe_parse_date(text, ['%b %d, %Y', '%B %d, %Y'])
            if parsed:
                date = parsed
                break

        # Summary: <p> with the article excerpt (has "text-pretty" class).
        desc_p = a_tag.find('p', class_=lambda c: c and 'text-pretty' in c)
        if not desc_p:
            desc_p = a_tag.find('p')
        summary = desc_p.get_text(strip=True) if desc_p else ""

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": None,  # No thumbnails on the XDOF listing page
            "company": company,
        })

    logger.info(f"[XDOF] Scraped {len(posts)} posts")
    return posts


# =============================================================================
# SCRAPER DISPATCH
# =============================================================================

SCRAPERS = {
    "Generalist AI": scrape_generalist_ai,
    "Physical Intelligence": scrape_physical_intelligence,
    "World Labs": scrape_world_labs,
    "Figure": scrape_figure,
    "Sunday Robotics": scrape_sunday_robotics,
    "Skild AI": scrape_skild_ai,
    "1X Technologies": scrape_1x_technologies,
    "Agility Robotics": scrape_agility_robotics,
    "Sharpa": scrape_sharpa,
    "Hexagon Robotics": scrape_hexagon_robotics,
    "MANUS": scrape_manus,
    "BeingBeyond": scrape_beingbeyond,
    "AGIBOT Finch": scrape_agibot_finch,
    "Genesis AI": scrape_genesis_ai,
    "Ropedia": scrape_ropedia,
    "OneRobotics": scrape_onerobot,
    "Galaxea": scrape_galaxea,
    "Spirit AI": scrape_spirit_ai,
    "Xiaomi Robotics": scrape_xiaomi_robotics,
    "ByteDance Seed": scrape_bytedance_seed,
    "NVIDIA Blog": scrape_nvidia_blog,
    "NVIDIA GEAR": scrape_nvidia_gear,
    "X Square Robot": scrape_x_square,
    "Sanctuary AI": scrape_sanctuary_ai,
    "Boston Dynamics": scrape_boston_dynamics,
    "NVIDIA Cosmos Lab": scrape_nvidia_cosmos,
    "Agile Robots": scrape_agile_robots,
    "DexForce": scrape_dexforce,
    "RL2 @ Georgia Tech": scrape_rl2_gatech,
    "Physical Superintelligence Lab": scrape_psi_lab,
    "Dexmal": scrape_dexmal,
    "XDOF": scrape_xdof,
}


# =============================================================================
# FALLBACK DATA - Used only when live scraping fails
# =============================================================================

FALLBACK_DATA = {
    "Generalist AI": [
        ("The Dark Matter of Robotics: Physical Commonsense", "https://generalistai.com/blog/jan-29-2026-physical-commonsense", datetime(2026, 1, 29), "Exploring physical commonsense as the reactive, closed-loop intelligence behind interacting in the physical world.", None),
        ("GEN-0: Embodied Foundation Models That Scale", "https://generalistai.com/blog/nov-04-2025-GEN-0", datetime(2025, 11, 4), "Introducing GEN-0, a new class of embodied foundation models built for multimodal training on high-fidelity physical interaction.", None),
        ("The Robots Build Now, Too", "https://generalistai.com/blog/sep-24-2025-the-robots-build-now-too", datetime(2025, 9, 24), "One-shot assembly: you build a Lego structure and the robot builds copies of it.", None),
        ("Research Preview", "https://generalistai.com/blog/jun-17-2025-research-preview", datetime(2025, 6, 17), "A first look at what Generalist is building in robotics.", None),
    ],
    "World Labs": [
        ("3D as code", "https://www.worldlabs.ai/blog/3d-as-code", datetime(2026, 3, 3), "Text became the universal interface for software; 3D is becoming the universal interface for space.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2F3d-as-code.jpg&w=3840&q=75"),
        ("Announcing the World API", "https://www.worldlabs.ai/blog/announcing-the-world-api", datetime(2026, 1, 21), "A public API for generating explorable 3D worlds from text, images, and video.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fworld-api.jpg&w=3840&q=75"),
        ("World Labs Announces New Funding", "https://www.worldlabs.ai/blog/funding-2026", datetime(2026, 2, 18), "An update on our vision for spatial intelligence in 2026.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Ffunding.jpg&w=3840&q=75"),
        ("Marble: A Multimodal World Model", "https://www.worldlabs.ai/blog/marble-world-model", datetime(2025, 11, 12), "Marble, our frontier multimodal world model, is now available to everyone.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fnov12-thumbnail.jpg&w=3840&q=75"),
        ("From Words to Worlds: Spatial Intelligence", "https://www.worldlabs.ai/blog/spatial-intelligence", datetime(2025, 11, 10), "A manifesto on spatial intelligence - AI's next frontier and how world models will unlock it.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2FManifesto-Magritte.jpg&w=3840&q=75"),
        ("RTFM: A Real-Time Frame Model", "https://www.worldlabs.ai/blog/rtfm", datetime(2025, 10, 16), "A research preview of RTFM - a generative world model that generates video in real-time.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Frtfm-thumbnail-glass.png&w=3840&q=75"),
        ("Generating Bigger and Better Worlds", "https://www.worldlabs.ai/blog/bigger-better-worlds", datetime(2025, 9, 16), "Latest breakthrough in 3D world generation with larger, more detailed environments.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fbigger-better-worlds-nologo.jpg&w=3840&q=75"),
        ("Generating Worlds", "https://www.worldlabs.ai/blog/generating-worlds", datetime(2024, 12, 2), "Early progress toward persistent, navigable 3D worlds you can explore in your browser.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fgenerating-worlds-nologo.jpg&w=3840&q=75"),
    ],
    "Skild AI": [
        ("Skild AI Expands Global Footprint To Bengaluru", "https://www.skild.ai/blogs/bengaluru", datetime(2026, 2, 19), "Skild AI announces expansion to Bengaluru, India.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fbengaluru.468e7705.jpg&w=3840&q=75"),
        ("Announcing Series C", "https://www.skild.ai/blogs/series-c", datetime(2026, 1, 14), "Skild AI announces Series C funding round.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fpress_release-2.5149b136.jpg&w=3840&q=75"),
        ("Learning by watching human videos", "https://www.skild.ai/blogs/learning-by-watching", datetime(2026, 1, 12), "Training robot models by learning from human videos.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fobservational-learning.1e829681.png&w=3840&q=75"),
        ("The case for an omni-bodied robot brain", "https://www.skild.ai/blogs/omni-bodied", datetime(2025, 9, 24), "Why a general-purpose robot brain should work across any robot body.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Flocoformer.fe908b66.png&w=3840&q=75"),
        ("One Model, Any Scenario", "https://www.skild.ai/blogs/one-policy-all-scenarios", datetime(2025, 8, 6), "End-to-end locomotion from vision - one model for any scenario.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fvision-loco.47034095.jpg&w=3840&q=75"),
        ("Building the general-purpose robotic brain", "https://www.skild.ai/blogs/building-the-general-purpose-robotic-brain", datetime(2025, 7, 29), "Building the foundation for general-purpose robotics.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fomni-body.3981c022.jpg&w=3840&q=75"),
    ],
    "Sunday Robotics": [
        ("ACT-1: A Robot Foundation Model Trained on Zero Robot Data", "https://www.sunday.ai/journal/no-robot-data", datetime(2025, 11, 19), "Sunday's first technical blog - ACT-1, a robot foundation model trained on zero robot data.", "https://cdn.sanity.io/images/1omys9i3/production/7d513e226ee4e1739175bacd03fa56ab52c0f215-4000x2668.jpg"),
        ("This Home Robot Clears Tables and Loads the Dishwasher", "https://www.wired.com/story/memo-sunday-robotics-home-robot/", datetime(2025, 11, 19), "WIRED coverage of Sunday's home robot capabilities.", "https://cdn.sanity.io/images/1omys9i3/production/3dc382088fcf41e138c21f757650f05961554335-1200x1500.png"),
        ("No Priors Episode | Conviction", "https://www.youtube.com/watch?v=4-VzXoZqAH0", datetime(2025, 11, 19), "Sunday Robotics on the No Priors podcast.", None),
    ],
    "Physical Intelligence": [
        ("VLAs with Long and Short-Term Memory", "https://www.pi.website/research/memory", datetime(2026, 3, 3), "Multi-Scale Embodied Memory (MEM) gives our models both long-term and short-term memory, enabling complex tasks longer than ten minutes.", None),
        ("The Physical Intelligence Layer", "https://www.pi.website/blog/partner", datetime(2026, 2, 24), "General-purpose physical intelligence models will enable a Cambrian explosion of robotics applications.", None),
        ("Moravec's Paradox and the Robot Olympics", "https://www.pi.website/blog/olympics", datetime(2025, 12, 22), "Fine-tuning models on difficult manipulation challenge tasks.", None),
        ("Emergence of Human to Robot Transfer in VLAs", "https://www.pi.website/research/human_to_robot", datetime(2025, 12, 16), "Exploring how transfer from human videos to robotic tasks emerges in VLAs as they scale.", None),
        ("pi*0.6: a VLA that Learns from Experience", "https://www.pi.website/blog/pistar06", datetime(2025, 11, 17), "Training generalist policies with RL to improve success rate and throughput.", None),
        ("Real-Time Action Chunking with Large Models", "https://www.pi.website/research/real_time_chunking", datetime(2025, 6, 9), "A real-time system for large VLAs that maintains precision and speed.", None),
        ("VLAs that Train Fast, Run Fast, and Generalize Better", "https://www.pi.website/research/knowledge_insulation", datetime(2025, 5, 28), "A method to train VLAs that train quickly and generalize well.", None),
        ("pi0.5: a VLA with Open-World Generalization", "https://www.pi.website/blog/pi05", datetime(2025, 4, 22), "Our latest generalist policy that enables open-world generalization.", None),
        ("Teaching Robots to Listen and Think Harder", "https://www.pi.website/research/hirobot", datetime(2025, 2, 26), "A method for robots to think through complex tasks step by step.", None),
        ("Open Sourcing pi0", "https://www.pi.website/blog/openpi", datetime(2025, 2, 4), "Releasing the weights and code for pi0 and pi0-FAST.", None),
        ("FAST: Efficient Robot Action Tokenization", "https://www.pi.website/research/fast", datetime(2025, 1, 16), "A new robot action tokenizer that trains generalist policies 5x faster.", None),
        ("pi0: Our First Generalist Policy", "https://www.pi.website/blog/pi0", datetime(2024, 10, 31), "Our first generalist policy combining large-scale data with a new architecture.", None),
    ],
    "1X Technologies": [
        ("EVE: General-Purpose Humanoid Platform", "https://www.1x.tech/discover/eve", datetime(2025, 12, 17), "Introducing EVE, a general-purpose humanoid robot platform designed for real-world tasks.", None),
        ("NEO: The Next Generation Android", "https://www.1x.tech/discover/neo", datetime(2025, 8, 15), "Unveiling NEO, an advanced android designed for domestic assistance.", None),
        ("1X Technologies Raises $100M Series B", "https://www.1x.tech/discover/series-b", datetime(2025, 6, 10), "1X Technologies announces $100M Series B funding to scale humanoid robot production.", None),
    ],
    "Agility Robotics": [
        ("Agility Gets a New Brand", "https://www.agilityrobotics.com/content/agility-gets-a-new-brand", datetime(2026, 3, 5), "Agility introduces its new brand identity.", "https://cdn.prod.website-files.com/68d6ca150ffa11fdc25d7575/69a98ff7fbf259b6de4ab977_Brand-Lauch_01%201.png"),
        ("2026: The Automation Evolution", "https://www.agilityrobotics.com/content/the-automation-evolution", datetime(2026, 1, 16), "Looking ahead to automation in 2026.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e3708677145336d500dcf_698e0485a8fa146cce743168_696aac3fc0fa3b57a66bbc7d_predictions-report-thumb.jpeg"),
        ("Beyond the Hype", "https://www.agilityrobotics.com/content/beyond-the-hype", datetime(2025, 11, 24), "Analysis of the humanoid robotics industry.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e3706aabc1d14b77ed872_698e0487f75bb3ecfc2e9050_69248f0bea797f53c19379e5_nrtl-final-thumb.jpeg"),
        ("Digit Moves Over 100,000 Totes in Commercial Deployment", "https://www.agilityrobotics.com/content/digit-moves-over-100k-totes", datetime(2025, 11, 20), "Digit achieves major milestone in commercial deployment.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e37060199c79ac58bbdb2_698e04859bba4e06e05cdb32_691e634fc31c30f89d18f476_GXO-Milestone-Square.jpeg"),
        ("Humanoid Robots: The Key to America's Automated Homecoming", "https://www.agilityrobotics.com/content/humanoid-robots-the-key-to-americas-automated-homecoming", datetime(2025, 10, 28), "The role of humanoid robots in American manufacturing.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e37078a703f83b00af39b_698e04887cd6858023f68a94_690011e638f31c1a70686c00_manufacturing-thumb.jpeg"),
        ("The Top Takeaways from the Conference on Robot Learning", "https://www.agilityrobotics.com/content/the-top-takeaways-from-the-conference-on-robot-learning", datetime(2025, 10, 14), "Key insights from CoRL 2025.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e3706721634c4dfc92261_698e0485612e413c0fcbae67_68eedb1e335a0c71442880b6_CoRL-Thumb.jpeg"),
        ("Digit's Next Steps", "https://www.agilityrobotics.com/content/digits-next-steps", datetime(2025, 10, 2), "What's next for Digit.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e3705dd8e5fdc8073c949_698e0485531c1eaf15826687_68ca0136093d1592df9bf968_nav-thumb.jpeg"),
        ("Agility Robotics Powers the Future of Robotics with NVIDIA", "https://www.agilityrobotics.com/content/agility-robotics-powers-the-future-of-robotics-with-nvidia", datetime(2025, 9, 10), "Partnership with NVIDIA to advance robotics.", "https://cdn.prod.website-files.com/6980c63561bbbeb67b4b7ab5/698e3705b2006b64c48a0716_698e0485f06f42cc8a66f7e9_68c1b757ca00040b76b1e3ab_jensen-digit-square.jpeg"),
    ],
    "Figure": [
        ("Helix 02 Living Room Tidy", "https://www.figure.ai/news/helix-02-living-room-tidy", datetime(2026, 3, 9), "Helix 02 demonstrates tidying up a living room.", None),
        ("Introducing Helix 02: Full-Body Autonomy", "https://www.figure.ai/news/helix-02", datetime(2026, 1, 27), "Introducing Helix 02 with full-body autonomy capabilities.", None),
        ("Introducing Figure 03", "https://www.figure.ai/news/introducing-figure-03", datetime(2025, 10, 9), "Meet Figure 03, the next generation humanoid robot.", None),
        ("Scaling Helix: a New State of the Art in Humanoid Logistics", "https://www.figure.ai/news/scaling-helix-logistics", datetime(2025, 6, 7), "Helix sets new standards in humanoid logistics.", None),
        ("F.02 Contributed to the Production of 30,000 Cars at BMW", "https://www.figure.ai/news/production-at-bmw", datetime(2025, 11, 19), "Figure's F.02 robots contribute to BMW car production.", None),
        ("Project Go-Big: Internet-Scale Humanoid Pretraining and Direct Human-to-Robot Transfer", "https://www.figure.ai/news/project-go-big", datetime(2025, 9, 18), "New research on internet-scale humanoid pretraining.", None),
        ("Figure Announces Strategic Partnership with Brookfield", "https://www.figure.ai/news/figure-announces-strategic-partnership-with-brookfield", datetime(2025, 9, 17), "Figure announces partnership with Brookfield.", None),
        ("Figure Exceeds $1B in Series C Funding at $39B Post-Money Valuation", "https://www.figure.ai/news/series-c", datetime(2025, 9, 16), "Figure raises $1B in Series C funding.", None),
        ("Helix Loads the Dishwasher", "https://www.figure.ai/news/helix-loads-the-dishwasher", datetime(2025, 9, 3), "Helix demonstrates loading the dishwasher.", None),
        ("Helix Learns to Fold Laundry", "https://www.figure.ai/news/helix-learns-to-fold-laundry", datetime(2025, 8, 12), "Helix learns to fold laundry through AI.", None),
    ],
    "Sharpa": [
        ("Towards Human-Like Manipulation through RL-Augmented Teleoperation and Mixture-of-Dexterous-Experts VLA", "https://www.sharpa.com/blogs/research/peeling-an-apple-with-63-dof-how-imcopilot-mode-vla-are-redefining-robotic-dexterity", datetime(2026, 3, 9), "Peeling an Apple with 63 DoF: How IMCopilot & MoDE-VLA are Redefining Robotic Dexterity", None),
        ("DexEMG: Towards Dexterous Teleoperation System via EMG2Pose Generalization", "https://www.sharpa.com/blogs/research/breaking-the-barriers-of-teleoperation-how-dexemg-and-sharpa-wave-are-revolutionizing-dexterous-manipulation", datetime(2026, 3, 6), "Breaking the barriers of teleoperation with DexEMG and Sharpa Wave.", None),
        ("Tacmap: Bridging the Tactile Sim-to-Real Gap via Geometry-Consistent Penetration Depth Map", "https://www.sharpa.com/blogs/research/tacmap-breaking-the-sim-to-real-deadlock-in-tactile-simulation-with-a-geometric-language", datetime(2026, 2, 18), "Breaking the sim-to-real deadlock in tactile simulation with a geometric language.", None),
        ("EgoScale: Scaling Dexterous Manipulation with Diverse Egocentric Human Data", "https://www.sharpa.com/blogs/research/egoscale-20-000-hours-of-video-grow-a-robot-hand-opening-the-scaling-law-era-of-dexterous-manipulation", datetime(2026, 2, 18), "20,000 hours of video grow a robot hand, opening the scaling law era of dexterous manipulation.", None),
        ("SimToolReal: An Object-Centric Policy for Zero-Shot Dexterous Tool Manipulation", "https://www.sharpa.com/blogs/research/moving-beyond-specialist-training-simtoolreal-enables-zero-shot-transfer-for-general-purpose-tool-use", datetime(2026, 2, 18), "Moving beyond specialist training for general-purpose tool use.", None),
        ("Spatially anchored Tactile Awareness for Robust Dexterous Manipulation", "https://www.sharpa.com/blogs/research/giving-robots-spatial-awareness-for-sub-millimeter-dexterous-manipulation", datetime(2026, 1, 28), "Giving robots spatial awareness for sub-millimeter dexterous manipulation.", None),
    ],
    "Hexagon Robotics": [
        ("Hexagon Robotics and Schaeffler deploy a fleet of AEON humanoids", "https://robotics.hexagon.com/hexagon-robotics-and-schaeffler-deploy-a-fleet-of-aeon-humanoids/", datetime(2026, 4, 22), "Hexagon Robotics and Schaeffler deploy a fleet of AEON humanoids.", "https://robotics.hexagon.com/wp-content/uploads/2026/04/Schaeffler_Hexagon_Partnership_AR_JS_new.jpg"),
        ("Industrial Autonomy Accelerates: Hexagon Robotics pushes Physical AI forward with NVIDIA", "https://robotics.hexagon.com/industrial-autonomy-hexagon-robotics-nvidia-physical-ai/", datetime(2026, 3, 16), "Hexagon Robotics pushes Physical AI forward with NVIDIA.", "https://robotics.hexagon.com/wp-content/uploads/2026/02/P90630892_lowRes_humanoid-robotics-at.jpg"),
        ("BMW deploys the humanoid robot AEON in production sites in Germany", "https://robotics.hexagon.com/bmw-deploys-aeon-hexagon-robotics-humanoid/", datetime(2026, 2, 27), "BMW deploys the AEON humanoid robot in production sites in Germany.", "https://robotics.hexagon.com/wp-content/uploads/2026/02/BMW-Factory-x-AEON_.jpg"),
        ("Hexagon Robotics' AEON wins the iF DESIGN AWARD 2026", "https://robotics.hexagon.com/hexagon-robotics-wins-the-if-design-award-2026/", datetime(2026, 2, 25), "AEON wins the iF DESIGN AWARD 2026.", "https://robotics.hexagon.com/wp-content/uploads/2026/02/AEON-Steps-IF-DESIGN-AWARD.jpg"),
        ("Homo Roboticus: When AI enters the physical world", "https://robotics.hexagon.com/homo-roboticus-when-ai-enters-the-physical-world/", datetime(2026, 2, 13), "When AI enters the physical world.", None),
        ("Hexagon Robotics partners with Microsoft to advance Physical AI", "https://robotics.hexagon.com/hexagon-robotics-partners-with-microsoft-to-advance-physical-ai/", datetime(2026, 1, 7), "Hexagon Robotics partners with Microsoft to advance Physical AI.", "https://robotics.hexagon.com/wp-content/uploads/2025/07/AEON-Arrives.png"),
    ],
    "MANUS": [
        ("MANUS at NVIDIA GTC 2026: From Jensen Huang's Keynote to the Show Floor", "https://www.manus-meta.com/blog/manus-at-nvidia-gtc-2026", datetime(2026, 3, 26), "MANUS at NVIDIA GTC 2026.", "https://cdn.prod.website-files.com/6641c0152b531df61b2cefca/69c4e80d4ad5c6fe8cf39ed2_use-case-thumbnail.jpg"),
        ("NVIDIA Launches Isaac Teleop at GTC 2026 With MANUS as the Official Data Glove", "https://www.manus-meta.com/blog/nvidia-launches-isaac-teleop-at-gtc-2026-with-manus-as-the-official-data-glove", datetime(2026, 3, 19), "NVIDIA launches Isaac Teleop at GTC 2026 with MANUS as the official data glove.", "https://cdn.prod.website-files.com/6641c0152b531df61b2cefca/69bbfa95e15a9a4ed1ecd839_thumbnail.jpg"),
        ("MANUS Gloves Now Natively Supported in NVIDIA Isaac Lab", "https://www.manus-meta.com/blog/manus-gloves-are-natively-supported-in-nvidia-isaac-lab", datetime(2026, 2, 25), "MANUS Gloves now natively supported in NVIDIA Isaac Lab.", "https://cdn.prod.website-files.com/6641c0152b531df61b2cefca/699ec492014b7a0fc62af19c_thumbnail.jpg"),
        ("Introducing MANUS Metagloves Pro Haptic: Precise Hand Tracking Meets Real-Time Haptic Feedback", "https://www.manus-meta.com/blog/metagloves-pro-haptic-precise-hand-tracking-meets-real-time-haptic-feedback", datetime(2026, 1, 19), "Precise hand tracking meets real-time haptic feedback.", "https://cdn.prod.website-files.com/6641c0152b531df61b2cefca/696f4473064a32d857df5b1d_Flyer_ProHaptic_simple-banner_2025.png"),
        ("MANUS in Embodied AI: From Human Motion to Robotic Dexterity", "https://www.manus-meta.com/blog/manus-in-embodied-ai-from-human-motion-to-robotic-dexterity", datetime(2025, 11, 3), "From human motion to robotic dexterity.", "https://cdn.prod.website-files.com/6641c0152b531df61b2cefca/690b68ed41de9bc07bfadf4c_thumbnail.jpg"),
    ],
    "BeingBeyond": [
        ("Unmasking the Illusion of Embodied Reasoning in Vision-Language-Action Models", "https://research.beingbeyond.com/better", datetime(2026, 4, 20), "BeTTER probes whether VLA models truly reason under controlled causal interventions, revealing shortcut learning and causal state-tracking failures.", "https://research.beingbeyond.com/projects/better/images/teaser.webp"),
        ("Being-H0.7: A Latent World-Action Model from Egocentric Videos", "https://research.beingbeyond.com/being-h07", datetime(2026, 4, 14), "Being-H0.7 is a latent world-action model that scales 200,000 hours of egocentric video into future-aware robot control.", "https://research.beingbeyond.com/projects/being-h07/images/thumb.webp"),
        ("OpenT2M: No-frill Motion Generation with Open-source, Large-scale, High-quality Data", "https://research.beingbeyond.com/opent2m", datetime(2026, 3, 19), "[Accepted: CVPR 2026] OpenT2M introduces a million-level, high-quality motion dataset and MonoFrill for stronger generalization.", "https://research.beingbeyond.com/projects/opent2m/images/2d-prq-pipeline.webp"),
        ("Joint-Aligned Latent Action: Towards Scalable VLA Pretraining in the Wild", "https://research.beingbeyond.com/jala", datetime(2026, 2, 26), "[Accepted: CVPR 2026] JALA combines lab-annotated and in-the-wild human manipulation data for scalable VLA pretraining.", "https://research.beingbeyond.com/projects/jala/images/fig1.webp"),
        ("Being-H0.5: Scaling Human-Centric Robot Learning for Cross-Embodiment Generalization", "https://research.beingbeyond.com/being-h05", datetime(2026, 1, 20), "Scaling human-centric robot learning with a Unified Action Space for cross-embodiment generalization.", "https://research.beingbeyond.com/projects/being-h05/images/thumb.webp"),
        ("Being-H0: Vision-Language-Action Pretraining from Large-Scale Human Videos", "https://research.beingbeyond.com/being-h0", datetime(2025, 7, 21), "The first dexterous VLA model pretrained from large-scale human videos via explicit hand motion modeling.", "https://research.beingbeyond.com/projects/being-h0/images/02_phy_inst_tune.webp"),
    ],
    "Genesis AI": [
        ("GENE-26.5: Advancing Robotic Manipulation to Human Level", "https://www.genesis.ai/blog/gene-26-5-advancing-robotic-manipulation-to-human-level", datetime(2026, 5, 7), "", "https://image.mux.com/N6002aDbA86yrpGu6MhH51wcPtkQgaRMN/thumbnail.jpg?width=2048&height=1152&fit_mode=pad&time=0.5"),
    ],
    "AGIBOT Finch": [
        ("LWD", "https://finch.agibot.com/research/lwd", datetime(2026, 4, 30), "Learning While Deploying turns real-world robot deployment into a continual reinforcement learning loop, where a shared generalist VLA policy improves from the experience collected by a robot fleet.", "https://finch.agibot.com/images/research/lwd-large.png"),
        ("SOP", "https://finch.agibot.com/research/sop", datetime(2026, 1, 6), "Scalable Online Post-Training for VLA Models", "https://finch.agibot.com/images/research/sop-large.png"),
        ("Act2Goal", "https://finch.agibot.com/research/act-2-goal", datetime(2026, 1, 1), "From World Model to General Goal-Conditioned Policy", "https://finch.agibot.com/images/research/act2-goal-large.png"),
        ("UniFact", "https://finch.agibot.com/research/uni-fact", datetime(2026, 1, 1), "Unified Embodied VLM Reasoning with Robotic Action", "https://finch.agibot.com/images/research/uni-fact-large.png"),
    ],
    "Ropedia": [
        ("Xperience-10M Dataset Release", "https://ropedia.com/blog/20260316_xperience_10m.html", datetime(2026, 3, 16), "We released Xperience-10M, a large-scale multimodal 4D human Xperience dataset for embodied AI.", "https://ropedia.com/img/xperience-10m-banner.png"),
        ("Introducing HOMIE", "https://ropedia.com/blog/20251216_introducing_ropedia.html", datetime(2025, 12, 16), "We introduced HOMIE, our human-centric platform for capturing and structuring real-world Xperience at scale.", "https://ropedia.com/img/homie-id-sample.png"),
    ],
    "OneRobotics": [
        ("No.1 in Real-Robot Benchmarks: OneRobotics Launches Its Proprietary World Action Model, OneModel 1.7 FrontoStria-RL", "https://www.onerobot.com/news/27", datetime(2026, 5, 20), "", "https://www.onerobot.com/uploads/upload/images/20260520/c1143671758f903d1ab028adab460be7.png"),
        ("OneRobotics Secures RMB 45 Million Bid for Embodied Intelligence Data Infrastructure Project, Accelerating Real-World Data Closed-Loop Development", "https://www.onerobot.com/news/26", datetime(2026, 5, 18), "", "https://www.onerobot.com/uploads/upload/images/20260518/f710c6dfaba5a4a65a956bee231f45e2.png"),
        ("OneRobotics Featured on Japan's NHK: Embodied Home Robots Go Global from China", "https://www.onerobot.com/news/24", datetime(2026, 5, 12), "", "https://www.onerobot.com/uploads/upload/images/20260512/11a4105ac3d0dd1494bb1abcc496bf17.png"),
        ("OneRobotics Brings \u201cOne Brain, Multiple Embodiments\u201d to Campus, with Acemate Becoming the Ultimate AI Teaching Assistant", "https://www.onerobot.com/news/22", datetime(2026, 5, 6), "", "https://www.onerobot.com/uploads/upload/images/20260506/93c83682b8d29708996bc456baf60240.png"),
        ("OneRobotics Launches Embodied Intelligence Chain with First Post-IPO Strategic Investment", "https://www.onerobot.com/news/20", datetime(2026, 4, 14), "", "https://www.onerobot.com/uploads/upload/images/20260506/52fc740c09223022840bff25cf62e938.png"),
        ("Defining a new paradigm for home embodied intelligence: OneRobotics AI Hub becomes the world's first local home AI agent officially supporting OpenClaw", "https://www.onerobot.com/news/19", datetime(2026, 2, 11), "", "https://www.onerobot.com/uploads/upload/images/20260211/046d9aeb0dc591af2dc1983f14665fa6.jpg"),
    ],
    "Galaxea": [
        ("Introducing G0.5: One Autoregressive Stream for Reasoning and Action", "https://opengalaxea.github.io/G05/", datetime(2026, 5, 31), "A pretrained autoregressive Vision-Language-Action model in which a single transformer decoder emits both reasoning and action tokens under one objective - keeping the VLM the decision-maker, not just a context encoder.", None),
    ],
    "Spirit AI": [
        ("Spirit-v1.5: Clean Data Is the Enemy of Great Robot Foundation Models", "https://www.spirit-ai.com/en/blog/spirit-v1-5", datetime(2026, 1, 11), "We advocate for a shift toward diverse and largely uncontrolled data for robot pretraining. Spirit-v1.5 achieves SoTA generalization by training on diverse, uncurated data rather than highly curated clean datasets.", "https://www.spirit-ai.com/blog/images/blogs/spirit-v1-5/cover.jpg"),
    ],
    "Xiaomi Robotics": [
        ("Open-Sourcing Post-Training Pipeline for Xiaomi-Robotics-0", "https://robotics.xiaomi.com/xiaomi-robotics-0.html#pack-earbuds", datetime(2026, 4, 27), "Xiaomi-Robotics-0 achieves precise earbud-to-case insertion using just 20 hours of post-training data. We open-source the full post-training pipeline.", "https://robotics.xiaomi.com/robot-static-resource/xiaomi-robotics-0/post-training.png"),
        ("Xiaomi-Robotics-0: An Open-Sourced Vision-Language-Action Model with Real-Time Execution", "https://robotics.xiaomi.com/xiaomi-robotics-0.html", datetime(2026, 2, 12), "Xiaomi-Robotics-0 is an advanced Vision-Language-Action (VLA) model optimized for high performance and real-time execution.", "https://robotics.xiaomi.com/robot-static-resource/xiaomi-robotics-0/xiaomi-robotics-0.png"),
    ],
    "ByteDance Seed": [
        ("GR-RL: Going Dexterous and Precise for Long-Horizon Robotic Manipulation", "https://arxiv.org/abs/2512.01801", datetime(2025, 12, 2), "[arXiv] We present GR-RL, a robotic learning framework that turns a generalist vision-language-action (VLA) policy into a highly capable specialist for long-horizon dexterous manipulation.", None),
        ("GR-3 Technical Report", "https://arxiv.org/pdf/2507.15493", datetime(2025, 7, 21), "[arXiv] We report our recent progress towards building generalist robot policies, the development of GR-3, a large-scale vision-language-action (VLA) model.", None),
        ("Dexterous Teleoperation of 20-DoF ByteDexter Hand via Human Motion Retargeting", "https://arxiv.org/abs/2507.03227", datetime(2025, 7, 4), "[arXiv] Replicating human-level dexterity remains a fundamental robotics challenge, requiring integrated solutions from mechatronic design to the control of high degree-of-freedom robotic hands.", None),
    ],
    "NVIDIA Blog": [
        ("NVIDIA Jetson Brings Agentic AI to the Physical World", "https://blogs.nvidia.com/blog/jetson-agentic-ai-physical-world/", datetime(2026, 6, 2), "At COMPUTEX, NVIDIA announced NVIDIA JetPack 7.2 and NemoClaw support on NVIDIA Jetson, bringing agentic AI skills to the physical world.", "https://blogs.nvidia.com/wp-content/uploads/2026/06/robotics-press-jetson-agentic-ready-cptx26-1920x1080-5180550.jpg"),
        ("NVIDIA Factory Operations Blueprint Gives Factories a New AI Brain", "https://blogs.nvidia.com/blog/factory-operations-fox-blueprint-ai-brain/", datetime(2026, 6, 1), "NVIDIA announced the Factory Operations Blueprint (FOX), a reference design for building an autonomous factory manager that unifies live machine signals into a decision layer.", "https://blogs.nvidia.com/wp-content/uploads/2026/05/robotics-factory-ai-computer-1280x680-5259650.jpg"),
        ("How Cosmos 3 Helps Physical AI Think Before It Acts", "https://blogs.nvidia.com/blog/cosmos-3-physical-ai-open-world-foundation-model/", datetime(2026, 6, 1), "Cosmos 3 is an open-world foundation model that helps physical AI reason before acting.", "https://blogs.nvidia.com/wp-content/uploads/2026/05/Featured-image.png"),
        ("NVIDIA Research Advances Robotics From Simulation to the Real World", "https://blogs.nvidia.com/blog/icra-research-robotics-simulation-to-real-world/", datetime(2026, 5, 28), "At ICRA, eight of NVIDIA Research's 28 accepted papers show how simulation-to-real transfer is becoming a foundation for generalizable, reliable embodied autonomy.", "https://blogs.nvidia.com/wp-content/uploads/2026/05/ICRA2026Blog-scaled.jpg"),
    ],
    "NVIDIA GEAR": [
        ("EgoScale", "https://research.nvidia.com/labs/gear/egoscale/", datetime(2026, 2, 19), "Scaling dexterous manipulation with diverse egocentric human data to unlock dexterous robot intelligence.", "https://research.nvidia.com/labs/gear/egoscale/videos/Pipeline.svg"),
        ("GR00T N1.6", "https://research.nvidia.com/labs/gear/gr00t-n1_6/", datetime(2025, 12, 15), "An improved open foundation model for generalist humanoid robots.", None),
        ("GR00T N1.5", "https://research.nvidia.com/labs/gear/gr00t-n1_5/", datetime(2025, 6, 11), "An improved open foundation model for generalist humanoid robots.", "https://research.nvidia.com/labs/gear/n1_5/architecture.svg"),
        ("FLARE", "https://research.nvidia.com/labs/gear/flare/", datetime(2025, 5, 22), "Robot learning with implicit world modeling via Future Latent Representation Alignment.", "https://research.nvidia.com/labs/gear/flare/videos/first_frame.jpg"),
        ("DreamGen", "https://research.nvidia.com/labs/gear/dreamgen/", datetime(2025, 5, 20), "Unlocking generalization in robot learning through video world models.", None),
    ],
    "X Square Robot": [
        ("X Square Robot Open-Sources WALL-WM, Shifting Robot World Modeling From Chunks to Events", "https://x2robot.com/en/news/6a195a10c0b46f559b2048af", datetime(2026, 5, 29), "X Square Robot open-sources WALL-WM, shifting robot world modeling from chunks to events.", None),
        ("X Square Robot Open-Sources Wall-OSS-0.5, Bringing Pretrained VLA Performance Closer to Post-Training Levels", "https://x2robot.com/en/news/6a17d057f182b06d9911e0a8", datetime(2026, 5, 28), "Wall-OSS-0.5 is a Vision-Language-Action (VLA) model designed for real-world robotic manipulation.", None),
        ("X Square Robot Named to Forbes China 2026 AI Tech Enterprises Top 50", "https://x2robot.com/en/news/6a0aaeb60ce54dd6a875e494", datetime(2026, 5, 18), "Forbes China recognized X Square Robot among China's top AI technology enterprises in the Embodied AI track.", None),
        ("X Square Robot Unveils New Embodied AI Model, Says Robots Will Arrive in Homes in 35 Days", "https://x2robot.com/en/news/69f3112631fe0538d4646e28", datetime(2026, 4, 21), "X Square Robot unveiled a next-generation embodied AI foundation model for home robots.", None),
        ("X Square Robot Hosts Inaugural EAIDC 2026, Advancing Real-World Deployment of Embodied AI", "https://x2robot.com/en/news/69f310b231fe0538d4646c1c", datetime(2026, 4, 2), "X Square Robot concluded the world's first Embodied AI Developers Conference (EAIDC 2026).", None),
    ],
    "Sanctuary AI": [
        ("Zeon Invests in Sanctuary AI and Partners to Advance Special Materials for Robotics", "https://www.sanctuary.ai/blog/zeon-sanctuary-ai-announcement", datetime(2026, 5, 26), "Zeon and Sanctuary AI will collaborate on rugged elastomeric components for robotics.", "https://images.squarespace-cdn.com/content/v1/66e8617ff9cbf43e43b040ef/1779752388791-1XYS8BOKNZV9VYK6JNZ4/Zeon+x+Sanctuary+Logo+Lockup.png?format=1500w"),
        ("Web Summit Reflections: Canada's Physical AI Moment Can't Wait", "https://www.sanctuary.ai/blog/web-summit-vancouver-2026", datetime(2026, 5, 20), "Reflections on Canada's Physical AI moment from Web Summit Vancouver 2026.", "https://images.squarespace-cdn.com/content/v1/66e8617ff9cbf43e43b040ef/1779217114733-2E8HVW0SIZVBFGC1INMZ/Frame+1000006202.png?format=1500w"),
        ("Sanctuary AI Demonstrates Zero-Shot In-Hand Manipulation on a Letter Cube", "https://www.sanctuary.ai/blog/in-hand-reorientation-policy-with-letter-cube", datetime(2026, 4, 1), "Sanctuary AI's proprietary hydraulic hand autonomously manipulates a letter cube with a zero-shot reorientation policy.", "https://images.squarespace-cdn.com/content/v1/66e8617ff9cbf43e43b040ef/1775060588888-2IQEF3SF3T05JICJ3YI8/Thumbnail-Cube-Reorientation-Policy-Still.png?format=1500w"),
    ],
    "Boston Dynamics": [
        ("Training a Humanoid Robot for Hard Work", "https://bostondynamics.com/blog/training-a-humanoid-robot-for-hard-work/", datetime.min, "How Boston Dynamics trains the Atlas humanoid robot for demanding real-world tasks.", "https://bostondynamics.com/wp-content/uploads/2026/05/training-fridge-tech-blog.jpg"),
        ("AIVI Learning Now Powered by Google Gemini Robotics", "https://bostondynamics.com/blog/aivi-learning-now-powered-google-gemini-robotics/", datetime.min, "Boston Dynamics' AIVI learning is now powered by Google Gemini Robotics.", None),
        ("Boston Dynamics and Google DeepMind Form New AI Partnership", "https://bostondynamics.com/blog/boston-dynamics-google-deepmind-form-new-ai-partnership/", datetime.min, "Boston Dynamics and Google DeepMind form a new partnership to advance robot AI.", None),
    ],
    "NVIDIA Cosmos Lab": [
        ("Cosmos 3", "https://research.nvidia.com/labs/cosmos-lab/cosmos3/", datetime.min, "A family of omnimodal world models designed to jointly process and generate language, image, video, audio, and action sequences.", None),
    ],
    "Agile Robots": [
        ("Simulating worlds: Agile Robots early access to NVIDIA Cosmos 3", "https://www.agile-robots.com/en/news/detail/simulating-worlds-agile-robots-early-access-to-nvidia-cosmos-3/", datetime(2026, 6, 1), "Agile Robots gains early access to NVIDIA Cosmos 3 for simulating worlds.", "https://www.agile-robots.com/media/_processed_/9/a/csm_AgileRobots-Blog-Data-Farm_cfab32960b.jpg"),
        ("Humanoid Agile ONE embodies Physical AI at Hannover Messe 2026", "https://www.agile-robots.com/en/news/detail/humanoid-agile-one-embodies-physical-ai-at-hannover-messe-2026/", datetime(2026, 4, 20), "The humanoid Agile ONE embodies Physical AI at Hannover Messe 2026.", "https://www.agile-robots.com/media/_processed_/6/e/csm_HMI_Messetag-1_2d3eab3dfc.jpg"),
        ("Agile Robots and Google DeepMind partner to bring intelligence to robotics", "https://www.agile-robots.com/en/news/detail/agile-robots-and-google-deepmind-partner-to-bring-intelligence-to-robotics/", datetime(2026, 3, 24), "Agile Robots and Google DeepMind partner to bring intelligence to robotics.", "https://www.agile-robots.com/media/_processed_/0/7/csm_AgileRobots_GDM_Partner_3d75d06884.jpg"),
        ("Physical AI - Digital intelligence, physical results", "https://www.agile-robots.com/en/news/detail/physical-ai-digital-intelligence-physical-results/", datetime(2026, 2, 10), "Physical AI: digital intelligence delivering physical results.", "https://www.agile-robots.com/media/_processed_/2/c/csm_AgileRobots-Blog-Physical-AI-009_9bc1c70fd4.jpeg"),
    ],
    "DexForce": [
        ("DexWorldModel: Causal Latent World Modeling towards Automated Learning of Embodied Tasks", "https://dexforce.com/technical-report/#/DexWorldModel", datetime.min, "DexWorldModel: causal latent world modeling towards automated learning of embodied tasks.", None),
        ("EmbodiChain", "https://dexforce.com/technical-report/#/EmbodiChain", datetime.min, "EmbodiChain: an automated, modular embodied intelligence platform to scale training and accelerate embodied AI learning.", None),
    ],
    "RL2 @ Georgia Tech": [
        ("KinDER: A Physical Reasoning Benchmark for Robot Learning and Planning", "https://prpl-group.com/kinder-site/", datetime(2026, 1, 1), "[RSS 2026] A benchmark for Kinematic and Dynamic Embodied Reasoning that targets physical reasoning challenges arising in robot learning and planning.", "https://rl2.cc.gatech.edu/assets/kinder_huang2026.png"),
        ("ReSteer: Quantifying and Refining the Steerability of Multitask Robot Policies", "https://resteer-vla.github.io/", datetime(2026, 1, 1), "[RSS 2026] A data-centric framework to quantify and improve the task steerability of multitask robot policies.", "https://rl2.cc.gatech.edu/assets/resteer_chen2026.png"),
        ("EgoVerse: An Egocentric Human Dataset for Robot Learning from Around the World", "https://egoverse.ai/", datetime(2026, 1, 1), "[RSS 2026] A consortium-driven cross-lab effort introducing a large-scale 1300+ hour diverse egocentric human dataset for robot learning.", None),
        ("Compositional Diffusion with Guided Search for Long-Horizon Planning", "https://cdgsearch.github.io/", datetime(2026, 1, 1), "[ICLR 2026] Inference time scaling of compositional diffusion planners with guided search. (Oral)", "https://rl2.cc.gatech.edu/assets/cdgs_mishra2026.png"),
        ("Compositional Visual Planning via Inference-Time Diffusion Scaling", "https://comp-visual-planning.github.io/", datetime(2026, 1, 1), "[ICLR 2026] An inference-time compositional sampling approach that scales to unseen and long-horizon tasks.", "https://rl2.cc.gatech.edu/assets/cvp_yixin2026.png"),
        ("EMMA: Scaling Mobile Manipulation via Egocentric Human Data", "https://ego-moma.github.io/", datetime(2025, 1, 1), "[IEEE RA-L 2025] Scaling mobile manipulation from co-training static robot data and egocentric human full-body data.", None),
        ("Generalizable Domain Adaptation for Sim-and-Real Policy Co-Training", "https://ot-sim2real.github.io/", datetime(2025, 1, 1), "[NeurIPS 2025] A sim-and-real co-training framework for learning generalizable manipulation policies.", "https://rl2.cc.gatech.edu/assets/ot_sim2real.png"),
        ("EgoBridge: Domain Adaptation for Generalizable Imitation from Egocentric Human Data", "https://ego-bridge.github.io/", datetime(2025, 1, 1), "[NeurIPS 2025] Joint observation-action domain adaptation using Optimal Transport to enable robot generalization from egocentric human data.", None),
        ("ImMimic: Cross-Domain Imitation from Human Videos via Mapping and Interpolation", "https://sites.google.com/view/immimic", datetime(2025, 1, 1), "[CoRL 2025] Embodiment-agnostic pipeline to learn from human videos. (Oral Presentation)", "https://rl2.cc.gatech.edu/assets/immimic.png"),
        ("SAIL: Faster-than-Demonstration Execution of Imitation Learning Policies", "https://nadunranawaka1.github.io/sail-policy/", datetime(2025, 1, 1), "[CoRL 2025] System to execute imitation learning policies faster than human demonstrations. (Oral Presentation)", "https://rl2.cc.gatech.edu/assets/sail.png"),
        ("EgoMimic: Scaling Imitation Learning through Egocentric Video", "https://egomimic.github.io/", datetime(2025, 1, 1), "[ICRA 2025] Robot Learning from Egocentric Human Data.", None),
    ],
    "Dexmal": [
        ("Realtime-VLA V2: Learning to Run VLAs Fast, Smooth, and Accurate", "https://arxiv.org/abs/2603.26360", datetime(2026, 5, 27), "A set of practical techniques to run a VLA-driven robot at impressive speed in real-world tasks requiring both accuracy and dexterity, spanning calibration, planning & control, and learning-based execution speed identification.", None),
        ("Realtime-VLA FLASH: Speculative Inference Framework for Diffusion-based VLAs", "https://arxiv.org/abs/2605.13778", datetime(2026, 5, 13), "A speculative inference framework that eliminates most full inference calls during replanning via a lightweight draft model with parallel verification and a phase-aware fallback mechanism.", None),
        ("GS-Playground: A High-Throughput Photorealistic Simulator for Vision-Informed Robot Learning", "https://arxiv.org/abs/2604.25459", datetime(2026, 4, 28), "A multi-modal simulation framework that integrates a novel parallel physics engine with batch 3D Gaussian Splatting rendering, achieving 10^4 FPS at 640x480 to accelerate large-scale visual RL.", None),
        ("SpatialActor: Exploring Disentangled Spatial Representations for Robust Robotic Manipulation", "https://arxiv.org/abs/2511.09555", datetime(2025, 11, 12), "A disentangled framework that decouples semantics and geometry, using a Semantic-guided Geometric Module and a Spatial Transformer for accurate 2D-3D mapping in robust robotic manipulation.", None),
        ("Running VLAs at Real-time Speed", "https://arxiv.org/abs/2510.26742", datetime(2025, 10, 30), "How to run a pi0-level multi-view VLA at 30Hz frame rate and up to 480Hz trajectory frequency on a single consumer GPU, enabling dynamic and real-time tasks previously thought unattainable for large VLAs.", None),
        ("IntentionVLA: Generalizable and Efficient Embodied Intention Reasoning for Human-Robot Interaction", "https://arxiv.org/abs/2510.07778", datetime(2025, 10, 9), "A VLA framework with curriculum training on intention inference, spatial grounding, and compact embodied reasoning, using reasoning outputs as contextual guidance for fast inference under indirect instructions.", None),
        ("MemoryVLA: Perceptual-Cognitive Memory In Vision-Language-Action Models For Robotic Manipulation", "https://arxiv.org/abs/2508.19236", datetime(2025, 8, 26), "A Cognition-Memory-Action framework for long-horizon manipulation with a Perceptual-Cognitive Memory Bank that stores low-level details and high-level semantics, adaptively fused with current working memory.", None),
    ],
    "XDOF": [
        ("Lowering the Noise Floor on Robot Data", "https://www.xdof.ai/blog/warp-rm", datetime(2026, 6, 30), "We gave a folding robot more demonstrations and it got worse. Chasing down why led to a way of teaching it to tell productive moments from dead time, with no labels.", None),
        ("The Robot That Learned to Grade Itself", "https://www.xdof.ai/blog/sarm2", datetime(2026, 6, 23), "Reward models are reshaping how machines learn to manipulate the world. SARM2 can grade dozens of tasks and turn raw demonstrations into policies that keep improving on their own.", None),
        ("ABC-130K: The largest open source teleoperation dataset", "https://www.xdof.ai/blog/abc-130k", datetime(2026, 6, 17), "130K+ episodes, 200 complex manipulation tasks. All on a low-cost bimanual rig. Fully open source under Apache 2.0.", None),
        ("Announcing XDOF", "https://www.xdof.ai/blog/announcing-xdof", datetime(2026, 6, 17), "XDOF builds world-class infrastructure for the most ambitious robotics builders. Join us on our mission to unlock abundant, useful embodied AI.", None),
    ],
}


# =============================================================================
# CORE DATA FETCHING
# =============================================================================

def fetch_blog_posts(source):
    """Fetch posts for a single source: try live scraper first, fall back to cached data."""
    company = source["name"]
    scraper = SCRAPERS.get(company)

    if scraper:
        try:
            posts = scraper(source)
            if posts and len(posts) > 0:
                logger.info(f"[{company}] Live scraping succeeded: {len(posts)} posts")
                return posts
            else:
                logger.warning(f"[{company}] Live scraping returned 0 posts, using fallback")
        except requests.exceptions.Timeout:
            logger.warning(f"[{company}] Request timed out after {REQUEST_TIMEOUT}s, using fallback")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"[{company}] Connection error: {e}, using fallback")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[{company}] HTTP error {e.response.status_code}: {e}, using fallback")
        except Exception as e:
            logger.error(f"[{company}] Scraping failed with unexpected error: {type(e).__name__}: {e}, using fallback")
    else:
        logger.warning(f"[{company}] No scraper configured, using fallback")

    # Fallback: use static data
    if company in FALLBACK_DATA:
        posts = []
        for item in FALLBACK_DATA[company]:
            title, url, date, summary, image = item[:5]
            posts.append({
                "title": title,
                "url": url,
                "date": date,
                "summary": summary,
                "image": image,
                "company": company,
            })
        logger.info(f"[{company}] Using fallback data: {len(posts)} posts")
        return posts

    return []


def get_all_posts(force_refresh=False):
    """Fetch posts from all sources concurrently, with caching."""
    global cached_posts, cache_timestamp

    with cache_lock:
        now = datetime.now()
        if not force_refresh and cache_timestamp and cached_posts:
            if (now - cache_timestamp).seconds < CACHE_DURATION:
                return cached_posts

    logger.info("Fetching posts from all sources...")
    all_posts = []

    with ThreadPoolExecutor(max_workers=len(BLOG_SOURCES)) as executor:
        futures = {executor.submit(fetch_blog_posts, source): source for source in BLOG_SOURCES}
        for future in as_completed(futures):
            source = futures[future]
            try:
                posts = future.result()
                # Add placeholder SVGs for posts without images, compress summaries
                for post in posts:
                    if not post.get("image"):
                        post["image"] = generate_placeholder_svg(post["title"], post["company"])
                    post["summary"] = compress_summary(post.get("summary", ""))
                all_posts.extend(posts)
            except Exception as e:
                logger.error(f"[{source['name']}] Future failed: {type(e).__name__}: {e}")

    all_posts.sort(key=lambda x: x["date"], reverse=True)

    # Deduplicate by (title, company)
    seen = set()
    unique_posts = []
    for post in all_posts:
        key = (post["title"].strip().lower(), post["company"])
        if key not in seen:
            seen.add(key)
            unique_posts.append(post)

    with cache_lock:
        cached_posts = unique_posts
        cache_timestamp = datetime.now()

    logger.info(f"Total: {len(unique_posts)} unique posts from {len(BLOG_SOURCES)} sources")
    return unique_posts


def get_by_company_dedup():
    """Get posts organized by company, removing duplicates preferring real images."""
    posts = get_all_posts()

    by_company = {}
    for post in posts:
        company = post["company"]
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(post)

    # Deduplicate within each company - use URL as unique key
    by_company_dedup = {}
    for company, company_posts in by_company.items():
        seen = {}
        for post in company_posts:
            url_key = post["url"].strip().lower()
            if url_key not in seen:
                seen[url_key] = post
            else:
                # If current has real image and existing doesn't, replace
                if has_real_image(post) and not has_real_image(seen[url_key]):
                    seen[url_key] = post

        by_company_dedup[company] = list(seen.values())

    # Order the company view alphabetically (A-Z) by company name.
    return {name: by_company_dedup[name] for name in sorted(by_company_dedup, key=str.lower)}


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Main route - shows all posts."""
    posts = get_all_posts()
    by_company = get_by_company_dedup()

    company_colors = {s["name"]: s["color"] for s in BLOG_SOURCES}

    return render_template(
        'index.html',
        posts=posts,
        by_company=by_company,
        company_colors=company_colors,
        companies=BLOG_SOURCES
    )


@app.route('/api/posts')
def api_posts():
    """API endpoint for posts."""
    posts = get_all_posts()
    return jsonify([{
        "title": p["title"],
        "url": p["url"],
        "date": p["date"].isoformat(),
        "summary": p.get("summary", ""),
        "image": p.get("image", ""),
        "company": p["company"]
    } for p in posts])


@app.route('/refresh')
def refresh():
    """Force refresh all data from live sources."""
    logger.info("Force refresh requested")
    posts = get_all_posts(force_refresh=True)
    return jsonify({"status": "ok", "posts_count": len(posts)})


# =============================================================================
# STARTUP
# =============================================================================

if __name__ == '__main__':
    print("Starting Embodied AI News Aggregator...")
    print(f"Configured {len(BLOG_SOURCES)} blog sources with live scrapers")
    print("Visit http://localhost:80 to view the news feed")
    app.run(debug=False, host='0.0.0.0', port=80)
