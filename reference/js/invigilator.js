/**
 * E-Voting System — Invigilator Panel Logic
 * Handles student management, voting session activation,
 * countdown timers, and real-time cross-window communication.
 */

/* ══════════════════════════════════════════
   INIT & GLOBALS
══════════════════════════════════════════ */

const channel = new BroadcastChannel(CHANNEL_NAME);

let students     = [];
let electionData = [];    // grouped by position
let votes        = {};
let filteredStudents = [];

// Active session state
let activeStudent     = null;
let countdownInterval = null;
let countdownTotal    = 60; // seconds
let countdownRemaining = 60;
let voterWindowRef    = null;
let voterWindowPingInterval = null;

/* ══════════════════════════════════════════
   DOM REFERENCES
══════════════════════════════════════════ */

const $ = id => document.getElementById(id);

const studentsTableBody    = $('studentsTableBody');
const emptyState           = $('emptyState');
const tableCountLabel      = $('tableCountLabel');
const activeFilterBadge    = $('activeFilterBadge');
const filterChips          = $('filterChips');

const filterClassEl        = $('filterClass');
const filterDivisionEl     = $('filterDivision');
const filterStatusEl       = $('filterStatus');
const searchInputEl        = $('searchInput');
const viewDetailsBtn       = $('viewDetailsBtn');
const clearFiltersBtn      = $('clearFiltersBtn');

const invigiModal          = $('invigiModal');
const modalVoterName       = $('modalVoterName');
const modalVoterRoll       = $('modalVoterRoll');
const modalVoterClass      = $('modalVoterClass');
const modalVoterDiv        = $('modalVoterDiv');
const invigiCountdownDisplay = $('invigiCountdownDisplay');
const invigiCountdownBar   = $('invigiCountdownBar');
const invigiConfirmBtn     = $('invigiConfirmBtn');
const invigiCancelBtn      = $('invigiCancelBtn');

const openVoterWindowBtn   = $('openVoterWindowBtn');
const voterWindowStatus    = $('voterWindowStatus');

/* ══════════════════════════════════════════
   STARTUP
══════════════════════════════════════════ */

function init() {
  initStorage();
  loadData();
  renderTable(students);
  updateStats();
  startClock();
  bindEvents();
  startVoterWindowPing();
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
    $('headerTime').textContent = time;
    $('headerDate').textContent = date;
  }
  tick();
  setInterval(tick, 1000);
}

/* ══════════════════════════════════════════
   AVATAR HELPERS
══════════════════════════════════════════ */

const AVATAR_COLORS = [
  '#4F46E5','#7C3AED','#DB2777','#D97706','#059669','#0891B2','#DC2626','#7C3AED'
];

function getAvatarColor(name) {
  let hash = 0;
  for (const c of name) hash = (hash + c.charCodeAt(0)) % AVATAR_COLORS.length;
  return AVATAR_COLORS[hash];
}

function getInitials(name) {
  return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
}

function getPronoun(gender) {
  return gender === 'female' ? 'Ms.' : 'Mr.';
}

/* ══════════════════════════════════════════
   STATS
══════════════════════════════════════════ */

function updateStats() {
  const total   = students.length;
  const voted   = students.filter(s => s.hasVoted).length;
  const pending = total - voted;
  const turnout = total > 0 ? Math.round((voted / total) * 100) : 0;

  $('statTotalStudents').textContent = total;
  $('statVotedCount').textContent    = voted;
  $('statPendingCount').textContent  = pending;
  $('statTurnout').textContent       = turnout + '%';
}

/* ══════════════════════════════════════════
   TABLE RENDER
══════════════════════════════════════════ */

function renderTable(list) {
  filteredStudents = list;
  studentsTableBody.innerHTML = '';

  tableCountLabel.textContent = `Showing ${list.length} student${list.length !== 1 ? 's' : ''}`;

  if (list.length === 0) {
    emptyState.style.display = 'flex';
    return;
  }

  emptyState.style.display = 'none';

  list.forEach((student, idx) => {
    const tr = document.createElement('tr');
    if (student.hasVoted) tr.classList.add('voted-row');

    const color    = getAvatarColor(student.name);
    const initials = getInitials(student.name);

    tr.innerHTML = `
      <td style="color:var(--text-muted);font-size:12px;padding-left:24px">${idx + 1}</td>
      <td class="td-roll">${student.rollNo}</td>
      <td class="td-admission">${student.admissionNo}</td>
      <td class="td-name">
        <div class="avatar" style="background:${color}">${initials}</div>
        ${student.name}
      </td>
      <td>
        <span class="badge badge-primary" style="font-size:11px">
          ${student.classNo} – ${student.division}
        </span>
      </td>
      <td>
        ${student.hasVoted
          ? '<span class="badge badge-success">✅ Voted</span>'
          : '<span class="badge badge-warning">⏳ Pending</span>'
        }
      </td>
      <td class="td-action">
        ${student.hasVoted
          ? `<span class="btn btn-voted btn-sm">✅ Voted</span>`
          : `<button class="vote-now-btn" data-roll="${student.rollNo}" aria-label="Vote Now for ${student.name}">
               🗳️ Vote Now
             </button>`
        }
      </td>
    `;

    studentsTableBody.appendChild(tr);
  });

  // Bind Vote Now buttons
  studentsTableBody.querySelectorAll('.vote-now-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const rollNo = btn.dataset.roll;
      const student = students.find(s => s.rollNo === rollNo);
      if (student) openInvigiModal(student);
    });
  });
}

