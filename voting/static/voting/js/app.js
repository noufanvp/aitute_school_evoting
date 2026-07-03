const state = {
  election: null,
  ballotId: null,
  sessionToken: null,
  currentStudent: null,
  votes: {},
  currentSectionIndex: 0,
};

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : '';
}

function getSchoolSlug() {
  const meta = document.querySelector('meta[name="school-slug"]');
  return meta ? meta.content : '';
}

function getCurrentUsername() {
  const meta = document.querySelector('meta[name="current-username"]');
  return meta ? meta.content : '';
}

/**
 * Resolve an image path to a full URL.
 * Legacy static paths start with 'voting/' → /static/voting/...
 * Uploaded media paths start with 'candidates/' or 'elections/' → /media/...
 */
function resolveImageUrl(path) {
  if (!path) return '';
  if (path.startsWith('voting/')) return `/static/${path}`;
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/')) return path;
  return `/media/${path}`;
}

function jsonHeaders() {
  const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken(),
  };
  if (state.sessionToken) {
    headers['X-Ballot-Token'] = state.sessionToken;
  }
  return headers;
}

function setWaitingMode() {
  document.getElementById('waiting-screen').classList.remove('hidden');
  document.getElementById('voting-content').classList.add('hidden');
  document.getElementById('success-screen').classList.remove('active');
  const modalOverlay = document.getElementById('modal-overlay');
  if (modalOverlay) {
    modalOverlay.classList.remove('active');
  }
  document.getElementById('progress-fill').style.width = '0%';
  document.getElementById('progress-text').textContent = '0 of 0 positions voted';
  document.getElementById('progress-percent').textContent = '0%';
  updateCurrentVoterDisplay(null);
  clearKioskCountdown();
  stopSessionHealthCheck(); // stop mid-vote health checks before resuming wait polling
  startSessionPolling();
  _activatedSessionId = null;
}

function setActiveVotingMode() {
  document.getElementById('waiting-screen').classList.add('hidden');
  document.getElementById('voting-content').classList.remove('hidden');
  document.getElementById('success-screen').classList.remove('active');
}

function updateCurrentVoterDisplay(student) {
  const nameEl = document.getElementById('current-voter-name');
  const classEl = document.getElementById('current-voter-class');
  
  const bannerEl = document.getElementById('voter-details-banner');
  const bannerName = document.getElementById('voter-banner-name');
  const bannerClass = document.getElementById('voter-banner-class');
  const bannerDivision = document.getElementById('voter-banner-division');

  const modalVoterName = document.getElementById('modal-voter-name');
  const modalVoterClass = document.getElementById('modal-voter-class');
  const modalVoterDivision = document.getElementById('modal-voter-division');

  if (!nameEl || !classEl) return;

  if (!student) {
    const isTestKiosk = document.querySelector('meta[name="is-test-kiosk"]')?.getAttribute('content') === 'true';
    nameEl.textContent = isTestKiosk ? 'Test Kiosk Mode' : 'Waiting';
    classEl.textContent = '';
    
    if (bannerEl) bannerEl.style.display = 'none';
    return;
  }

  const classText = [student.student_class, student.division].filter(Boolean).join('-');
  nameEl.textContent = student.name || student.student_id || 'Assigned';
  classEl.textContent = classText ? `(${classText})` : '';

  // Update voter banner in main content
  if (bannerEl) bannerEl.style.display = 'flex';
  if (bannerName) bannerName.textContent = student.name || student.student_id || 'Assigned';
  if (bannerClass) bannerClass.textContent = student.student_class || 'N/A';
  if (bannerDivision) bannerDivision.textContent = student.division || 'N/A';

  // Update voter card in confirmation modal
  if (modalVoterName) modalVoterName.textContent = student.name || student.student_id || 'Assigned';
  if (modalVoterClass) modalVoterClass.textContent = student.student_class || 'N/A';
  if (modalVoterDivision) modalVoterDivision.textContent = student.division || 'N/A';
}

function blockBackNavigation() {
  history.pushState(null, document.title, location.href);
  window.addEventListener('popstate', () => {
    history.pushState(null, document.title, location.href);
  });
}

function countVotes() {
  return Object.keys(state.votes).length;
}

