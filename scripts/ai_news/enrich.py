"""
Claude API による日本語化（海外記事の翻訳）と、PwCマネージャー視点の一言コメント付与。

ANTHROPIC_API_KEY が無い環境でも収集自体は止めない。
その場合、海外記事は原題のまま translated=False で表示され、
UI 側で「原文」バッジが付く（黙って欠落させない）。
"""

from __future__ import annotations

import json
import os
import re

MODEL = os.environ.get("AI_NEWS_MODEL", "claude-opus-5")
BATCH_SIZE = 8
# 1回の実行でAPIに渡す最大件数（コスト上限）
MAX_ENRICH_PER_RUN = int(os.environ.get("AI_NEWS_MAX_ENRICH", "40"))

SYSTEM_PROMPT = """\
あなたはPwCコンサルティング合同会社のマネージャー向けに、AIニュースを日本語で整理するアナリストです。

読者像:
- 国内大企業のクライアントにAI活用・DXを提案する立場のマネージャー
- 提案書・社内勉強会・クライアントとの会話ですぐ使える情報を求めている
- 技術の細部より「誰が・何を・どういう経営インパクトで」を重視する

各記事について次を作成してください。
- title_ja: 日本語の見出し（40字以内、誇張せず事実ベース。元が日本語ならほぼそのまま整える）
- summary_ja: 日本語の要約2〜3文（数字・固有名詞は保持。記事に書かれていない事実を足さない）
- insight: コンサルタント視点の一言（60字以内。クライアント提案・リスク説明のどこに効くか）
- confidence: 記事本文が十分か。"high"（要約に足る情報があった）/"low"（見出しのみで推測を含む）

厳守事項:
- 記事の情報だけを使い、推測で事実を作らない。情報が足りなければ confidence を "low" にする。
- 数値、企業名、製品名、日付は原文どおり正確に。
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title_ja": {"type": "string"},
                    "summary_ja": {"type": "string"},
                    "insight": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "low"]},
                },
                "required": ["id", "title_ja", "summary_ja", "insight", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["articles"],
    "additionalProperties": False,
}


def _client():
    """APIキーがある場合のみ Anthropic クライアントを返す。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        print("  [warn] anthropic パッケージが無いため日本語化をスキップします")
        return None
    return anthropic.Anthropic()


def _strip_html(text: str, limit: int = 700) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _needs_enrichment(item: dict) -> bool:
    """海外記事は必ず対象。国内記事は重要なものだけコメントを付ける。"""
    if item.get("lang") == "en":
        return True
    return item.get("priority") in ("must-read", "watch")


def _batch_payload(items: list[dict]) -> str:
    payload = [
        {
            "id": it["id"],
            "lang": it.get("lang", "ja"),
            "source": it.get("source_name", ""),
            "title": it.get("title_original") or it.get("title", ""),
            "body": _strip_html(it.get("summary_original") or it.get("summary", "")),
        }
        for it in items
    ]
    return json.dumps(payload, ensure_ascii=False, indent=1)


def enrich(items: list[dict]) -> tuple[list[dict], dict]:
    """
    items を破壊的に更新し、(items, 統計) を返す。
    APIが使えない場合も items は必ず表示可能な状態で返る。
    """
    stats = {"requested": 0, "enriched": 0, "skipped_no_api": 0, "errors": 0}

    # 表示用フィールドの既定値を必ず入れておく（UI側の分岐を減らす）
    for it in items:
        it.setdefault("title_original", it.get("title", ""))
        it.setdefault("summary_original", it.get("summary", ""))
        it.setdefault("translated", False)
        it.setdefault("insight", "")
        it.setdefault("confidence", "")

    targets = [it for it in items if _needs_enrichment(it) and not it.get("translated")]
    # 重要度の高い順にAPI予算を割り当てる
    targets.sort(key=lambda it: it.get("score", 0), reverse=True)
    targets = targets[:MAX_ENRICH_PER_RUN]
    stats["requested"] = len(targets)

    client = _client()
    if client is None:
        stats["skipped_no_api"] = len(targets)
        if targets:
            print(f"  [info] ANTHROPIC_API_KEY 未設定のため {len(targets)} 件を原文のまま掲載します")
        return items, stats

    by_id = {it["id"]: it for it in items}

    for start in range(0, len(targets), BATCH_SIZE):
        batch = targets[start:start + BATCH_SIZE]
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=8000,
                system=SYSTEM_PROMPT,
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
                },
                messages=[{
                    "role": "user",
                    "content": (
                        "次の記事を日本語で整理してください。"
                        "入力と同じ id をそのまま返してください。\n\n"
                        + _batch_payload(batch)
                    ),
                }],
            )
            text = next(b.text for b in response.content if b.type == "text")
            result = json.loads(text)
        except Exception as exc:  # APIエラーで収集全体を落とさない
            stats["errors"] += len(batch)
            print(f"  [warn] 日本語化に失敗（{len(batch)}件）: {type(exc).__name__}: {exc}")
            continue

        for article in result.get("articles", []):
            item = by_id.get(article.get("id"))
            if not item:
                continue
            title_ja = (article.get("title_ja") or "").strip()
            summary_ja = (article.get("summary_ja") or "").strip()
            if title_ja:
                item["title"] = title_ja
            if summary_ja:
                item["summary"] = summary_ja
            item["insight"] = (article.get("insight") or "").strip()
            item["confidence"] = article.get("confidence") or ""
            item["translated"] = True
            stats["enriched"] += 1

    return items, stats
