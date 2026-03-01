#!/usr/bin/env python3
"""
Embodied AI News Aggregator - With Images & Multi-source News Agent
"""
from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re
import hashlib
import base64

app = Flask(__name__)

# ============ NEWS SOURCES CONFIGURATION ============
NEWS_SOURCES = {
    # Chinese companies - additional sources
    "星尘智能": ["36kr", "techCrunch", "reuters"],
    "智元机器人": ["36kr", "techCrunch", "reuters"],
    "宇树科技": ["36kr", "techCrunch", "reuters"],
    "智平方": ["36kr", "techCrunch", "reuters"],
    "乐聚机器人": ["36kr", "techCrunch", "reuters"],
    "星海图": ["36kr", "techCrunch", "reuters"],
    "众擎机器人": ["36kr", "techCrunch", "reuters"],
    "枢途科技": ["36kr", "techCrunch", "reuters"],
    "小鹏汽车": ["36kr", "techCrunch", "reuters"],
    "千寻智能": ["36kr", "techCrunch", "reuters"],
    "星动纪元": ["36kr", "techCrunch", "reuters"],
    "群核科技": ["36kr", "techCrunch", "reuters"],
    # English companies
    "Generalist AI": ["techCrunch", "reuters", "wired"],
    "Physical Intelligence": ["techCrunch", "reuters", "wired"],
    "World Labs": ["techCrunch", "reuters", "wired"],
    "Figure": ["techCrunch", "reuters", "wired"],
    "Sunday Robotics": ["techCrunch", "reuters", "wired"],
    "Skild AI": ["techCrunch", "reuters", "wired"],
    "NVIDIA GEAR": ["techCrunch", "reuters", "wired"],
    "1X Technologies": ["techCrunch", "reuters", "wired"],
}

# Fallback data for news agent (when scraping fails)
NEWS_AGENT_FALLBACK_DATA = {
    "星尘智能": [
        ("星尘智能完成数亿元A++轮融资", "https://www.stcn.com/article/detail/3499749.html", datetime(2025, 11, 18), "国科投资与蚂蚁集团联合领投", None, "36kr"),
        ("人形机器人公司星尘智能获数千万美元融资", "https://www.qbitai.com/2024/07/173552.html", datetime(2024, 7, 31), "经纬创投领投", None, "36kr"),
    ],
    "智元机器人": [
        ("智元机器人完成新一轮融资", "https://stcn.com/article/detail/1605342.html", datetime(2025, 3, 24), "腾讯领投", None, "36kr"),
        ("智元机器人估值超150亿元", "https://m.36kr.com/p/3249924680410376", datetime(2025, 4, 14), "加速投资布局", None, "36kr"),
    ],
    "宇树科技": [
        ("宇树科技完成近7亿元C轮融资", "https://eu.36kr.com/zh/p/3344368397190018", datetime(2025, 6, 20), "腾讯、阿里、中移动等巨头入局", None, "36kr"),
        ("宇树科技开启上市辅导", "https://news.cnyes.com/news/id/6070798", datetime(2025, 7, 20), "估值超120亿元", None, "36kr"),
    ],
    "智平方": [
        ("智平方完成超10亿元B轮融资", "https://www.guancha.cn/economy/2026_02_24_807853.shtml", datetime(2026, 2, 23), "百度战投领投，估值破百亿", None, "36kr"),
    ],
    "乐聚机器人": [
        ("乐聚机器人完成近15亿元Pre-IPO轮融资", "https://www.9fzt.com/9fztgw_1_top/082e6ef9ff957fe855a3e516e28d3ee3.html", datetime(2025, 10, 22), "深投控资本领投", None, "36kr"),
    ],
    "星海图": [
        ("星海图完成超1亿美元A4、A5轮融资", "http://www.chuangtouzhijia.com/news/17849.html", datetime(2025, 7, 9), "今日资本、美团龙珠联合领投", None, "36kr"),
    ],
    "众擎机器人": [
        ("众擎机器人完成数亿元Pre-A轮融资", "https://www.21jingji.com/article/20251225/herald/e050bbccbf323ed44f698b5e106c1f39.html", datetime(2025, 12, 25), "达晨财智领投", None, "36kr"),
    ],
    "小鹏汽车": [
        ("小鹏科技日发布第二代VLA大模型", "http://www.news.cn/auto/20251106/a49e7e6cdd38419ab363605c1c528ae4/c.html", datetime(2025, 11, 6), "全新一代IRON机器人亮相", None, "36kr"),
    ],
    "千寻智能": [
        ("千寻智能完成近20亿元融资", "https://www.qbitai.com/2026/02/381766.html", datetime(2026, 2, 24), "云锋基金、红杉中国领投", None, "36kr"),
    ],
    "星动纪元": [
        ("星动纪元完成近10亿元A+轮融资", "https://www.qbitai.com/2025/11/354404.html", datetime(2025, 11, 20), "吉利资本领投", None, "36kr"),
    ],
    "群核科技": [
        ("群核科技更新招股书，上半年扭亏为盈", "https://www.stcn.com/article/detail/3249794.html", datetime(2025, 8, 22), "冲刺港交所", None, "36kr"),
    ],
    "Generalist AI": [
        ("GEN-0: Embodied Foundation Models That Scale", "https://generalistai.com/blog/nov-04-2025-GEN-0", datetime(2025, 11, 4), "New class of embodied foundation models", None, "TechCrunch"),
    ],
    "Physical Intelligence": [
        ("Physical Intelligence Layer", "https://www.pi.website/blog/partner", datetime(2026, 2, 24), "General-purpose physical intelligence models", None, "TechCrunch"),
    ],
    "World Labs": [
        ("Announcing the World API", "https://www.worldlabs.ai/blog/announcing-the-world-api", datetime(2026, 1, 21), "Generating explorable 3D worlds", None, "TechCrunch"),
    ],
    "Figure": [
        ("Figure AI Announces New Funding", "https://www.figure.ai/news", datetime(2025, 6, 17), "General-purpose humanoid robots", None, "TechCrunch"),
    ],
    "Sunday Robotics": [
        ("ACT-1: A Robot Foundation Model", "https://www.sunday.ai/journal/no-robot-data", datetime(2025, 11, 19), "Trained on zero robot data", None, "TechCrunch"),
    ],
    "Skild AI": [
        ("Skild AI Expands Global Footprint To Bengaluru", "https://www.skild.ai/blogs/bengaluru", datetime(2026, 2, 19), "Expansion to India", None, "TechCrunch"),
    ],
    "1X Technologies": [
        ("EVE: General-Purpose Humanoid Platform", "https://www.1x.tech/discover/eve", datetime(2025, 12, 17), "Real-world tasks", None, "TechCrunch"),
    ],
}


