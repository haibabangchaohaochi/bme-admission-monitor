const FORM_KEY = 'bme_monitor_temp_schools';
const DEFAULT_REPO = 'https://github.com/YOUR_GITHUB/YOUR_REPOSITORY';

function getFormData() {
  const form = document.getElementById('addSchoolForm');
  const formData = new FormData(form);
  const splitLines = (value) => String(value || '').split(/[，,\n]/).map((item) => item.trim()).filter(Boolean);
  const name = String(formData.get('name') || '').trim();
  const slug = name ? name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || `school-${Date.now()}` : `school-${Date.now()}`;
  return {
    id: slug,
    name,
    aliases: splitLines(formData.get('aliases')),
    level: formData.get('level') || '其他',
    province_city: String(formData.get('province_city') || '').trim(),
    target_colleges: splitLines(formData.get('target_colleges')),
    official_sites: splitLines(formData.get('official_sites')),
    search_domains: splitLines(formData.get('search_domains')),
    college_notice_url: String(formData.get('college_notice_url') || '').trim(),
    preferred_directions: splitLines(formData.get('preferred_directions')),
    priority: formData.get('priority') || 'medium',
    notes: String(formData.get('notes') || '').trim(),
    manual_override: false,
    source_type: '人工新增',
    source_reliability: 'medium',
    summer_camp_status: '未发布',
    pre_recommend_status: '未发布',
  };
}

function readTempSchools() {
  try {
    return JSON.parse(localStorage.getItem(FORM_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveTempSchool(school) {
  const existing = readTempSchools().filter((item) => item.id !== school.id);
  existing.unshift({ ...school, temporary_local: true, source_type: '本机临时新增', source_reliability: 'medium' });
  localStorage.setItem(FORM_KEY, JSON.stringify(existing));
}

function inferRepoUrl() {
  if (window.BME_MONITOR_REPO_URL) {
    return String(window.BME_MONITOR_REPO_URL).replace(/\/$/, '');
  }
  const host = window.location.hostname || '';
  if (host.endsWith('github.io')) {
    const user = host.split('.')[0];
    const repo = window.location.pathname.split('/').filter(Boolean)[0] || '';
    if (user && repo) {
      return `https://github.com/${user}/${repo}`;
    }
  }
  return DEFAULT_REPO;
}

function toYaml(value, indent = 0) {
  const pad = ' '.repeat(indent);
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => `${pad}- ${typeof item === 'object' ? '\n' + toYaml(item, indent + 2) : item}`).join('\n') : `${pad}[]`;
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([key, item]) => {
      if (Array.isArray(item)) return `${pad}${key}:\n${toYaml(item, indent + 2)}`;
      if (item && typeof item === 'object') return `${pad}${key}:\n${toYaml(item, indent + 2)}`;
      return `${pad}${key}: ${item === '' ? '""' : item}`;
    }).join('\n');
  }
  return `${pad}${value}`;
}

function buildYamlSchool(school) {
  return {
    schools: [
      {
        id: school.id,
        name: school.name,
        aliases: school.aliases,
        level: school.level,
        province_city: school.province_city,
        target_colleges: school.target_colleges,
        official_sites: school.official_sites,
        search_domains: school.search_domains,
        college_notice_url: school.college_notice_url,
        preferred_directions: school.preferred_directions,
        priority: school.priority,
        notes: school.notes,
      }
    ]
  };
}

function updatePreview() {
  const school = getFormData();
  document.getElementById('yamlPreview').value = toYaml(buildYamlSchool(school));
}

function openIssue() {
  const school = getFormData();
  const yamlText = toYaml(buildYamlSchool(school));
  const body = `新增学校申请\n\n请确认以下 YAML 是否可追加到 data/extra_schools.yaml：\n\n\
\
\

\
\
\
\
\
\
\
\
\
\
\
\
\
\
\`\`\`yaml\n${yamlText}\n\`\`\`\n\n备注：如自动解析失败，请手动复制到 extra_schools.yaml。`;
  const repoUrl = (window.BME_MONITOR_REPO_URL || DEFAULT_REPO).replace(/\/$/, '');
  const url = `${repoUrl}/issues/new?title=${encodeURIComponent(`新增学校：${school.name}`)}&body=${encodeURIComponent(body)}&labels=add-school`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

function init() {
  const form = document.getElementById('addSchoolForm');
  form.addEventListener('input', updatePreview);
  const body = `新增学校申请\n\n请确认以下 YAML 是否可追加到 data/extra_schools.yaml：\n\n\`\`\`yaml\n${yamlText}\n\`\`\`\n\n备注：如自动解析失败，请手动复制到 extra_schools.yaml。`;
  const repoUrl = inferRepoUrl();