function cardColumns(count) {
  if (count <= 2) return 2;
  if (count === 3) return 3;
  if (count === 4) return 4;
  if (count === 5) return 5;
  if (count === 6) return 3;  // 3+3 (perfect)
  if (count === 7) return 4;  // 4+3
  return 4;
}

function getInitials(name) {
  return name.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

function getAvatarColor(id) {
  return `av-${id % 8}`;
}

function updateProgress() {
  const total = state.election.positions.length;
  const done = countVotes();
  const percent = total ? Math.round((done / total) * 100) : 0;

  document.getElementById('progress-fill').style.width = `${percent}%`;
  document.getElementById('progress-text').textContent = `${done} of ${total} positions voted`;
  document.getElementById('progress-percent').textContent = `${percent}%`;

  const statusEl = document.getElementById('submit-status');
  if (!statusEl) return;

  statusEl.innerHTML = done < total
    ? `<strong>${done}</strong> / <strong>${total}</strong> positions voted`
    : `All <strong>${total}</strong> positions voted`;
}

function handleConcurrentLogout(message) {
  // Prevent multiple overlays
  if (document.getElementById('concurrent-logout-overlay')) return;

  // Stop all polling/pinging
  stopSessionPolling();
  stopSessionHealthCheck();

  const overlay = document.createElement('div');
  overlay.id = 'concurrent-logout-overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(15, 23, 42, 0.95);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-family: system-ui, -apple-system, sans-serif;
  `;

  overlay.innerHTML = `
    <div style="background: #1e293b; border: 1px solid #334155; padding: 32px; border-radius: 16px; max-width: 420px; width: 90%; text-align: center; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);">
      <div style="width: 56px; height: 56px; background: rgba(239, 68, 68, 0.15); border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 20px;">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
      </div>
      <h3 style="font-size: 20px; font-weight: 700; margin-bottom: 10px; color: #fff;">Logged Out</h3>
      <p style="font-size: 14px; color: #94a3b8; margin-bottom: 24px; line-height: 1.5;">${message || 'This kiosk has been opened on another device.'}</p>
      <a href="/accounts/logout/" class="btn-confirm" style="display: inline-block; padding: 10px 24px; background: #ef4444; color: white; border-radius: 8px; font-weight: 600; text-decoration: none; transition: background 0.2s;">Go to Login</a>
    </div>
  `;

  document.body.appendChild(overlay);

  // Redirect automatically after 6 seconds
  setTimeout(() => {
    window.location.href = '/accounts/logout/';
  }, 6000);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && data.status === 'logged_out') {
    handleConcurrentLogout(data.detail);
    throw new Error(data.detail || 'Logged out.');
  }
  if (!response.ok) {
    throw new Error(data.detail || 'Request failed.');
  }
  return data;
}

function startSession() {
  const modal = document.getElementById('manual-override-modal');
  const input = document.getElementById('manual-override-password-input');
  const errorDiv = document.getElementById('manual-override-error');
  if (input) {
    input.value = '';
  }
  if (errorDiv) {
    errorDiv.textContent = '';
    errorDiv.classList.add('hidden');
  }
  if (modal) {
    modal.classList.add('active');
  }
  if (input) {
    input.focus();
  }
}

function closeManualOverrideModal() {
  const modal = document.getElementById('manual-override-modal');
  if (modal) {
    modal.classList.remove('active');
  }
  const startBtn = document.getElementById('btn-start-session');
  if (startBtn) {
    startBtn.disabled = false;
  }
}

async function submitManualOverride() {
  const input = document.getElementById('manual-override-password-input');
  const errorDiv = document.getElementById('manual-override-error');
  const manualOverridePassword = input ? input.value.trim() : '';

  if (!manualOverridePassword) {
    if (errorDiv) {
      errorDiv.textContent = 'Manual override password is required.';
      errorDiv.classList.remove('hidden');
    }
    if (input) {
      input.focus();
    }
    return;
  }

  const btnSubmit = document.getElementById('btn-submit-manual-override');
  const btnCancel = document.getElementById('btn-cancel-manual-override');
  const startBtn = document.getElementById('btn-start-session');

  if (btnSubmit) btnSubmit.disabled = true;
  if (btnCancel) btnCancel.disabled = true;
  if (errorDiv) {
    errorDiv.classList.add('hidden');
    errorDiv.textContent = '';
  }

  try {
    const payload = await api('/api/kiosk/start-session/', {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({ 
        school_slug: getSchoolSlug(),
        manual_override_password: manualOverridePassword
      }),
    });

    state.ballotId = payload.ballot_id;
    state.sessionToken = payload.session_token;
    state.election = payload.election;
    state.currentStudent = payload.student || { name: 'Manual Override Session', student_class: 'Manual', division: 'Override' };
    state.votes = {};
    state.currentSectionIndex = 0;
    updateCurrentVoterDisplay(state.currentStudent);

    if (!state.election || !state.election.positions || state.election.positions.length === 0) {
      alert("No active election positions configured. Please configure them in the Django Admin panel first.");
      closeManualOverrideModal();
      return;
    }

    preloadElectionImages(payload.election);
    
    // Start session monitoring
    _activatedSessionId = payload.session_id;
    startSessionHealthCheck(_activatedSessionId);

    const rightLogoContainer = document.getElementById('header-right-logo-container');
    if (rightLogoContainer) {
      if (payload.election.logo_url) {
        rightLogoContainer.innerHTML = `
          <div class="school-logo-wrap">
            <img src="${payload.election.logo_url}" alt="${payload.election.school_name} Logo" class="school-logo" onerror="this.closest('.school-logo-wrap').style.display='none';" />
          </div>
        `;
      } else {
        rightLogoContainer.innerHTML = '';
      }
    }
    document.getElementById('school-name').textContent = state.election.school_name;
    document.getElementById('election-title').textContent = state.election.title;
    document.title = `${state.election.title} | ${state.election.school_name}`;

    setActiveVotingMode();
    renderSection(state.currentSectionIndex);
    closeManualOverrideModal();
    startKioskCountdown((state.election && state.election.kiosk_timeout) || 90);
  } catch (error) {
    console.error('Failed to start session:', error);
    if (errorDiv) {
      errorDiv.textContent = error.message || 'Authorization failed. Please try again.';
      errorDiv.classList.remove('hidden');
    }
  } finally {
    if (btnSubmit) btnSubmit.disabled = false;
    if (btnCancel) btnCancel.disabled = false;
    if (startBtn) startBtn.disabled = false;
  }
}

async function saveSelection(positionId, candidateId) {
  await api('/api/kiosk/save-selection/', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({
      ballot_id: state.ballotId,
      position_id: positionId,
      candidate_id: candidateId,
    }),
  });
}

function renderSection(index) {
  const container = document.getElementById('voting-container');
  const section = state.election.positions[index];
  const total = state.election.positions.length;

  container.innerHTML = '';

  const posEl = document.createElement('div');
  posEl.className = 'position-section';

  const voted = state.votes[section.id];
  const badgeText = voted ? `✓ ${voted.name}` : 'Not voted';
  const badgeCls = voted ? 'position-badge voted' : 'position-badge';

  posEl.innerHTML = `
    <div class="position-header">
      <span class="position-icon">${section.icon || '🗳️'}</span>
      <div>
        <div class="position-title">${section.position}</div>
        <div class="position-subtitle">Step ${index + 1} of ${total} - Choose one candidate</div>
      </div>
      <span class="${badgeCls}" id="badge-single">${badgeText}</span>
    </div>
    <div class="candidates-grid" id="grid-single" style="--card-cols:${cardColumns(section.candidates.length)}"></div>
  `;

  const grid = posEl.querySelector('#grid-single');

  section.candidates.forEach((candidate) => {
    const card = document.createElement('div');
    card.className = 'candidate-card';

    // ── Build photo/avatar area (top, fills flex space) ──
    let mediaHTML = '';
    if (candidate.photo) {
      const photoSrc = resolveImageUrl(candidate.photo);
      mediaHTML = `
        <div class="candidate-media">
          <img src="${photoSrc}" alt="${candidate.name}" loading="eager" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
          <div class="initials-avatar ${getAvatarColor(candidate.id)}" style="display:none;">${getInitials(candidate.name)}</div>
        </div>
      `;
    } else {
      mediaHTML = `
        <div class="candidate-media">
          <div class="initials-avatar ${getAvatarColor(candidate.id)}">${getInitials(candidate.name)}</div>
        </div>
      `;
    }

    // ── Build symbol badge ──
    let symbolHTML = '';
    if (candidate.symbol) {
      const symbolSrc = resolveImageUrl(candidate.symbol);
      let symbolName = candidate.symbol_name || '';
      let symbolTextHTML = '';
      if (symbolName.trim()) {
        symbolTextHTML = `
          <div class="candidate-symbol-text">
            <span class="symbol-label">Symbol</span>
            <span class="symbol-name">${symbolName}</span>
          </div>
        `;
      }
      symbolHTML = `
        <div class="candidate-symbol-wrap" id="symbol-wrap-${candidate.id}">
          ${symbolTextHTML}
          <div class="candidate-symbol-badge">
            <img src="${symbolSrc}" alt="${candidate.name} symbol" loading="eager" onerror="document.getElementById('symbol-wrap-${candidate.id}').style.display='none';">
          </div>
        </div>
      `;
    }

    let classHTML = '';
    if (candidate['class'] && candidate['class'].trim() !== '') {
      classHTML = `<div class="candidate-class">${candidate['class']}</div>`;
    }

    let mottoHTML = '';
    if (candidate.motto && candidate.motto.trim() !== '') {
      mottoHTML = `<div class="candidate-motto">"${candidate.motto}"</div>`;
    }

    card.innerHTML = `
      <div class="check-badge">✓</div>
      ${mediaHTML}
      <div class="candidate-details">
        <div class="candidate-info">
          <div class="candidate-name">${candidate.name}</div>
          ${classHTML}
          ${mottoHTML}
        </div>
        ${symbolHTML}
      </div>
    `;

    if (voted && voted.id === candidate.id) {
      card.classList.add('selected');
    }

    card.addEventListener('click', async () => {
      try {
        await saveSelection(section.id, candidate.id);
        grid.querySelectorAll('.candidate-card').forEach((node) => node.classList.remove('selected'));
        card.classList.add('selected');
        state.votes[section.id] = { id: candidate.id, name: candidate.name };

        const badge = document.getElementById('badge-single');
        badge.textContent = `✓ ${candidate.name}`;
        badge.className = 'position-badge voted';

        const btnNext = document.getElementById('btn-next');
        const btnSubmit = document.getElementById('btn-submit');
        if (btnNext) btnNext.disabled = false;
        if (btnSubmit) btnSubmit.disabled = countVotes() < total;

        updateProgress();
      } catch (error) {
        alert(error.message);
      }
    });

    grid.appendChild(card);
  });

  // ── Center orphan cards in the last row ──────────────────
  // Move any partial-last-row cards into a full-width flex wrapper
  // so they are perfectly centred AND the same size as the cards above.
  const cols = cardColumns(section.candidates.length);
  const orphans = section.candidates.length % cols;
  if (orphans > 0) {
    const allCards = Array.from(grid.querySelectorAll('.candidate-card'));
    const orphanCards = allCards.slice(section.candidates.length - orphans);

    const orphanRow = document.createElement('div');
    orphanRow.style.cssText = [
      'grid-column: 1 / -1',
      'display: flex',
      'justify-content: center',
      'align-items: stretch',
      `gap: clamp(10px, 1.8vw, 28px)`,
    ].join(';');

    orphanCards.forEach((card) => {
      card.style.flex = `0 0 calc((100% - ${cols - 1} * clamp(10px, 1.8vw, 28px)) / ${cols})`;
      card.style.maxWidth = '340px';
      card.style.height = '100%';
      orphanRow.appendChild(card);
    });

    grid.appendChild(orphanRow);
  }


  const isLast = index === total - 1;
  const nav = document.createElement('div');
  nav.className = 'nav-controls';

  nav.innerHTML = `
    <button id="btn-back" class="btn-nav" ${index === 0 ? 'disabled' : ''}>◀ Back</button>
    <p class="submit-status" id="submit-status"></p>
    ${isLast
      ? `<button id="btn-submit" class="btn-submit" ${countVotes() === total ? '' : 'disabled'}>🗳️ Review &amp; Submit Ballot</button>`
      : `<button id="btn-next" class="btn-nav primary" ${voted ? '' : 'disabled'}>Next ▶</button>`
    }
  `;

  container.appendChild(posEl);
  container.appendChild(nav);

  document.getElementById('btn-back').addEventListener('click', () => {
    if (state.currentSectionIndex > 0) {
      state.currentSectionIndex -= 1;
      renderSection(state.currentSectionIndex);
    }
  });

  const btnNext = document.getElementById('btn-next');
  if (btnNext) {
    btnNext.addEventListener('click', () => {
      if (!state.votes[section.id]) return;
      state.currentSectionIndex += 1;
      renderSection(state.currentSectionIndex);
    });
  }

  const btnSubmit = document.getElementById('btn-submit');
  if (btnSubmit) {
    btnSubmit.addEventListener('click', openModal);
  }

  updateProgress();
}

function openModal() {
  const summaryEl = document.getElementById('modal-summary');
  summaryEl.innerHTML = '';

  state.election.positions.forEach((position) => {
    const vote = state.votes[position.id];
    const item = document.createElement('div');
    item.className = 'summary-item';
    item.innerHTML = `
      <span class="summary-position">${position.icon || '🗳️'} ${position.position}</span>
      <span class="summary-candidate">${vote ? vote.name : '-'}</span>
    `;
    summaryEl.appendChild(item);
  });

  document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

async function submitBallot() {
  try {
    const payload = await api('/api/kiosk/submit/', {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({ ballot_id: state.ballotId }),
    });

    stopSessionHealthCheck(); // vote complete — no longer need to monitor the session
    closeModal();
    clearKioskCountdown();
    document.getElementById('voting-content').classList.add('hidden');
    document.getElementById('success-screen').classList.add('active');
    document.getElementById('receipt-token').textContent = payload.receipt_token;
    
    // Trigger high-fidelity confetti VFX celebration
    launchConfetti();

    state.ballotId = null;
    state.sessionToken = null;
    state.votes = {};
    _activatedSessionId = null;

    setTimeout(() => {
      setWaitingMode();
    }, 5000);
  } catch (error) {
    alert(error.message);
  }
}

function launchConfetti() {
  const canvas = document.createElement('canvas');
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.width = '100vw';
  canvas.style.height = '100vh';
  canvas.style.pointerEvents = 'none';
  canvas.style.zIndex = '9999';
  document.body.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const colors = ['#4f46e5', '#818cf8', '#06b6d4', '#22c55e', '#ec4899', '#f59e0b', '#8b5cf6'];
  const confetti = [];

  function spawnConfetti(side) {
    const isLeft = side === 'left';
    const count = 80;
    for (let i = 0; i < count; i++) {
      confetti.push({
        x: isLeft ? 0 : width,
        y: height - 20,
        size: Math.random() * 8 + 6,
        color: colors[Math.floor(Math.random() * colors.length)],
        speedX: (isLeft ? 1 : -1) * (Math.random() * 12 + 4),
        speedY: -(Math.random() * 18 + 12),
        gravity: 0.35,
        drag: 0.97,
        rotation: Math.random() * 360,
        rotationSpeed: Math.random() * 10 - 5
      });
    }
  }

  spawnConfetti('left');
  spawnConfetti('right');

  const startTime = Date.now();

  function animate() {
    ctx.clearRect(0, 0, width, height);

    let hasActive = false;
    const elapsed = Date.now() - startTime;

    confetti.forEach((p) => {
      p.speedX *= p.drag;
      p.speedY += p.gravity;
      p.x += p.speedX;
      p.y += p.speedY;
      p.rotation += p.rotationSpeed;

      if (p.y < height + 50 && p.x > -50 && p.x < width + 50) {
        hasActive = true;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 1.5, p.size, p.size * 1.2);
        ctx.restore();
      }
    });

    if (hasActive && elapsed < 5000) {
      requestAnimationFrame(animate);
    } else {
      canvas.remove();
    }
  }

  animate();
}

function preloadElectionImages(election) {
  if (!election || !election.positions) return;
  const urls = [];
  election.positions.forEach(position => {
    if (position.candidates) {
      position.candidates.forEach(candidate => {
        if (candidate.photo) {
          const photoSrc = resolveImageUrl(candidate.photo);
          urls.push(photoSrc);
        }
        if (candidate.symbol) {
          const symbolSrc = resolveImageUrl(candidate.symbol);
          urls.push(symbolSrc);
        }
      });
    }
  });

  // Prefetch Aitute logo
  urls.push('/static/voting/photos/aitute_logo.webp');

  // De-duplicate URLs and preload
  const uniqueUrls = [...new Set(urls)];
  uniqueUrls.forEach(url => {
    const img = new Image();
    img.src = url;
  });
}

async function loadActiveElection() {
  try {
    const slug = getSchoolSlug();
    const url = slug
      ? `/api/kiosk/current-election/?school=${encodeURIComponent(slug)}`
      : '/api/kiosk/current-election/';
    const election = await api(url);
    state.election = election;
    preloadElectionImages(election);
    const rightLogoContainer = document.getElementById('header-right-logo-container');
    if (rightLogoContainer) {
      if (election.logo_url) {
        rightLogoContainer.innerHTML = `
          <div class="school-logo-wrap">
            <img src="${election.logo_url}" alt="${election.school_name} Logo" class="school-logo" onerror="this.closest('.school-logo-wrap').style.display='none';" />
          </div>
        `;
      } else {
        rightLogoContainer.innerHTML = '';
      }
    }
    document.getElementById('school-name').textContent = election.school_name;
    document.getElementById('election-title').textContent = election.title;
    document.title = `${election.title} | ${election.school_name}`;
  } catch (error) {
    console.error('Failed to load active election:', error);
  }
}

// ── Kiosk ID (unique per browser instance) ──────────────────────────────────
function getKioskId() {
  // Keep kiosk identifier compatible with server-side presence list,
  // which currently keys kiosks by authenticated username.
  const username = getCurrentUsername();
  if (username) return username;

  let id = localStorage.getItem('evoting_kiosk_id');
  if (!id) {
    id = 'kiosk-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    localStorage.setItem('evoting_kiosk_id', id);
  }
  return id;
}

// ── Kiosk presence ping (every 10s) ─────────────────────────────────────────
function startKioskPing() {
  const ping = async () => {
    try {
      const res = await fetch('/api/kiosk/ping/', {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({ school_slug: getSchoolSlug(), kiosk_id: getKioskId() }),
      });
      if (res.status === 401) {
        const data = await res.json().catch(() => ({}));
        if (data.status === 'logged_out') {
          handleConcurrentLogout(data.detail);
          return;
        }
      }
    } catch (e) {
      console.warn('Presence ping failed:', e);
    }
  };
  ping();
  setInterval(ping, 10000);
}

// ── Invigilator session polling (every 2s, only while in waiting screen) ─────
let _sessionPollInterval = null;
let _activatedSessionId = null;

// ── Kiosk session health check (every 2s, only while in voting mode) ─────────
// Polls the session status; if the invigilator cancels/times out, the kiosk
// immediately returns to the waiting screen without requiring a manual refresh.
let _sessionHealthInterval = null;

function startSessionHealthCheck(sessionId) {
  stopSessionHealthCheck();
  _sessionHealthInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/session/${sessionId}/status/`);
      if (res.status === 401) {
        const data = await res.json().catch(() => ({}));
        if (data.status === 'logged_out') {
          handleConcurrentLogout(data.detail);
          return;
        }
      }
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'cancelled' || data.status === 'expired') {
        stopSessionHealthCheck();
        // Clear voting state so no orphaned ballot data remains
        state.ballotId = null;
        state.sessionToken = null;
        state.votes = {};
        setWaitingMode();
      }
    } catch (e) {}
  }, 2000);
}