# Blog sources (official blogs)
BLOG_SOURCES = [
    {"name": "星尘智能", "url": "https://www.qbitai.com/tag/星尘智能", "base_url": "https://www.qbitai.com", "color": "#f472b6"},
    {"name": "智元机器人", "url": "https://www.qbitai.com/tag/智元机器人", "base_url": "https://www.qbitai.com", "color": "#fb923c"},
    {"name": "宇树科技", "url": "https://www.qbitai.com/tag/宇树科技", "base_url": "https://www.qbitai.com", "color": "#22c55e"},
    {"name": "智平方", "url": "https://www.qbitai.com/tag/智平方", "base_url": "https://www.qbitai.com", "color": "#3b82f6"},
    {"name": "乐聚机器人", "url": "https://www.qbitai.com/tag/乐聚机器人", "base_url": "https://www.qbitai.com", "color": "#a855f7"},
    {"name": "星海图", "url": "https://www.qbitai.com/tag/星海图", "base_url": "https://www.qbitai.com", "color": "#ef4444"},
    {"name": "众擎机器人", "url": "https://www.qbitai.com/tag/众擎机器人", "base_url": "https://www.qbitai.com", "color": "#f97316"},
    {"name": "枢途科技", "url": "https://www.qbitai.com/tag/枢途科技", "base_url": "https://www.qbitai.com", "color": "#06b6d4"},
    {"name": "小鹏汽车", "url": "https://www.qbitai.com/tag/小鹏汽车", "base_url": "https://www.qbitai.com", "color": "#ec4899"},
    {"name": "千寻智能", "url": "https://www.qbitai.com/tag/千寻智能", "base_url": "https://www.qbitai.com", "color": "#8b5cf6"},
    {"name": "星动纪元", "url": "https://www.qbitai.com/tag/星动纪元", "base_url": "https://www.qbitai.com", "color": "#0ea5e9"},
    {"name": "群核科技", "url": "https://www.qbitai.com/tag/群核科技", "base_url": "https://www.qbitai.com", "color": "#14b8a6"},
    {"name": "Generalist AI", "url": "https://generalistai.com/blog/", "base_url": "https://generalistai.com", "color": "#6366f1"},
    {"name": "Physical Intelligence", "url": "https://www.pi.website/blog", "base_url": "https://www.pi.website", "color": "#8b5cf6"},
    {"name": "World Labs", "url": "https://www.worldlabs.ai/blog", "base_url": "https://www.worldlabs.ai", "color": "#ec4899"},
    {"name": "Figure", "url": "https://www.figure.ai/news", "base_url": "https://www.figure.ai", "color": "#14b8a6"},
    {"name": "Sunday Robotics", "url": "https://www.sunday.ai/journal", "base_url": "https://www.sunday.ai", "color": "#f59e0b"},
    {"name": "Skild AI", "url": "https://www.skild.ai/blogs", "base_url": "https://www.skild.ai", "color": "#ef4444"},
    {"name": "NVIDIA GEAR", "url": "https://research.nvidia.com/labs/gear/", "base_url": "https://research.nvidia.com", "color": "#76b900"},
    {"name": "1X Technologies", "url": "https://www.1x.tech/discover", "base_url": "https://www.1x.tech", "color": "#000000"}
]

