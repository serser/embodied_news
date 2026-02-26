#!/usr/bin/env python3
"""
Embodied AI News Aggregator - With Images
"""

from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re
import hashlib

app = Flask(__name__)

BLOG_SOURCES = [
    {"name": "Generalist AI", "url": "https://generalistai.com/blog/", "base_url": "https://generalistai.com", "color": "#6366f1"},
    {"name": "Physical Intelligence", "url": "https://www.pi.website/blog", "base_url": "https://www.pi.website", "color": "#8b5cf6"},
    {"name": "World Labs", "url": "https://www.worldlabs.ai/blog", "base_url": "https://www.worldlabs.ai", "color": "#ec4899"},
    {"name": "Figure", "url": "https://www.figure.ai/news", "base_url": "https://www.figure.ai", "color": "#14b8a6"},
    {"name": "Sunday Robotics", "url": "https://www.sunday.ai/journal", "base_url": "https://www.sunday.ai", "color": "#f59e0b"},
    {"name": "Skild AI", "url": "https://www.skild.ai/blogs", "base_url": "https://www.skild.ai", "color": "#ef4444"}
]

# Company colors for gradient generation
COMPANY_COLORS = {
    "Generalist AI": "#6366f1",
    "Physical Intelligence": "#8b5cf6",
    "World Labs": "#ec4899",
    "Figure": "#14b8a6",
    "Sunday Robotics": "#f59e0b",
    "Skild AI": "#ef4444"
}

