/**
 * E-Voting System — Admin Panel Logic
 * Handles student registration, candidate management,
 * live results rendering (grouped by position), and data reset.
 */

/* ══════════════════════════════════════════
   INIT & GLOBALS
══════════════════════════════════════════ */

const channel = new BroadcastChannel(CHANNEL_NAME);

let students     = [];
let electionData = [];  // grouped by position
let votes        = {};

/* ══════════════════════════════════════════
   DOM REFERENCES
══════════════════════════════════════════ */

const $ = id => document.getElementById(id);

const addStudentForm    = $('addStudentForm');
const addCandidateForm  = $('addCandidateForm');
const resetAllDataBtn   = $('resetAllDataBtn');
const resultsContainer  = $('resultsContainer');
const emptyResults      = $('emptyResults');
const totalVotesBadge   = $('totalVotesBadge');
const studentCountBadge = $('studentCountBadge');

/* ══════════════════════════════════════════
   STARTUP
══════════════════════════════════════════ */

function init() {
  initStorage();
  loadData();
  renderResults();
  updateStudentCount();
  startClock();
  bindEvents();
  listenChannel();
}

function loadData() {
  students     = loadStudents();
  electionData = loadElectionData();
  votes        = loadVotes();
}

/* ══════════════════════════════════════════
   CLOCK
══════════════════════════════════════════ */

function startClock() {
  function tick() {
    const now  = new Date();
    const time = now.toLocaleTimeString('en-IN', { hour12: true });
    const date = now.toLocaleDateString('en-IN', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
    $('adminTime').textContent = time;
    $('adminDate').textContent = date;
  }
  tick();
  setInterval(tick, 1000);
}

/* ══════════════════════════════════════════
   STUDENT COUNT
══════════════════════════════════════════ */

function updateStudentCount() {
  studentCountBadge.textContent = students.length;
}

/* ══════════════════════════════════════════
   RESULTS RENDER — grouped by position
══════════════════════════════════════════ */

function renderResults() {
  resultsContainer.innerHTML = '';

  // Flatten all candidates from all positions
  const allCandidates = flattenCandidates(electionData);

  if (allCandidates.length === 0) {
    emptyResults.style.display = 'flex';
    totalVotesBadge.textContent = '0 Votes Cast';
    return;
  }

  emptyResults.style.display = 'none';

  // Total votes across all positions/candidates
  const totalVotes = allCandidates.reduce((sum, c) => sum + (c.votes || 0), 0);
  totalVotesBadge.textContent = `${totalVotes} Vote${totalVotes !== 1 ? 's' : ''} Cast`;

  // Render a group per position
  electionData.forEach(section => {
    if (section.candidates.length === 0) return;

    // ── Position Group Header ──
    const groupHeader = document.createElement('div');
    groupHeader.className = 'results-position-group';
    groupHeader.innerHTML = `
      <div class="results-position-label">
        <span>${section.icon}</span>
        <span>${section.position}</span>
      </div>
    `;
    resultsContainer.appendChild(groupHeader);

    // Sort candidates in this position by votes descending
    const sorted = [...section.candidates].sort((a, b) => (b.votes || 0) - (a.votes || 0));
    const positionTotalVotes = sorted.reduce((s, c) => s + (c.votes || 0), 0);
    const maxVotes = sorted[0]?.votes || 0;

    sorted.forEach((cand, idx) => {
      const isWinner = idx === 0 && maxVotes > 0;
      const pct      = positionTotalVotes > 0 ? Math.round(((cand.votes || 0) / positionTotalVotes) * 100) : 0;
      const barWidth = maxVotes > 0 ? Math.round(((cand.votes || 0) / maxVotes) * 100) : 0;

      const div = document.createElement('div');
      div.className = 'result-item' + (isWinner ? ' winner' : '');
      div.innerHTML = `
        <div class="result-item-top">
          <div class="result-rank">${isWinner ? '🥇' : idx + 1}</div>
          <div class="result-avatar-wrap">
            ${cand.photo
              ? `<img src="${cand.photo}" alt="${cand.name}" class="result-avatar-img" loading="lazy" />`
              : `<div class="result-symbol">${cand.symbol || '⭐'}</div>`
            }
          </div>
          <div class="result-info">
            <div class="result-name">${cand.name}</div>
            <div class="result-meta">Class ${cand.classNo}–${cand.division}</div>
          </div>
          <div class="result-votes">${cand.votes || 0}</div>
        </div>
        <div class="result-bar-wrap">
          <div class="result-bar-fill" style="width:${barWidth}%"></div>
        </div>
        <div class="result-bar-pct">${pct}% of position votes</div>
      `;
      resultsContainer.appendChild(div);
    });
  });
}

/* ══════════════════════════════════════════
   TOAST NOTIFICATIONS
══════════════════════════════════════════ */

function showToast(type, title, message, duration = 4000) {
  const container = $('toastContainer');
  const icons = { success: '✅', error: '❌', info: '💬' };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      ${message ? `<div class="toast-msg">${message}</div>` : ''}
    </div>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 350);
  }, duration);
}

