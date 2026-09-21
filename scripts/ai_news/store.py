"""フィードデータの永続化と重複排除。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

JST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "docs" / "data"
FEED_PATH = DATA_DIR / "feed.json"
DIGEST_DIR = DATA_DIR / "digests"
DIGEST_INDEX_PATH = DATA_DIR / "digests" / "index.json"
REPORT_DIR = BASE_DIR / "reports_ai"

# フィードに保持する期間と最大件数
RETENTION_DAYS = 14
MAX_ITEMS = 600

TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|ref|ref_src|cmpid|spm|from)", re.I)


def now_jst() -> datetime:
    return datetime.now(JST)


def canonical_url(url: str) -> str:
    """トラッキングパラメータを除いた比較用URL。"""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def title_key(title: str) -> str:
    """表記ゆれを吸収した見出しキー（別媒体の同一ニュース検出用）。"""
    norm = unicodedata.normalize("NFKC", title or "").lower()
    norm = re.sub(r"[\s　]+", "", norm)
    norm = re.sub(r"[「」『』【】［］\[\]（）()、。,\.\-–—:：/|｜!！?？\"'’”]", "", norm)
    return norm[:60]


def item_id(url: str, title: str) -> str:
    seed = canonical_url(url) or title_key(title)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def load_feed() -> dict:
    """既存フィードを読む。無ければ空の構造を返す。"""
    if FEED_PATH.exists():
        try:
            with FEED_PATH.open(encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("items", [])
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"generated_at": None, "runs": [], "items": []}


def merge_items(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int]:
    """
    既存フィードに新着をマージする。
    重複はURL正規化 → 見出しキーの順で判定し、新着数を返す。
    """
    by_id = {it["id"]: it for it in existing}
    seen_titles = {title_key(it.get("title_original") or it.get("title", "")): it["id"]
                   for it in existing}
    added = 0

    for item in incoming:
        if item["id"] in by_id:
            # 既出：判定結果だけ最新に更新する（記事は増やさない）。
            # 分類ルールを直した際に、古い記事の表示も追随させるため。
            by_id[item["id"]].update({
                "score": item["score"],
                "priority": item["priority"],
                "category": item["category"],
                "reasons": item["reasons"],
            })
            continue
        tkey = title_key(item.get("title_original") or item.get("title", ""))
        if tkey and tkey in seen_titles:
            # 別媒体の同一ニュース：先着を残し、関連ソースとして記録
            original = by_id[seen_titles[tkey]]
            also = original.setdefault("also_reported_by", [])
            if item["source_name"] not in also and item["source_name"] != original["source_name"]:
                also.append(item["source_name"])
            continue
        by_id[item["id"]] = item
        if tkey:
            seen_titles[tkey] = item["id"]
        added += 1

    merged = list(by_id.values())
    cutoff = now_jst() - timedelta(days=RETENTION_DAYS)
    merged = [it for it in merged if _published_dt(it) >= cutoff]
    merged.sort(key=lambda it: (_published_dt(it), it.get("score", 0)), reverse=True)
    return merged[:MAX_ITEMS], added


def _published_dt(item: dict) -> datetime:
    try:
        return datetime.fromisoformat(item["published_at"])
    except (KeyError, ValueError, TypeError):
        return datetime.fromtimestamp(0, JST)


def save_feed(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with FEED_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def save_digest(date_str: str, digest: dict) -> None:
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    with (DIGEST_DIR / f"{date_str}.json").open("w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=1)

    index = []
    for path in sorted(DIGEST_DIR.glob("20*.json"), reverse=True)[:90]:
        try:
            with path.open(encoding="utf-8") as f:
                d = json.load(f)
            index.append({
                "date": d.get("date", path.stem),
                "headline": d.get("headline", ""),
                "item_count": len(d.get("highlights", [])),
            })
        except (json.JSONDecodeError, OSError):
            continue
    with DIGEST_INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