# Fallback data with image URLs (image_url can be None for auto-generation)
FALLBACK_DATA = {
    "Generalist AI": [
        ("The Dark Matter of Robotics: Physical Commonsense", "https://generalistai.com/blog/jan-29-2026-physical-commonsense", datetime(2026, 1, 29), "Exploring physical commonsense as the reactive, closed-loop intelligence behind interacting in the physical world.", None),
        ("GEN-0: Embodied Foundation Models That Scale", "https://generalistai.com/blog/nov-04-2025-GEN-0", datetime(2025, 11, 4), "Introducing GEN-0, a new class of embodied foundation models built for multimodal training on high-fidelity physical interaction.", None),
        ("The Robots Build Now, Too", "https://generalistai.com/blog/sep-24-2025-the-robots-build-now-too", datetime(2025, 9, 24), "One-shot assembly: you build a Lego structure and the robot builds copies of it.", None),
        ("Research Preview", "https://generalistai.com/blog/jun-17-2025-research-preview", datetime(2025, 6, 17), "A first look at what Generalist is building in robotics.", None),
    ],
    "World Labs": [
        ("Announcing the World API", "https://www.worldlabs.ai/blog/announcing-the-world-api", datetime(2026, 1, 21), "A public API for generating explorable 3D worlds from text, images, and video.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fworld-api.jpg&w=3840&q=75"),
        ("Marble: A Multimodal World Model", "https://www.worldlabs.ai/blog/marble-world-model", datetime(2025, 11, 12), "Marble, our frontier multimodal world model, is now available to everyone.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fnov12-thumbnail.jpg&w=3840&q=75"),
        ("From Words to Worlds: Spatial Intelligence", "https://www.worldlabs.ai/blog/spatial-intelligence", datetime(2025, 11, 10), "A manifesto on spatial intelligence - AI's next frontier and how world models will unlock it.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2FManifesto-Magritte.jpg&w=3840&q=75"),
        ("RTFM: A Real-Time Frame Model", "https://www.worldlabs.ai/blog/rtfm", datetime(2025, 10, 16), "A research preview of RTFM - a generative world model that generates video in real-time.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Frtfm-thumbnail-glass.png&w=3840&q=75"),
        ("Generating Bigger and Better Worlds", "https://www.worldlabs.ai/blog/bigger-better-worlds", datetime(2025, 9, 16), "Latest breakthrough in 3D world generation with larger, more detailed environments.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fbigger-better-worlds-nologo.jpg&w=3840&q=75"),
        ("Generating Worlds", "https://www.worldlabs.ai/blog/generating-worlds", datetime(2024, 12, 2), "Early progress toward persistent, navigable 3D worlds you can explore in your browser.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fgenerating-worlds-nologo.jpg&w=3840&q=75"),
        ("World Labs Announces New Funding", "https://www.worldlabs.ai/blog/funding-2026", datetime(2026, 2, 18), "An update on our vision for spatial intelligence in 2026.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Ffunding.jpg&w=3840&q=75"),
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
        ("The Physical Intelligence Layer", "https://www.pi.website/blog/partner", datetime(2026, 2, 24), "General-purpose physical intelligence models will enable a Cambrian explosion of robotics applications.", None),
        ("Moravec's Paradox and the Robot Olympics", "https://www.pi.website/blog/olympics", datetime(2025, 12, 22), "Fine-tuning models on difficult manipulation challenge tasks.", None),
        ("Emergence of Human to Robot Transfer in VLAs", "https://www.pi.website/research/human_to_robot", datetime(2025, 12, 16), "Exploring how transfer from human videos to robotic tasks emerges in VLAs as they scale.", None),
        ("π*0.6: a VLA that Learns from Experience", "https://www.pi.website/blog/pistar06", datetime(2025, 11, 17), "Training generalist policies with RL to improve success rate and throughput.", None),
        ("Real-Time Action Chunking with Large Models", "https://www.pi.website/research/real_time_chunking", datetime(2025, 6, 9), "A real-time system for large VLAs that maintains precision and speed.", None),
        ("VLAs that Train Fast, Run Fast, and Generalize Better", "https://www.pi.website/research/knowledge_insulation", datetime(2025, 5, 28), "A method to train VLAs that train quickly and generalize well.", None),
        ("π0.5: a VLA with Open-World Generalization", "https://www.pi.website/blog/pi05", datetime(2025, 4, 22), "Our latest generalist policy that enables open-world generalization.", None),
        ("Teaching Robots to Listen and Think Harder", "https://www.pi.website/research/hirobot", datetime(2025, 2, 26), "A method for robots to think through complex tasks step by step.", None),
        ("Open Sourcing π0", "https://www.pi.website/blog/openpi", datetime(2025, 2, 4), "Releasing the weights and code for π0 and π0-FAST.", None),
        ("FAST: Efficient Robot Action Tokenization", "https://www.pi.website/research/fast", datetime(2025, 1, 16), "A new robot action tokenizer that trains generalist policies 5x faster.", None),
        ("π0: Our First Generalist Policy", "https://www.pi.website/blog/pi0", datetime(2024, 10, 31), "Our first generalist policy combining large-scale data with a new architecture.", None),
    ],
}

cache_lock = threading.RLock()
cached_posts = []
cache_timestamp = None
CACHE_DURATION = 300


