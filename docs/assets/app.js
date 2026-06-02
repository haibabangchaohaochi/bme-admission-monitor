const STATUS_LABELS = ['未发布', '疑似发布', '已发布', '报名中', '已截止', '需人工核验'];
const TEMP_KEY = 'bme_monitor_temp_schools';

let allSchools = [];
let filteredSchools = [];
let priorityOnly = false;

function getTempSchools() {
  try {
    return JSON.parse(localStorage.getItem(TEMP_KEY) || '[]');
  } catch {
    return [];
  }
}

function normalizeArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function renderStats(schools) {
  const stats = {
    total: schools.length,
    summer: schools.filter((item) => ['已发布', '报名中'].includes(item.summer_camp_status)).length,
    pre: schools.filter((item) => ['已发布', '报名中'].includes(item.pre_recommend_status)).length,
    open: schools.filter((item) => ['报名中'].includes(item.summer_camp_status) || ['报名中'].includes(item.pre_recommend_status)).length,
    deadline: schools.filter((item) => isWithin72Hours(item.registration_deadline)).length,
    review: schools.filter((item) => ['需人工核验'].includes(item.summer_camp_status) || ['需人工核验'].includes(item.pre_recommend_status)).length,
  };

  const items = [
    ['总监控学校数', stats.total],
    ['夏令营已发布数', stats.summer],
    ['预推免已发布数', stats.pre],
    ['报名中数量', stats.open],
    ['72 小时内截止数量', stats.deadline],
    ['需人工核验数量', stats.review],
  ];

  const grid = document.getElementById('statsGrid');
  grid.innerHTML = items.map(([label, value]) => `<article class="stat-card"><div class="stat-label">${label}</div><div class="stat-value">${value}</div></article>`).join('');
}

function isWithin72Hours(dateText) {
  if (!dateText) return false;
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) return false;
  const diff = date.getTime() - Date.now();
  return diff >= 0 && diff <= 72 * 60 * 60 * 1000;
}

function compareDates(a, b) {
  const da = a ? new Date(a).getTime() : Number.POSITIVE_INFINITY;
  const db = b ? new Date(b).getTime() : Number.POSITIVE_INFINITY;
  return da - db;
}

function normalizeExpectedDate(value) {
  const text = String(value || '');
  const match = text.match(/(20\d{2})[年/-](\d{1,2})(?:[月/-](\d{1,2}))?/);
  if (!match) return Number.POSITIVE_INFINITY;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3] || 1);
  const date = new Date(year, month - 1, day);
  return Number.isNaN(date.getTime()) ? Number.POSITIVE_INFINITY : date.getTime();
}

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

function getSearchText(school) {
  return [school.name, school.level, school.province_city, school.latest_notice_title, school.expected_release_window, school.notes, ...normalizeArray(school.aliases), ...normalizeArray(school.target_colleges), ...normalizeArray(school.preferred_directions), ...normalizeArray(school.candidate_links)].join(' ').toLowerCase();
}

function filterSchool(school) {
  const search = document.getElementById('searchInput').value.trim().toLowerCase();
  const levelFilter = document.getElementById('levelFilter').value;
  const summerFilter = document.getElementById('summerFilter').value;
  const preFilter = document.getElementById('preFilter').value;
  const cityFilter = document.getElementById('cityFilter').value.trim().toLowerCase();
  const directionFilter = document.getElementById('directionFilter').value.trim().toLowerCase();

  if (priorityOnly && school.priority !== 'high') return false;
  if (levelFilter !== 'all' && school.level !== levelFilter) return false;
  if (summerFilter !== 'all' && school.summer_camp_status !== summerFilter) return false;
  if (preFilter !== 'all' && school.pre_recommend_status !== preFilter) return false;
  if (search && !getSearchText(school).includes(search)) return false;
  if (cityFilter && !(school.province_city || '').toLowerCase().includes(cityFilter)) return false;
  if (directionFilter && !normalizeArray(school.preferred_directions).join(' ').toLowerCase().includes(directionFilter) && !normalizeArray(school.target_colleges).join(' ').toLowerCase().includes(directionFilter)) return false;
  return true;
}