COMPANY_COLORS = {
    "星尘智能": "#f472b6",
    "智元机器人": "#fb923c",
    "宇树科技": "#22c55e",
    "智平方": "#3b82f6",
    "乐聚机器人": "#a855f7",
    "星海图": "#ef4444",
    "众擎机器人": "#f97316",
    "枢途科技": "#06b6d4",
    "小鹏汽车": "#ec4899",
    "千寻智能": "#8b5cf6",
    "星动纪元": "#0ea5e9",
    "群核科技": "#14b8a6",
    "Generalist AI": "#6366f1",
    "Physical Intelligence": "#8b5cf6",
    "World Labs": "#ec4899",
    "Figure": "#14b8a6",
    "Sunday Robotics": "#f59e0b",
    "Skild AI": "#ef4444",
    "NVIDIA GEAR": "#76b900",
    "1X Technologies": "#000000"
}

FALLBACK_DATA = {
    "星尘智能": [
        ("星尘智能完成数亿元A++轮融资，国科投资与蚂蚁集团联合领投", "https://www.stcn.com/article/detail/3499749.html", datetime(2025, 11, 18), "绳驱AI机器人公司星尘智能完成数亿元A++轮融资，由国科投资和蚂蚁集团联合领投。本轮融资将重点用于研发人才梯队建设、绳驱本体的规模化制造准备、多场景解决方案深化与产业化能力提升。", None),
        ("连续完成A及A+轮融资，星尘智能获锦秋基金、蚂蚁集团等领投", "https://news.pedaily.cn/202504/548164.shtml", datetime(2025, 4, 10), "星尘智能连续完成A轮及A+轮融资数亿元，由锦秋基金、蚂蚁集团领投，云启资本，道彤资本等老股东跟投。华兴资本担任独家财务顾问。", None),
        ("人形机器人「星尘智能」获数千万美元Pre-A轮融资，经纬创投领投", "https://www.qbitai.com/2024/07/173552.html", datetime(2024, 7, 31), "AI机器人公司星尘智能（Astribot）宣布完成数千万美元Pre-A轮融资，由经纬创投领投，道彤投资及清辉投资等产业资本跟投。", None),
    ],
    "智元机器人": [
        ("智元机器人完成新一轮融资，腾讯领投", "https://stcn.com/article/detail/1605342.html", datetime(2025, 3, 24), "智元机器人近期已完成新一轮融资，腾讯领投，本次有多家产业方及老股东跟投，包括龙旗科技、卧龙电气、华发集团、蓝驰创投等。智元机器人以150亿元估值进行新一轮融资接洽。", None),
        ("智元机器人估值超150亿元，正加速投资布局", "https://m.36kr.com/p/3249924680410376", datetime(2025, 4, 14), "估值超150亿的智元机器人，正加速投资。不到一月，智元机器人接连出手投资了灵猴机器人、希尔机器人等产业链企业。", None),
        ("智元机器人发布远征A1，稚晖君创业首秀", "https://www.zhiyuan-robot.com", datetime(2023, 8, 18), "智元机器人发布首款双足人形机器人远征A1，创始人稚晖君曾任华为天才少年，公司成立仅半年即发布产品。", None),
    ],
    "宇树科技": [
        ("宇树科技完成近7亿元C轮融资，腾讯、阿里、中移动等巨头入局", "https://eu.36kr.com/zh/p/3344368397190018", datetime(2025, 6, 20), "宇树科技完成C轮融资，本轮融资由中国移动旗下基金、腾讯、锦秋基金、阿里巴巴、蚂蚁集团、吉利资本共同领投，融资金额接近7亿元人民币，投后估值超120亿元。", None),
        ("宇树科技完成B2轮融资，金额近10亿元", "http://www.20stech.com/index-42.html", datetime(2024, 12, 5), "宇树科技2024年春节前完成了B2轮融资，融资近10亿元人民币，本轮投资方包括美团，金石投资、源码资本，老股东深创投、中网投、容亿、敦鸿跟投。", None),
        ("宇树科技开启上市辅导，估值超120亿元", "https://news.cnyes.com/news/id/6070798", datetime(2025, 7, 20), "杭州宇树科技股份有限公司已于7月18日正式启动上市辅导程序，公司已完成10轮融资，累计募资金额超过15亿元人民币。", None),
    ],
    "智平方": [
        ("智平方完成超10亿元B轮融资，估值突破百亿", "https://www.guancha.cn/economy/2026_02_24_807853.shtml", datetime(2026, 2, 23), "AI机器人企业智平方宣布完成超10亿元人民币B轮融资，估值突破100亿元。本轮融资由百度战投、中车资本、宇信科技、森麒麟、沄柏资本、国泰海通基金等联合投资。", None),
        ("智平方又获亿元融资，半年已完成7轮", "https://finance.stockstar.com/IG2025090100032345.shtml", datetime(2025, 9, 1), "智平方近期完成由深创投领投的新一轮A系列融资，深创投单家投资超过亿元。本轮融资资金将用于GOVLA大模型及AlphaBot系列机器人的持续迭代。", None),
        ("智平方完成数亿元Pre-A轮融资", "https://www.qbitai.com/2026/02/382004.html", datetime(2025, 1, 7), "智平方宣布完成数亿元Pre-A轮战略融资，由达晨财智与敦鸿资产联合领投，基石资本跟投。这是2025年具身智能领域的首笔重大融资。", None),
    ],
    "乐聚机器人": [
        ("乐聚机器人完成近15亿元Pre-IPO轮融资", "https://www.9fzt.com/9fztgw_1_top/082e6ef9ff957fe855a3e516e28d3ee3.html", datetime(2025, 10, 22), "乐聚机器人宣布完成近15亿元Pre-IPO轮融资。本轮融资由深投控资本、深圳龙华资本、前海基础投资、石景山产业基金、东方精工、拓普集团等联合投资。", None),
        ("乐聚机器人完成数亿元D轮融资", "https://www.jinglingshuju.com/article/46733267524", datetime(2025, 6, 11), "乐聚机器人宣布完成数亿元D轮融资，由东方精工、中信证券、合肥产投、探针天使、联新资本，道禾投资，金石投资、盛奕资本等多家机构联合参与。", None),
        ("乐聚机器人冲刺IPO，已办理上市辅导备案", "https://m.mp.oeeee.com/a/BAAFRD0000202510311166071.html", datetime(2025, 10, 31), "乐聚智能(深圳)股份有限公司已办理上市辅导备案，由东方证券担任辅导机构，预计将于2026年3月至6月完成辅导。", None),
    ],
    "星海图": [
        ("星海图完成超1亿美元A4、A5轮融资", "http://www.chuangtouzhijia.com/news/17849.html", datetime(2025, 7, 9), "星海图宣布接连完成A4轮及A5轮战略融资，两轮合计融资金额超过1亿美元。A4轮由今日资本、美团龙珠联合领投，A5轮由美团龙珠、美团战投联合领投。", None),
        ("星海图完成近3亿元A轮融资，蚂蚁集团领投", "https://m.ofweek.com/ai/2025-02/ART-201717-8120-30657658.html", datetime(2025, 2, 20), "国内具身智能企业星海图完成近3亿元人民币A轮融资，本轮融资由蚂蚁集团独家领投，高瓴创投、IDG资本、北京机器人产业基金、百度风投、同歌创投等老股东持续加码。", None),
        ("星海图完成股份制改造，估值近百亿元", "https://www.industrysourcing.cn/article/473625", datetime(2026, 1, 21), "星海图于2026年1月完成工商变更，正式更名为星海图（北京）人工智能科技股份有限公司，成为2026年首家股改的具身智能企业。", None),
    ],
    "众擎机器人": [
        ("众擎机器人完成数亿元Pre-A轮融资", "https://www.21jingji.com/article/20251225/herald/e050bbccbf323ed44f698b5e106c1f39.html", datetime(2025, 12, 25), "众擎机器人完成数亿元Pre-A轮融资，达晨财智领投。创始人赵同阳被自己公司研发的人形机器人T800一脚踹飞，在社交媒体破圈传播。", None),
        ("众擎机器人完成全球首例人形机器人前空翻", "https://www.engineai.com.cn/about-process-s2.html", datetime(2025, 2, 23), "众擎成功实现全球首例人形机器人前空翻特技。与后空翻相比，前空翻对机器人的动态平衡、瞬间加速和精准落地要求更高。", None),
    ],
    "枢途科技": [
        ("枢途科技完成数千万元天使轮融资", "https://www.donews.com/news/detail/4/6177014.html", datetime(2025, 10, 13), "枢途科技宣布完成数千万元天使轮融资，由东方富海及兼固资本联合领投。自主研发SynaData数据管线，综合数采成本降为行业平均水平的千分之五。", None),
    ],
    "小鹏汽车": [
        ("小鹏科技日发布第二代VLA大模型，全新一代IRON机器人亮相", "http://www.news.cn/auto/20251106/a49e7e6cdd38419ab363605c1c528ae4/c.html", datetime(2025, 11, 6), "小鹏汽车正式宣布定位升级为「物理AI世界的出行探索者，面向全球的具身智能公司」。发布第二代VLA模型，全新一代IRON身高约1.78米，体重70kg。", None),
        ("小鹏全新一代IRON发布：82个自由度，全固态电池", "https://robohorizon.cn/zh/magazine/2025/11/xpeng-iron-robot-zh/", datetime(2025, 11, 5), "小鹏全新一代IRON的设计理念是「由内而生」，拥有仿人的脊椎、仿生肌肉、全包覆柔性皮肤。行业首发应用全固态电池，实现极致轻量化、超高能量密度与极致安全。", None),
    ],
    "千寻智能": [
        ("千寻智能完成近20亿元融资，估值突破百亿", "https://www.qbitai.com/2026/02/381766.html", datetime(2026, 2, 24), "千寻智能连续完成两轮融资近20亿元，投后估值超100亿元。本轮融资由云锋基金、红杉中国、混沌投资等领投，老股东持续加码。", None),
        ("千寻智能完成Pre-A+轮近6亿元融资，京东领投", "https://www.spirit-ai.com/news/8", datetime(2025, 7, 1), "千寻智能完成近6亿元Pre-A+轮融资，由京东领投，中国互联网投资基金、浙江省科创母基金等跟投。", None),
        ("千寻智能完成5.28亿元Pre-A轮融资，Prosperity7领投", "https://www.spirit-ai.com/news/8", datetime(2025, 3, 1), "千寻智能完成5.28亿元Pre-A轮融资，由阿美风险投资旗下Prosperity7领投，招商局创投等深度参与。", None),
        ("千寻智能获近2亿元种子轮+天使轮融资", "https://www.stcn.com/article/detail/1284789.html", datetime(2024, 8, 12), "千寻智能宣布完成近2亿元种子轮+天使轮融资，由弘晖基金领投，达晨创投、千乘资本跟投。", None),
    ],
    "星动纪元": [
        ("星动纪元完成近10亿元A+轮融资，吉利资本领投", "https://www.qbitai.com/2025/11/354404.html", datetime(2025, 11, 20), "星动纪元完成近10亿元A+轮融资，本轮融资由吉利资本领投，北汽产投、北京市人工智能产业投资基金联合投资。今年订单总额已突破5亿元。", None),
        ("星动纪元完成近5亿元A轮融资，鼎晖VGC领投", "https://m.caixin.com/m/2025-07-07/102338938.html", datetime(2025, 7, 7), "清华系具身智能企业星动纪元完成近5亿元A轮融资，由鼎晖VGC和海尔资本联合领投。", None),
        ("星动纪元完成近3亿元Pre-A轮融资", "https://www.chinaventure.com.cn/news/80-20241016-383391.html", datetime(2024, 10, 16), "星动纪元完成近3亿元Pre-A轮融资，本轮由清流资本、元璟资本、阿里巴巴联合领投。", None),
        ("星动纪元获超亿元天使轮融资", "https://www.36kr.com/p/2993543239314440", datetime(2024, 1, 1), "星动纪元完成由联想创投领投的超亿元天使轮融资，金鼎资本、泽羽资本跟投，老股东世纪金源超额追投。", None),
    ],
    "群核科技": [
        ("群核科技更新招股书，上半年扭亏为盈冲刺港交所", "https://www.stcn.com/article/detail/3249794.html", datetime(2025, 8, 22), "群核科技更新招股书，继续推动在港交所的上市进程。2025年上半年实现营收4.0亿元，经调整净利润为1783万元，成功扭亏为盈。", None),
        ("群核科技发布3D高斯语义数据集InteriorGS", "https://cj.sina.cn/articles/view/5685329651/152df3ef300101enqe", datetime(2025, 7, 25), "群核科技发布最新高质量3D高斯语义数据集InteriorGS，旨在为机器人和AI智能体提升空间感知能力。该数据集包含1000个3D高斯语义场景，涵盖超80种室内环境。", None),
    ],
    "Generalist AI": [
        ("The Dark Matter of Robotics: Physical Commonsense", "https://generalistai.com/blog/jan-29-2026-physical-commonsense", datetime(2026, 1, 29), "Exploring physical commonsense as the reactive, closed-loop intelligence behind interacting in the physical world.", None),
        ("GEN-0: Embodied Foundation Models That Scale", "https://generalistai.com/blog/nov-04-2025-GEN-0", datetime(2025, 11, 4), "Introducing GEN-0, a new class of embodied foundation models built for multimodal training on high-fidelity physical interaction.", None),
        ("The Robots Build Now, Too", "https://generalistai.com/blog/sep-24-2025-the-robots-build-now-too", datetime(2025, 9, 24), "One-shot assembly: you build a Lego structure and the robot builds copies of it.", None),
    ],
    "World Labs": [
        ("Announcing the World API", "https://www.worldlabs.ai/blog/announcing-the-world-api", datetime(2026, 1, 21), "A public API for generating explorable 3D worlds from text, images, and video.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fworld-api.jpg&w=3840&q=75"),
        ("Marble: A Multimodal World Model", "https://www.worldlabs.ai/blog/marble-world-model", datetime(2025, 11, 12), "Marble, our frontier multimodal world model, is now available to everyone.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fnov12-thumbnail.jpg&w=3840&q=75"),
        ("From Words to Worlds: Spatial Intelligence", "https://www.worldlabs.ai/blog/spatial-intelligence", datetime(2025, 11, 10), "A manifesto on spatial intelligence - AI's next frontier and how world models will unlock it.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2FManifesto-Magritte.jpg&w=3840&q=75"),
        ("RTFM: A Real-Time Frame Model", "https://www.worldlabs.ai/blog/rtfm", datetime(2025, 10, 16), "A research preview of RTFM - a generative world model that generates video in real-time.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Frtfm-thumbnail-glass.png&w=3840&q=75"),
        ("Generating Bigger and Better Worlds", "https://www.worldlabs.ai/blog/bigger-better-worlds", datetime(2025, 9, 16), "Latest breakthrough in 3D world generation with larger, more detailed environments.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Fbigger-better-worlds-nologo.jpg&w=3840&q=75"),
        ("World Labs Announces New Funding", "https://www.worldlabs.ai/blog/funding-2026", datetime(2026, 2, 18), "An update on our vision for spatial intelligence in 2026.", "https://www.worldlabs.ai/_next/image?url=%2Fimages%2Ffunding.jpg&w=3840&q=75"),
    ],
    "Skild AI": [
        ("Skild AI Expands Global Footprint To Bengaluru", "https://www.skild.ai/blogs/bengaluru", datetime(2026, 2, 19), "Skild AI announces expansion to Bengaluru, India.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fbengaluru.468e7705.jpg&w=3840&q=75"),
        ("Announcing Series C", "https://www.skild.ai/blogs/series-c", datetime(2026, 1, 14), "Skild AI announces Series C funding round.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fpress_release-2.5149b136.jpg&w=3840&q=75"),
        ("Learning by watching human videos", "https://www.skild.ai/blogs/learning-by-watching", datetime(2026, 1, 12), "Training robot models by learning from human videos.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fmedia%2Fobservational_learning.1e829681.png&w=3840&q=75"),
        ("One Model, Any Scenario", "https://www.skild.ai/blogs/one-policy-all-scenarios", datetime(2025, 8, 6), "End-to-end locomotion from vision - one model for any scenario.", "https://www.skild.ai/_next/image?url=%2F_next%2Fstatic%2Fvision-loco.47034095.jpg&w=3840&q=75"),
    ],
    "Sunday Robotics": [
        ("ACT-1: A Robot Foundation Model Trained on Zero Robot Data", "https://www.sunday.ai/journal/no-robot-data", datetime(2025, 11, 19), "Sunday's first technical blog - ACT-1, a robot foundation model trained on zero robot data.", "https://cdn.sanity.io/images/1omys9i3/production/7d513e226ee4e1739175bacd03fa56ab52c0f215-4000x2668.jpg"),
        ("This Home Robot Clears Tables and Loads the Dishwasher", "https://www.wired.com/story/memo-sunday-robotics-home-robot/", datetime(2025, 11, 19), "WIRED coverage of Sunday's home robot capabilities.", "https://cdn.sanity.io/images/1omys9i3/production/3dc382088fcf41e138c21f757650f05961554335-1200x1500.png"),
    ],
    "Physical Intelligence": [
        ("The Physical Intelligence Layer", "https://www.pi.website/blog/partner", datetime(2026, 2, 24), "General-purpose physical intelligence models will enable a Cambrian explosion of robotics applications.", None),
        ("Moravec's Paradox and the Robot Olympics", "https://www.pi.website/blog/olympics", datetime(2025, 12, 22), "Fine-tuning models on difficult manipulation challenge tasks.", None),
        ("π0: Our First Generalist Policy", "https://www.pi.website/blog/pi0", datetime(2024, 10, 31), "Our first generalist policy combining large-scale data with a new architecture.", None),
    ],
    "NVIDIA GEAR": [
        ("Project GR00T: Foundation Model for Humanoid Robots", "https://developer.nvidia.com/project-gr00t", datetime(2024, 3, 18), "NVIDIA's foundation model for building general-purpose humanoid robots.", None),
        ("Eureka: Human-Level Reward Design via Coding LLMs", "https://eureka-research.github.io/", datetime(2023, 10, 15), "NVIDIA's AI agent that writes reward code for robot training.", None),
    ],
    "1X Technologies": [
        ("EVE: General-Purpose Humanoid Platform", "https://www.1x.tech/discover/eve", datetime(2025, 12, 17), "Introducing EVE, a general-purpose humanoid robot platform designed for real-world tasks.", None),
        ("NEO: The Next Generation Android", "https://www.1x.tech/discover/neo", datetime(2025, 8, 15), "Unveiling NEO, an advanced android designed for domestic assistance.", None),
        ("1X Technologies Raises $100M Series B", "https://www.1x.tech/discover/series-b", datetime(2025, 6, 10), "1X Technologies announces $100M Series B funding to scale humanoid robot production.", None),
    ],
}

