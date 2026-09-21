"""
AIニュース収集（朝・昼・夜の1日3回実行）。

RSS/Atomを巡回 → AI関連記事を抽出 → 重要度スコアリング → 日本語化 → docs/data/feed.json

使い方:
    python scripts/fetch_ai_news.py            # 通常実行
    python scripts/fetch_ai_news.py --dry-run  # 保存せず結果だけ表示
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feedparser
import requests

from ai_news import enrich, scoring, store
from ai_news.sources import SOURCES

# 一部の媒体（ZDNET/CNET Japan、VentureBeat 等）はボット系のUAを拒否するため、
# 通常のブラウザと同じUAを送る。
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT = 25
REQUEST_INTERVAL = 1.0
# この時間より古い記事は新規取り込みしない
MAX_AGE_HOURS = 36


def slot_label(now: datetime) -> str:
    """実行時刻から朝／昼／夜のラベルを決める。"""
    hour = now.hour
    if 4 <= hour < 11:
        return "朝"
    if 11 <= hour < 17:
        return "昼"
    return "夜"


def parse_published(entry, fallback: datetime) -> datetime:
    """フィードの日時を JST の datetime に変換する。"""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                naive = datetime(*parsed[:6])
                return naive.replace(tzinfo=timezone.utc).astimezone(store.JST)
            except (TypeError, ValueError):
                continue
    return fallback


def fetch_source(source: dict, now: datetime) -> tuple[list[dict], str, bool]:
    """
    1ソースを取得して (記事リスト, 状態文字列, フィードが生きているか) を返す。

    状態文字列は「ソース状況」タブにそのまま出るので、原因が切り分けられる
    粒度にする（HTTPステータス、フィードの総件数など）。
    """
    try:
        response = requests.get(
            source["url"],
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "不明"
        return [], f"取得失敗 (HTTP {code})", False
    except requests.RequestException as exc:
        return [], f"取得失敗 ({type(exc).__name__})", False

    parsed = feedparser.parse(response.content)
    total = len(parsed.entries)
    if total == 0:
        return [], "フィードが空（URLの形式を確認）", False

    cutoff = now - timedelta(hours=MAX_AGE_HOURS)
    collected: list[dict] = []

    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue

        raw_summary = entry.get("summary") or entry.get("description") or ""
        summary = enrich._strip_html(raw_summary)

        if not scoring.is_ai_related(title, summary, source.get("tags")):
            continue

        published = parse_published(entry, now)
        if published < cutoff:
            continue
        if published > now + timedelta(hours=6):
            # フィード側の日付異常はスキップせず現在時刻に寄せる
            published = now

        category = scoring.classify(title, summary, source.get("tags"))
        item = {
            "id": store.item_id(link, title),
            "title": title,
            "title_original": title,
            "summary": summary,
            "summary_original": summary,
            "url": link,
            "source_id": source["id"],
            "source_name": source["name"],
            "lang": source["lang"],
            "region": source["region"],
            "category": category,
            "published_at": published.isoformat(),
            "collected_at": now.isoformat(),
            "slot": slot_label(now),
            "translated": source["lang"] == "ja",
            "insight": "",
            "confidence": "",
        }
        score_value, reasons = scoring.score(item, source)
        item["score"] = score_value
        item["priority"] = scoring.priority_label(score_value)
        item["reasons"] = reasons
        collected.append(item)

    # フィード自体は取れているがAI記事が無い日もある。障害と区別できるようにする。
    if not collected:
        return [], f"AI関連なし（全{total}件）", True
    return collected, f"{len(collected)}件 / 全{total}件", True


def main() -> int:
    parser = argparse.ArgumentParser(description="AIニュースを収集してフィードを更新する")
    parser.add_argument("--dry-run", action="store_true", help="ファイルに保存しない")
    parser.add_argument("--no-enrich", action="store_true", help="Claude APIによる日本語化を行わない")
    args = parser.parse_args()

    now = store.now_jst()
    slot = slot_label(now)
    print(f"=== AIニュース収集 {now:%Y-%m-%d %H:%M} JST（{slot}の便）===")

    incoming: list[dict] = []
    source_status: list[dict] = []

    for source in SOURCES:
        items, status, alive = fetch_source(source, now)
        source_status.append({
            "id": source["id"], "name": source["name"],
            "region": source["region"], "status": status,
            "ok": alive,
        })
        marker = "OK " if items else "-- "
        print(f"{marker}{source['name']:<28} {status}")
        incoming.extend(items)
        time.sleep(REQUEST_INTERVAL)

    print(f"\nAI関連記事 {len(incoming)} 件を取得")

    feed = store.load_feed()
    merged, added = store.merge_items(feed.get("items", []), incoming)
    print(f"重複除去後の新着: {added} 件 / フィード総数 {len(merged)} 件")

    if not args.no_enrich:
        merged, enrich_stats = enrich.enrich(merged)
        print(f"日本語化: 対象{enrich_stats['requested']}件 "
              f"/ 完了{enrich_stats['enriched']}件 "
              f"/ エラー{enrich_stats['errors']}件")
    else:
        enrich_stats = {"requested": 0, "enriched": 0, "errors": 0, "skipped_no_api": 0}

    runs = feed.get("runs", [])
    runs.insert(0, {
        "at": now.isoformat(),
        "slot": slot,
        "fetched": len(incoming),
        "added": added,
        "enriched": enrich_stats["enriched"],
    })
    feed.update({
        "generated_at": now.isoformat(),
        "slot": slot,
        "items": merged,
        "runs": runs[:30],
        "sources": source_status,
    })

    if args.dry_run:
        print("\n[dry-run] 保存しません。上位5件:")
        for item in sorted(merged, key=lambda i: i["score"], reverse=True)[:5]:
            print(f"  [{item['score']:>3}] {item['category']:<12} {item['title'][:50]}")
        return 0

    store.save_feed(feed)
    print(f"\n保存しました: {store.FEED_PATH.relative_to(store.BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
