#!/usr/bin/env python3
"""
Embodied AI News Aggregator - Fallback Data Only
"""

from flask import Flask, render_template, jsonify
from datetime import datetime
import hashlib
import base64

app = Flask(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

BLOG_SOURCES = [
    {"name": "Generalist AI", "url": "https://generalistai.com/blog/", "base_url": "https://generalistai.com", "color": "#6366f1"},
    {"name": "Physical Intelligence", "url": "https://www.pi.website/blog", "base_url": "https://www.pi.website", "color": "#8b5cf6"},
    {"name": "World Labs", "url": "https://www.worldlabs.ai/blog", "base_url": "https://www.worldlabs.ai", "color": "#ec4899"},
    {"name": "Figure", "url": "https://www.figure.ai/news", "base_url": "https://www.figure.ai", "color": "#14b8a6"},
    {"name": "Sunday Robotics", "url": "https://www.sunday.ai/journal", "base_url": "https://www.sunday.ai", "color": "#f59e0b"},
    {"name": "Skild AI", "url": "https://www.skild.ai/blogs", "base_url": "https://www.skild.ai", "color": "#ef4444"},
    {"name": "NVIDIA GEAR", "url": "https://research.nvidia.com/labs/gear/", "base_url": "https://research.nvidia.com", "color": "#76b900"},
    {"name": "1X Technologies", "url": "https://www.1x.tech/discover", "base_url": "https://www.1x.tech", "color": "#000000"},
    {"name": "Agility Robotics", "url": "https://www.agilityrobotics.com/resources", "base_url": "https://www.agilityrobotics.com", "color": "#ff6b35"}
]

COMPANY_COLORS = {s["name"]: s["color"] for s in BLOG_SOURCES}

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


# =============================================================================
# FALLBACK DATA - Current as of March 2026
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
        ("π*0.6: a VLA that Learns from Experience", "https://www.pi.website/blog/pistar06", datetime(2025, 11, 17), "Training generalist policies with RL to improve success rate and throughput.", None),
        ("Real-Time Action Chunking with Large Models", "https://www.pi.website/research/real_time_chunking", datetime(2025, 6, 9), "A real-time system for large VLAs that maintains precision and speed.", None),
        ("VLAs that Train Fast, Run Fast, and Generalize Better", "https://www.pi.website/research/knowledge_insulation", datetime(2025, 5, 28), "A method to train VLAs that train quickly and generalize well.", None),
        ("π0.5: a VLA with Open-World Generalization", "https://www.pi.website/blog/pi05", datetime(2025, 4, 22), "Our latest generalist policy that enables open-world generalization.", None),
        ("Teaching Robots to Listen and Think Harder", "https://www.pi.website/research/hirobot", datetime(2025, 2, 26), "A method for robots to think through complex tasks step by step.", None),
        ("Open Sourcing π0", "https://www.pi.website/blog/openpi", datetime(2025, 2, 4), "Releasing the weights and code for π0 and π0-FAST.", None),
        ("FAST: Efficient Robot Action Tokenization", "https://www.pi.website/research/fast", datetime(2025, 1, 16), "A new robot action tokenizer that trains generalist policies 5x faster.", None),
        ("π0: Our First Generalist Policy", "https://www.pi.website/blog/pi0", datetime(2024, 10, 31), "Our first generalist policy combining large-scale data with a new architecture.", None),
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


def get_all_posts():
    """Get all posts from fallback data with placeholder SVGs for posts without images."""
    posts = []
    for company, items in FALLBACK_DATA.items():
        for item in items:
            title, url, date, summary, image = item[:5]
            if image is None:
                image = generate_placeholder_svg(title, company)
            posts.append({
                "title": title,
                "url": url,
                "date": date,
                "summary": summary,
                "image": image,
                "company": company
            })
    
    # Sort by date descending
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts


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
            has_img = post.get("image") is not None
            
            if url_key not in seen:
                seen[url_key] = post
            else:
                # If current has image and existing doesn't, replace
                existing_has_img = seen[url_key].get("image") is not None
                if has_img and not existing_has_img:
                    seen[url_key] = post
        
        # Filter out posts without images
        by_company_dedup[company] = [p for p in seen.values() if p.get("image") is not None]
    
    return by_company_dedup

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


# =============================================================================
# STARTUP
# =============================================================================

if __name__ == '__main__':
    print("Starting Embodied AI News Aggregator...")
    print("Visit http://localhost:80 to view the news feed")
    app.run(debug=False, host='0.0.0.0', port=80)