function sortSchools(schools) {
  const sortValue = document.getElementById('sortFilter').value;
  const ranked = { high: 0, medium: 1, low: 2 };
  return [...schools].sort((left, right) => {
    if (sortValue === 'deadline') return compareDates(left.registration_deadline, right.registration_deadline) || (ranked[left.priority] - ranked[right.priority]);
    if (sortValue === 'expected') return normalizeExpectedDate(left.expected_release_window) - normalizeExpectedDate(right.expected_release_window) || (ranked[left.priority] - ranked[right.priority]);
    if (sortValue === 'checked') return compareDates(right.last_checked_at, left.last_checked_at) || (ranked[left.priority] - ranked[right.priority]);
    return (ranked[left.priority] - ranked[right.priority]) || left.name.localeCompare(right.name, 'zh-Hans-CN');
  });
}

function statusBadge(status) {
  return `<span class="status ${status}">${status || '未发布'}</span>`;
}

function renderCard(school) {
  const tempLabel = school.temporary_local ? '<span class="pill priority-medium">本机临时新增</span>' : '';
  const manualLabel = school.manual_override ? '<span class="pill priority-high">人工修正</span>' : '';
  const candidateLinks = normalizeArray(school.candidate_links).map((link) => `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">候选链接</a>`).join('');
  const colleges = normalizeArray(school.target_colleges).map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join('');
  const directions = normalizeArray(school.preferred_directions).map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join('');
  const history = normalizeArray(school.history).map((item) => `<div class="history-item"><strong>${escapeHtml(item.field_name || item.event_type || '')}</strong><br><small>${escapeHtml(item.old_value || '')} → ${escapeHtml(item.new_value || '')}</small></div>`).join('');

  return `
    <article class="school-card">
      <div class="school-head">
        <div>
          <h3 class="school-title">${escapeHtml(school.name)} ${school.temporary_local ? '<span class="pill priority-medium">本机临时新增</span>' : ''}</h3>
          <div class="tag-row">
            <span class="pill level">${escapeHtml(school.level || '')}</span>
            <span class="pill priority-${escapeHtml(school.priority || 'medium')}">${escapeHtml(school.priority || 'medium')}</span>
            ${manualLabel}
          </div>
        </div>
        <div class="school-meta">
          ${statusBadge(school.summer_camp_status)}
          ${statusBadge(school.pre_recommend_status)}
        </div>
      </div>

      <div class="detail-grid">
        <div class="field"><span>预计发布时间</span><strong>${escapeHtml(school.expected_release_window || '')}</strong></div>
        <div class="field"><span>报名截止</span><strong>${escapeHtml(school.registration_deadline || '')}</strong></div>
        <div class="field"><span>活动时间</span><strong>${escapeHtml(school.event_time || '')}</strong></div>
        <div class="field"><span>最近检查时间</span><strong>${escapeHtml(school.last_checked_at || '')}</strong></div>
      </div>

      <div class="field" style="margin-top:10px;">
        <span>最新公告</span>
        <strong>${escapeHtml(school.latest_notice_title || '暂无')}</strong>
      </div>

      ${school.change_summary ? `<div class="field" style="margin-top:10px;"><span>变更摘要</span><strong>${escapeHtml(school.change_summary)}</strong></div>` : ''}

      <div class="link-row" style="margin-top:10px;">
        ${school.latest_notice_url ? `<a href="${escapeHtml(school.latest_notice_url)}" target="_blank" rel="noopener noreferrer">官方链接</a>` : '<span class="pill">暂无官方链接</span>'}
        ${tempLabel}
      </div>

      <details class="details">
        <summary>展开详情</summary>
        <div style="margin-top:12px; display:grid; gap:12px;">
          <div><strong>重点学院</strong><div class="tag-row" style="margin-top:8px;">${colleges || '<span class="pill">暂无</span>'}</div></div>
          <div><strong>适配方向</strong><div class="tag-row" style="margin-top:8px;">${directions || '<span class="pill">暂无</span>'}</div></div>
          <div><strong>候选链接</strong><div class="link-row" style="margin-top:8px;">${candidateLinks || '<span class="pill">暂无</span>'}</div></div>
          <div><strong>人工备注</strong><p>${escapeHtml(school.notes || '')}</p></div>
          <div><strong>历史变更</strong><div class="history-list">${history || '<div class="history-item"><small>暂无历史记录</small></div>'}</div></div>
        </div>
      </details>
    </article>
  `;
}