function stopSessionHealthCheck() {
  if (_sessionHealthInterval) {
    clearInterval(_sessionHealthInterval);
    _sessionHealthInterval = null;
  }
}

function startSessionPolling() {
  if (_sessionPollInterval) return;
  _sessionPollInterval = setInterval(checkForInvigilatorSession, 2000);
}

function stopSessionPolling() {
  if (_sessionPollInterval) { clearInterval(_sessionPollInterval); _sessionPollInterval = null; }
}

async function checkForInvigilatorSession() {
  // Don't poll if already voting
  const votingContent = document.getElementById('voting-content');
  if (votingContent && !votingContent.classList.contains('hidden')) return;

  try {
    const res = await fetch(`/api/kiosk/session-check/?kiosk_id=${encodeURIComponent(getKioskId())}&school_slug=${encodeURIComponent(getSchoolSlug())}`);
    if (res.status === 401) {
      const data = await res.json().catch(() => ({}));
      if (data.status === 'logged_out') {
        handleConcurrentLogout(data.detail);
        return;
      }
    }
    const data = await res.json();

    if (data.status === 'session_ready') {
      _activatedSessionId = data.session_id;
      await launchInvigilatorSession(data);
    }
  } catch (e) {
    console.warn('Session check failed:', e);
  }
}

