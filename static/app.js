/**
 * app.js - Frontend reactivity, SSE events, countdown timer, sound chime,
 * and keyword/website filter management for News Monitor.
 */

// Application state
const state = {
  keywords: [],
  websites: [],
  articles: [],
  selectedArticleIds: new Set(),
  activeTab: 'all',          // 'all', 'unread', 'bookmarked'
  selectedKeyword: 'all',
  selectedWebsite: 'all',
  searchQuery: '',
  remainingSeconds: 0,
  isScanning: false,
  settings: {},
  timerInterval: null
};

// Web Audio API Synthesizer Chime
function playAlertChime() {
  if (state.settings.enable_sound === 'false') return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();

    // Two pleasant bell notes (E5 -> G#5)
    const now = ctx.currentTime;
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(659.25, now); // E5
    gain1.gain.setValueAtTime(0.15, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.45);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(830.61, now + 0.15); // G#5
    gain2.gain.setValueAtTime(0.15, now + 0.15);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.65);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.15);
    osc2.stop(now + 0.65);
  } catch (e) {
    console.debug('Audio chime error:', e);
  }
}

// Format seconds into MM:SS
function formatTime(totalSeconds) {
  if (totalSeconds < 0) totalSeconds = 0;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Relative time formatter
function formatRelativeTime(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffSec = Math.floor((now - d) / 1000);
    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  } catch (e) {
    return dateStr;
  }
}

// Highlight keywords in text
function highlightText(text, keyword) {
  if (!text) return '';
  if (!keyword) return escapeHtml(text);
  const escaped = escapeHtml(text);
  const cleanKw = keyword.replace(/^"|"$/g, '').trim();
  if (!cleanKw) return escaped;

  const words = cleanKw.split(/[\s,]+/).filter(w => w.length > 1);
  words.push(cleanKw);
  const uniqueWords = [...new Set(words)];

  const regex = new RegExp(`(${uniqueWords.map(escapeRegex).join('|')})`, 'gi');
  return escaped.replace(regex, '<mark>$1</mark>');
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ==================== API CALLS ====================

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    if (data.status === 'ok') {
      updateStatusUI(data);
    }
  } catch (e) {
    console.error('Failed to fetch status:', e);
  }
}

async function fetchKeywords() {
  try {
    const res = await fetch('/api/keywords');
    const data = await res.json();
    state.keywords = data.keywords || [];
    renderKeywords();
    updateKeywordDropdown();
  } catch (e) {
    console.error('Failed to fetch keywords:', e);
  }
}

async function fetchWebsites() {
  try {
    const res = await fetch('/api/websites');
    const data = await res.json();
    state.websites = data.websites || [];
    renderWebsites();
    updateWebsiteDropdown();
    updateWebsiteFilterBanner();
  } catch (e) {
    console.error('Failed to fetch websites:', e);
  }
}

async function fetchArticles() {
  const container = document.getElementById('articles-feed');
  try {
    const params = new URLSearchParams();
    if (state.selectedKeyword !== 'all') params.set('keyword', state.selectedKeyword);
    if (state.selectedWebsite !== 'all') params.set('website', state.selectedWebsite);
    if (state.activeTab !== 'all') params.set('filter', state.activeTab);
    if (state.searchQuery.trim()) params.set('search', state.searchQuery.trim());
    params.set('limit', '100');

    const res = await fetch(`/api/articles?${params.toString()}`);
    const data = await res.json();
    state.articles = data.articles || [];
    renderArticles();
  } catch (e) {
    console.error('Failed to fetch articles:', e);
    container.innerHTML = `<div class="empty-feed-state"><p>Error loading articles: ${e.message}</p></div>`;
  }
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    state.settings = await res.json();
    populateSettingsModal();
  } catch (e) {
    console.error('Failed to fetch settings:', e);
  }
}

// ==================== UI RENDERING ====================

