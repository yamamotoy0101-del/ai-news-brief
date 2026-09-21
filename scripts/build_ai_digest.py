"""
1日1回のサマリノート生成（夜の収集後に実行）。

その日のフィードから重要記事を選び、PwCマネージャー視点で
「何が起きたか / だから何なのか」をまとめた日次ノートを作る。

出力:
    docs/data/digests/YYYY-MM-DD.json   … UI表示用
    reports_ai/YYYY-MM-DD.md            … メール送信・保管用

ANTHROPIC_API_KEY が無い場合はスコア順の機械的な抽出のみを行い、
generated_by="score-only" として「要約ではない」ことを明示する。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_news import store

MODEL = os.environ.get("AI_NEWS_DIGEST_MODEL", "claude-opus-5")
# 1日の候補上限。フィードが薄い日は select_candidates が48時間まで広げる。
MAX_CANDIDATES = 28
MAX_HIGHLIGHTS = 6

SYSTEM_PROMPT = """\
あなたはPwCコンサルティング合同会社のマネージャー向けに、その日のAIニュースを
1本のサマリノートにまとめるアナリストです。

読者像:
- 国内大企業のクライアントにAI活用・DXを提案する立場のマネージャー
- 朝の移動中に3分で読み、その日のクライアントとの会話で使いたい
- 「技術的に何が新しいか」より「自分の案件・提案にどう効くか」を知りたい

作成物:
- headline: その日を一言で表す見出し（30字以内）
- overview: 全体観を3〜4文。個別記事の羅列ではなく、その日の潮流として書く
- highlights: 重要記事を3〜6本。それぞれ
    - item_id: 入力の id をそのまま
    - point: 何が起きたか（1〜2文、事実のみ）
    - so_what: コンサルタントとして何を意味するか（1〜2文。提案・リスク・クライアントへの示唆）
- watchlist: 今後1〜2週間で注視すべき論点を2〜4個（各30字以内の短文）

厳守事項:
- 入力にある記事の情報だけを使う。推測で事実・数値・企業名を作らない。
- so_what は具体的に書く。「注目される」「重要だ」のような中身のない表現は使わない。
- 重要な記事が無い日は、無理に盛らず highlights を少なくしてよい。
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "overview": {"type": "string"},
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "point": {"type": "string"},
                    "so_what": {"type": "string"},
                },
                "required": ["item_id", "point", "so_what"],
                "additionalProperties": False,
            },
        },
        "watchlist": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "overview", "highlights", "watchlist"],
    "additionalProperties": False,
}


def select_candidates(items: list[dict], target_date: datetime) -> list[dict]:
    """当日分の記事を、カテゴリが偏らないようスコア順に選ぶ。"""
    start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    todays = []
    for item in items:
        try:
            published = datetime.fromisoformat(item["published_at"])
        except (KeyError, ValueError, TypeError):
            continue
        if start <= published < end:
            todays.append(item)

    # 当日分が乏しい日（休日・年末年始）は直近48時間まで広げる
    if len(todays) < 8:
        widened = []
        for item in items:
            try:
                published = datetime.fromisoformat(item["published_at"])
            except (KeyError, ValueError, TypeError):
                continue
            if end - timedelta(days=2) <= published < end:
                widened.append(item)
        todays = widened

    todays.sort(key=lambda i: i.get("score", 0), reverse=True)

    # カテゴリごとの上限を設けて、同じ話題で埋まるのを防ぐ
    per_category: dict[str, int] = {}
    selected = []
    for item in todays:
        category = item.get("category", "その他")
        if per_category.get(category, 0) >= 6:
            continue
        per_category[category] = per_category.get(category, 0) + 1
        selected.append(item)
        if len(selected) >= MAX_CANDIDATES:
            break
    return selected


def _payload(items: list[dict]) -> str:
    return json.dumps([
        {
            "id": it["id"],
            "title": it.get("title", ""),
            "summary": it.get("summary", "")[:400],
            "category": it.get("category", ""),
            "source": it.get("source_name", ""),
            "region": it.get("region", ""),
            "score": it.get("score", 0),
        }
        for it in items
    ], ensure_ascii=False, indent=1)


def generate_with_claude(items: list[dict], date_str: str) -> dict | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        print("[warn] anthropic パッケージが無いためサマリ生成をスキップします")
        return None

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
            },
            messages=[{
                "role": "user",
                "content": (
                    f"{date_str} のAIニュース候補です。サマリノートを作成してください。\n\n"
                    + _payload(items)
                ),
            }],
        )
    except Exception as exc:
        print(f"[warn] サマリ生成に失敗しました: {type(exc).__name__}: {exc}")
        return None

    if response.stop_reason == "refusal":
        print("[warn] サマリ生成が拒否されました。スコア順の抽出に切り替えます。")
        return None

    try:
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except (StopIteration, json.JSONDecodeError) as exc:
        print(f"[warn] サマリの解析に失敗しました: {exc}")
        return None