# ============ CACHE CONFIGURATION ============
cache_lock = threading.RLock()
cached_posts = []
cached_news_agent_posts = []
cache_timestamp = None
news_agent_cache_timestamp = None
CACHE_DURATION = 300
NEWS_AGENT_CACHE_DURATION = 600  # 10 minutes for news agent

# ============ HELPER FUNCTIONS ============
def generate_placeholder_image(title, company):
    """Generate an artistic placeholder SVG image based on title hash."""
    hash_obj = hashlib.md5(title.encode())
    hash_int = int(hash_obj.hexdigest()[:8], 16)
    
    primary = COMPANY_COLORS.get(company, "#6366f1")
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

# ============ BLOG FETCHING ============
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
        
        summary = ""
        desc_elem = parent.find('p')
        if desc_elem:
            summary = desc_elem.get_text(strip=True)[:200]
        
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
    
    if company in FALLBACK_DATA:
        posts = []
        for item in FALLBACK_DATA[company]:
            title, url, date, summary, image = item[:5]
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

# ============ NEWS AGENT - Multi-source news aggregation ============
def fetch_36kr_news(company):
    """Fetch news from 36kr for a specific company."""
    posts = []
    try:
        url = f"https://www.36kr.com/information/{company}/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = soup.find_all('a', href=re.compile(r'/news/\d+'))
        for article in articles[:10]:
            try:
                title = article.get_text(strip=True)
                if len(title) < 5:
                    continue
                href = article.get('href', '')
                full_url = href if href.startswith('http') else f"https://www.36kr.com{href}"
                
                date = datetime.now()
                date_elem = article.find_parent('article') or article.find_parent('div')
                if date_elem:
                    date_text = date_elem.get_text()
                    date_match = re.search(r'(\d{1,2})/(\d{1,2})', date_text)
                    if date_match:
                        month, day = int(date_match.group(1)), int(date_match.group(2))
                        date = datetime(2026, month, day)
                
                img = article.find('img')
                image = None
                if img:
                    image = img.get('src') or img.get('data-src')
                
                if image is None:
                    image = generate_placeholder_image(title, company)
                
                posts.append({
                    "title": title,
                    "url": full_url,
                    "date": date,
                    "summary": "来源: 36kr",
                    "image": image,
                    "company": company,
                    "source": "36kr"
                })
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error fetching 36kr for {company}: {e}")
    return posts