function updateStatusUI(data) {
  const sched = data.scheduler || {};
  const stats = data.stats || {};

  state.isScanning = sched.is_scanning;
  state.remainingSeconds = sched.remaining_seconds || 0;

  // Status Pill
  const statusPill = document.getElementById('status-pill');
  const statusText = document.getElementById('status-text');
  const scanBtn = document.getElementById('btn-scan-now');
  const scanBtnLabel = document.getElementById('scan-btn-label');
  const scanIcon = scanBtn.querySelector('.icon');

  if (state.isScanning) {
    statusText.textContent = sched.status_message || 'Scanning internet...';
    scanBtnLabel.textContent = 'Scanning...';
    scanIcon.classList.add('spinning');
    scanBtn.disabled = true;
  } else {
    statusText.textContent = sched.status_message || 'Ready';
    scanBtnLabel.textContent = 'Scan Now';
    scanIcon.classList.remove('spinning');
    scanBtn.disabled = false;
  }

  // Countdown timer
  document.getElementById('countdown-display').textContent = formatTime(state.remainingSeconds);

  // Top stats
  document.getElementById('stat-active-keywords').textContent = stats.active_keywords || 0;
  
  const activeWebsCount = sched.active_websites_count || 0;
  const webStatVal = document.getElementById('stat-active-websites');
  const webStatMode = document.getElementById('stat-website-mode');
  if (activeWebsCount > 0) {
    webStatVal.textContent = activeWebsCount;
    webStatMode.textContent = `${activeWebsCount} Active`;
    webStatMode.className = 'stat-badge filtered';
  } else {
    webStatVal.textContent = 'All';
    webStatMode.textContent = 'Entire Web';
    webStatMode.className = 'stat-badge';
  }

  document.getElementById('stat-total-articles').textContent = stats.total_articles || 0;
  document.getElementById('stat-unread-articles').textContent = stats.unread_articles || 0;
  document.getElementById('stat-bookmarked-articles').textContent = stats.bookmarked_articles || 0;
  document.getElementById('tab-unread-count').textContent = stats.unread_articles || 0;
}

function renderKeywords() {
  const container = document.getElementById('keywords-list');
  const pill = document.getElementById('keyword-count-pill');
  pill.textContent = state.keywords.length;

  if (state.keywords.length === 0) {
    container.innerHTML = '<div class="empty-hint">No keywords tracked yet. Add one above!</div>';
    return;
  }

  container.innerHTML = state.keywords.map(kw => `
    <div class="tag-item ${kw.is_active ? '' : 'paused'}" data-id="${kw.id}">
      <div class="tag-info">
        <span class="tag-name" title="${escapeHtml(kw.keyword)}">${escapeHtml(kw.keyword)}</span>
        <span class="tag-badge" title="Articles found">${kw.article_count}</span>
      </div>
      <div class="tag-actions">
        <button class="tag-btn toggle-kw" title="${kw.is_active ? 'Pause tracking' : 'Resume tracking'}">
          ${kw.is_active ? '⏸' : '▶'}
        </button>
        <button class="tag-btn delete delete-kw" title="Delete keyword">
          🗑
        </button>
      </div>
    </div>
  `).join('');
}

function updateKeywordDropdown() {
  const select = document.getElementById('select-filter-keyword');
  const current = select.value;
  select.innerHTML = '<option value="all">All Keywords</option>';
  state.keywords.forEach(kw => {
    const opt = document.createElement('option');
    opt.value = kw.keyword;
    opt.textContent = `${kw.keyword} (${kw.article_count})`;
    select.appendChild(opt);
  });
  select.value = current;
}

function renderWebsites() {
  const container = document.getElementById('websites-list');
  const pill = document.getElementById('website-count-pill');
  const activeCount = state.websites.filter(w => w.is_active).length;
  pill.textContent = activeCount > 0 ? `${activeCount} Active` : 'All';

  if (state.websites.length === 0) {
    container.innerHTML = '<div class="empty-hint">No website filter active (searches entire web).</div>';
    return;
  }

  container.innerHTML = state.websites.map(w => `
    <div class="tag-item ${w.is_active ? '' : 'paused'}" data-id="${w.id}">
      <div class="tag-info">
        <span class="tag-name" title="${escapeHtml(w.name)}">${escapeHtml(w.name)}</span>
        <span class="tag-badge" title="Articles found">${w.article_count}</span>
      </div>
      <div class="tag-actions">
        <button class="tag-btn toggle-web" title="${w.is_active ? 'Pause filter' : 'Activate filter'}">
          ${w.is_active ? '⏸' : '▶'}
        </button>
        <button class="tag-btn delete delete-web" title="Delete website filter">
          🗑
        </button>
      </div>
    </div>
  `).join('');
}