def fallback_digest(items: list[dict]) -> dict:
    """API未設定・失敗時。要約はせず、スコア上位を機械的に並べる。"""
    highlights = []
    for it in items[:MAX_HIGHLIGHTS]:
        reasons = it.get("reasons", [])
        so_what = (
            "（自動要約なし）スコアの根拠: " + "、".join(reasons)
            if reasons else "（自動要約なし）"
        )
        highlights.append({
            "item_id": it["id"],
            "point": it.get("summary", "")[:160] or it.get("title", ""),
            "so_what": so_what,
        })
    return {
        "headline": "重要度スコア上位の記事（自動要約なし）",
        "overview": (
            "Claude APIが利用できなかったため、要約は生成していません。"
            "以下はキーワードベースの重要度スコアが高い順に並べた記事です。"
        ),
        "highlights": highlights,
        "watchlist": [],
    }


def build_markdown(digest: dict, date_str: str) -> str:
    lines = [
        f"# AIニュース サマリノート {date_str}",
        "",
        f"## {digest['headline']}",
        "",
        digest["overview"],
        "",
        "## 注目ニュース",
        "",
    ]
    for i, highlight in enumerate(digest.get("highlights", []), 1):
        item = highlight.get("item", {})
        lines += [
            f"### {i}. {item.get('title', '（見出し不明）')}",
            "",
            f"- 出典: {item.get('source_name', '')}（{item.get('category', '')}）",
            f"- URL: {item.get('url', '')}",
            f"- 何が起きたか: {highlight.get('point', '')}",
            f"- 示唆: {highlight.get('so_what', '')}",
            "",
        ]
    if digest.get("watchlist"):
        lines += ["## 今後の注視点", ""]
        lines += [f"- {w}" for w in digest["watchlist"]]
        lines.append("")
    lines += [
        "---",
        "",
        f"生成方法: {digest.get('generated_by', 'unknown')} / "
        f"候補記事 {digest.get('candidate_count', 0)} 件",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="AIニュースの日次サマリノートを生成する")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD)。既定は今日")
    parser.add_argument("--dry-run", action="store_true", help="ファイルに保存しない")
    args = parser.parse_args()

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=store.JST)
    else:
        target = store.now_jst()
    date_str = target.strftime("%Y-%m-%d")

    feed = store.load_feed()
    items = feed.get("items", [])
    if not items:
        print("フィードが空です。先に fetch_ai_news.py を実行してください。")
        return 1

    candidates = select_candidates(items, target)
    print(f"{date_str} の候補記事: {len(candidates)} 件")
    if not candidates:
        print("対象日の記事がありません。")
        return 1

    result = generate_with_claude(candidates, date_str)
    generated_by = MODEL if result else "score-only"
    if result is None:
        result = fallback_digest(candidates)

    # highlights に記事本体を結合する（UI・Markdown双方で使う）
    by_id = {it["id"]: it for it in candidates}
    highlights = []
    for highlight in result.get("highlights", [])[:MAX_HIGHLIGHTS]:
        item = by_id.get(highlight.get("item_id"))
        if not item:
            continue
        highlights.append({
            "point": highlight.get("point", ""),
            "so_what": highlight.get("so_what", ""),
            "item": {
                "id": item["id"],
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source_name": item.get("source_name", ""),
                "category": item.get("category", ""),
                "region": item.get("region", ""),
                "score": item.get("score", 0),
            },
        })

    digest = {
        "date": date_str,
        "generated_at": store.now_jst().isoformat(),
        "generated_by": generated_by,
        "candidate_count": len(candidates),
        "headline": result.get("headline", ""),
        "overview": result.get("overview", ""),
        "highlights": highlights,
        "watchlist": result.get("watchlist", []),
    }

    markdown = build_markdown(digest, date_str)

    if args.dry_run:
        print("\n[dry-run] 保存しません。\n")
        print(markdown)
        return 0

    store.save_digest(date_str, digest)
    store.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (store.REPORT_DIR / f"{date_str}.md").write_text(markdown, encoding="utf-8")
    print(f"保存しました: docs/data/digests/{date_str}.json, reports_ai/{date_str}.md")
    print(f"生成方法: {generated_by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