def generate_placeholder_image(title, company):
    """Generate an artistic placeholder SVG image based on title hash."""
    import base64
    
    # Create a hash from title to get consistent colors
    hash_obj = hashlib.md5(title.encode())
    hash_int = int(hash_obj.hexdigest()[:8], 16)
    
    # Get company color as primary
    primary = COMPANY_COLORS.get(company, "#6366f1")
    
    # Generate colors based on hash
    h1 = (hash_int % 360)
    hue2 = (h1 + 30) % 360
    
    # Convert HSL to hex (simplified)
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
    
    # Generate abstract SVG with the title
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
    
    # Return as data URI
    svg_b64 = base64.b64encode(svg.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{svg_b64}"
    """Generate an artistic placeholder image based on title hash."""
    # Create a hash from title to get consistent colors
    hash_obj = hashlib.md5(title.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    
    # Get company color as primary
    primary = COMPANY_COLORS.get(company, "#6366f1")
    
    # Generate a secondary color by rotating hue
    # Simple approach: use the gradients.durham.columbia.edu API or create local SVG
    
    # Use a gradient service with seed based on title
    # Generate colors based on hash
    h1 = (hash_int % 360)
    h2 = (h1 + 45) % 360
    
    # Use picsum for a real image with a seed
    seed = hash_int % 1000
    
    # Use a gradient placeholder service
    gradient_url = f"https://gradient.ishove.com/{primary.replace('#','')}/000000/{h1}/{h2}/600x400.png"
    
    return gradient_url


def fetch_figure(soup, base_url):
    """Parse Figure blog posts."""
    posts = []
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if not href.startswith('/news/'):
            continue
        parent = link.find_parent(['div', 'li', 'article'])
        if not parent:
            continue
        title_elem = parent.find(['h1', 'h2', 'h3', 'h4'])
        title = title_elem.get_text(strip=True) if title_elem else link.get_text(strip=True)
        
        # Try to get description/summary
        summary = ""
        desc_elem = parent.find('p')
        if desc_elem:
            summary = desc_elem.get_text(strip=True)[:200]
        
        # Try to get image
        image_url = None
        img_elem = parent.find('img', src=True)
        if img_elem:
            image_url = img_elem.get('src')
        
        date_elem = parent.find(string=lambda t: t and any(m in t for m in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']))
        if date_elem:
            try:
                date = datetime.strptime(date_elem.strip(), '%B %d, %Y')
                if date and title and len(title) > 3:
                    full_url = href if href.startswith('http') else f"{base_url}{href}"
                    posts.append({"title": title, "url": full_url, "date": date, "summary": summary, "image": image_url, "company": "Figure"})
            except:
                pass
    return posts


def fetch_blog_posts(source):
    """Fetch and parse blog posts from a single source."""
    company = source["name"]
    
    # Use fallback data
    if company in FALLBACK_DATA:
        posts = []
        for item in FALLBACK_DATA[company]:
            title, url, date, summary, image = item[:5]
            # Generate placeholder if no image
            if image is None:
                image = generate_placeholder_image(title, company)
            posts.append({"title": title, "url": url, "date": date, "summary": summary, "image": image, "company": company})
        return posts
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(source["url"], headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if company == "Figure":
            return fetch_figure(soup, source["base_url"])
    except Exception as e:
        print(f"Error fetching {company}: {e}")
    
    return []


def get_all_posts():
    global cached_posts, cache_timestamp
    
    with cache_lock:
        now = datetime.now()
        if cache_timestamp and cached_posts and (now - cache_timestamp).seconds < CACHE_DURATION:
            return cached_posts
    
    all_posts = []
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_blog_posts, source): source for source in BLOG_SOURCES}
        for future in as_completed(futures):
            source = futures[future]
            try:
                posts = future.result()
                all_posts.extend(posts)
                print(f"Fetched {len(posts)} posts from {source['name']}")
            except Exception as e:
                print(f"Error fetching {source['name']}: {e}")
    
    # Sort by date descending
    all_posts.sort(key=lambda x: x["date"], reverse=True)
    
    # Deduplicate
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
    
    return unique_posts


@app.route('/')
def index():
    posts = get_all_posts()
    by_company = {}
    for post in posts:
        company = post["company"]
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(post)
    company_colors = {s["name"]: s["color"] for s in BLOG_SOURCES}
    return render_template('index.html', posts=posts, by_company=by_company, company_colors=company_colors, companies=BLOG_SOURCES)


@app.route('/api/posts')
def api_posts():
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
    global cache_timestamp
    with cache_lock:
        cache_timestamp = None
    posts = get_all_posts()
    return jsonify({"status": "ok", "posts_count": len(posts)})


if __name__ == '__main__':
    print("Starting Embodied AI News Aggregator...")
    print("Visit http://localhost:8000 to view the news feed")
    app.run(debug=False, host='0.0.0.0', port=8080)