/* ══════════════════════════════════════════
   FILTER & SEARCH
══════════════════════════════════════════ */

let activeFilters = { classNo: '', division: '', status: '', search: '' };

function applyFilters() {
  let list = [...students];

  if (activeFilters.classNo) {
    list = list.filter(s => s.classNo === activeFilters.classNo);
  }
  if (activeFilters.division) {
    list = list.filter(s => s.division === activeFilters.division);
  }
  if (activeFilters.status === 'voted') {
    list = list.filter(s => s.hasVoted);
  } else if (activeFilters.status === 'pending') {
    list = list.filter(s => !s.hasVoted);
  }
  if (activeFilters.search) {
    const q = activeFilters.search.toLowerCase();
    list = list.filter(s =>
      s.name.toLowerCase().includes(q) ||
      s.rollNo.toLowerCase().includes(q) ||
      s.admissionNo.toLowerCase().includes(q)
    );
  }

  const hasFilters = Object.values(activeFilters).some(v => v !== '');
  activeFilterBadge.style.display = hasFilters ? 'inline-flex' : 'none';

  renderTable(list);
  renderFilterChips();
}

function renderFilterChips() {
  filterChips.innerHTML = '';
  const labels = {
    classNo:  v => `Class ${v}`,
    division: v => `Division ${v}`,
    status:   v => v.charAt(0).toUpperCase() + v.slice(1),
    search:   v => `"${v}"`,
  };
  Object.entries(activeFilters).forEach(([key, val]) => {
    if (!val) return;
    const chip = document.createElement('div');
    chip.className = 'filter-chip';
    chip.innerHTML = `${labels[key](val)} <span class="filter-chip-remove" data-key="${key}">✕</span>`;
    filterChips.appendChild(chip);
  });

  filterChips.querySelectorAll('.filter-chip-remove').forEach(el => {
    el.addEventListener('click', () => {
      const key = el.dataset.key;
      activeFilters[key] = '';
      if (key === 'classNo')  filterClassEl.value    = '';
      if (key === 'division') filterDivisionEl.value = '';
      if (key === 'status')   filterStatusEl.value   = '';
      if (key === 'search')   searchInputEl.value    = '';
      applyFilters();
    });
  });
}

/* ══════════════════════════════════════════
   INVIGILATOR MODAL
══════════════════════════════════════════ */

function openInvigiModal(student) {
  activeStudent = student;

  modalVoterName.textContent  = student.name;
  modalVoterRoll.textContent  = student.rollNo;
  modalVoterClass.textContent = `Class ${student.classNo}`;
  modalVoterDiv.textContent   = `Division ${student.division}`;

  countdownRemaining = countdownTotal;
  updateInvigiCountdown();

  invigiModal.classList.add('active');
}

function closeInvigiModal(cancelSession = false) {
  invigiModal.classList.remove('active');
  clearCountdownTimer();

  if (cancelSession && activeStudent) {
    // Tell voter window to go back to idle
    channel.postMessage({ type: 'CANCEL_SESSION' });
    setActiveSession(null);
  }
  activeStudent = null;
}

function updateInvigiCountdown() {
  const pct = (countdownRemaining / countdownTotal) * 100;
  invigiCountdownDisplay.textContent = countdownRemaining;
  invigiCountdownBar.style.width = pct + '%';

  const isWarning = countdownRemaining <= 15;
  invigiCountdownDisplay.classList.toggle('warning', isWarning);
  invigiCountdownBar.classList.toggle('warning', isWarning);
}

function startCountdownTimer() {
  clearCountdownTimer();
  countdownInterval = setInterval(() => {
    countdownRemaining--;

    updateInvigiCountdown();
    // Sync countdown to voter window via channel
    channel.postMessage({ type: 'COUNTDOWN_TICK', remaining: countdownRemaining });

    if (countdownRemaining <= 0) {
      clearCountdownTimer();
      // Capture name before clearing state
      const expiredName = activeStudent?.name || 'voter';
      channel.postMessage({ type: 'SESSION_EXPIRED' });
      setActiveSession(null);
      closeInvigiModal(false);
      showToast('info', 'Session Expired', `Voting session for ${expiredName} has expired.`);
    }
  }, 1000);
}

function clearCountdownTimer() {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
}

/* ══════════════════════════════════════════
   VOTER WINDOW MANAGEMENT
══════════════════════════════════════════ */