/* ══════════════════════════════════════════
   BROADCAST CHANNEL — listen for vote updates
══════════════════════════════════════════ */

function listenChannel() {
  channel.onmessage = function(event) {
    const msg = event.data;

    // Re-render results whenever a vote is cast from the voter window
    if (msg.type === 'VOTE_CAST') {
      loadData();
      renderResults();
    }
  };
}

/* ══════════════════════════════════════════
   EVENT BINDINGS
══════════════════════════════════════════ */

function bindEvents() {

  // ── Add Student Form ──
  addStudentForm.addEventListener('submit', e => {
    e.preventDefault();
    const rollNo      = $('studentRollNo').value.trim();
    const admissionNo = $('studentAdmNo').value.trim();
    const name        = $('studentName').value.trim();
    const classNo     = $('studentClass').value;
    const division    = $('studentDiv').value;
    const gender      = $('studentGender').value;

    if (!rollNo || !admissionNo || !name || !classNo || !division) return;

    if (students.find(s => s.rollNo === rollNo)) {
      showToast('error', 'Duplicate Roll No', `Roll No ${rollNo} already exists.`);
      return;
    }

    const newStudent = { rollNo, admissionNo, name, classNo, division, gender, hasVoted: false };
    students.push(newStudent);
    saveStudents(students);
    updateStudentCount();
    addStudentForm.reset();
    showToast('success', 'Student Added', `${name} has been added to the voter list.`);
  });

  // ── Add Candidate Form ──
  addCandidateForm.addEventListener('submit', e => {
    e.preventDefault();
    const name     = $('candName').value.trim();
    const classNo  = $('candClass').value;
    const division = $('candDiv').value;
    const position = $('candPosition').value;
    const symbol   = $('candSymbol').value.trim() || '⭐';
    const photo    = $('candPhoto').value.trim();

    if (!name || !classNo || !division || !position) return;

    // Find the matching position section in electionData
    const section = electionData.find(s => s.position === position);
    if (!section) {
      showToast('error', 'Invalid Position', `Position "${position}" not found.`);
      return;
    }

    const id = 'C' + Date.now();
    section.candidates.push({ id, name, classNo, division, position, symbol, photo, votes: 0 });
    saveElectionData(electionData);
    renderResults();
    addCandidateForm.reset();
    showToast('success', 'Candidate Added', `${name} has been registered for ${position}.`);
  });

  // ── Reset All Data ──
  resetAllDataBtn.addEventListener('click', () => {
    if (!confirm('⚠️ This will reset ALL votes and restore demo data. Continue?')) return;
    localStorage.clear();
    initStorage();
    loadData();
    renderResults();
    updateStudentCount();
    channel.postMessage({ type: 'CANCEL_SESSION' });
    showToast('info', 'Data Reset', 'All data has been restored to demo state.');
  });
}

/* ══════════════════════════════════════════
   BOOT
══════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', init);
