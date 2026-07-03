/**
 * E-Voting System — Voter Panel Logic
 * Handles multi-position voter session lifecycle:
 *   - Receives election data grouped by position from invigilator
 *   - Renders one candidate section per position with photos
 *   - Tracks one vote per position
 *   - Progress bar, ballot review modal, and vote submission
 */

/* ══════════════════════════════════════════
   INIT & GLOBALS
══════════════════════════════════════════ */

const channel = new BroadcastChannel(CHANNEL_NAME);

let currentSession    = null;   // { student, electionData }
let sessionVotes      = {};     // { [position]: { id, name, position } }
let countdownTimer    = null;
let countdownTotal    = 60;
let countdownRemaining = 60;

/* ══════════════════════════════════════════
   DOM REFERENCES
══════════════════════════════════════════ */

const $ = id => document.getElementById(id);

const idleScreen    = $('idleScreen');
const votingScreen  = $('votingScreen');
const successScreen = $('successScreen');

const voterAvatarLg          = $('voterAvatarLg');
const voterDisplayName       = $('voterDisplayName');
const voterMetaChips         = $('voterMetaChips');
const voterCountdownPill     = $('voterCountdownPill');
const voterCountdownDisplay  = $('voterCountdownDisplay');
const voterCountdownBar      = $('voterCountdownBar');

const progressFill        = $('progressFill');
const progressText        = $('progressText');
const progressPct         = $('progressPct');
const electionSectionsContainer = $('electionSectionsContainer');
const submitVoteBtn       = $('submitVoteBtn');
const voteSubmitStatus    = $('voteSubmitStatus');

const voteConfirmModal    = $('voteConfirmModal');
const voteConfirmText     = $('voteConfirmText');
const ballotSummary       = $('ballotSummary');
const voteConfirmCancelBtn = $('voteConfirmCancelBtn');
const voteConfirmOkBtn    = $('voteConfirmOkBtn');
const successMessage      = $('successMessage');

/* ══════════════════════════════════════════
   STARTUP
══════════════════════════════════════════ */

function init() {
  startClock();
  bindEvents();

  // Tell invigilator window we're ready
  channel.postMessage({ type: 'VOTER_WINDOW_READY' });

  // Check for already-active session (in case page was refreshed)
  const session = getActiveSession();
  if (session && session.expiresAt > Date.now()) {
    const remaining = Math.round((session.expiresAt - Date.now()) / 1000);
    activateVotingSession(session.student, session.electionData, remaining);
  } else {
    showIdle();
  }
}

/* ══════════════════════════════════════════
   CLOCK
══════════════════════════════════════════ */