function updateWebsiteDropdown() {
  const select = document.getElementById('select-filter-website');
  const current = select.value;
  select.innerHTML = '<option value="all">All Sources / Webs</option>';
  state.websites.forEach(w => {
    const opt = document.createElement('option');
    opt.value = w.name;
    opt.textContent = `${w.name} (${w.article_count})`;
    select.appendChild(opt);
  });
  select.value = current;
}

function updateWebsiteFilterBanner() {
  const banner = document.getElementById('website-filter-banner');
  const text = document.getElementById('website-filter-status-text');
  const activeWebs = state.websites.filter(w => w.is_active);

  if (activeWebs.length > 0) {
    banner.classList.add('active');
    const names = activeWebs.map(w => w.name).join(', ');
    text.textContent = `Targeting ${activeWebs.length} website(s): ${names}. News searches are restricted to these sources.`;
  } else {
    banner.classList.remove('active');
    text.textContent = 'Searching all internet sources. Add website names below to restrict searches to specific sites.';
  }
}

function updateSelectionUI() {
  const count = state.selectedArticleIds.size;
  const countSpan = document.getElementById('selected-count');
  if (countSpan) countSpan.textContent = count;

  const btnDeleteSelected = document.getElementById('btn-delete-selected');
  if (btnDeleteSelected) {
    btnDeleteSelected.style.display = count > 0 ? 'inline-flex' : 'none';
  }

  const selectAllCheck = document.getElementById('check-select-all');
  if (selectAllCheck) {
    const totalVisible = state.articles.length;
    if (totalVisible === 0) {
      selectAllCheck.checked = false;
      selectAllCheck.indeterminate = false;
    } else {
      const selectedVisibleCount = state.articles.filter(a => state.selectedArticleIds.has(a.id)).length;
      if (selectedVisibleCount === 0) {
        selectAllCheck.checked = false;
        selectAllCheck.indeterminate = false;
      } else if (selectedVisibleCount === totalVisible) {
        selectAllCheck.checked = true;
        selectAllCheck.indeterminate = false;
      } else {
        selectAllCheck.checked = false;
        selectAllCheck.indeterminate = true;
      }
    }
  }
}

function renderArticles() {
  const container = document.getElementById('articles-feed');
  if (state.articles.length === 0) {
    container.innerHTML = `
      <div class="empty-feed-state">
        <p style="font-size: 1.1rem; font-weight: 600; margin-bottom: 6px;">No articles found</p>
        <p style="font-size: 0.85rem; color: var(--text-muted);">
          ${state.keywords.length === 0 ? 'Add keywords on the left to start tracking.' : 'Try adjusting your filters or click "Scan Now" to fetch latest news.'}
        </p>
      </div>
    `;
    updateSelectionUI();
    return;
  }

  container.innerHTML = state.articles.map(art => {
    const highlightedTitle = highlightText(art.title, art.keyword_matched);
    const highlightedSnippet = highlightText(art.snippet, art.keyword_matched);
    const isRead = art.is_read === 1;
    const isBookmarked = art.is_bookmarked === 1;
    const isSelected = state.selectedArticleIds.has(art.id);
    const timeAgo = formatRelativeTime(art.published_at || art.discovered_at);

    return `
      <article class="article-card ${isRead ? 'read' : ''} ${isSelected ? 'selected' : ''}" data-id="${art.id}">
        <div class="article-meta">
          <input type="checkbox" class="article-checkbox" data-id="${art.id}" ${isSelected ? 'checked' : ''} title="Select this article">
          <a class="meta-source" href="${escapeHtml(art.source_url || art.link)}" target="_blank" rel="noopener noreferrer">
            ${escapeHtml(art.source || 'Web')}
          </a>
          <span class="meta-keyword">${escapeHtml(art.keyword_matched || 'News')}</span>
          <span class="meta-time" title="${escapeHtml(art.published_at || art.discovered_at)}">${timeAgo}</span>
        </div>

        <h3 class="article-title">
          <a href="${escapeHtml(art.link)}" target="_blank" rel="noopener noreferrer" class="article-link">
            ${highlightedTitle}
          </a>
        </h3>

        <p class="article-snippet">${highlightedSnippet}</p>

        <div class="article-footer">
          <span class="article-url-preview" title="${escapeHtml(art.link)}">${escapeHtml(art.link)}</span>
          <div class="article-actions">
            <button class="btn-act bookmark-toggle ${isBookmarked ? 'bookmarked' : ''}" title="${isBookmarked ? 'Remove bookmark' : 'Bookmark article'}">
              ${isBookmarked ? '⭐ Saved' : '☆ Save'}
            </button>
            <button class="btn-act read-toggle ${isRead ? 'is-read' : ''}" title="${isRead ? 'Mark as unread' : 'Mark as read'}">
              ${isRead ? '✓ Read' : '○ Mark read'}
            </button>
            <button class="btn-act btn-delete-single delete-article" title="Delete this article">
              🗑 Delete
            </button>
          </div>
        </div>
      </article>
    `;
  }).join('');
  updateSelectionUI();
}

