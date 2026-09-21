/* AI News Brief — フィード描画 */
'use strict';

const state = {
  items: [],
  runs: [],
  sources: [],
  generatedAt: null,
  digestIndex: [],
  digestCache: new Map(),
  filters: { q: '', category: 'all', priority: 'all', region: 'all' },
};

const PRIORITY_LABEL = { 'must-read': '要チェック', watch: '注目', reference: '参考' };
const $ = (sel) => document.querySelector(sel);

/* ───────── ユーティリティ ───────── */

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function parseDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

// 日本のニュースを日本時間の区切りで読むアプリなので、閲覧端末の
// タイムゾーンによらず JST で表示する。サマリノートの日付（JST基準で
// 生成）とフィードの日付見出しが食い違わないようにする狙いもある。
const JST = 'Asia/Tokyo';

function jstParts(iso) {
  const d = parseDate(iso);
  if (!d) return null;
  const f = new Intl.DateTimeFormat('ja-JP', {
    timeZone: JST, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', weekday: 'short', hour12: false,
  });
  const parts = {};
  for (const p of f.formatToParts(d)) parts[p.type] = p.value;
  return parts;
}

function formatTime(iso) {
  const p = jstParts(iso);
  return p ? `${p.hour}:${p.minute}` : '';
}

function dayKey(iso) {
  const p = jstParts(iso);
  return p ? `${p.year}-${p.month}-${p.day}` : '不明';
}

function formatDayHeading(key) {
  const p = jstParts(`${key}T12:00:00+09:00`);
  if (!p) return key;
  const todayKey = dayKey(new Date().toISOString());
  const diff = Math.round(
    (Date.parse(`${todayKey}T00:00:00+09:00`) - Date.parse(`${key}T00:00:00+09:00`)) / 86400000,
  );
  const base = `${Number(p.month)}月${Number(p.day)}日（${p.weekday}）`;
  if (diff === 0) return `今日 ・ ${base}`;
  if (diff === 1) return `昨日 ・ ${base}`;
  return base;
}

function relativeTime(iso) {
  const d = parseDate(iso);
  if (!d) return '';
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 0)}分前`;
  if (mins < 60 * 24) return `${Math.floor(mins / 60)}時間前`;
  return `${Math.floor(mins / 1440)}日前`;
}

/* ───────── 読み込み ───────── */

async function loadJSON(path) {
  const res = await fetch(`${path}?t=${Date.now()}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

async function boot() {
  try {
    const feed = await loadJSON('data/feed.json');
    state.items = feed.items || [];
    state.runs = feed.runs || [];
    state.sources = feed.sources || [];
    state.generatedAt = feed.generated_at || null;
  } catch (err) {
    $('#status').className = 'status is-error';
    $('#status-text').textContent = 'フィード未生成';
    $('#feed').innerHTML = emptyBlock(
      'まだニュースが収集されていません。',
      'GitHub Actions の「AIニュース収集」ワークフローを一度手動実行すると、ここに記事が並びます。'
    );
    renderSources();
    return;
  }

  try {
    state.digestIndex = await loadJSON('data/digests/index.json');
  } catch {
    state.digestIndex = [];
  }

  renderStatus();
  renderCategoryChips();
  renderFeed();
  renderSources();
  await renderDigestTeaser();
  bindEvents();
}

/* ───────── ヘッダ状態 ───────── */

function renderStatus() {
  const d = parseDate(state.generatedAt);
  if (!d) return;
  const hoursOld = (Date.now() - d.getTime()) / 3600000;
  const el = $('#status');
  // 収集は最長でも9時間間隔。12時間を超えたら停止を疑う。
  el.className = hoursOld > 12 ? 'status is-stale' : 'status';
  const p = jstParts(state.generatedAt);
  $('#status-text').textContent =
    `最終更新 ${Number(p.month)}/${Number(p.day)} ${p.hour}:${p.minute}（${relativeTime(state.generatedAt)}）`;
}

/* ───────── 絞り込み ───────── */

function renderCategoryChips() {
  const counts = new Map();
  state.items.forEach((it) => {
    counts.set(it.category, (counts.get(it.category) || 0) + 1);
  });
  const ordered = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const chips = [`<button class="chip is-active" data-category="all">すべて<span class="n">${state.items.length}</span></button>`];
  ordered.forEach(([cat, n]) => {
    chips.push(`<button class="chip" data-category="${escapeHtml(cat)}">${escapeHtml(cat)}<span class="n">${n}</span></button>`);
  });
  $('#cat-chips').innerHTML = chips.join('');
}

function matchesFilters(item) {
  const f = state.filters;
  if (f.category !== 'all' && item.category !== f.category) return false;
  if (f.priority === 'must-read' && item.priority !== 'must-read') return false;
  if (f.region !== 'all' && item.region !== f.region) return false;
  if (f.q) {
    const hay = [
      item.title, item.title_original, item.summary,
      item.summary_original, item.source_name, item.insight, item.category,
    ].join(' ').toLowerCase();
    if (!f.q.split(/\s+/).filter(Boolean).every((term) => hay.includes(term))) return false;
  }
  return true;
}