function startClock() {
  function tick() {
    const now  = new Date();
    const time = now.toLocaleTimeString('en-IN', { hour12: true });
    const date = now.toLocaleDateString('en-IN', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
    $('voterTime').textContent = time;
    $('voterDate').textContent = date;
  }
  tick();
  setInterval(tick, 1000);
}

/* ══════════════════════════════════════════
   SCREEN MANAGEMENT
══════════════════════════════════════════ */

function showIdle() {
  idleScreen.style.display    = 'flex';
  votingScreen.style.display  = 'none';
  successScreen.style.display = 'none';

  sessionVotes   = {};
  currentSession = null;
  clearCountdown();
}

function showVoting() {
  idleScreen.style.display    = 'none';
  votingScreen.style.display  = 'block';
  successScreen.style.display = 'none';
}

function showSuccess(studentName) {
  idleScreen.style.display    = 'none';
  votingScreen.style.display  = 'none';
  successScreen.style.display = 'flex';

  successMessage.innerHTML = `
    <strong>${getPronoun(currentSession?.student?.gender)} ${studentName}</strong>,
    your ballot has been successfully recorded!<br />
    <span style="color:var(--text-muted);font-size:13px;margin-top:6px;display:block">
      Thank you for participating in the Student Council Elections.
    </span>
  `;

  // Return to idle after 5 seconds
  setTimeout(() => showIdle(), 5000);
}

/* ══════════════════════════════════════════
   AVATAR / HELPERS
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

/** Returns an avatar colour class based on candidate id (for initials fallback). */
function getInitialsClass(id) {
  const num = parseInt(String(id).replace(/\D/g, ''), 10) || 0;
  return `av-${num % 8}`;
}

/* ══════════════════════════════════════════
   ACTIVATE VOTING SESSION
══════════════════════════════════════════ */

function activateVotingSession(student, electionData, countdown) {
  currentSession      = { student, electionData };
  countdownTotal      = countdown;
  countdownRemaining  = countdown;
  sessionVotes        = {};

  // Populate voter identity card
  const color    = getAvatarColor(student.name);
  const initials = getInitials(student.name);
  voterAvatarLg.style.background = color;
  voterAvatarLg.textContent      = initials;
  voterDisplayName.textContent   = student.name;

  voterMetaChips.innerHTML = `
    <span class="meta-chip class">📚 Class ${student.classNo}</span>
    <span class="meta-chip div">🏷️ Division ${student.division}</span>
    <span class="meta-chip roll">🎫 Roll No. ${student.rollNo}</span>
  `;

  // Render election sections
  renderElectionSections(electionData);

  // Reset progress & submit
  updateProgress();
  submitVoteBtn.disabled = true;

  // Start countdown
  updateCountdownUI();
  startCountdown();

  showVoting();
}

/* ══════════════════════════════════════════
   RENDER ELECTION SECTIONS
══════════════════════════════════════════ */

function renderElectionSections(electionData) {
  electionSectionsContainer.innerHTML = '';

  electionData.forEach((section, sectionIdx) => {

    // ── Section Wrapper ──
    const sectionEl = document.createElement('div');
    sectionEl.className = 'election-section';
    sectionEl.dataset.position = section.position;

    // ── Position Header ──
    const header = document.createElement('div');
    header.className = 'position-header';
    header.innerHTML = `
      <span class="position-icon">${section.icon}</span>
      <div>
        <div class="position-title">${section.position}</div>
        <div class="position-subtitle">Choose one candidate</div>
      </div>
      <span class="position-badge" id="badge-${sectionIdx}">Not voted</span>
    `;
    sectionEl.appendChild(header);

    // ── Candidate Grid ──
    const grid = document.createElement('div');
    grid.className = 'candidates-grid';
    grid.id = `grid-${sectionIdx}`;

    section.candidates.forEach(cand => {
      const card = document.createElement('div');
      card.className = 'candidate-card';
      card.dataset.id = cand.id;
      card.dataset.position = section.position;
      card.dataset.sectionIdx = sectionIdx;
      card.setAttribute('tabindex', '0');
      card.setAttribute('role', 'radio');
      card.setAttribute('aria-checked', 'false');
      card.setAttribute('aria-label', `Vote for ${cand.name}, ${section.position}`);

      // Build avatar HTML — photo if available, initials fallback otherwise
      const avatarHTML = cand.photo
        ? `<img src="${cand.photo}" alt="${cand.name}" loading="lazy" />`
        : `<div class="candidate-initials ${getInitialsClass(cand.id)}">${getInitials(cand.name)}</div>`;

      card.innerHTML = `
        <div class="select-check" aria-hidden="true">✓</div>
        <div class="candidate-avatar">${avatarHTML}</div>
        <div class="candidate-details">
          <div class="candidate-card-name">${cand.name}</div>
          <div class="candidate-card-class">Class ${cand.classNo}–${cand.division}</div>
        </div>
      `;

      card.addEventListener('click', () =>
        selectCandidate(card, cand, section.position, sectionIdx)
      );
      card.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectCandidate(card, cand, section.position, sectionIdx);
        }
      });

      grid.appendChild(card);
    });

    sectionEl.appendChild(grid);

    // ── Divider (not after last) ──
    if (sectionIdx < electionData.length - 1) {
      const divider = document.createElement('div');
      divider.className = 'section-divider';
      sectionEl.appendChild(divider);
    }

    electionSectionsContainer.appendChild(sectionEl);
  });
}

/* ══════════════════════════════════════════
   CANDIDATE SELECTION
══════════════════════════════════════════ */

function selectCandidate(clickedCard, cand, position, sectionIdx) {
  // Deselect all cards in this section
  const grid = $(`grid-${sectionIdx}`);
  grid.querySelectorAll('.candidate-card').forEach(c => {
    c.classList.remove('selected');
    c.setAttribute('aria-checked', 'false');
  });

  // Select clicked card
  clickedCard.classList.add('selected');
  clickedCard.setAttribute('aria-checked', 'true');

  // Record vote for this position
  sessionVotes[position] = { id: cand.id, name: cand.name, position };

  // Update badge
  const badge = $(`badge-${sectionIdx}`);
  badge.textContent = `✓ ${cand.name}`;
  badge.classList.add('voted');

  updateProgress();
}

