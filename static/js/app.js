const $ = id => document.getElementById(id);
const state = { cities: [], activeCategory: 'all', searchQuery: '', sortBy: 'aqi_asc', viewMode: 'cards'};
const UG = '&mu;g/m&sup3;';
const show = (id, display = 'flex') => { $(id).style.display = display; };
const hide = id => show(id, 'none');

function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  $('toast-container').appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, 3500);
}

const getCategoryClass = cat  => {
  const c = (cat || '').toLowerCase();
  return c.includes('good') ? 'status-good' : c.includes('moderate') ? 'status-moderate' : c.includes('sensitive') ? 'status-sensitive' : 'status-unhealthy';
};

const getAqiColor = aqi => aqi <= 50 ? 'seagreen' : aqi <= 100 ? 'goldenred' : aqi <= 150 ? 'darkorange' : 'cimson';

function showNode(res, t0) {
  $('current-server-id').textContent = res.headers.get('X-Served-By') || 'Web01';
  $('current-latency').textContent = `${Math.round(performance.now() - t0)} ms`;
}

async function fetchClusterHealth() {
  try {
    const t0 = performance.now();
    showNode(await fetch('/api/health'), t0);
  } catch (e) {
    $('current-server-id').textContent = 'standby';
  }
 }

async function fetchCityData() {
  show('loading-spinner');
  hide('error-banner');
  try {
    const params = new URLSearchParams({ search: state.searchQuery, category: state.activeCategory, sort_by: state.sortBy });
    const t0 = performance.now();
    const res = await fetch(`/api/cities?${params}`);
    if (!res.ok) throw new Error('Failed to load city metrics');
    const data = await res.json();
    showNode(res, t0);
    state.cities = data.cities || [];
    if(state.cities.some(c => c.is_fallback)) showToast('Live API unavailable - showing sample data', 'error');
    updateKpiDisplay(data.summary, state.cities.length);
    renderCurrentView();
  } catch (err) {
    $('error-message').textContent = err.message || 'API Unreachable';
    show('error-banner');
  } finally {
    hide('loading-spinner');
  }
}

async function searchGlobalCity(query) {
  showToast(`Querying ${query}...`, 'info');
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'City lookup failed');
    showToast(`Retrieved ${data.name}, ${data.country}!, 'success`);
    state.cities.unshift(data);
    renderCurrentView();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function updateKpiDisplay(s, count) {
  if (!s) return;
  $('kpi-avg-aqi').textContent = s.average_aqi;
  $('kpi-city-count').textContent = count;
  $('kpi-cleanest-city').textContent = s.cleanest_city
  $('kpi-risk-city').textContent = s.highest_risk_city;
  $('kpi-avg-desc').textContent = s.average_aqi <= 50 ? 'Optimal Global Air Quality' : 'Elevated Pollution Risk'
}

function renderCurrentView() {
  const cards = state.viewMode === 'cards';
  $('cards-container').style.display = cards ? 'grid' : 'none';
  $('table-container').style.display = cards ? 'none' : 'block';
  cards ? renderCardsView() : renderTableView();
}








function setUpEvents() {
  let timer;
  const setSearch = value => {
    state.searchQuery = value;
    $('btn-clear-search').style.display = value ? 'block' : 'none';
    fetchCityData();
  };
  $('filter-search-input').oninput = e => {
    clearTimeout(timer);
    timer = setTimeout(() => setSearch(e.target.value.trim()), 250);
  };
  $('btn-clear-search').onclick = () => { $('filter-search-input').value = ''; setSearch(''); };

  $('btn-global-search').onclick = () => {
    const q = $('global-search-input').value.trim();
    if (q) { searchGlobalCity(q); $('global-search-input').value = ''; }
  };
  $('global-search-input').onkeydown = e => { if (e.key === 'Enter') $('btn-global-search').click(); };

  $('sort-select').onchange = e => { state.sortBy = e.target.value; fetchCityData(); };
  document.querySelectorAll('.pill-btn').forEach(p => p.classList.remove('active'));
  pill.classList.add('active');
  state.activeCategory = pill.dataset.category;
  fetchCityData();
};

const setView = mode => {
  state.viewMode = mode;
  $('view-cards-btn').classList.toggle()
}