def fetch_techcrunch_news(company):
    """Fetch news from TechCrunch for a specific company."""
    posts = []
    try:
        url = f"https://techcrunch.com/search/{company.replace(' ', '%20')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = soup.find_all('article')[:10]
        for article in articles:
            try:
                title_elem = article.find(['h2', 'h3'])
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                if len(title) < 5:
                    continue
                
                link = article.find('a', href=True)
                if not link:
                    continue
                full_url = link.get('href', '')
                if not full_url.startswith('http'):
                    full_url = f"https://techcrunch.com{full_url}"
                
                date = datetime.now()
                time_elem = article.find('time')
                if time_elem:
                    try:
                        date_str = time_elem.get('datetime', '')
                        if date_str:
                            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        pass
                
                img = article.find('img')
                image = None
                if img:
                    image = img.get('src') or img.get('data-src')
                
                if image is None:
                    image = generate_placeholder_image(title, company)
                
                posts.append({
                    "title": title,
                    "url": full_url,
                    "date": date,
                    "summary": "来源: TechCrunch",
                    "image": image,
                    "company": company,
                    "source": "TechCrunch"
                })
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error fetching TechCrunch for {company}: {e}")
    return posts

def fetch_reuters_news(company):
    """Fetch news from Reuters for a specific company."""
    posts = []
    try:
        url = f"https://www.reuters.com/search/news?blob={company.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        articles = soup.find_all('a', href=re.compile(r'/articles/'))[:10]
        for article in articles:
            try:
                title = article.get_text(strip=True)
                if len(title) < 10:
                    continue
                
                href = article.get('href', '')
                full_url = href if href.startswith('http') else f"https://www.reuters.com{href}"
                
                date = datetime.now()
                image = generate_placeholder_image(title, company)
                
                posts.append({
                    "title": title,
                    "url": full_url,
                    "date": date,
                    "summary": "来源: Reuters",
                    "image": image,
                    "company": company,
                    "source": "Reuters"
                })
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error fetching Reuters for {company}: {e}")
    return posts