function openVoterWindow() {
  if (voterWindowRef && !voterWindowRef.closed) {
    voterWindowRef.focus();
    return;
  }
  voterWindowRef = window.open('voter.html', 'evoting_voter_window',
    'width=1000,height=720,resizable=yes,scrollbars=yes');
  updateVoterWindowStatus(true);
}

function startVoterWindowPing() {
  voterWindowPingInterval = setInterval(() => {
    const open = voterWindowRef && !voterWindowRef.closed;
    updateVoterWindowStatus(open);
  }, 2000);
}

function updateVoterWindowStatus(online) {
  voterWindowStatus.className = 'voter-status ' + (online ? 'online' : 'offline');
  voterWindowStatus.innerHTML = `
    <div class="voter-status-dot"></div>
    <span>Voter Window ${online ? 'Active' : 'Offline'}</span>
  `;
}

/* ══════════════════════════════════════════
   BROADCAST CHANNEL HANDLER
══════════════════════════════════════════ */

channel.onmessage = function(event) {
  const msg = event.data;

  if (msg.type === 'VOTE_CAST') {
    // A ballot was submitted from the voter window (contains votes for all positions)
    const student = students.find(s => s.rollNo === msg.studentRollNo);
    if (student) {
      student.hasVoted = true;
      saveStudents(students);

      // Record each position vote into the election data
      const posVotes = msg.votes || {}; // { [position]: { id, name } }
      Object.values(posVotes).forEach(v => {
        // Increment candidate's vote count inside electionData
        electionData.forEach(section => {
          const cand = section.candidates.find(c => c.id === v.id);
          if (cand) cand.votes = (cand.votes || 0) + 1;
        });
        // Also persist in flat votes map
        votes[v.id] = (votes[v.id] || 0) + 1;
      });

      saveElectionData(electionData);
      saveVotes(votes);

      clearCountdownTimer();
      closeInvigiModal(false);
      setActiveSession(null);

      applyFilters();
      updateStats();

      showToast('success', 'Vote Recorded!',
        `${student.name} voted successfully.`);
    }
  }

  if (msg.type === 'VOTER_WINDOW_READY') {
    updateVoterWindowStatus(true);
  }
};


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
   EVENT BINDINGS
══════════════════════════════════════════ */

function bindEvents() {

  // Open voter window
  openVoterWindowBtn.addEventListener('click', openVoterWindow);

  // Filter — View Details button
  viewDetailsBtn.addEventListener('click', () => {
    activeFilters.classNo  = filterClassEl.value;
    activeFilters.division = filterDivisionEl.value;
    activeFilters.status   = filterStatusEl.value;
    activeFilters.search   = searchInputEl.value.trim();
    applyFilters();
  });

  // Search input — live search
  searchInputEl.addEventListener('input', () => {
    activeFilters.search = searchInputEl.value.trim();
    applyFilters();
  });

  // Enter key on search
  searchInputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter') applyFilters();
  });

  // Clear filters
  clearFiltersBtn.addEventListener('click', () => {
    activeFilters = { classNo: '', division: '', status: '', search: '' };
    filterClassEl.value    = '';
    filterDivisionEl.value = '';
    filterStatusEl.value   = '';
    searchInputEl.value    = '';
    applyFilters();
  });

  // Invigilator modal — Confirm (Activate)
  invigiConfirmBtn.addEventListener('click', () => {
    if (!activeStudent) return;

    // Ensure voter window is open
    if (!voterWindowRef || voterWindowRef.closed) {
      voterWindowRef = window.open('voter.html', 'evoting_voter_window',
        'width=1000,height=720,resizable=yes,scrollbars=yes');
      updateVoterWindowStatus(true);
      // Give window time to load
      setTimeout(() => activateVoterSession(), 1200);
    } else {
      activateVoterSession();
    }
  });

  // Invigilator modal — Cancel
  invigiCancelBtn.addEventListener('click', () => {
    closeInvigiModal(true);
  });

  // Click outside modal to do nothing (keep modal open intentionally)

  // Listen for data changes from the Admin Panel (students added)
  channel.addEventListener && window.addEventListener('storage', () => {
    loadData();
    applyFilters();
    updateStats();
  });
}

/* ══════════════════════════════════════════
   ACTIVATE VOTER SESSION
══════════════════════════════════════════ */

function activateVoterSession() {
  if (!activeStudent) return;

  const sessionData = {
    student:     activeStudent,
    electionData: electionData,
    expiresAt:   Date.now() + (countdownTotal * 1000),
    countdown:   countdownTotal,
  };

  setActiveSession(sessionData);

  channel.postMessage({
    type:         'ACTIVATE_VOTER',
    student:      activeStudent,
    electionData: electionData,
    countdown:    countdownTotal,
  });

  startCountdownTimer();
  showToast('info', 'Session Activated', `Voter window is active for ${activeStudent.name}.`);
}

/* ══════════════════════════════════════════
   BOOT
══════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', init);