// ==================== EVENT HANDLERS ====================

function initEventHandlers() {
  // Add Keyword
  document.getElementById('form-add-keyword').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('input-keyword');
    const val = input.value.trim();
    if (!val) return;
    input.value = '';
    try {
      await fetch('/api/keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: val })
      });
      await fetchKeywords();
      await fetchStatus();
    } catch (err) {
      console.error('Error adding keyword:', err);
    }
  });

  // Keyword list clicks (Toggle & Delete)
  document.getElementById('keywords-list').addEventListener('click', async (e) => {
    const item = e.target.closest('.tag-item');
    if (!item) return;
    const id = item.dataset.id;

    if (e.target.closest('.toggle-kw')) {
      await fetch(`/api/keywords/${id}/toggle`, { method: 'PUT' });
      await fetchKeywords();
      await fetchStatus();
    } else if (e.target.closest('.delete-kw')) {
      await fetch(`/api/keywords/${id}`, { method: 'DELETE' });
      await fetchKeywords();
      await fetchStatus();
      await fetchArticles();
    }
  });

  // Add Website Filter
  document.getElementById('form-add-website').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('input-website');
    const val = input.value.trim();
    if (!val) return;
    input.value = '';
    try {
      await fetch('/api/websites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ website: val })
      });
      await fetchWebsites();
      await fetchStatus();
    } catch (err) {
      console.error('Error adding website filter:', err);
    }
  });

  // Website list clicks (Toggle & Delete)
  document.getElementById('websites-list').addEventListener('click', async (e) => {
    const item = e.target.closest('.tag-item');
    if (!item) return;
    const id = item.dataset.id;

    if (e.target.closest('.toggle-web')) {
      await fetch(`/api/websites/${id}/toggle`, { method: 'PUT' });
      await fetchWebsites();
      await fetchStatus();
    } else if (e.target.closest('.delete-web')) {
      await fetch(`/api/websites/${id}`, { method: 'DELETE' });
      await fetchWebsites();
      await fetchStatus();
      await fetchArticles();
    }
  });

  // Scan Now button
  document.getElementById('btn-scan-now').addEventListener('click', async () => {
    try {
      await fetch('/api/scan', { method: 'POST' });
      await fetchStatus();
    } catch (err) {
      console.error('Scan error:', err);
    }
  });

  // Tabs (All, Unread, Bookmarked)
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeTab = btn.dataset.filter;
      fetchArticles();
    });
  });

  // Dropdown filter: Keyword
  document.getElementById('select-filter-keyword').addEventListener('change', (e) => {
    state.selectedKeyword = e.target.value;
    fetchArticles();
  });

  // Dropdown filter: Website
  document.getElementById('select-filter-website').addEventListener('change', (e) => {
    state.selectedWebsite = e.target.value;
    fetchArticles();
  });

  // Search input
  const searchInput = document.getElementById('input-search-feed');
  const clearSearchBtn = document.getElementById('btn-clear-search');
  let searchDebounce = null;

  searchInput.addEventListener('input', (e) => {
    const val = e.target.value;
    clearSearchBtn.style.display = val ? 'block' : 'none';
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.searchQuery = val;
      fetchArticles();
    }, 250);
  });

  clearSearchBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearSearchBtn.style.display = 'none';
    state.searchQuery = '';
    fetchArticles();
  });

  // Article card clicks (Read, Bookmark, Delete, Open)
  document.getElementById('articles-feed').addEventListener('click', async (e) => {
    const card = e.target.closest('.article-card');
    if (!card) return;
    const id = card.dataset.id;

    // Link clicked: auto-mark as read if enabled
    if (e.target.closest('.article-link')) {
      if (!card.classList.contains('read')) {
        card.classList.add('read');
        fetch(`/api/articles/${id}/read`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_read: true })
        });
      }
      return;
    }

    // Toggle bookmark
    if (e.target.closest('.bookmark-toggle')) {
      const res = await fetch(`/api/articles/${id}/bookmark`, { method: 'POST' });
      const data = await res.json();
      const btn = card.querySelector('.bookmark-toggle');
      if (data.is_bookmarked) {
        btn.classList.add('bookmarked');
        btn.innerHTML = '⭐ Saved';
      } else {
        btn.classList.remove('bookmarked');
        btn.innerHTML = '☆ Save';
        if (state.activeTab === 'bookmarked') card.remove();
      }
      fetchStatus();
      return;
    }

    // Toggle read
    if (e.target.closest('.read-toggle')) {
      const isCurrentlyRead = card.classList.contains('read');
      const newRead = !isCurrentlyRead;
      await fetch(`/api/articles/${id}/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_read: newRead })
      });
      card.classList.toggle('read', newRead);
      const btn = card.querySelector('.read-toggle');
      if (newRead) {
        btn.classList.add('is-read');
        btn.innerHTML = '✓ Read';
        if (state.activeTab === 'unread') card.remove();
      } else {
        btn.classList.remove('is-read');
        btn.innerHTML = '○ Mark read';
      }
      fetchStatus();
      return;
    }

    // Delete single article
    if (e.target.closest('.delete-article')) {
      const numId = parseInt(id, 10);
      card.classList.add('deleting');
      state.selectedArticleIds.delete(numId);
      updateSelectionUI();
      try {
        await fetch(`/api/articles/${id}`, { method: 'DELETE' });
        setTimeout(() => {
          card.remove();
          fetchStatus();
        }, 220);
      } catch (err) {
        card.classList.remove('deleting');
        console.error('Error deleting article:', err);
      }
      return;
    }
  });

  // Handle article checkbox change
  document.getElementById('articles-feed').addEventListener('change', (e) => {
    if (e.target.classList.contains('article-checkbox')) {
      const card = e.target.closest('.article-card');
      const id = parseInt(e.target.dataset.id, 10);
      if (e.target.checked) {
        state.selectedArticleIds.add(id);
        if (card) card.classList.add('selected');
      } else {
        state.selectedArticleIds.delete(id);
        if (card) card.classList.remove('selected');
      }
      updateSelectionUI();
    }
  });

  // Select / Deselect All visible articles
  const checkSelectAll = document.getElementById('check-select-all');
  if (checkSelectAll) {
    checkSelectAll.addEventListener('change', (e) => {
      const checked = e.target.checked;
      state.articles.forEach(art => {
        if (checked) {
          state.selectedArticleIds.add(art.id);
        } else {
          state.selectedArticleIds.delete(art.id);
        }
      });
      document.querySelectorAll('.article-card').forEach(card => {
        const id = parseInt(card.dataset.id, 10);
        const isSel = state.selectedArticleIds.has(id);
        card.classList.toggle('selected', isSel);
        const cb = card.querySelector('.article-checkbox');
        if (cb) cb.checked = isSel;
      });
      updateSelectionUI();
    });
  }

  // Delete Selected Articles
  const btnDeleteSelected = document.getElementById('btn-delete-selected');
  if (btnDeleteSelected) {
    btnDeleteSelected.addEventListener('click', async () => {
      const count = state.selectedArticleIds.size;
      if (count === 0) return;
      if (!confirm(`Are you sure you want to delete ${count} selected article(s)?`)) return;

      const ids = Array.from(state.selectedArticleIds);
      btnDeleteSelected.disabled = true;
      try {
        await fetch('/api/articles/delete-batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids })
        });
        state.selectedArticleIds.clear();
        await fetchArticles();
        await fetchStatus();
      } catch (err) {
        console.error('Error batch deleting articles:', err);
      } finally {
        btnDeleteSelected.disabled = false;
      }
    });
  }

  // Delete All News Modal Open/Close & Actions
  const deleteAllModal = document.getElementById('modal-delete-all');
  const btnDeleteAll = document.getElementById('btn-delete-all-news');
  const btnCloseDeleteAll = document.getElementById('btn-close-delete-all');
  const btnCancelDeleteAll = document.getElementById('btn-cancel-delete-all');
  const btnConfirmDeleteAll = document.getElementById('btn-confirm-delete-all');
  const checkPreserve = document.getElementById('check-preserve-bookmarks');

  if (btnDeleteAll && deleteAllModal) {
    btnDeleteAll.addEventListener('click', () => {
      deleteAllModal.classList.add('open');
    });
  }

  const closeDeleteAllModal = () => {
    if (deleteAllModal) deleteAllModal.classList.remove('open');
  };

  if (btnCloseDeleteAll) btnCloseDeleteAll.addEventListener('click', closeDeleteAllModal);
  if (btnCancelDeleteAll) btnCancelDeleteAll.addEventListener('click', closeDeleteAllModal);

  if (btnConfirmDeleteAll) {
    btnConfirmDeleteAll.addEventListener('click', async () => {
      const preserve = checkPreserve ? checkPreserve.checked : false;
      btnConfirmDeleteAll.disabled = true;
      btnConfirmDeleteAll.textContent = 'Deleting...';
      try {
        await fetch(`/api/articles/clear?preserve_bookmarks=${preserve}`, { method: 'DELETE' });
        closeDeleteAllModal();
        state.selectedArticleIds.clear();
        await fetchArticles();
        await fetchStatus();
      } catch (err) {
        console.error('Error clearing articles:', err);
      } finally {
        btnConfirmDeleteAll.disabled = false;
        btnConfirmDeleteAll.textContent = 'Delete All News';
      }
    });
  }

  // Mark all read
  document.getElementById('btn-mark-all-read').addEventListener('click', async () => {
    await fetch('/api/articles/mark-all-read', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword: state.selectedKeyword === 'all' ? null : state.selectedKeyword })
    });
    await fetchArticles();
    await fetchStatus();
  });

  // Export dropdown
  const exportBtn = document.getElementById('btn-export-dropdown');
  const exportMenu = document.getElementById('export-menu');
  exportBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    exportMenu.classList.toggle('show');
  });
  document.addEventListener('click', () => exportMenu.classList.remove('show'));

  document.getElementById('export-csv').addEventListener('click', (e) => {
    e.preventDefault();
    const params = new URLSearchParams({
      format: 'csv',
      keyword: state.selectedKeyword,
      website: state.selectedWebsite,
      filter: state.activeTab
    });
    window.location.href = `/api/export?${params.toString()}`;
  });

  document.getElementById('export-json').addEventListener('click', (e) => {
    e.preventDefault();
    const params = new URLSearchParams({
      format: 'json',
      keyword: state.selectedKeyword,
      website: state.selectedWebsite,
      filter: state.activeTab
    });
    window.location.href = `/api/export?${params.toString()}`;
  });

  // Settings Modal Open/Close
  const settingsModal = document.getElementById('modal-settings');
  document.getElementById('btn-open-settings').addEventListener('click', () => {
    settingsModal.classList.add('open');
  });
  document.getElementById('btn-close-settings').addEventListener('click', () => {
    settingsModal.classList.remove('open');
  });

  // Save Settings
  document.getElementById('btn-save-settings').addEventListener('click', async () => {
    const updated = {
      refresh_interval_minutes: document.getElementById('setting-interval').value,
      region_language: document.getElementById('setting-region').value,
      enable_windows_notifications: document.getElementById('setting-notifications').checked ? 'true' : 'false',
      enable_sound: document.getElementById('setting-sound').checked ? 'true' : 'false',
      enable_reddit: document.getElementById('setting-reddit').checked ? 'true' : 'false',
      enable_hackernews: document.getElementById('setting-hn').checked ? 'true' : 'false'
    };
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updated)
    });
    state.settings = updated;
    settingsModal.classList.remove('open');
    await fetchStatus();
  });

  // Links File Modal Open/Close
  const linksModal = document.getElementById('modal-links');
  document.getElementById('btn-open-links').addEventListener('click', async () => {
    linksModal.classList.add('open');
    await refreshLinksPreview();
  });
  document.getElementById('btn-close-links').addEventListener('click', () => {
    linksModal.classList.remove('open');
  });
  document.getElementById('btn-refresh-links').addEventListener('click', refreshLinksPreview);

  document.getElementById('btn-clear-links').addEventListener('click', async () => {
    if (confirm('Clear the contents of news_links.txt?')) {
      await fetch('/api/links-file/clear', { method: 'POST' });
      await refreshLinksPreview();
    }
  });

  // Close modals when clicking backdrop
  [settingsModal, linksModal, deleteAllModal].forEach(modal => {
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('open');
      });
    }
  });
}

async function refreshLinksPreview() {
  const pre = document.getElementById('links-file-content');
  pre.textContent = 'Loading...';
  try {
    const res = await fetch('/api/links-file');
    pre.textContent = await res.text();
  } catch (e) {
    pre.textContent = 'Error reading file: ' + e.message;
  }
}

function populateSettingsModal() {
  const s = state.settings;
  if (s.refresh_interval_minutes) document.getElementById('setting-interval').value = s.refresh_interval_minutes;
  if (s.region_language) document.getElementById('setting-region').value = s.region_language;
  document.getElementById('setting-notifications').checked = s.enable_windows_notifications !== 'false';
  document.getElementById('setting-sound').checked = s.enable_sound !== 'false';
  document.getElementById('setting-reddit').checked = s.enable_reddit === 'true';
  document.getElementById('setting-hn').checked = s.enable_hackernews === 'true';
}

// ==================== TIMER LOOP ====================

function startTimerLoop() {
  clearInterval(state.timerInterval);
  state.timerInterval = setInterval(() => {
    if (state.remainingSeconds > 0) {
      state.remainingSeconds -= 1;
      document.getElementById('countdown-display').textContent = formatTime(state.remainingSeconds);
    }
  }, 1000);
}

// ==================== REAL-TIME SSE EVENTS ====================

function initSSE() {
  const evtSource = new EventSource('/api/events');

  evtSource.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      const ev = msg.event;
      const data = msg.data || {};

      if (ev === 'scan_started') {
        state.isScanning = true;
        document.getElementById('status-text').textContent = data.message || 'Scanning for updates...';
        document.getElementById('scan-btn-label').textContent = 'Scanning...';
        document.querySelector('.spin-icon').classList.add('spinning');
        document.getElementById('btn-scan-now').disabled = true;
      } else if (ev === 'scanning_keyword') {
        let msgText = `Scanning for '${data.keyword}'`;
        if (data.websites && data.websites.length > 0) {
          msgText += ` on ${data.websites.join(', ')}`;
        }
        document.getElementById('status-text').textContent = msgText + '...';
      } else if (ev === 'scan_finished') {
        state.isScanning = false;
        let doneMsg = `Completed. Found ${data.new_count || 0} new item(s).`;
        if (data.websites && data.websites.length > 0) {
          doneMsg += ` (${data.websites.join(', ')})`;
        }
        document.getElementById('status-text').textContent = doneMsg;
        document.getElementById('scan-btn-label').textContent = 'Scan Now';
        document.querySelector('.spin-icon').classList.remove('spinning');
        document.getElementById('btn-scan-now').disabled = false;

        // If new articles arrived, play chime and refresh
        if (data.new_count > 0) {
          playAlertChime();
        }
        fetchArticles();
        fetchStatus();
        fetchKeywords();
        fetchWebsites();
      } else if (ev === 'scan_error') {
        state.isScanning = false;
        document.getElementById('status-text').textContent = 'Scan error';
        document.getElementById('scan-btn-label').textContent = 'Scan Now';
        document.querySelector('.spin-icon').classList.remove('spinning');
        document.getElementById('btn-scan-now').disabled = false;
      }
    } catch (err) {
      console.debug('SSE parse error:', err);
    }
  };

  evtSource.onerror = (e) => {
    document.getElementById('status-text').textContent = 'Reconnecting...';
  };
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
  initEventHandlers();
  await fetchSettings();
  await fetchKeywords();
  await fetchWebsites();
  await fetchArticles();
  await fetchStatus();
  startTimerLoop();
  initSSE();

  // Polling fallback every 30s in case SSE is interrupted
  setInterval(fetchStatus, 30000);
});