async function launchInvigilatorSession(sessionData) {
  stopSessionPolling();
  try {
    // Start the actual ballot session without a student_id modal
    // (student was already validated by the invigilator panel)
    const payload = await api('/api/kiosk/start-session/', {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({
        school_slug: getSchoolSlug(),
        student_id: '__invigilator_activated__',  // sentinel bypassed server-side
        kiosk_session_id: sessionData.session_id,
      }),
    });

    state.ballotId = payload.ballot_id;
    state.sessionToken = payload.session_token;
    state.election = payload.election;
    state.currentStudent = sessionData.student || null;
    state.votes = {};
    state.currentSectionIndex = 0;
    updateCurrentVoterDisplay(state.currentStudent);

    if (!state.election || !state.election.positions || state.election.positions.length === 0) {
      console.error('No election positions found');
      startSessionPolling();
      return;
    }

    renderSection(0);
    setActiveVotingMode();

    // Monitor this session while the student votes — if the invigilator
    // cancels or the session expires, the kiosk returns to waiting screen.
    if (sessionData.session_id) {
      startSessionHealthCheck(sessionData.session_id);
    }

    // Show countdown if provided
    if (sessionData.countdown) {
      startKioskCountdown(sessionData.countdown);
    }
  } catch (err) {
    console.error('Failed to start invigilator session:', err);
    // Resume polling so invigilator can try again
    startSessionPolling();
  }
}