/* ══════════════════════════════════════════
   PROGRESS BAR
══════════════════════════════════════════ */

function updateProgress() {
  const total   = currentSession?.electionData?.length || 0;
  const done    = Object.keys(sessionVotes).length;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  progressFill.style.width   = `${percent}%`;
  progressText.textContent   = `${done} of ${total} positions voted`;
  progressPct.textContent    = `${percent}%`;

  const allDone = done >= total && total > 0;
  submitVoteBtn.disabled = !allDone;

  voteSubmitStatus.innerHTML = allDone
    ? `All <strong>${total}</strong> positions voted! Review and submit your ballot.`
    : `You have voted for <strong>${done}</strong> of <strong>${total}</strong> positions. Please vote for all positions to submit.`;
}

/* ══════════════════════════════════════════
   COUNTDOWN TIMER
══════════════════════════════════════════ */

function startCountdown() {
  clearCountdown();
  countdownTimer = setInterval(() => {
    countdownRemaining--;
    updateCountdownUI();

    if (countdownRemaining <= 0) {
      clearCountdown();
      showIdle();
    }
  }, 1000);
}

function clearCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

function updateCountdownUI() {
  const pct = (countdownRemaining / countdownTotal) * 100;
  voterCountdownDisplay.textContent = countdownRemaining;
  voterCountdownBar.style.width     = pct + '%';

  const isWarning = countdownRemaining <= 15;
  voterCountdownPill.classList.toggle('warning', isWarning);
}

/* ══════════════════════════════════════════
   BALLOT REVIEW MODAL
══════════════════════════════════════════ */

function openBallotModal() {
  if (!currentSession) return;

  const student = currentSession.student;
  voteConfirmText.innerHTML = `
    <strong>${getPronoun(student.gender)} ${student.name}</strong>, please review your selections before submitting.
  `;

  // Build summary list
  ballotSummary.innerHTML = '';
  currentSession.electionData.forEach(section => {
    const vote = sessionVotes[section.position];
    const item = document.createElement('div');
    item.className = 'ballot-summary-item';
    item.innerHTML = `
      <span class="ballot-summary-position">${section.icon} ${section.position}</span>
      <span class="ballot-summary-candidate">${vote ? vote.name : '—'}</span>
    `;
    ballotSummary.appendChild(item);
  });

  voteConfirmModal.classList.add('active');
}

function closeBallotModal() {
  voteConfirmModal.classList.remove('active');
}

/* ══════════════════════════════════════════
   SUBMIT VOTE
══════════════════════════════════════════ */

function submitVote() {
  if (!currentSession) return;

  const student = currentSession.student;
  closeBallotModal();
  clearCountdown();

  // Notify invigilator with all position votes
  channel.postMessage({
    type:           'VOTE_CAST',
    studentRollNo:  student.rollNo,
    votes:          sessionVotes,          // { [position]: { id, name } }
  });

  setActiveSession(null);
  showSuccess(student.name);
}

/* ══════════════════════════════════════════
   BROADCAST CHANNEL HANDLER
══════════════════════════════════════════ */

channel.onmessage = function(event) {
  const msg = event.data;

  switch (msg.type) {
    case 'ACTIVATE_VOTER':
      activateVotingSession(msg.student, msg.electionData, msg.countdown);
      break;

    case 'CANCEL_SESSION':
      closeBallotModal();
      showIdle();
      break;

    case 'SESSION_EXPIRED':
      closeBallotModal();
      showIdle();
      break;

    case 'COUNTDOWN_TICK':
      // Sync countdown from invigilator (fallback)
      if (Math.abs(countdownRemaining - msg.remaining) > 2) {
        countdownRemaining = msg.remaining;
        updateCountdownUI();
      }
      break;
  }
};

/* ══════════════════════════════════════════
   EVENT BINDINGS
══════════════════════════════════════════ */

function bindEvents() {

  // Submit vote button → open ballot review modal
  submitVoteBtn.addEventListener('click', () => {
    if (!submitVoteBtn.disabled) openBallotModal();
  });

  // Ballot modal — Go Back
  voteConfirmCancelBtn.addEventListener('click', closeBallotModal);

  // Ballot modal — Confirm & Submit
  voteConfirmOkBtn.addEventListener('click', submitVote);

  // Click backdrop to close modal
  voteConfirmModal.addEventListener('click', e => {
    if (e.target === voteConfirmModal) closeBallotModal();
  });
}

/* ══════════════════════════════════════════
   BOOT
══════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', init);
