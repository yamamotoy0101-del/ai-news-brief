# AI News Brief

PwCコンサルティング合同会社のマネージャーが見るべきAIニュースを、1日3回自動で集めて
日本語で整理するフィードアプリ。サーバー不要（GitHub Actions + GitHub Pages）。

**公開URL: https://yamamotoy0101-del.github.io/ai-news-brief/**

- **収集**: 朝7:00 ／ 昼12:30 ／ 夜21:00（JST）に国内13・海外11サイトのRSSを巡回
- **サマリノート**: 毎日22:30（JST）にその日の重要ニュースをまとめる
- **ソース**: 国内サイトが基本。海外記事は見出し・要約とも日本語化して表示
- **費用**: GitHub は無料枠。Claude API のみ従量課金（下記「費用の目安」参照）

---

## 1. セットアップ（初回だけ）

### 1-1. Claude APIキーを登録する

リポジトリの **Settings → Secrets and variables → Actions → Secrets** で、
`ANTHROPIC_API_KEY` が登録されているか確認する。
（京都物件サーチで既に登録済みなら、そのまま使えるので何もしなくてよい）

未登録の場合は [Anthropic Console](https://console.anthropic.com/) でキーを発行し、
`New repository secret` から `ANTHROPIC_API_KEY` という名前で登録する。

> APIキーが無くても収集自体は動く。その場合、海外記事は原題のまま
> 「原文（未翻訳）」バッジ付きで表示され、サマリノートは
> スコア上位の機械的な抽出のみになる（要約文は作られない）。

### 1-2. 画面を公開する（GitHub Pages）

**Settings → Pages** を開き、`Build and deployment` を次のように設定して Save。

- Source: `Deploy from a branch`
- Branch: `main` / フォルダ `/docs`

これで `main` に push されるたびに自動で再公開される。
収集ワークフローが `docs/data/` を更新するので、記事の更新も自動で反映される。

公開URL:

```
https://yamamotoy0101-del.github.io/ai-news-brief/
```

スマホのホーム画面に追加しておくと、通常のアプリのように使える。

### 1-3. 最初のデータを入れる

**Actions → 「AIニュース収集（朝・昼・夜）」→ Run workflow** を手動で1回実行する。
5分ほどで記事が入り、画面に表示される。

その後 **「AIニュース サマリノート（1日1回）」** も手動実行すると、サマリノートが作られる。
（以降は自動で動くので操作不要）

---

## 2. 画面の見かた

| タブ | 内容 |
|---|---|
| **フィード** | 日付ごとに記事を表示。重要度順に並ぶ |
| **サマリノート** | その日の注目ニュースと「だから何なのか」。過去分も日付で選べる |
| **ソース状況** | 各RSSの取得結果と実行履歴。取得失敗の検知に使う |

### バッジの意味

| 表示 | 意味 |
|---|---|
| **要チェック**（赤） | 重要度スコア36以上。規制・自社/競合ファーム・大型導入事例など |
| **注目**（橙） | スコア24以上 |
| **原文（未翻訳）** | APIエラー等で日本語化できなかった海外記事。原題のまま表示している |
| **コンサル視点** | クライアント提案・リスク説明のどこに効くかの一言 |

### 重要度スコアの考え方

`scripts/ai_news/scoring.py` にルールを書いてある。配点の方針は次のとおり。

1. **カテゴリ**（政策・規制 18点 ＞ リスク・ガバナンス 15点 ＞ コンサル・組織 12点 …）
   クライアントへの説明責任に直結する話題を最優先にしている
2. **キーワード加点**: PwC 20点、経産省・個人情報保護法などの当局系、競合ファーム、
   国内大手企業名、ROI・全社展開などの経営インパクト語
3. **ソースの質**: 一次情報・重要メディア（tier 1）に +8点
4. **国内ソースに +5点**（「ソースは基本的に日本」という方針の反映）
5. **減点**: セール・値下げ・ゲーム・ガジェットレビューなど

配点を変えたいときは `SIGNAL_WEIGHTS` と `BOOST_KEYWORDS` を編集し、
必ず `python scripts/test_ai_news.py` を実行して回帰テストを通すこと。

---

## 3. カスタマイズ

### フィードURLが変わったとき

媒体がRSSのURLを変更・廃止しても、**自動で追随する仕組みが入っている**。

1. 指定URLが404などで取れない、またはパースして0件だった場合
2. サイトのトップページから `<link rel="alternate" type="application/rss+xml">` を探す
3. 見つかればそちらで再取得し、「ソース状況」タブに `※要URL更新→<URL>` と表示する

この表示が出たら `sources.py` のURLを書き換える。書き換えなくても収集は続くが、
毎回2回リクエストすることになるので反映しておくのが望ましい。

配信専用ホスト（`feed.example.com` など）が落ちている場合は親ドメインも試し、
https と http の両方を試す。

### ニュースソースを足す・消す

`scripts/ai_news/sources.py` を編集する。

```python
{
    "id": "my_source",          # 内部ID（重複しないこと）
    "name": "表示名",
    "url": "https://example.com/rss",
    "lang": "ja",               # "ja" | "en"   en は日本語化の対象になる
    "region": "domestic",       # "domestic" | "global"
    "tier": 1,                  # 1=一次情報/重要 2=一般 3=参考
    "tags": ["政策・規制"],
}
```

追加したら「ソース状況」タブで取得できているか確認する。

### 取得頻度を変える

`.github/workflows/ai-news-collect.yml` の `cron` を編集する。**UTC指定**なので
JSTから9時間引く（例: 朝7:00 JST → `0 22 * * *`）。

### 収集時間帯の表示（朝／昼／夜）

`scripts/fetch_ai_news.py` の `slot_label()` で判定している（4-11時=朝、11-17時=昼、それ以外=夜）。

---

## 4. 費用の目安

Claude API（`claude-opus-5`）を使うのは次の2か所。

| 処理 | 頻度 | 1回あたりの入力 |
|---|---|---|
| 海外記事の翻訳・要約 | 1日3回 × 最大40件 | 見出し＋抜粋のみ（記事全文は送らない） |
| サマリノート生成 | 1日1回 × 最大28件 | 見出し＋要約のみ |

1回の実行でAPIに渡す件数は `AI_NEWS_MAX_ENRICH`（既定40）で上限を設けている。
安く抑えたい場合は、ワークフローの環境変数で次を指定する。

```yaml
env:
  AI_NEWS_MODEL: claude-sonnet-5        # 翻訳をより安いモデルに
  AI_NEWS_MAX_ENRICH: '20'              # 1回あたりの日本語化件数を半減
```

---

## 5. ローカルで動かす

```bash
pip install feedparser requests anthropic

python scripts/test_ai_news.py                 # 回帰テスト（ネットワーク不要）
python scripts/fetch_ai_news.py --dry-run      # 収集結果を表示するだけ
python scripts/fetch_ai_news.py --no-enrich    # APIを使わずに収集
python scripts/build_ai_digest.py --dry-run    # サマリノートを表示するだけ

python -m http.server 8000 --directory docs    # http://localhost:8000 で画面確認
```

---

## 6. トラブルシューティング

| 症状 | 確認すること |
|---|---|
| 記事が増えない | Actions タブでワークフローが失敗していないか。「ソース状況」タブで取得失敗が増えていないか |
| 特定のソースだけ「取得失敗 (HTTP 404)」 | URLが廃止された。自動探索でも見つからなければ `sources.py` から外す |
| 「取得失敗 (HTTP 429)」 | 媒体側のレート制限。CIのIPが弾かれている場合は継続的に出る |
| 「取得失敗 (HTTP 403)」 | アクセス拒否。User-Agent を変えても通らなければ収集対象から外す |
| 「※要URL更新→...」と出る | 自動探索が正しいURLを見つけた。`sources.py` に反映する |
| 「AI関連なし（全N件）」 | 障害ではない。フィードは取れているがAI記事が無かっただけ |
| 「記事0件（フィード形式を確認）」 | URLは生きているがRSSではない。フィードURLを確認する |
| 海外記事が英語のまま | `ANTHROPIC_API_KEY` が未設定か、APIがエラーを返している。Actions のログを見る |
| サマリが「自動要約なし」 | 同上。`generated_by: score-only` と表示される |
| 画面が「フィード未生成」のまま | 収集ワークフローをまだ実行していない。手動実行する |
| URLが404になる | Settings → Pages の設定がまだ。上記 1-2 を行う |

---

## ファイル構成

```
scripts/
  fetch_ai_news.py        収集（1日3回）
  build_ai_digest.py      サマリノート生成（1日1回）
  test_ai_news.py         回帰テスト
  ai_news/
    sources.py            収集元RSSの定義
    scoring.py            AI判定・カテゴリ分類・重要度スコア
    enrich.py             Claude APIによる日本語化
    store.py              保存と重複排除
docs/                     GitHub Pagesで公開される画面
  index.html
  assets/style.css
  assets/app.js
  data/feed.json          記事データ（直近14日・最大600件）
  data/digests/           日次サマリノート
reports_ai/               サマリノートのMarkdown版
.github/workflows/
  ai-news-collect.yml    収集（朝・昼・夜）
  ai-news-digest.yml     サマリノート（1日1回）
```