/* ───────── フィード ───────── */

function emptyBlock(title, detail) {
  return `<div class="empty"><strong>${escapeHtml(title)}</strong><br>${escapeHtml(detail)}</div>`;
}

function cardHtml(item) {
  const badges = [];
  if (item.priority === 'must-read' || item.priority === 'watch') {
    badges.push(`<span class="badge badge-${item.priority}">${PRIORITY_LABEL[item.priority]}</span>`);
  }
  badges.push(`<span class="badge badge-cat">${escapeHtml(item.category)}</span>`);
  if (item.lang === 'en' && !item.translated) {
    badges.push('<span class="badge badge-raw">原文（未翻訳）</span>');
  }

  const alsoBy = (item.also_reported_by || []).length
    ? ` ・ 他${item.also_reported_by.length}媒体`
    : '';

  const insight = item.insight
    ? `<p class="insight"><b>コンサル視点</b>${escapeHtml(item.insight)}</p>`
    : '';

  // 翻訳済みの海外記事は、原題を確認できるようフッタに残す
  const original = (item.translated && item.lang === 'en' && item.title_original)
    ? `<span class="orig">原題: ${escapeHtml(item.title_original)}</span>`
    : '';

  const lowConfidence = item.confidence === 'low'
    ? '<span class="orig">※ 見出し中心の要約です。原文を確認してください</span>'
    : '';

  return `
    <article class="card p-${escapeHtml(item.priority)}">
      <div class="card-meta">
        ${badges.join('')}
        <span class="source">${escapeHtml(item.source_name)}</span>
        <span>${escapeHtml(item.region === 'global' ? '海外' : '国内')}${alsoBy}</span>
        <span>${formatTime(item.published_at)}</span>
      </div>
      <h3><a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a></h3>
      ${item.summary ? `<p class="summary">${escapeHtml(item.summary)}</p>` : ''}
      ${insight}
      <div class="card-foot">${original}${lowConfidence}</div>
    </article>`;
}

function renderFeed() {
  const visible = state.items.filter(matchesFilters);
  const mustRead = visible.filter((i) => i.priority === 'must-read').length;
  $('#count').textContent = visible.length
    ? `${visible.length}件を表示（うち要チェック ${mustRead}件）`
    : '';

  if (!visible.length) {
    $('#feed').innerHTML = emptyBlock(
      '条件に合う記事がありません。',
      '検索語やカテゴリの絞り込みを外してみてください。'
    );
    return;
  }

  const groups = new Map();
  visible.forEach((item) => {
    const key = dayKey(item.published_at);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });

  const html = [...groups.entries()]
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([key, items]) => {
      // 日付内は重要度順。同点なら新しい順。
      items.sort((a, b) => (b.score - a.score) || (a.published_at < b.published_at ? 1 : -1));
      return `<h2 class="day-head">${escapeHtml(formatDayHeading(key))}　${items.length}件</h2>`
        + items.map(cardHtml).join('');
    })
    .join('');

  $('#feed').innerHTML = html;
}

/* ───────── サマリノート ───────── */

async function fetchDigest(date) {
  if (state.digestCache.has(date)) return state.digestCache.get(date);
  const digest = await loadJSON(`data/digests/${date}.json`);
  state.digestCache.set(date, digest);
  return digest;
}

async function renderDigestTeaser() {
  if (!state.digestIndex.length) return;
  const latest = state.digestIndex[0];
  let digest;
  try {
    digest = await fetchDigest(latest.date);
  } catch {
    return;
  }
  const teaser = $('#digest-teaser');
  teaser.hidden = false;
  teaser.innerHTML = `
    <p class="kicker">サマリノート ${escapeHtml(digest.date)}</p>
    <h2>${escapeHtml(digest.headline)}</h2>
    <p>${escapeHtml(digest.overview)}</p>
    <button type="button" class="more">注目ニュース ${digest.highlights.length}本を読む →</button>`;
  teaser.querySelector('.more').addEventListener('click', () => switchView('digest'));
}

function digestHtml(digest) {
  const highlights = digest.highlights.map((h, i) => `
    <div class="hl">
      <span class="num">${i + 1}</span>
      <div>
        <h4><a href="${escapeHtml(h.item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(h.item.title)}</a></h4>
        <p class="src">${escapeHtml(h.item.source_name)} ・ ${escapeHtml(h.item.category)} ・ ${escapeHtml(h.item.region === 'global' ? '海外' : '国内')}</p>
        <p>${escapeHtml(h.point)}</p>
        <p class="so-what"><b>だから何なのか</b><br>${escapeHtml(h.so_what)}</p>
      </div>
    </div>`).join('');

  const watchlist = digest.watchlist && digest.watchlist.length
    ? `<h3 class="section-title">今後の注視点</h3>
       <ul class="watchlist">${digest.watchlist.map((w) => `<li>${escapeHtml(w)}</li>`).join('')}</ul>`
    : '';

  const scoreOnly = digest.generated_by === 'score-only'
    ? '　※ 自動要約は生成されていません（APIキー未設定または生成失敗）'
    : '';

  return `
    <article class="digest">
      <h2>${escapeHtml(digest.headline)}</h2>
      <p class="overview">${escapeHtml(digest.overview)}</p>
      <h3 class="section-title">注目ニュース</h3>
      ${highlights || '<p class="summary">該当なし</p>'}
      ${watchlist}
      <p class="digest-foot">
        ${escapeHtml(digest.date)} ／ 候補記事 ${digest.candidate_count}件から選定
        ／ 生成: ${escapeHtml(digest.generated_by)}${escapeHtml(scoreOnly)}
      </p>
    </article>`;
}