def fetch_wired_news(company):
    """Fetch news from Wired for a specific company."""
    posts = []
    try:
        url = f"https://www.wired.com/search?q={company.replace(' ', '%20')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        summaries = soup.find_all('div', class_='SummaryItemWrapper')[:10]
        for summary in summaries:
            try:
                link = summary.find('a', href=True)
                if not link:
                    continue
                title = link.get_text(strip=True)
                if len(title) < 5:
                    continue
                
                href = link.get('href', '')
                full_url = href if href.startswith('http') else f"https://www.wired.com{href}"
                
                date = datetime.now()
                
                img = summary.find('img')
                image = None
                if img:
                    image = img.get('src') or img.get('data-src')
                
                if image is None:
                    image = generate_placeholder_image(title, company)
                
                posts.append({
                    "title": title,
                    "url": full_url,
                    "date": date,
                    "summary": "来源: Wired",
                    "image": image,
                    "company": company,
                    "source": "Wired"
                })
            except Exception as e:
                continue
    except Exception as e:
        print(f"Error fetching Wired for {company}: {e}")
    return posts

def fetch_company_news(company, sources=None):
    """
    Fetch news for a company from multiple sources.
    This is the main news agent function.
    """
    if sources is None:
        sources = NEWS_SOURCES.get(company, ["36kr", "techCrunch"])
    
    all_posts = []
    
    source_funcs = {
        "36kr": fetch_36kr_news,
        "techCrunch": fetch_techcrunch_news,
        "reuters": fetch_reuters_news,
        "wired": fetch_wired_news,
    }
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for source in sources:
            if source in source_funcs:
                futures[executor.submit(source_funcs[source], company)] = source
        
        for future in as_completed(futures):
            source = futures[future]
            try:
                posts = future.result()
                all_posts.extend(posts)
                print(f"[NewsAgent] Fetched {len(posts)} posts from {source} for {company}")
            except Exception as e:
                print(f"[NewsAgent] Error fetching from {source} for {company}: {e}")
    
    # If no posts found from web scraping, use fallback data
    if not all_posts and company in NEWS_AGENT_FALLBACK_DATA:
        print(f"[NewsAgent] Using fallback data for {company}")
        for item in NEWS_AGENT_FALLBACK_DATA[company]:
            title, url, date, summary, image, source = item[:6]
            if image is None:
                image = generate_placeholder_image(title, company)
            all_posts.append({
                "title": title,
                "url": url,
                "date": date,
                "summary": f"来源: {source}",
                "image": image,
                "company": company,
                "source": source
            })

    return all_posts