// ── Kiosk countdown timer ──────────────────────────────────────────────────
let _kioskCountdownInterval = null;

async function cancelSessionOnServer(reason) {
  if (!_activatedSessionId) return;
  try {
    await fetch('/api/kiosk/session-complete/', {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({
        session_id: _activatedSessionId,
        status: reason
      })
    });
  } catch (e) {
    console.warn('Failed to cancel session on server:', e);
  }
}

function startKioskCountdown(seconds) {
  const el = document.getElementById('kiosk-countdown');
  const txtEl = document.getElementById('kiosk-countdown-text');
  if (!el) return;
  el.style.display = 'inline-flex';

  let remaining = seconds;
  async function tick() {
    if (txtEl) {
      txtEl.textContent = `${remaining}s remaining`;
    } else {
      el.textContent = `⏱ ${remaining}s remaining`;
    }
    if (remaining <= 0) {
      clearInterval(_kioskCountdownInterval);
      el.style.display = 'none';
      await cancelSessionOnServer('expired');
      setWaitingMode();
    }
    remaining--;
  }
  tick();
  _kioskCountdownInterval = setInterval(tick, 1000);
}

function clearKioskCountdown() {
  if (_kioskCountdownInterval) { clearInterval(_kioskCountdownInterval); _kioskCountdownInterval = null; }
  const el = document.getElementById('kiosk-countdown');
  if (el) el.style.display = 'none';
}

