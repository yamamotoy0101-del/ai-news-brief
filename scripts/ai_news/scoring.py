"""
記事のAI関連度判定・カテゴリ分類・重要度スコアリング。

想定読者は「PwCコンサルティング合同会社のマネージャー」。
クライアント提案・社内ナレッジ・リスク説明に直結する記事ほど高スコアにする。
APIキーが無くてもここまでは必ず動く（キーワードベース）。
"""

from __future__ import annotations

import re
import unicodedata

# ──────────────────────────────────────────
# 1. AI関連度ゲート（一般テック記事を落とす）
# ──────────────────────────────────────────
AI_TERMS = [
    "ai", "a.i.", "人工知能", "生成ai", "生成系ai", "ジェネレーティブ",
    "genai", "generative ai", "llm", "大規模言語モデル", "言語モデル",
    "chatgpt", "gpt-", "gpt4", "gpt5", "claude", "gemini", "copilot",
    "llama", "mistral", "deepseek", "sora", "midjourney", "stable diffusion",
    "機械学習", "machine learning", "ディープラーニング", "deep learning",
    "ニューラルネット", "neural network", "transformer", "トランスフォーマー",
    "agentic", "aiエージェント", "ai agent", "エージェント型",
    "rag", "ファインチューニング", "fine-tun", "推論基盤", "inference",
    "openai", "anthropic", "deepmind", "hugging face", "nvidia",
    "基盤モデル", "foundation model", "マルチモーダル", "multimodal",
    "プロンプト", "prompt", "vibe coding", "mcp",
]

# 誤検出しやすい語（単体では AI と見なさない）
AI_FALSE_FRIENDS = re.compile(r"(said|paid|maid|aid\b|air\b|aim\b)", re.I)


def _norm(text: str) -> str:
    """全角→半角、小文字化した比較用テキスト。"""
    return unicodedata.normalize("NFKC", text or "").lower()


def is_ai_related(title: str, summary: str = "", source_tags=None) -> bool:
    """AI関連記事かどうか。AI専門ソースのタグがあれば緩める。"""
    blob = _norm(f"{title} {summary}")
    for term in AI_TERMS:
        if term == "ai":
            # 単語としての "AI" のみ拾う（"said" などを除外）
            if re.search(r"(?<![a-z])ai(?![a-z])", blob) and not AI_FALSE_FRIENDS.search(title or ""):
                return True
            continue
        if term in blob:
            return True
    return False


