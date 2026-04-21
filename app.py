#!/usr/bin/env python3
"""
Embodied AI News Aggregator - Live Scraping with Fallback
Fetches live data from 9 blog sources, falls back to cached data on failure.
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
    {"name": "NVIDIA GEAR", "url": "https://research.nvidia.com/labs/gear/", "base_url": "https://research.nvidia.com", "color": "#76b900"},
    {"name": "1X Technologies", "url": "https://www.1x.tech/discover", "base_url": "https://www.1x.tech", "color": "#000000"},
    {"name": "Agility Robotics", "url": "https://www.agilityrobotics.com/resources", "base_url": "https://www.agilityrobotics.com", "color": "#ff6b35"},
]

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


def scrape_nvidia_gear(source):
    """
    NVIDIA GEAR lab page lists research projects.
    The publications are client-rendered, but the main page lists projects
    with links that we can extract. We scrape the project listing from the
    SSR HTML on the lab homepage.
    """
    company = source["name"]
    base_url = source["base_url"]
    response = make_request(source["url"])
    soup = BeautifulSoup(response.content, 'html.parser')

    posts = []

    # Try __NEXT_DATA__ first (static export)
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    if next_data_script:
        try:
            next_data = json.loads(next_data_script.string)
            # Navigate to projects in the page props
            page_props = next_data.get('props', {}).get('pageProps', {})

            # Look for project data in all nested structures
            def find_projects(obj, depth=0):
                """Recursively search for project-like structures."""
                results = []
                if depth > 10:
                    return results
                if isinstance(obj, dict):
                    # Check if this dict looks like a project
                    if 'title' in obj and ('link' in obj or 'url' in obj or 'projectLink' in obj):
                        results.append(obj)
                    for v in obj.values():
                        results.extend(find_projects(v, depth + 1))
                elif isinstance(obj, list):
                    for item in obj:
                        results.extend(find_projects(item, depth + 1))
                return results

            projects = find_projects(next_data)
            for proj in projects:
                title = proj.get('title', '').strip()
                if not title or len(title) < 3:
                    continue
                url = proj.get('projectLink') or proj.get('link') or proj.get('url', '')
                if not url:
                    continue

                posts.append({
                    "title": title,
                    "url": url,
                    "date": datetime.min,
                    "summary": proj.get('description', '') or proj.get('conference', ''),
                    "image": None,
                    "company": company,
                })

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"[NVIDIA GEAR] Failed to parse __NEXT_DATA__: {e}")

    # HTML fallback: scrape project links from the page
    if not posts:
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            # Look for project links (external research pages, arxiv, github pages)
            if not any(domain in href for domain in ['github.io', 'arxiv.org', 'developer.nvidia.com', 'nvidia.com/labs/gear']):
                continue

            text = a_tag.get_text(strip=True)
            if not text or len(text) < 3 or len(text) > 200:
                continue

            # Skip navigation/footer links
            parent = a_tag.find_parent(['nav', 'footer', 'header'])
            if parent:
                continue

            posts.append({
                "title": text,
                "url": href,
                "date": datetime.min,
                "summary": "",
                "image": None,
                "company": company,
            })

    # Deduplicate by URL
    seen = set()
    unique = []
    for p in posts:
        if p["url"] not in seen:
            seen.add(p["url"])
            unique.append(p)
    posts = unique

    logger.info(f"[NVIDIA GEAR] Scraped {len(posts)} projects/publications")
    return posts


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
    "NVIDIA GEAR": scrape_nvidia_gear,
    "1X Technologies": scrape_1x_technologies,
    "Agility Robotics": scrape_agility_robotics,
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
    "NVIDIA GEAR": [
        ("Project GR00T: Foundation Model for Humanoid Robots", "https://developer.nvidia.com/project-gr00t", datetime(2024, 3, 18), "NVIDIA's foundation model for building general-purpose humanoid robots.", None),
        ("Eureka: Human-Level Reward Design via Coding LLMs", "https://eureka-research.github.io/", datetime(2023, 10, 15), "NVIDIA's AI agent that writes reward code for robot training.", None),
        ("Voyager: Open-Ended Embodied Agent with LLMs", "https://voyager.minedojo.org/", datetime(2023, 5, 15), "An open-ended embodied agent that uses LLMs for lifelong learning in Minecraft.", None),
        ("MimicPlay: Long-Horizon Imitation Learning", "https://mimic-play.github.io/", datetime(2023, 3, 20), "Learning long-horizon imitation learning from human videos.", None),
        ("VIMA: Robot Manipulation with Multimodal Prompts", "https://vimalabs.github.io/", datetime(2023, 2, 10), "Generalist robot manipulation with multimodal prompt understanding.", None),
        ("MineDojo: Open-Ended Embodied Agents", "https://minedojo.org/", datetime(2022, 10, 20), "Building open-ended embodied agents in Minecraft using internet knowledge.", None),
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

    with ThreadPoolExecutor(max_workers=9) as executor:
        futures = {executor.submit(fetch_blog_posts, source): source for source in BLOG_SOURCES}
        for future in as_completed(futures):
            source = futures[future]
            try:
                posts = future.result()
                # Add placeholder SVGs for posts without images
                for post in posts:
                    if not post.get("image"):
                        post["image"] = generate_placeholder_svg(post["title"], post["company"])
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

    return by_company_dedup


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