function refreshList() {
  const container = document.getElementById('listContainer');
  filteredSchools = sortSchools(allSchools.filter(filterSchool));
  container.innerHTML = filteredSchools.map(renderCard).join('') || '<div class="school-card">没有符合条件的数据。</div>';
  document.getElementById('summaryText').textContent = `当前显示 ${filteredSchools.length} 条，共 ${allSchools.length} 条。`;
  renderStats(allSchools);
}

function toCsv(rows) {
  const header = ['id', 'name', 'level', 'province_city', 'summer_camp_status', 'pre_recommend_status', 'expected_release_window', 'registration_deadline', 'event_time', 'latest_notice_title', 'latest_notice_url', 'last_checked_at', 'priority', 'notes'];
  const escapeCsv = (value) => `"${String(value ?? '').replace(/"/g, '""')}"`;
  return [header.join(','), ...rows.map((row) => header.map((key) => escapeCsv(row[key])).join(','))].join('\n');
}

function exportData() {
  const jsonBlob = new Blob([JSON.stringify({ generated_at: new Date().toISOString(), schools: filteredSchools.length ? filteredSchools : allSchools }, null, 2)], { type: 'application/json;charset=utf-8' });
  const csvBlob = new Blob([toCsv(filteredSchools.length ? filteredSchools : allSchools)], { type: 'text/csv;charset=utf-8' });
  downloadBlob(jsonBlob, 'status-export.json');
  downloadBlob(csvBlob, 'status-export.csv');
}

function downloadBlob(blob, filename) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function renderHistory(statusData) {
  const historyList = document.getElementById('historyList');
  const records = normalizeArray(statusData.recent_history).slice().reverse();
  historyList.innerHTML = records.map((item) => `
    <div class="history-item">
      <strong>${escapeHtml(item.school_name || '')}</strong>
      <div><small>${escapeHtml(item.timestamp || '')}</small></div>
      <div>${escapeHtml(item.field_name || item.event_type || '')}: ${escapeHtml(item.old_value || '')} → ${escapeHtml(item.new_value || '')}</div>
      <div><small>${escapeHtml(item.notes || '')}</small></div>
    </div>
  `).join('') || '<div class="history-item"><small>暂无历史变更记录。</small></div>';
}

async function loadDashboard() {
  const response = await fetch('status.json', { cache: 'no-store' });
  const statusData = await response.json();
  const tempSchools = getTempSchools().map((item) => ({ ...item, temporary_local: true, manual_override: true, priority: item.priority || 'medium', summer_camp_status: item.summer_camp_status || '未发布', pre_recommend_status: item.pre_recommend_status || '未发布' }));
  allSchools = [...normalizeArray(statusData.schools), ...tempSchools];
  renderHistory(statusData);
  refreshList();
}

function bindEvents() {
  const controls = ['searchInput', 'levelFilter', 'summerFilter', 'preFilter', 'cityFilter', 'directionFilter', 'sortFilter'];
  controls.forEach((id) => document.getElementById(id).addEventListener('input', refreshList));
  controls.forEach((id) => document.getElementById(id).addEventListener('change', refreshList));
  document.getElementById('exportBtn').addEventListener('click', exportData);
  document.getElementById('historyBtn').addEventListener('click', () => document.getElementById('historyDialog').showModal());
  document.getElementById('priorityBtn').addEventListener('click', () => {
    priorityOnly = !priorityOnly;
    document.getElementById('priorityBtn').textContent = priorityOnly ? '显示全部' : '仅看高优先级';
    refreshList();
  });
}

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('service-worker.js').catch(() => {});
}

bindEvents();
loadDashboard().catch((error) => {
  document.getElementById('listContainer').innerHTML = `<div class="school-card">数据加载失败：${escapeHtml(error.message)}</div>`;
});
