#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask app for displaying 36Kr news about Chinese robotics companies.
Timeline view and company view for robotics news.

Scrapes 36Kr articles via their search page for each company.
Falls back to demo data when scraping is unavailable.
"""

from flask import Flask, render_template_string, jsonify
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, parse_qs, urlparse
import threading
import time
import re
import json
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

# Set to False to use only demo data (no network requests)
ENABLE_LIVE_SEARCH = True

# How many companies to scrape concurrently (keep low to avoid rate limiting)
MAX_WORKERS = 3

# Request settings
REQUEST_TIMEOUT = 15

# Delay between search requests to avoid rate-limiting (seconds)
SEARCH_DELAY = 2.0
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# Only scrape the most notable companies (reduces load and rate-limiting risk)
# The full list is kept in COMPANIES for display, but only these are actively scraped
PRIORITY_COMPANIES = [
    "宇树科技", "智元", "优必选", "小米机器人", "傅利叶智能", "达闼科技",
    "银河通用", "星动纪元", "极智嘉", "思灵机器人", "逐际动力", "开普勒智能",
    "云深处科技", "越疆机器人", "星尘智能", "擎朗智能", "小鹏", "加速进化",
    "智身科技", "北京人形机器人创新中心",
]

# Company list with colors
COMPANIES = [
    {"name": "理工华汇", "color": "#FF6B6B"},
    {"name": "钢铁侠科技", "color": "#4ECDC4"},
    {"name": "极智嘉", "color": "#45B7D1"},
    {"name": "伟景智能", "color": "#96CEB4"},
    {"name": "睿尔曼智能", "color": "#FFEAA7"},
    {"name": "思灵机器人", "color": "#DDA0DD"},
    {"name": "月泉仿生", "color": "#98D8C8"},
    {"name": "深谋科技", "color": "#F7DC6F"},
    {"name": "星动纪元", "color": "#BB8FCE"},
    {"name": "银河通用", "color": "#85C1E9"},
    {"name": "松延动力", "color": "#F8B500"},
    {"name": "加速进化", "color": "#00CED1"},
    {"name": "星海图", "color": "#FF69B4"},
    {"name": "北京人形机器人创新中心", "color": "#32CD32"},
    {"name": "灵宝机器人", "color": "#FF8C00"},
    {"name": "源络科技", "color": "#8A2BE2"},
    {"name": "智身科技", "color": "#00FA9A"},
    {"name": "小米机器人", "color": "#FF4500"},
    {"name": "方舟无限", "color": "#1E90FF"},
    {"name": "长兴动力", "color": "#7B68EE"},
    {"name": "灵生科技", "color": "#3CB371"},
    {"name": "极佳视界", "color": "#FF6347"},
    {"name": "动易科技", "color": "#4682B4"},
    {"name": "阿米奥机器人", "color": "#D2691E"},
    {"name": "灵初智能", "color": "#8B008B"},
    {"name": "中科第五纪", "color": "#2E8B57"},
    {"name": "维他动力", "color": "#CD853F"},
    {"name": "灵御智能", "color": "#6B8E23"},
    {"name": "智往未来", "color": "#483D8B"},
    {"name": "无界动力", "color": "#20B2AA"},
    {"name": "深度机智", "color": "#D2B48C"},
    {"name": "大咖机器人", "color": "#008B8B"},
    {"name": "视界求索", "color": "#B8860B"},
    {"name": "擎朗智能", "color": "#9ACD32"},
    {"name": "节卡机器人", "color": "#6A5ACD"},
    {"name": "傅利叶智能", "color": "#FF7F50"},
    {"name": "达闼科技", "color": "#6495ED"},
    {"name": "鲸鱼机器人", "color": "#DC143C"},
    {"name": "傲鲨智能", "color": "#00FFFF"},
    {"name": "钛虎机器人", "color": "#8B4513"},
    {"name": "仙工智能", "color": "#A0522D"},
    {"name": "卓益得机器人", "color": "#2F4F4F"},
    {"name": "清宝机器人", "color": "#556B2F"},
    {"name": "半醒科技", "color": "#FFA500"},
    {"name": "智元", "color": "#800080"},
    {"name": "开普勒智能", "color": "#228B22"},
    {"name": "青心意创", "color": "#A52A2A"},
    {"name": "人形机器人（上海）有限公司", "color": "#5F9EA0"},
    {"name": "如身机器人", "color": "#D2B48C"},
    {"name": "矩阵超智", "color": "#008080"},
    {"name": "智可派机器人", "color": "#FF0000"},
    {"name": "无限工坊机器人", "color": "#000080"},
    {"name": "首形科技", "color": "#808000"},
    {"name": "镜识科技", "color": "#800000"},
    {"name": "灵波科技", "color": "#191970"},
    {"name": "它石智航", "color": "#2F2F2F"},
    {"name": "萝博派对", "color": "#483D8B"},
    {"name": "未来不远", "color": "#8B0000"},
    {"name": "浩海星空", "color": "#0000CD"},
    {"name": "优必选", "color": "#FF1493"},
    {"name": "越疆机器人", "color": "#00FA9A"},
    {"name": "乐聚机器人", "color": "#8B4789"},
    {"name": "普渡科技", "color": "#4B0082"},
    {"name": "大象机器人", "color": "#9370DB"},
    {"name": "优艾智合", "color": "#3CB371"},
    {"name": "卧安机器人", "color": "#FF8C69"},
    {"name": "腾讯 Robotics 实验室", "color": "#1E90FF"},
    {"name": "跨维智能", "color": "#DAA520"},
    {"name": "帕西尼感知", "color": "#B22222"},
    {"name": "星尘智能", "color": "#FF8C00"},
    {"name": "逐际动力", "color": "#8B6914"},
    {"name": "众擎机器人", "color": "#5F9EA0"},
    {"name": "智平方", "color": "#CD5C5C"},
    {"name": "戴盟机器人", "color": "#32CD32"},
    {"name": "自变量机器人", "color": "#E9967A"},
    {"name": "灵锶智能", "color": "#8FBC8F"},
    {"name": "若愚科技", "color": "#9932CC"},
    {"name": "数字华夏", "color": "#8B008B"},
    {"name": "鹿明机器人", "color": "#8B4500"},
    {"name": "赛博格", "color": "#6E7B59"},
    {"name": "智动未来", "color": "#B0C4DE"},
    {"name": "妙动科技", "color": "#7FFFD4"},
    {"name": "三号宇宙", "color": "#AFAFAF"},
    {"name": "塔克斯机器人", "color": "#D2691E"},
    {"name": "超维动力", "color": "#FF7F24"},
    {"name": "领益机器人", "color": "#C71585"},
    {"name": "宇树科技", "color": "#00FF7F"},
    {"name": "蓝芯机器人", "color": "#DC143C"},
    {"name": "海康机器人", "color": "#00CED1"},
    {"name": "云深处科技", "color": "#FF6A6A"},
    {"name": "西湖机器人", "color": "#4A4A4A"},
    {"name": "五八智能", "color": "#9B59B6"},
    {"name": "图睿智能", "color": "#3498DB"},
    {"name": "原力无限", "color": "#E74C3C"},
    {"name": "智澄 AI", "color": "#2ECC71"},
    {"name": "千寻智能", "color": "#E67E22"},
    {"name": "行思无界", "color": "#1ABC9C"},
    {"name": "纽鼐机器人", "color": "#9B59B6"},
    {"name": "穿山甲机器人", "color": "#34495E"},
    {"name": "云幕智造", "color": "#16A085"},
    {"name": "优理奇机器人", "color": "#27AE60"},
    {"name": "普罗宇宙", "color": "#2980B9"},
    {"name": "双子智擎", "color": "#8E44AD"},
    {"name": "星工聚将", "color": "#F39C12"},
    {"name": "小鹏", "color": "#C0392B"},
    {"name": "广汽集团", "color": "#7D3C98"},
    {"name": "高擎机电", "color": "#2C3E50"},
    {"name": "富唯智能", "color": "#1A5276"},
    {"name": "未来动力", "color": "#148F77"},
    {"name": "里工实业", "color": "#AF7AC5"},
    {"name": "斯帝尔科技", "color": "#F4D03F"},
    {"name": "均普智能", "color": "#E59866"},
    {"name": "PNDbotics", "color": "#82E0AA"},
    {"name": "浙江人形机器人创新中心", "color": "#FAD7A0"},
    {"name": "无论科技", "color": "#ABEBC6"},
    {"name": "中科灵犀", "color": "#D2B4DE"},
    {"name": "聆动通用", "color": "#AED6F1"},
    {"name": "零次方", "color": "#F5B7B1"},
    {"name": "天创智能", "color": "#D5F5E3"},
    {"name": "埃斯顿酷卓", "color": "#FCF3CF"},
    {"name": "中科硅纪", "color": "#D7BDE2"},
    {"name": "箸境智能", "color": "#A3E4D7"},
    {"name": "斯坦德", "color": "#FAD7A0"},
    {"name": "无界探索", "color": "#EDBB99"},
    {"name": "魔法原子", "color": "#D4E6F1"},
    {"name": "启智机器人", "color": "#EDBB99"},
    {"name": "墨甲智创", "color": "#A9DFBF"},
    {"name": "光谷华汇", "color": "#F5EEF8"},
    {"name": "格蓝若机器人", "color": "#FCF3CF"},
    {"name": "光谷东智", "color": "#E8DAEF"},
    {"name": "荆楚机器人", "color": "#D4EFDF"},
    {"name": "阿加犀智能", "color": "#FADBD8"},
    {"name": "四川具身人形机器人", "color": "#D6EAF8"},
    {"name": "阿瑞斯动力", "color": "#D1F2EB"},
    {"name": "天太机器人", "color": "#FCF3CF"},
    {"name": "美的", "color": "#EBDEF0"},
    {"name": "超能机器人", "color": "#F9E79F"},
    {"name": "比邻星科技", "color": "#F5CBA7"},
    {"name": "天链机器人", "color": "#EDBB99"},
    {"name": "阿童木机器人", "color": "#D7BDE2"},
    {"name": "优宝特机器人", "color": "#C39BD3"},
    {"name": "珞石机器人", "color": "#AF7AC5"},
    {"name": "有恰科技", "color": "#7D3C98"},
]

COMPANY_COLOR_MAP = {c["name"]: c["color"] for c in COMPANIES}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_company_color(company_name):
    """Get color for a company."""
    return COMPANY_COLOR_MAP.get(company_name, "#808080")


def parse_date(date_str):
    """Parse date string to datetime object."""
    if not date_str:
        return datetime.min

    date_str = date_str.strip()
    date_formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y年%m月%d日",
        "%Y/%m/%d",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try to extract date pattern from text like "2025-03-15" embedded in strings
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    return datetime.min


def parse_relative_time(text):
    """Parse relative time strings like '3小时前', '2天前' into datetime."""
    if not text:
        return None

    now = datetime.now()
    text = text.strip()

    patterns = [
        (r'(\d+)\s*分钟前', lambda m: now.replace(minute=max(0, now.minute - int(m.group(1))))),
        (r'(\d+)\s*小时前', lambda m: now.replace(hour=max(0, now.hour - int(m.group(1))))),
        (r'(\d+)\s*天前', lambda m: datetime(now.year, now.month, max(1, now.day - int(m.group(1))))),
    ]

    for pattern, handler in patterns:
        match = re.match(pattern, text)
        if match:
            try:
                return handler(match)
            except (ValueError, OverflowError):
                return now

    # If it looks like a date string, try direct parsing
    return parse_date(text) if parse_date(text) != datetime.min else None


# =============================================================================
# 36KR SCRAPING
# =============================================================================

def scrape_36kr_for_company(company_name):
    """
    Scrape 36Kr articles for a specific company.

    36Kr search page is a SPA with encrypted initialState, so direct scraping
    is not feasible. Instead we use DuckDuckGo HTML search (no JS required)
    with site:36kr.com to find articles about each company.
    """
    articles = []
    color = get_company_color(company_name)

    try:
        # Use DuckDuckGo HTML search for 36Kr articles
        # Try multiple query variations for best coverage
        queries = [
            f'site:36kr.com {company_name}',
            f'36kr.com {company_name} 机器人',
        ]

        soup = None
        for query in queries:
            search_url = f'https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}'
            response = requests.get(
                search_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
                timeout=REQUEST_TIMEOUT,
            )

            # Check for rate-limiting (DDG returns 202 with CAPTCHA)
            if response.status_code == 202:
                logger.warning(f"[36Kr] Rate-limited by search engine for {company_name}")
                return articles

            response.raise_for_status()
            candidate = BeautifulSoup(response.content, 'html.parser')

            # Check for bot detection page
            if 'bots use DuckDuckGo' in candidate.get_text():
                logger.warning(f"[36Kr] Bot detection triggered for {company_name}")
                return articles

            # Count 36kr results
            kr_count = sum(1 for d in candidate.find_all('div', class_='result')
                           if d.find('a', class_='result__a') and '36kr.com' in str(d))
            if kr_count > 0:
                soup = candidate
                break

            # Small delay before trying next query
            time.sleep(SEARCH_DELAY)

        if soup is None:
            logger.info(f"[36Kr] No results found for {company_name}")
            return articles

        seen_urls = set()
        for result in soup.find_all('div', class_='result'):
            # Title and link
            title_el = result.find('a', class_='result__a')
            if not title_el:
                continue

            # Extract the actual URL from DuckDuckGo redirect
            raw_href = title_el.get('href', '')
            link = raw_href
            if 'duckduckgo.com/l/' in raw_href:
                parsed_qs = parse_qs(urlparse(raw_href).query)
                if 'uddg' in parsed_qs:
                    link = unquote(parsed_qs['uddg'][0])

            # Only keep 36kr.com article links (not mobile duplicates)
            if '36kr.com/p/' not in link:
                continue
            # Normalize to www.36kr.com (skip m.36kr.com duplicates)
            link = re.sub(r'https?://m\.36kr\.com/', 'https://www.36kr.com/', link)
            if link in seen_urls:
                continue
            seen_urls.add(link)

            title = title_el.get_text(strip=True)
            # Clean up title - remove "- 36氪" or "- 36Kr" suffix
            title = re.sub(r'\s*[-|]\s*36[氪Kk]r?.*$', '', title).strip()
            if not title or len(title) < 5:
                continue

            # Description/snippet
            snippet_el = result.find('a', class_='result__snippet')
            description = ""
            if snippet_el:
                description = snippet_el.get_text(strip=True)[:200]

            # Try to extract date from snippet text
            date_str = ""
            full_text = result.get_text()
            date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', full_text)
            if date_match:
                date_str = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"
            else:
                date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', full_text)
                if date_match:
                    date_str = date_match.group(1).replace('/', '-')

            articles.append({
                "title": title,
                "link": link,
                "description": description,
                "date": date_str,
                "company": company_name,
                "color": color,
            })

        logger.info(f"[36Kr] Found {len(articles)} articles for {company_name}")

    except requests.exceptions.Timeout:
        logger.warning(f"[36Kr] Timeout searching for {company_name}")
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"[36Kr] Connection error for {company_name}: {e}")
    except Exception as e:
        logger.error(f"[36Kr] Error searching for {company_name}: {type(e).__name__}: {e}")

    return articles


# =============================================================================
# DEMO DATA (FALLBACK)
# =============================================================================

def get_demo_data():
    """Generate demo data for the app (used when live search is disabled or fails)."""
    demo_articles = [
        {
            "title": "宇树科技发布新一代四足机器人Go2",
            "link": "https://www.36kr.com/p/123456",
            "description": "宇树科技近日发布了其新一代四足机器人产品Go2，具备更强大的运动能力和智能感知系统。",
            "date": "2024-03-10",
            "company": "宇树科技",
            "color": "#00FF7F"
        },
        {
            "title": "智元机器人完成新一轮数亿元融资",
            "link": "https://www.36kr.com/p/234567",
            "description": "人形机器人公司智元机器人宣布完成数亿元融资，将用于加速产品研发和市场拓展。",
            "date": "2024-03-09",
            "company": "智元",
            "color": "#800080"
        },
        {
            "title": "优必选Q4财报：营收同比增长40%",
            "link": "https://www.36kr.com/p/345678",
            "description": "优必选发布2023年第四季度财报，显示营收持续增长，人形机器人业务成为新的增长引擎。",
            "date": "2024-03-08",
            "company": "优必选",
            "color": "#FF1493"
        },
        {
            "title": "小米发布全尺寸人形机器人CyberOne",
            "link": "https://www.36kr.com/p/456789",
            "description": "小米在年度发布会上展示了新一代全尺寸人形机器人CyberOne，展现强大的运动控制能力。",
            "date": "2024-03-07",
            "company": "小米机器人",
            "color": "#FF4500"
        },
        {
            "title": "思灵机器人获评年度最具创新力企业",
            "link": "https://www.36kr.com/p/567890",
            "description": "思灵机器人凭借其在工业机器人领域的创新技术获得行业权威评选认可。",
            "date": "2024-03-06",
            "company": "思灵机器人",
            "color": "#DDA0DD"
        },
        {
            "title": "极智嘉推出新一代仓储机器人系统",
            "link": "https://www.36kr.com/p/678901",
            "description": "极智嘉发布了其新一代仓储物流机器人解决方案，大幅提升仓储作业效率。",
            "date": "2024-03-05",
            "company": "极智嘉",
            "color": "#45B7D1"
        },
        {
            "title": "星动纪元发布具身大模型",
            "link": "https://www.36kr.com/p/789012",
            "description": "星动纪元发布了基于具身智能的多模态大模型，赋能人形机器人自主决策能力。",
            "date": "2024-03-04",
            "company": "星动纪元",
            "color": "#BB8FCE"
        },
        {
            "title": "达闼科技获批国家重点研发计划",
            "link": "https://www.36kr.com/p/890123",
            "description": "达闼科技作为牵头单位获批国家重点研发计划，推动云端机器人技术发展。",
            "date": "2024-03-03",
            "company": "达闼科技",
            "color": "#6495ED"
        },
        {
            "title": "傅利叶智能发布通用人形机器人GR-1",
            "link": "https://www.36kr.com/p/901234",
            "description": "傅利叶智能发布了其通用人形机器人GR-1，具备全身运动控制和多模态感知能力。",
            "date": "2024-03-02",
            "company": "傅利叶智能",
            "color": "#FF7F50"
        },
        {
            "title": "银河通用完成天使轮融资",
            "link": "https://www.36kr.com/p/012345",
            "description": "专注于轮式人形机器人的银河通用机器人完成天使轮融资，加速产品落地。",
            "date": "2024-03-01",
            "company": "银河通用",
            "color": "#85C1E9"
        },
        {
            "title": "云深处科技发布绝影X30四足机器人",
            "link": "https://www.36kr.com/p/112233",
            "description": "云深处科技发布了新一代四足机器人绝影X30，适用于复杂地形作业场景。",
            "date": "2024-02-28",
            "company": "云深处科技",
            "color": "#FF6A6A"
        },
        {
            "title": "越疆机器人发布协作机械臂新品",
            "link": "https://www.36kr.com/p/223344",
            "description": "越疆机器人发布了其新一代协作机械臂产品，适用于更广泛的工业和服务场景。",
            "date": "2024-02-27",
            "company": "越疆机器人",
            "color": "#00FA9A"
        },
    ]

    demo_articles.sort(key=lambda x: parse_date(x["date"]), reverse=True)

    company_groups = {}
    for article in demo_articles:
        company = article["company"]
        if company not in company_groups:
            company_groups[company] = {
                "name": company,
                "color": article["color"],
                "articles": []
            }
        company_groups[company]["articles"].append(article)

    return {
        "articles": demo_articles,
        "company_groups": list(company_groups.values())
    }


# =============================================================================
# CORE DATA FETCHING
# =============================================================================

cache_lock = threading.RLock()
news_cache = {}
cache_timestamp = None
CACHE_DURATION = 3600  # 1 hour


def get_all_news(force_refresh=False):
    """Get news for all companies. Tries live search first, falls back to demo data."""
    global news_cache, cache_timestamp

    current_time = time.time()

    # Use cache if fresh
    with cache_lock:
        if news_cache and not force_refresh and cache_timestamp:
            if current_time - cache_timestamp < CACHE_DURATION:
                return news_cache

    if not ENABLE_LIVE_SEARCH:
        logger.info("Live search disabled, using demo data")
        result = get_demo_data()
        with cache_lock:
            news_cache = result
            cache_timestamp = current_time
        return result

    logger.info(f"Starting live 36Kr search for {len(PRIORITY_COMPANIES)} priority companies...")
    all_articles = []
    companies_with_results = 0
    rate_limited = False

    # Process companies sequentially with delays to avoid rate-limiting
    for i, company_name in enumerate(PRIORITY_COMPANIES):
        if rate_limited:
            logger.warning(f"[36Kr] Stopping early due to rate limiting (processed {i}/{len(PRIORITY_COMPANIES)})")
            break

        try:
            articles = scrape_36kr_for_company(company_name)
            if articles:
                all_articles.extend(articles)
                companies_with_results += 1
            # Add delay between companies to avoid triggering bot detection
            if i < len(PRIORITY_COMPANIES) - 1:
                time.sleep(SEARCH_DELAY)
        except Exception as e:
            if 'rate' in str(e).lower() or 'bot' in str(e).lower():
                rate_limited = True
            logger.error(f"[36Kr] Error for {company_name}: {type(e).__name__}: {e}")

    logger.info(f"Live search complete: {len(all_articles)} articles from {companies_with_results} companies")

    # If live search found very few results, supplement with demo data
    if len(all_articles) < 3:
        logger.warning("Live search returned too few results, supplementing with demo data")
        demo = get_demo_data()
        demo_articles = demo["articles"]
        # Add demo articles that don't conflict with live results
        live_links = {a["link"] for a in all_articles}
        for article in demo_articles:
            if article["link"] not in live_links:
                all_articles.append(article)

    # Sort by date
    all_articles.sort(key=lambda x: parse_date(x.get("date", "")), reverse=True)

    # Build company groups
    company_groups = {}
    for article in all_articles:
        company = article["company"]
        if company not in company_groups:
            company_groups[company] = {
                "name": company,
                "color": article.get("color", get_company_color(company)),
                "articles": []
            }
        company_groups[company]["articles"].append(article)

    result = {
        "articles": all_articles,
        "company_groups": list(company_groups.values()),
        "live_search": True,
        "sources_count": companies_with_results,
    }

    with cache_lock:
        news_cache = result
        cache_timestamp = current_time

    return result


# =============================================================================
# HTML TEMPLATE
# =============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>中国机器人公司新闻 - 36Kr</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            padding: 30px;
        }

        h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
        }

        .tabs {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .tab-btn {
            padding: 12px 30px;
            font-size: 1.1rem;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            transition: all 0.3s ease;
        }

        .tab-btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }

        .tab-btn.active {
            background: white;
            color: #667eea;
            font-weight: bold;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Status bar */
        .status-bar {
            background: rgba(255, 255, 255, 0.15);
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.9rem;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }

        .status-dot.live { background: #00ff88; }
        .status-dot.demo { background: #ffaa00; }

        /* Timeline View */
        .timeline {
            position: relative;
            padding-left: 30px;
        }

        .timeline::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 2px;
        }

        .timeline-item {
            position: relative;
            margin-bottom: 25px;
            padding: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }

        .timeline-item:hover {
            transform: translateX(10px);
        }

        .timeline-item::before {
            content: '';
            position: absolute;
            left: -34px;
            top: 25px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 3px solid white;
        }

        .timeline-date {
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 8px;
        }

        .timeline-title {
            font-size: 1.2rem;
            color: #333;
            margin-bottom: 8px;
            font-weight: 600;
        }

        .timeline-title a {
            color: inherit;
            text-decoration: none;
        }

        .timeline-title a:hover {
            color: #667eea;
        }

        .timeline-desc {
            font-size: 0.95rem;
            color: #666;
            margin-bottom: 12px;
            line-height: 1.5;
        }

        .timeline-company {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.85rem;
            color: white;
        }

        /* Company View */
        .company-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }

        .company-card {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }

        .company-header {
            padding: 15px 20px;
            color: white;
            font-size: 1.1rem;
            font-weight: 600;
        }

        .company-articles {
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
        }

        .company-article {
            padding: 12px 0;
            border-bottom: 1px solid #eee;
        }

        .company-article:last-child {
            border-bottom: none;
        }

        .company-article-title {
            font-size: 0.95rem;
            margin-bottom: 6px;
        }

        .company-article-title a {
            color: #333;
            text-decoration: none;
        }

        .company-article-title a:hover {
            color: #667eea;
        }

        .company-article-meta {
            font-size: 0.8rem;
            color: #999;
        }

        .company-article-desc {
            font-size: 0.85rem;
            color: #666;
            margin-top: 6px;
            line-height: 1.4;
        }

        .no-news {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.1rem;
        }

        .refresh-btn {
            display: inline-block;
            padding: 8px 20px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s ease;
        }

        .refresh-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        .refresh-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        @media (max-width: 768px) {
            .company-grid {
                grid-template-columns: 1fr;
            }

            h1 {
                font-size: 1.8rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>中国机器人公司新闻</h1>
            <p class="subtitle">数据来源: 36Kr | 共 {{ companies|length }} 家公司 | {{ articles|length }} 篇文章</p>
        </header>

        <div class="status-bar">
            {% if is_live %}
                <span><span class="status-dot live"></span> 实时数据</span>
                <span>已从 {{ sources_count }} 个来源获取新闻</span>
            {% else %}
                <span><span class="status-dot demo"></span> 演示数据</span>
                <span>设置 ENABLE_LIVE_SEARCH = True 以获取实时新闻</span>
            {% endif %}
            <span>缓存有效期: 1小时</span>
        </div>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('timeline', this)">时间线视图</button>
            <button class="tab-btn" onclick="switchTab('company', this)">公司视图</button>
            <button class="refresh-btn" id="refresh-btn" onclick="refreshNews()">刷新数据</button>
        </div>

        <div id="timeline" class="tab-content active">
            {% if articles %}
                <div class="timeline">
                    {% for article in articles %}
                        <div class="timeline-item" style="--company-color: {{ article.color }}">
                            <div class="timeline-date">{{ article.date }}</div>
                            <div class="timeline-title">
                                <a href="{{ article.link }}" target="_blank" rel="noopener">{{ article.title }}</a>
                            </div>
                            {% if article.description %}
                                <div class="timeline-desc">{{ article.description }}</div>
                            {% endif %}
                            <span class="timeline-company" style="background-color: {{ article.color }}">{{ article.company }}</span>
                        </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="no-news">
                    <p>暂无新闻数据</p>
                    <p>请点击"刷新数据"按钮</p>
                </div>
            {% endif %}
        </div>

        <div id="company" class="tab-content">
            {% if company_groups %}
                <div class="company-grid">
                    {% for group in company_groups %}
                        {% if group.articles %}
                            <div class="company-card">
                                <div class="company-header" style="background-color: {{ group.color }}">
                                    {{ group.name }} ({{ group.articles|length }}篇)
                                </div>
                                <div class="company-articles">
                                    {% for article in group.articles %}
                                        <div class="company-article">
                                            <div class="company-article-title">
                                                <a href="{{ article.link }}" target="_blank" rel="noopener">{{ article.title }}</a>
                                            </div>
                                            <div class="company-article-meta">{{ article.date }}</div>
                                            {% if article.description %}
                                                <div class="company-article-desc">{{ article.description }}</div>
                                            {% endif %}
                                        </div>
                                    {% endfor %}
                                </div>
                            </div>
                        {% endif %}
                    {% endfor %}
                </div>
            {% else %}
                <div class="no-news">
                    <p>暂无新闻数据</p>
                    <p>请点击"刷新数据"按钮</p>
                </div>
            {% endif %}
        </div>
    </div>

    <script>
        function switchTab(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active');
            });

            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');

            localStorage.setItem('zh_preferredView', tabId);
        }

        function refreshNews() {
            const btn = document.getElementById('refresh-btn');
            btn.disabled = true;
            btn.textContent = '刷新中...';

            fetch('/api/refresh')
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success') {
                        location.reload();
                    }
                })
                .catch(err => {
                    console.error('Refresh failed:', err);
                    btn.disabled = false;
                    btn.textContent = '刷新数据';
                });
        }

        // Restore view preference
        const savedView = localStorage.getItem('zh_preferredView');
        if (savedView === 'company') {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('company').classList.add('active');
            document.querySelectorAll('.tab-btn')[1].classList.add('active');
        }

        // Auto-refresh every 30 minutes
        setInterval(() => {
            fetch('/api/refresh')
                .then(res => res.json())
                .then(data => {
                    if (data.count > 0) {
                        location.reload();
                    }
                })
                .catch(err => console.log('Auto-refresh skipped:', err));
        }, 1800000);
    </script>
</body>
</html>
"""