# ──────────────────────────────────────────
# 2. カテゴリ分類
# ──────────────────────────────────────────
CATEGORY_RULES = [
    ("政策・規制", [
        "規制", "法案", "法律", "ガイドライン", "指針", "省令", "政府", "総務省",
        "経済産業省", "経産省", "デジタル庁", "個人情報保護", "ai事業者",
        "ai基本法", "eu ai act", "ai act", "regulation", "policy", "lawmaker",
        "議会", "国会", "パブリックコメント", "標準化", "iso", "nist",
        "executive order", "compliance", "著作権", "copyright",
        "規制当局", "当局", "公聴会", "行政指導", "義務", "透明性", "開示",
        "regulator", "probe", "inquiry", "antitrust", "watchdog", "obligation",
        "transparency", "enforcement", "ruling", "court", "裁判所", "命令",
    ]),
    ("リスク・ガバナンス", [
        "リスク", "ガバナンス", "セキュリティ", "情報漏えい", "情報漏洩", "脆弱性",
        "ディープフェイク", "deepfake", "ハルシネーション", "hallucination",
        "バイアス", "bias", "倫理", "ethic", "safety", "監査", "audit",
        "内部統制", "プライバシー", "privacy", "訴訟", "lawsuit", "breach",
        "不正", "誤作動", "責任", "liability",
        "誤り", "誤情報", "誤回答", "誤出力", "謝罪", "炎上", "差別",
        "不適切", "撤回", "利用停止", "検証体制", "人権", "misinformation",
        "inaccurate", "apolog", "withdraw", "misuse",
    ]),
    ("投資・M&A", [
        # 「調達」単体は購買（部材調達・調達部門）と紛らわしいので入れない
        "資金調達", "出資", "買収", "m&a", "ipo", "上場", "時価総額",
        "funding", "raise", "raised", "acquisition", "acquires", "valuation",
        "investment", "億円", "billion", "million", "決算", "earnings",
    ]),
    ("企業導入", [
        "導入", "実証実験", "poc", "内製", "dx", "業務効率",
        "全社", "導入事例", "enterprise", "deployment", "adoption",
        "rollout", "case study", "生産性", "productivity", "業務改革",
        "基幹システム", "erp", "コンタクトセンター", "業務効率化", "業務提携",
        "協業", "共同検証", "実用化", "運用開始", "本格展開", "横展開",
        "現場", "社内利用", "利用開始", "採用事例", "商用化",
        "社内業務", "定型業務", "バックオフィス", "自動化", "移行",
        "企業向け", "法人向け", "業務プロセス", "workflow", "業務フロー",
    ]),
    ("コンサル・組織", [
        "コンサル", "consult", "accenture", "アクセンチュア", "deloitte",
        "デロイト", "kpmg", "ey", "pwc", "mckinsey", "マッキンゼー", "bcg",
        "人材", "採用", "リスキリング", "reskilling", "組織", "働き方",
        "雇用", "workforce", "talent", "job", "レイオフ", "layoff",
        "スキル", "研修", "教育",
    ]),
    ("技術・モデル", [
        # 「発表」「公開」はほぼ全記事に出るため、分類の根拠にはしない
        "モデル", "model", "リリース", "release", "launch",
        "ベンチマーク", "benchmark", "オープンソース",
        "open source", "api", "gpu", "半導体", "データセンター", "推論",
        "研究", "research", "論文", "paper",
    ]),
]

DEFAULT_CATEGORY = "その他"
CATEGORIES = [c for c, _ in CATEGORY_RULES] + [DEFAULT_CATEGORY]


# 規制・リスクは見落とすと痛いので、同程度のヒット数なら優先して拾う
CATEGORY_PRIORITY = {
    "政策・規制": 1.6,
    "リスク・ガバナンス": 1.5,
    "コンサル・組織": 1.2,
    "投資・M&A": 1.1,
    "企業導入": 1.0,
    "技術・モデル": 0.7,
}


def classify(title: str, summary: str = "", source_tags=None) -> str:
    """最もマッチしたカテゴリを1つ返す。ヒット数にカテゴリ重みを掛けて比較する。"""
    blob = _norm(f"{title} {summary}")
    best, best_weight = None, 0.0
    for category, keywords in CATEGORY_RULES:
        hits = sum(1 for kw in keywords if kw in blob)
        weighted = hits * CATEGORY_PRIORITY.get(category, 1.0)
        if weighted > best_weight:
            best, best_weight = category, weighted
    if best:
        return best
    for tag in (source_tags or []):
        if tag in CATEGORIES:
            return tag
    return DEFAULT_CATEGORY


# ──────────────────────────────────────────
# 3. 重要度スコア（PwCマネージャー視点）
# ──────────────────────────────────────────
# 提案・クライアント対応に直接効く論点ほど重く配点する
SIGNAL_WEIGHTS = {
    # 規制・制度は「クライアントへの説明責任」に直結。最重要。
    "政策・規制": 18,
    "リスク・ガバナンス": 15,
    "コンサル・組織": 12,
    "企業導入": 11,
    "投資・M&A": 8,
    "技術・モデル": 6,
    DEFAULT_CATEGORY: 3,
}