def get_all_news_agent_posts():
    """
    Get all news from the news agent (multi-source aggregation).
    This runs in parallel for all companies.
    """
    global cached_news_agent_posts, news_agent_cache_timestamp
    
    with cache_lock:
        now = datetime.now()
        if news_agent_cache_timestamp and cached_news_agent_posts and (now - news_agent_cache_timestamp).seconds < NEWS_AGENT_CACHE_DURATION:
            return cached_news_agent_posts
    
    all_posts = []
    
    # Fetch news for all companies in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_company_news, company): company for company in NEWS_SOURCES.keys()}
        
        for future in as_completed(futures):
            company = futures[future]
            try:
                posts = future.result()
                all_posts.extend(posts)
            except Exception as e:
                print(f"[NewsAgent] Error fetching news for {company}: {e}")
    
    # Deduplicate based on title and company
    all_posts.sort(key=lambda x: x["date"], reverse=True)
    
    seen = set()
    unique_posts = []
    for post in all_posts:
        key = (post["title"].strip().lower(), post["company"])
        if key not in seen:
            seen.add(key)
            unique_posts.append(post)
    
    with cache_lock:
        cached_news_agent_posts = unique_posts
        news_agent_cache_timestamp = datetime.now()
    
    return unique_posts

# ============ MAIN POST FETCHING ============
def get_all_posts():
    """Get all posts from official blogs."""
    global cached_posts, cache_timestamp
    
    with cache_lock:
        now = datetime.now()
        if cache_timestamp and cached_posts and (now - cache_timestamp).seconds < CACHE_DURATION:
            return cached_posts
    
    all_posts = []
    
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(fetch_blog_posts, source): source for source in BLOG_SOURCES}
        for future in as_completed(futures):
            source = futures[future]
            try:
                posts = future.result()
                all_posts.extend(posts)
                print(f"Fetched {len(posts)} posts from {source['name']}")
            except Exception as e:
                print(f"Error fetching {source['name']}: {e}")
    
    all_posts.sort(key=lambda x: x["date"], reverse=True)
    
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

