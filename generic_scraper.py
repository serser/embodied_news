"""
Deterministic generic scraper: RSS/Atom -> Next.js __NEXT_DATA__ -> HTML heuristics.

Tries each strategy in order. Returns a list of post dicts (same shape as
app.py scrapers) on the first strategy that yields >= MIN_ACCEPTABLE_POSTS
with real dates. Returns an empty list if all strategies fail - the caller
(admin route) then decides whether to invoke the LLM fallback.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 20
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml,application/atom+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MIN_ACCEPTABLE_POSTS = 3

RSS_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M:%S GMT",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]

HTML_DATE_FORMATS = [
    "%B %d, %Y", "%b %d, %Y",
    "%d %B %Y", "%d %b %Y",
    "%Y-%m-%d", "%m/%d/%Y",
    "%B %d %Y", "%b %d %Y",
]


def _make_request(url: str) -> requests.Response:
    r = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r


def _try_parse_date(text: str, formats: list[str]) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None


def _strip_ordinals(text: str) -> str:
    return re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text)


def _absolute_url(href: str, base_url: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url.rstrip("/") + "/", href.lstrip("./"))


def _looks_like_post_url(url: str, base_url: str) -> bool:
    """Filter out nav links, category pages, and off-site links."""
    if not url:
        return False
    try:
        base_host = urlparse(base_url).netloc
        url_host = urlparse(url).netloc
    except ValueError:
        return False
    if base_host and url_host and base_host != url_host:
        return False
    path = urlparse(url).path.strip("/")
    if not path or path in {"blog", "news", "research", "posts", "articles"}:
        return False
    if path.endswith(("/tag", "/category", "/author", "/page")):
        return False
    return True


def _has_enough_real_dates(posts: list[dict], threshold: float = 0.5) -> bool:
    if not posts:
        return False
    real = sum(1 for p in posts if p["date"] > datetime(1900, 1, 1))
    return real / len(posts) >= threshold


# =============================================================================
# STRATEGY 1: RSS / Atom
# =============================================================================

RSS_CANDIDATE_PATHS = [
    "/feed", "/feed/", "/rss", "/rss/", "/atom.xml", "/feed.xml",
    "/rss.xml", "/index.xml", "/blog/feed", "/blog/rss",
    "/blog/feed.xml", "/blog/rss.xml", "/news/feed", "/news/rss",
]


def _discover_rss_urls(html: str, page_url: str) -> list[str]:
    """Find RSS feeds via <link rel=alternate> and common paths."""
    urls = []
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link", rel="alternate"):
        t = (link.get("type") or "").lower()
        if "rss" in t or "atom" in t or "xml" in t:
            href = link.get("href")
            if href:
                urls.append(_absolute_url(href, page_url))

    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for path in RSS_CANDIDATE_PATHS:
        urls.append(origin + path)

    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _parse_rss(xml_text: str, feed_url: str, company: str) -> list[dict]:
    """Parse RSS 2.0 or Atom feeds. BeautifulSoup handles both."""
    soup = BeautifulSoup(xml_text, "xml")

    items = soup.find_all("item")
    is_atom = False
    if not items:
        items = soup.find_all("entry")
        is_atom = True
    if not items:
        return []

    posts = []
    for item in items:
        title_el = item.find("title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue

        if is_atom:
            link_el = item.find("link", attrs={"rel": "alternate"}) or item.find("link")
            url = link_el.get("href", "") if link_el else ""
        else:
            link_el = item.find("link")
            url = link_el.get_text(strip=True) if link_el else ""
        if not url:
            continue

        date = None
        for date_tag in ("pubDate", "published", "updated", "dc:date"):
            d_el = item.find(date_tag)
            if d_el:
                date = _try_parse_date(d_el.get_text(strip=True), RSS_DATE_FORMATS)
                if date:
                    break

        summary = ""
        for desc_tag in ("description", "summary", "content"):
            d_el = item.find(desc_tag)
            if d_el:
                raw = d_el.get_text(strip=True)
                summary = BeautifulSoup(raw, "html.parser").get_text(strip=True)
                if summary:
                    break

        image = None
        media = item.find("media:thumbnail") or item.find("media:content")
        if media:
            image = media.get("url")
        if not image:
            enc = item.find("enclosure")
            if enc and (enc.get("type") or "").startswith("image/"):
                image = enc.get("url")
        if not image and summary:
            match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
            if match:
                image = match.group(1)

        posts.append({
            "title": title,
            "url": url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    return posts


def try_rss(url: str, company: str) -> tuple[list[dict], str | None]:
    """Return (posts, feed_url_used) or ([], None)."""
    try:
        r = _make_request(url)
    except requests.RequestException as e:
        logger.info(f"[generic:rss] initial fetch failed for {url}: {e}")
        return [], None

    ctype = r.headers.get("Content-Type", "").lower()
    if any(t in ctype for t in ("xml", "rss", "atom")):
        posts = _parse_rss(r.text, url, company)
        if posts:
            logger.info(f"[generic:rss] direct feed hit at {url}: {len(posts)} posts")
            return posts, url

    candidates = _discover_rss_urls(r.text, url)
    for feed_url in candidates:
        try:
            fr = _make_request(feed_url)
        except requests.RequestException:
            continue
        fctype = fr.headers.get("Content-Type", "").lower()
        looks_xml = any(t in fctype for t in ("xml", "rss", "atom")) or fr.text.lstrip().startswith("<?xml")
        if not looks_xml:
            continue
        posts = _parse_rss(fr.text, feed_url, company)
        if len(posts) >= MIN_ACCEPTABLE_POSTS:
            logger.info(f"[generic:rss] discovered feed at {feed_url}: {len(posts)} posts")
            return posts, feed_url

    return [], None


# =============================================================================
# STRATEGY 2: Next.js __NEXT_DATA__
# =============================================================================

_NEXT_DATA_TITLE_KEYS = ("title", "articleTitle", "name", "heading", "headline")
_NEXT_DATA_DATE_KEYS = ("date", "publishedAt", "publicationDate", "publishDate", "createdAt", "pubDate", "published")
_NEXT_DATA_SLUG_KEYS = ("slug", "url", "path", "href", "permalink")
_NEXT_DATA_DESC_KEYS = ("description", "summary", "excerpt", "tldr", "subtitle", "subDesc")
_NEXT_DATA_IMAGE_KEYS = ("image", "thumbnail", "cover", "featuredImage", "heroImage", "largeImage", "coverImage")


def _walk_next_data(obj: Any, out: list[dict]) -> None:
    """Recursively collect any dict that has BOTH a title-ish and slug/url-ish key."""
    if isinstance(obj, dict):
        title_key = next((k for k in _NEXT_DATA_TITLE_KEYS if k in obj and isinstance(obj[k], str) and obj[k].strip()), None)
        slug_key = next((k for k in _NEXT_DATA_SLUG_KEYS if k in obj and isinstance(obj[k], str) and obj[k].strip()), None)
        if title_key and slug_key:
            out.append(obj)
        for v in obj.values():
            _walk_next_data(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_next_data(v, out)


def try_next_data(url: str, company: str, base_url: str) -> list[dict]:
    try:
        r = _make_request(url)
    except requests.RequestException as e:
        logger.info(f"[generic:next] fetch failed: {e}")
        return []

    soup = BeautifulSoup(r.content, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return []

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return []

    candidates: list[dict] = []
    _walk_next_data(data, candidates)

    seen_urls: set[str] = set()
    posts = []
    for item in candidates:
        title = next((item[k].strip() for k in _NEXT_DATA_TITLE_KEYS if k in item and isinstance(item[k], str) and item[k].strip()), "")
        slug = next((item[k].strip() for k in _NEXT_DATA_SLUG_KEYS if k in item and isinstance(item[k], str) and item[k].strip()), "")
        if not title or not slug or len(title) < 3:
            continue

        post_url = _absolute_url(slug, base_url) if slug.startswith("/") else (slug if slug.startswith("http") else _absolute_url("/" + slug.lstrip("/"), base_url))
        if not _looks_like_post_url(post_url, base_url):
            continue
        if post_url in seen_urls:
            continue
        seen_urls.add(post_url)

        date = None
        for k in _NEXT_DATA_DATE_KEYS:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                date = _try_parse_date(v, RSS_DATE_FORMATS + HTML_DATE_FORMATS)
                if date:
                    break

        summary = ""
        for k in _NEXT_DATA_DESC_KEYS:
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                summary = v.strip()
                break

        image = None
        for k in _NEXT_DATA_IMAGE_KEYS:
            v = item.get(k)
            if isinstance(v, str) and v.startswith(("http", "/")):
                image = _absolute_url(v, base_url) if v.startswith("/") else v
                break
            if isinstance(v, dict):
                for sub in ("src", "url", "href"):
                    sv = v.get(sub)
                    if isinstance(sv, str) and sv.startswith(("http", "/")):
                        image = _absolute_url(sv, base_url) if sv.startswith("/") else sv
                        break
                if image:
                    break

        posts.append({
            "title": title,
            "url": post_url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    if posts:
        logger.info(f"[generic:next] extracted {len(posts)} candidate posts from __NEXT_DATA__")
    return posts


# =============================================================================
# STRATEGY 3: HTML heuristics
# =============================================================================

def _find_date_in_text(text: str) -> datetime | None:
    if not text:
        return None
    text = _strip_ordinals(text)
    patterns = [
        (r"([A-Z][a-z]+\s+\d{1,2},\s*\d{4})", HTML_DATE_FORMATS),
        (r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})", HTML_DATE_FORMATS),
        (r"(\d{4}-\d{2}-\d{2})", ["%Y-%m-%d"]),
    ]
    for pat, fmts in patterns:
        m = re.search(pat, text)
        if m:
            dt = _try_parse_date(m.group(1), fmts)
            if dt:
                return dt
    return None


def try_html_heuristic(url: str, company: str, base_url: str) -> list[dict]:
    """Grab every <a> that looks like a post card. Rough but broadly applicable."""
    try:
        r = _make_request(url)
    except requests.RequestException as e:
        logger.info(f"[generic:html] fetch failed: {e}")
        return []

    soup = BeautifulSoup(r.content, "html.parser")

    for tag in soup.find_all(["nav", "header", "footer", "script", "style"]):
        tag.decompose()

    posts = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        post_url = _absolute_url(href, url)
        if not _looks_like_post_url(post_url, base_url):
            continue
        if post_url in seen_urls:
            continue

        heading = a.find(["h1", "h2", "h3", "h4"])
        if heading:
            title = heading.get_text(strip=True)
        else:
            title_attr = a.get("title") or a.get("aria-label") or ""
            title = title_attr.strip() or a.get_text(strip=True)
        if not title or len(title) < 6:
            continue

        seen_urls.add(post_url)

        date = None
        time_el = a.find("time")
        if time_el:
            dt_attr = time_el.get("datetime") or time_el.get_text(strip=True)
            date = _try_parse_date(dt_attr, RSS_DATE_FORMATS + HTML_DATE_FORMATS) or _find_date_in_text(dt_attr)
        if not date:
            date = _find_date_in_text(a.get_text(" ", strip=True))

        img = a.find("img")
        image = None
        if img:
            src = img.get("src") or img.get("data-src") or ""
            if src and not src.startswith("data:"):
                image = _absolute_url(src, base_url)
                if image and ".svg" in image.lower() and re.search(r"width=[12]\d(\D|$)", image):
                    image = None

        summary = ""
        for p in a.find_all("p"):
            t = p.get_text(strip=True)
            if t and t != title and len(t) > 20:
                summary = t
                break

        posts.append({
            "title": title,
            "url": post_url,
            "date": date or datetime.min,
            "summary": summary,
            "image": image,
            "company": company,
        })

    if posts:
        logger.info(f"[generic:html] harvested {len(posts)} candidate cards")
    return posts


# =============================================================================
# DISPATCH
# =============================================================================

def scrape_generic(source: dict) -> tuple[list[dict], str]:
    """Try each strategy in order. Return (posts, strategy_name).

    Accept a strategy's result when it yields >= MIN_ACCEPTABLE_POSTS AND at
    least half of them have real dates - low-quality output would just
    pollute the feed with datetime.min entries at the bottom.
    """
    company = source["name"]
    url = source["url"]
    base_url = source["base_url"]

    posts, feed_url = try_rss(url, company)
    if len(posts) >= MIN_ACCEPTABLE_POSTS and _has_enough_real_dates(posts):
        return posts, f"rss:{feed_url}"

    nd_posts = try_next_data(url, company, base_url)
    if len(nd_posts) >= MIN_ACCEPTABLE_POSTS and _has_enough_real_dates(nd_posts):
        return nd_posts, "next_data"

    html_posts = try_html_heuristic(url, company, base_url)
    if len(html_posts) >= MIN_ACCEPTABLE_POSTS and _has_enough_real_dates(html_posts):
        return html_posts, "html_heuristic"

    best_pool = [(len(posts), posts, "rss"), (len(nd_posts), nd_posts, "next_data"), (len(html_posts), html_posts, "html_heuristic")]
    best_pool.sort(key=lambda t: t[0], reverse=True)
    _, best, name = best_pool[0]
    return best, f"weak:{name}"


def extract_site_metadata(url: str) -> dict:
    """Pull <title>, og:site_name, and first color hint for the admin form.

    Used only when the user leaves the Name / Color inputs blank so we can
    prefill sensible defaults from the landing page.
    """
    out = {"suggested_name": "", "suggested_color": "#6366f1"}
    try:
        r = _make_request(url)
    except requests.RequestException:
        return out
    soup = BeautifulSoup(r.content, "html.parser")

    for og in ("og:site_name", "twitter:site"):
        el = soup.find("meta", attrs={"property": og}) or soup.find("meta", attrs={"name": og})
        if el and el.get("content"):
            out["suggested_name"] = el["content"].strip().lstrip("@")
            break
    if not out["suggested_name"]:
        t = soup.find("title")
        if t:
            out["suggested_name"] = t.get_text(strip=True).split("|")[0].split("-")[0].strip()

    theme = soup.find("meta", attrs={"name": "theme-color"})
    if theme and theme.get("content", "").startswith("#"):
        out["suggested_color"] = theme["content"].strip()

    return out
