"""
AIニュース収集ロジックの回帰テスト（ネットワーク不要）。

    python scripts/test_ai_news.py

分類ルールやスコア配点を変更したら必ず実行する。
収集ワークフローでも取得前に走らせ、壊れたルールで上書きするのを防ぐ。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_news import scoring, store

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    if condition:
        print(f"  OK  {label}")
    else:
        print(f"  NG  {label}")
        failures.append(label)


# ──────────────────────────────────────────
print("AI関連度の判定")
# ──────────────────────────────────────────
AI_YES = [
    ("経済産業省、AI事業者ガイドラインを改定", ""),
    ("生成AIで議事録作成を自動化", ""),
    ("OpenAI releases new enterprise agent platform", ""),
    ("大規模言語モデルの推論コストが半減", ""),
    ("新製品を発表", "同社は機械学習を用いた需要予測機能を搭載したと説明する。"),
]
AI_NO = [
    ("【セール】人気キーボードが30%値下げ", "本日限りのセール情報"),
    ("Amazon said the deal is paid in full", "Retail earnings roundup"),
    ("新型スマートフォンのカメラ性能を検証", "夜景撮影の画質を比較した"),
]
for title, summary in AI_YES:
    check(scoring.is_ai_related(title, summary), f"AI記事と判定: {title[:34]}")
for title, summary in AI_NO:
    check(not scoring.is_ai_related(title, summary), f"非AI記事を除外: {title[:34]}")

# ──────────────────────────────────────────
print("\nカテゴリ分類")
# ──────────────────────────────────────────
CLASSIFY_CASES = [
    ("経済産業省、AI事業者ガイドラインを改定",
     "生成AI利用企業に内部統制の整備を要請", "政策・規制"),
    ("EU regulators open probe into enterprise AI deployments",
     "European regulators opened a formal inquiry into transparency obligations under the AI Act.",
     "政策・規制"),
    ("生成AIの誤出力で顧客情報が流出　企業が謝罪",
     "セキュリティ上の脆弱性が原因だった", "リスク・ガバナンス"),
    ("アクセンチュア、AI人材2万人を追加採用へ",
     "コンサルティング需要の高まりに対応", "コンサル・組織"),
    ("AI半導体スタートアップ、600億円を調達",
     "シリーズDで4億ドルを調達した。", "投資・M&A"),
    # 「調達」を購買の意味で使う記事を投資・M&Aに誤分類しないこと
    ("Microsoft、社内業務の30%をAIエージェントに移行と発表",
     "定型業務のうち約30%を移行した。対象は調達と経理の一部プロセス。", "企業導入"),
    ("国内銀行3行、AI与信モデルの共同検証で合意",
     "2027年度の実用化を目指す。", "企業導入"),
    # 「発表」「公開」だけで技術・モデルに寄らないこと
    ("OpenAI、企業向けAIエージェント基盤を公開　監査ログと権限管理を標準搭載",
     "企業の業務フローにAIエージェントを展開するための基盤を発表した。", "企業導入"),
    ("新モデルGPT-6をリリース、ベンチマークで首位",
     "オープンソース版も公開", "技術・モデル"),
]
for title, summary, expected in CLASSIFY_CASES:
    actual = scoring.classify(title, summary)
    check(actual == expected, f"{expected:<11} ← {title[:32]}"
                              + ("" if actual == expected else f"（実際: {actual}）"))

# ──────────────────────────────────────────
print("\n重要度スコア")
# ──────────────────────────────────────────
TIER1_DOMESTIC = {"tier": 1, "region": "domestic"}
TIER3_DOMESTIC = {"tier": 3, "region": "domestic"}


def scored(title: str, summary: str, source: dict) -> int:
    item = {"title": title, "summary": summary,
            "category": scoring.classify(title, summary)}
    return scoring.score(item, source)[0]


regulation = scored("経済産業省、AI事業者ガイドラインを改定",
                    "生成AI利用企業に内部統制の整備を要請", TIER1_DOMESTIC)
gadget = scored("AI搭載スマートスピーカーのレビュー",
                "実際に使ってみた感想をお届けします", TIER3_DOMESTIC)
check(scoring.priority_label(regulation) == "must-read",
      f"規制記事が要チェック（score={regulation}）")
check(regulation > gadget + 20, f"規制記事 > 消費者向け記事（{regulation} vs {gadget}）")
check(scoring.priority_label(gadget) == "reference", f"レビュー記事は参考（score={gadget}）")

pwc = scored("PwC、生成AIコンサルティング部門を新設", "1000人規模で立ち上げる", TIER1_DOMESTIC)
check(scoring.priority_label(pwc) == "must-read", f"自社関連が要チェック（score={pwc}）")

# ──────────────────────────────────────────
print("\n重複排除")
# ──────────────────────────────────────────
check(store.canonical_url("https://Example.com/a/?utm_source=x&id=3")
      == store.canonical_url("https://example.com/a?id=3"),
      "トラッキングパラメータと末尾スラッシュを無視する")
check(store.title_key("トヨタ、全社で生成AI基盤を導入　7万人が利用へ")
      == store.title_key("トヨタ、全社で生成AI基盤を導入 7万人が利用へ"),
      "全角スペース・約物の差を吸収する")
check(store.title_key("AI規制") != store.title_key("AI導入"), "別見出しは別キーになる")

base = {
    "id": "x1", "title": "トヨタ、生成AIを全社導入", "title_original": "トヨタ、生成AIを全社導入",
    "published_at": store.now_jst().isoformat(), "source_name": "媒体A",
    "score": 40, "priority": "must-read", "category": "企業導入", "reasons": [],
}
other_source = dict(base, id="x2", source_name="媒体B",
                    title_original="トヨタ、生成AIを全社導入 ")
merged, added = store.merge_items([base], [other_source])
check(added == 0 and len(merged) == 1, "別媒体の同一ニュースを増やさない")
check(merged[0].get("also_reported_by") == ["媒体B"], "重複元を関連媒体として記録する")

fresh = dict(base, id="x3", title="別のニュース", title_original="別のニュース")
merged, added = store.merge_items([base], [fresh])
check(added == 1 and len(merged) == 2, "別ニュースは追加される")

# ──────────────────────────────────────────
print()
if failures:
    print(f"失敗 {len(failures)} 件:")
    for f in failures:
        print(f"  - {f}")
    raise SystemExit(1)
print("全テスト通過")