# 個別キーワードの加点（カテゴリ配点に上乗せ）
BOOST_KEYWORDS = {
    # 日本の制度・当局
    "ai事業者ガイドライン": 12, "ai基本法": 12, "個人情報保護法": 10,
    "経済産業省": 8, "総務省": 8, "デジタル庁": 8, "金融庁": 8,
    "公正取引委員会": 7, "パブリックコメント": 6,
    # グローバル規制
    "eu ai act": 12, "ai act": 10, "gdpr": 8, "nist": 6, "iso/iec 42001": 10,
    # 自社（PwC）関連は読者にとって最優先。競合ファームの動向がこれに次ぐ。
    "pwc": 20, "プライスウォーターハウス": 20, "accenture": 10, "アクセンチュア": 10, "deloitte": 9,
    "デロイト": 9, "kpmg": 8, "ey": 7, "mckinsey": 8, "マッキンゼー": 8,
    "bcg": 7, "ベイン": 6,
    # 日本の大手クライアント層
    "トヨタ": 6, "ソニー": 5, "ntt": 6, "ソフトバンク": 6, "日立": 6,
    "三菱": 5, "みずほ": 5, "三井住友": 5, "野村": 5, "富士通": 5,
    "nec": 5, "パナソニック": 5, "kddi": 5, "楽天": 4, "サイバーエージェント": 4,
    # 経営インパクト
    "全社": 8, "国内初": 6, "業界初": 5, "実証実験": 4, "roi": 7,
    "投資対効果": 7, "生産性": 5, "人員削減": 7, "レイオフ": 6,
    "内製化": 6, "エンタープライズ": 4,
    # 主要プレイヤー
    "openai": 6, "anthropic": 6, "google": 4, "microsoft": 5,
    "nvidia": 4, "meta": 3, "amazon": 3,
    # 減点したい話題（消費者向けガジェットなど）
}

PENALTY_KEYWORDS = {
    "セール": -8, "値下げ": -6, "クーポン": -8, "ふるさと納税": -10,
    "レビュー": -4, "ゲーム": -5, "アニメ": -5, "スマホ新製品": -5,
    "deal": -6, "discount": -6, "giveaway": -8, "gift guide": -10,
}

TIER_BONUS = {1: 8, 2: 3, 3: 0}


def score(item: dict, source: dict) -> tuple[int, list[str]]:
    """
    重要度スコア(0-100)と、その根拠ラベルを返す。

    item   : {"title", "summary", "category", ...}
    source : sources.py のソース定義
    """
    blob = _norm(f"{item.get('title','')} {item.get('summary','')}")
    reasons: list[str] = []

    category = item.get("category", DEFAULT_CATEGORY)
    total = SIGNAL_WEIGHTS.get(category, 3)
    if total >= 11:
        reasons.append(f"{category}カテゴリ")

    tier_bonus = TIER_BONUS.get(source.get("tier", 3), 0)
    total += tier_bonus
    if tier_bonus >= 8:
        reasons.append("一次情報・重要メディア")

    hit_boosts: list[tuple[str, int]] = []
    for kw, weight in BOOST_KEYWORDS.items():
        if kw in blob:
            total += weight
            hit_boosts.append((kw, weight))
    for kw, weight in PENALTY_KEYWORDS.items():
        if kw in blob:
            total += weight

    # 上位3件の加点キーワードを根拠として残す
    for kw, _w in sorted(hit_boosts, key=lambda x: -x[1])[:3]:
        reasons.append(kw.upper() if kw.isascii() else kw)

    # 国内ソースは基本重視（ユーザー指定：ソースは基本的に日本）
    if source.get("region") == "domestic":
        total += 5

    # 本文要約が取れている記事はレビュー価値が高い
    if len(item.get("summary", "")) > 120:
        total += 2

    total = max(0, min(100, int(total)))
    return total, reasons[:4]


def priority_label(score_value: int) -> str:
    """スコアを3段階のラベルに落とす（UIのバッジ用）。"""
    if score_value >= 36:
        return "must-read"
    if score_value >= 24:
        return "watch"
    return "reference"