# =============================================================================
# ROUTES
# =============================================================================

@app.route("/")
def index():
    """Main page showing timeline and company views."""
    news_data = get_all_news()

    return render_template_string(
        HTML_TEMPLATE,
        articles=news_data.get("articles", []),
        company_groups=news_data.get("company_groups", []),
        companies=COMPANIES,
        is_live=news_data.get("live_search", False),
        sources_count=news_data.get("sources_count", 0),
    )


@app.route("/api/news")
def api_news():
    """API endpoint for news data."""
    news_data = get_all_news()
    return jsonify(news_data)


@app.route("/api/refresh")
def api_refresh():
    """Force refresh news data."""
    logger.info("Force refresh requested for Chinese news")
    news_data = get_all_news(force_refresh=True)
    return jsonify({
        "status": "success",
        "count": len(news_data.get("articles", [])),
        "live_search": news_data.get("live_search", False),
    })


# =============================================================================
# STARTUP
# =============================================================================

if __name__ == "__main__":
    print("Starting Chinese Robotics News Aggregator...")
    print(f"Loaded {len(COMPANIES)} companies ({len(PRIORITY_COMPANIES)} priority)")
    print(f"Live search: {'ENABLED' if ENABLE_LIVE_SEARCH else 'DISABLED'}")
    app.run(debug=False, host="0.0.0.0", port=8080)