async function renderDigestView(date) {
  const body = $('#digest-body');
  if (!state.digestIndex.length) {
    body.innerHTML = emptyBlock(
      'サマリノートはまだありません。',
      '毎日22:30（JST）に、その日のフィードから自動生成されます。'
    );
    return;
  }
  body.innerHTML = '<div class="empty">読み込み中…</div>';
  try {
    body.innerHTML = digestHtml(await fetchDigest(date));
  } catch {
    body.innerHTML = emptyBlock('このノートを読み込めませんでした。', `data/digests/${date}.json が見つかりません。`);
  }
}

function renderDigestPicker() {
  const select = $('#digest-date');
  if (select.options.length || !state.digestIndex.length) return;
  select.innerHTML = state.digestIndex
    .map((d) => `<option value="${escapeHtml(d.date)}">${escapeHtml(d.date)}　${escapeHtml(d.headline || '')}</option>`)
    .join('');
  select.addEventListener('change', () => renderDigestView(select.value));
}

/* ───────── ソース状況 ───────── */

function renderSources() {
  const body = $('#sources-body');
  if (!state.sources.length) {
    body.innerHTML = emptyBlock('取得状況の記録がありません。', '収集ワークフローを一度実行してください。');
  } else {
    const groups = [
      ['国内ソース', state.sources.filter((s) => s.region === 'domestic')],
      ['海外ソース', state.sources.filter((s) => s.region === 'global')],
    ];
    body.innerHTML = groups.map(([label, list]) => {
      if (!list.length) return '';
      const rows = list.map((s) => `<div class="src-row${s.ok ? '' : ' is-bad'}">
          <span class="dot"></span>
          <span class="nm">${escapeHtml(s.name)}</span>
          <span class="st">${escapeHtml(s.status)}</span>
        </div>`).join('');
      const bad = list.filter((s) => !s.ok).length;
      return `<div class="src-group">
        <h3>${escapeHtml(label)}　${list.length}件中 ${bad}件に問題</h3>${rows}
      </div>`;
    }).join('');
  }

  const runs = $('#runs-body');
  runs.innerHTML = state.runs.length
    ? state.runs.slice(0, 12).map((r) => {
        const p = jstParts(r.at);
        const when = p ? `${Number(p.month)}/${Number(p.day)} ${p.hour}:${p.minute}` : '';
        return `<div class="run-row">
          <span class="slot">${escapeHtml(r.slot)}</span>
          <span class="rt">${escapeHtml(when)}</span>
          <span class="rn">取得${r.fetched} ／ 新着${r.added} ／ 日本語化${r.enriched}</span>
        </div>`;
      }).join('')
    : emptyBlock('実行履歴がありません。', '');
}

/* ───────── ビュー切り替え ───────── */

function switchView(view) {
  document.querySelectorAll('.tab').forEach((tab) => {
    const active = tab.dataset.view === view;
    tab.classList.toggle('is-active', active);
    tab.setAttribute('aria-selected', String(active));
  });
  ['feed', 'digest', 'sources'].forEach((name) => {
    $(`#view-${name}`).hidden = name !== view;
  });
  if (view === 'digest') {
    renderDigestPicker();
    const select = $('#digest-date');
    renderDigestView(select.value || (state.digestIndex[0] && state.digestIndex[0].date));
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ───────── イベント ───────── */

function bindEvents() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => switchView(tab.dataset.view));
  });

  let timer;
  $('#q').addEventListener('input', (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      state.filters.q = e.target.value.trim().toLowerCase();
      renderFeed();
    }, 160);
  });

  $('#reset').addEventListener('click', () => {
    state.filters = { q: '', category: 'all', priority: 'all', region: 'all' };
    $('#q').value = '';
    document.querySelectorAll('.chip').forEach((chip) => {
      const isDefault = chip.dataset.category === 'all'
        || chip.dataset.priority === 'all'
        || chip.dataset.region === 'all';
      chip.classList.toggle('is-active', isDefault);
    });
    renderFeed();
  });

  // チップは3グループ（カテゴリ／重要度／地域）で排他選択する
  document.querySelectorAll('.chip-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      const key = ['category', 'priority', 'region'].find((k) => chip.dataset[k] !== undefined);
      if (!key) return;
      const scope = chip.closest('.chip-group') || row;
      scope.querySelectorAll('.chip').forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      state.filters[key] = chip.dataset[key];
      renderFeed();
    });
  });
}

boot();