// ── Update kiosk display on idle screen ─────────────────────────────────────
function updateKioskIdDisplay() {
  const el = document.getElementById('kiosk-id-display');
  if (el) {
    const id = getKioskId();
    el.textContent = `Kiosk ID: ${id.slice(0,12)}`;
  }
}

async function startTestSession() {
  const btn = document.getElementById('btn-start-test-session');
  if (btn) btn.disabled = true;

  try {
    const payload = await api('/api/kiosk/start-session/', {
      method: 'POST',
      headers: jsonHeaders(),
      body: JSON.stringify({ 
        school_slug: getSchoolSlug(),
        student_id: 'test_student_' + Math.floor(Math.random() * 1000000)
      }),
    });

    state.ballotId = payload.ballot_id;
    state.sessionToken = payload.session_token;
    state.election = payload.election;
    state.currentStudent = payload.student || { name: 'Test Vote Session', student_class: 'Test', division: 'Kiosk' };
    state.votes = {};
    state.currentSectionIndex = 0;
    updateCurrentVoterDisplay(state.currentStudent);

    if (!state.election || !state.election.positions || state.election.positions.length === 0) {
      alert("No active election positions configured. Please configure them in the Django Admin panel first.");
      setWaitingMode();
      return;
    }

    preloadElectionImages(payload.election);
    
    // Stop waiting-room session polling
    stopSessionPolling();

    const rightLogoContainer = document.getElementById('header-right-logo-container');
    if (rightLogoContainer) {
      if (payload.election.logo_url) {
        rightLogoContainer.innerHTML = `
          <div class="school-logo-wrap">
            <img src="${payload.election.logo_url}" alt="${payload.election.school_name} Logo" class="school-logo" onerror="this.closest('.school-logo-wrap').style.display='none';" />
          </div>
        `;
      } else {
        rightLogoContainer.innerHTML = '';
      }
    }

    renderSection(0);
    setActiveVotingMode();

  } catch (err) {
    alert(err.message || 'Failed to start test session.');
    setWaitingMode();
  } finally {
    if (btn) btn.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setWaitingMode();
  blockBackNavigation();
  loadActiveElection();
  startKioskPing();
  startSessionPolling();
  updateKioskIdDisplay();

  // Start button action conditional on test kiosk mode
  const btnStart = document.getElementById('btn-start-session');
  if (btnStart) {
    btnStart.addEventListener('click', () => {
      const isTestKiosk = document.querySelector('meta[name="is-test-kiosk"]')?.getAttribute('content') === 'true';
      if (isTestKiosk) {
        startTestSession();
      } else {
        startSession();
      }
    });
  }

  const btnTest = document.getElementById('btn-start-test-session');
  if (btnTest) btnTest.addEventListener('click', startTestSession);

  const btnManual = document.getElementById('btn-manual-override');
  if (btnManual) btnManual.addEventListener('click', startSession);

  document.getElementById('btn-close-modal').addEventListener('click', closeModal);
  document.getElementById('btn-confirm-submit').addEventListener('click', submitBallot);

  // Voter registration modal controls (manual fallback)
  const btnCancelManualOverride = document.getElementById('btn-cancel-manual-override');
  if (btnCancelManualOverride) btnCancelManualOverride.addEventListener('click', closeManualOverrideModal);

  const btnSubmitManualOverride = document.getElementById('btn-submit-manual-override');
  if (btnSubmitManualOverride) btnSubmitManualOverride.addEventListener('click', submitManualOverride);

  const manualOverrideInput = document.getElementById('manual-override-password-input');
  if (manualOverrideInput) {
    manualOverrideInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); submitManualOverride(); }
    });
  }
  // Handle takeover button action
  const takeoverBtn = document.getElementById('btn-confirm-takeover');
  if (takeoverBtn) {
    takeoverBtn.addEventListener('click', async () => {
      takeoverBtn.disabled = true;
      takeoverBtn.textContent = 'Taking over...';
      try {
        const res = await fetch('/api/kiosk/takeover/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
          }
        });
        if (res.ok) {
          // Hide takeover modal and reload to resume normally
          document.getElementById('takeover-modal-overlay').classList.remove('active');
          window.location.reload();
        } else {
          takeoverBtn.disabled = false;
          takeoverBtn.textContent = 'Yes, Sign Out Other Device';
          alert('Failed to take over kiosk. Please try again.');
        }
      } catch (e) {
        takeoverBtn.disabled = false;
        takeoverBtn.textContent = 'Yes, Sign Out Other Device';
        alert('Network error. Please try again.');
      }
    });
  }
});