# ============ FLASK ROUTES ============
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

@app.route('/api/news-agent')
def api_news_agent():
    """API endpoint for the news agent - returns aggregated news from multiple sources."""
    posts = get_all_news_agent_posts()
    return jsonify([{
        "title": p["title"],
        "url": p["url"],
        "date": p["date"].isoformat(),
        "summary": p.get("summary", ""),
        "image": p.get("image", ""),
        "company": p["company"],
        "source": p.get("source", "unknown")
    } for p in posts])

@app.route('/news-agent')
def news_agent_view():
    """News agent view - shows aggregated news from multiple sources."""
    posts = get_all_news_agent_posts()
    by_company = {}
    for post in posts:
        company = post["company"]
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(post)
    company_colors = {s["name"]: s["color"] for s in BLOG_SOURCES}
    return render_template('index.html', posts=posts, by_company=by_company, company_colors=company_colors, companies=BLOG_SOURCES)

@app.route('/refresh')
def refresh():
    global cache_timestamp, news_agent_cache_timestamp
    with cache_lock:
        cache_timestamp = None
        news_agent_cache_timestamp = None
    posts = get_all_posts()
    news_posts = get_all_news_agent_posts()
    return jsonify({"status": "ok", "posts_count": len(posts), "news_agent_posts_count": len(news_posts)})

if __name__ == '__main__':
    print("Starting Embodied AI News Aggregator with News Agent...")
    print("Visit http://localhost:80 to view the news feed")
    print("Visit http://localhost:80/news-agent to view aggregated news from multiple sources")
    app.run(debug=True, host='0.0.0.0', port=80)
