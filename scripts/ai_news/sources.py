"""
AIニュースの収集元（RSS/Atom）定義。

PwCコンサルティング合同会社のマネージャーが見るべき情報、という観点で
「日本のニュースサイトを基本」としつつ、海外の一次情報・規制動向を補う。

各ソースの属性:
    id       : 内部ID（重複判定・フィルタUIで使用）
    name     : 表示名
    url      : フィードURL
    lang     : "ja" | "en"   en は翻訳・日本語要約の対象
    region   : "domestic" | "global"
    tier     : 1=一次情報/重要メディア 2=一般メディア 3=参考
    tags     : 既定カテゴリのヒント（スコアリングの補助）
"""

from __future__ import annotations

# ──────────────────────────────────────────
# 国内（基本ソース）
# ──────────────────────────────────────────
DOMESTIC_SOURCES = [
    {
        "id": "itmedia_ai",
        "name": "ITmedia AI+",
        "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
        "lang": "ja", "region": "domestic", "tier": 1,
        "tags": ["技術・モデル", "企業導入"],
    },
    {
        "id": "itmedia_enterprise",
        "name": "ITmedia エンタープライズ",
        "url": "https://rss.itmedia.co.jp/rss/2.0/enterprise.xml",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "itmedia_news",
        "name": "ITmedia NEWS",
        "url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": [],
    },
    {
        "id": "atmarkit",
        "name": "＠IT",
        "url": "https://rss.itmedia.co.jp/rss/2.0/ait.xml",
        "lang": "ja", "region": "domestic", "tier": 3,
        "tags": ["技術・モデル"],
    },
    {
        "id": "nikkei_xtech",
        "name": "日経クロステック",
        "url": "https://xtech.nikkei.com/rss/xtech-it.rdf",
        "lang": "ja", "region": "domestic", "tier": 1,
        "tags": ["企業導入"],
    },
    {
        "id": "zdnet_jp",
        "name": "ZDNET Japan",
        "url": "https://japan.zdnet.com/rss/index.rdf",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "cnet_jp",
        "name": "CNET Japan",
        "url": "https://japan.cnet.com/rss/index.rdf",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": [],
    },
    {
        "id": "impress_cloud",
        "name": "クラウド Watch",
        "url": "https://cloud.watch.impress.co.jp/data/rss/1.0/clw/feed.rdf",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "impress_internet",
        "name": "INTERNET Watch",
        "url": "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf",
        "lang": "ja", "region": "domestic", "tier": 3,
        "tags": [],
    },
    {
        "id": "publickey",
        "name": "Publickey",
        "url": "https://www.publickey1.jp/atom.xml",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": ["技術・モデル"],
    },
    {
        "id": "sbbit",
        "name": "ビジネス+IT",
        "url": "https://www.sbbit.jp/rss/HotTopics.rss",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "ledge_ai",
        "name": "Ledge.ai",
        "url": "https://ledge.ai/feed/",
        "lang": "ja", "region": "domestic", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "meti",
        "name": "経済産業省 ニュースリリース",
        "url": "https://www.meti.go.jp/ml_index_release_atom.xml",
        "lang": "ja", "region": "domestic", "tier": 1,
        "tags": ["政策・規制"],
    },
    {
        "id": "digital_agency",
        "name": "デジタル庁",
        "url": "https://www.digital.go.jp/rss/news.xml",
        "lang": "ja", "region": "domestic", "tier": 1,
        "tags": ["政策・規制"],
    },
    {
        "id": "ppc_japan",
        "name": "個人情報保護委員会",
        "url": "https://www.ppc.go.jp/rss/news.xml",
        "lang": "ja", "region": "domestic", "tier": 1,
        "tags": ["政策・規制", "リスク・ガバナンス"],
    },
]

# ──────────────────────────────────────────
# 海外（日本語サマリを付けて表示する）
# ──────────────────────────────────────────
GLOBAL_SOURCES = [
    {
        "id": "openai",
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
        "lang": "en", "region": "global", "tier": 1,
        "tags": ["技術・モデル"],
    },
    {
        "id": "deepmind",
        "name": "Google DeepMind",
        "url": "https://deepmind.google/blog/rss.xml",
        "lang": "en", "region": "global", "tier": 1,
        "tags": ["技術・モデル"],
    },
    {
        "id": "anthropic",
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/news/rss.xml",
        "lang": "en", "region": "global", "tier": 1,
        "tags": ["技術・モデル"],
    },
    {
        "id": "aws_ml",
        "name": "AWS Machine Learning Blog",
        "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "lang": "en", "region": "global", "tier": 3,
        "tags": ["技術・モデル"],
    },
    {
        "id": "microsoft_ai",
        "name": "Microsoft AI Blog",
        "url": "https://blogs.microsoft.com/ai/feed/",
        "lang": "en", "region": "global", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "nvidia",
        "name": "NVIDIA Blog",
        "url": "https://blogs.nvidia.com/feed/",
        "lang": "en", "region": "global", "tier": 3,
        "tags": ["技術・モデル"],
    },
    {
        "id": "mit_tr_ai",
        "name": "MIT Technology Review (AI)",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        "lang": "en", "region": "global", "tier": 1,
        "tags": ["政策・規制", "技術・モデル"],
    },
    {
        "id": "techcrunch_ai",
        "name": "TechCrunch (AI)",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "lang": "en", "region": "global", "tier": 2,
        "tags": ["投資・M&A"],
    },
    {
        "id": "venturebeat_ai",
        "name": "VentureBeat (AI)",
        "url": "https://venturebeat.com/category/ai/feed/",
        "lang": "en", "region": "global", "tier": 2,
        "tags": ["企業導入"],
    },
    {
        "id": "verge_ai",
        "name": "The Verge (AI)",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "lang": "en", "region": "global", "tier": 3,
        "tags": [],
    },
    {
        "id": "stanford_hai",
        "name": "Stanford HAI",
        "url": "https://hai.stanford.edu/news/rss.xml",
        "lang": "en", "region": "global", "tier": 2,
        "tags": ["政策・規制"],
    },
    {
        "id": "sloan_review",
        "name": "MIT Sloan Management Review",
        "url": "https://sloanreview.mit.edu/feed/",
        "lang": "en", "region": "global", "tier": 2,
        "tags": ["コンサル・組織"],
    },
    {
        "id": "mckinsey",
        "name": "McKinsey Insights",
        "url": "https://www.mckinsey.com/insights/rss",
        "lang": "en", "region": "global", "tier": 1,
        "tags": ["コンサル・組織"],
    },
]

SOURCES = DOMESTIC_SOURCES + GLOBAL_SOURCES
SOURCES_BY_ID = {s["id"]: s for s in SOURCES}
