# embodied_news

A Flask-based news aggregator that scrapes the latest blog posts, research
updates, and product news from companies and labs working on embodied AI
(humanoid robots, manipulation, robot-learning foundation models, world
models, simulation).

Each source has a dedicated scraper in [`app.py`](app.py) and is dispatched
through the `SCRAPERS` registry. Results are cached for 5 minutes and
served at `/` (rendered) and `/api/posts` (JSON). Failed scrapes fall back
to a hand-curated snapshot in `FALLBACK_DATA`.

## Run

```bash
pip install -r requirements.txt
python app.py     # serves on 0.0.0.0:80
```

Routes:
- `GET /` &mdash; rendered feed (`templates/index.html`)
- `GET /api/posts` &mdash; aggregated posts as JSON
- `GET /refresh` &mdash; force-invalidate the cache

## Sources

34 sources, displayed alphabetically in the UI. Grouped below by focus
area for readability.

### Foundation models for robotics / robot learning

| Source | URL |
| --- | --- |
| Physical Intelligence | https://www.pi.website/blog |
| Skild AI | https://www.skild.ai/blogs |
| Generalist AI | https://generalistai.com |
| Genesis AI | https://www.genesis.ai/blog |
| Sunday Robotics | https://www.sunday.ai/journal |
| World Labs | https://www.worldlabs.ai/blog |
| Dexmal | https://www.dexmal.com/research |
| XDOF | https://www.xdof.ai/blog |

### Humanoid & general-purpose robot companies

| Source | URL |
| --- | --- |
| 1X Technologies | https://www.1x.tech/discover |
| Agility Robotics | https://www.agilityrobotics.com/resources |
| Boston Dynamics | https://bostondynamics.com/blog/ |
| Figure | https://www.figure.ai/news |
| Sanctuary AI | https://www.sanctuary.ai |
| AGIBOT Finch | https://finch.agibot.com/research |
| Galaxea | https://opengalaxea.github.io/G05/ |
| OneRobotics | https://www.onerobot.com/news |
| X Square Robot | https://x2robot.com/en/news |
| BeingBeyond | https://research.beingbeyond.com |
| Spirit AI | https://www.spirit-ai.com/en/blog/ |
| MANUS | https://www.manus-meta.com/blog |

### Manipulation, dexterous hands & industrial robotics

| Source | URL |
| --- | --- |
| Sharpa | https://www.sharpa.com/blogs/research |
| DexForce | https://www.dexforce.com/core.html |
| Agile Robots | https://www.agile-robots.com/en/news/ |
| Hexagon Robotics | https://robotics.hexagon.com/news/ |
| Ropedia | https://ropedia.com |

### Big-tech AI / robotics research

| Source | URL |
| --- | --- |
| NVIDIA Blog (Robotics) | https://blogs.nvidia.com/blog/category/robotics/ |
| NVIDIA GEAR | https://research.nvidia.com/labs/gear/ |
| NVIDIA Cosmos Lab | https://research.nvidia.com/labs/cosmos-lab/ |
| ByteDance Seed (Robotics) | https://seed.bytedance.com/en/direction/robotics |
| Xiaomi Robotics | https://robotics.xiaomi.com |

### Academic labs

| Source | URL |
| --- | --- |
| RL2 @ Georgia Tech | https://rl2.cc.gatech.edu |
| RoboTouch Lab | https://www.robotouchlab.com/publication/ |
| REAL @ Stanford | https://real.stanford.edu/research.html |

## Adding a new source

1. Add an entry to `BLOG_SOURCES` in `app.py` (`name`, `url`, `base_url`,
   `color`).
2. Write a `scrape_<name>(source)` function returning a list of post dicts
   (`title`, `url`, `date`, `summary`, `image`, `company`).
3. Register it in the `SCRAPERS` dispatch dict.
4. Optionally add a `FALLBACK_DATA` entry so the source still renders if
   the live site is down.
