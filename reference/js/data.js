/**
 * E-Voting System — Shared Data Store
 * Manages students, candidates (grouped by position), votes,
 * and cross-window state via BroadcastChannel + localStorage.
 */

const CHANNEL_NAME = 'evoting-channel';
const STORAGE_KEYS = {
  STUDENTS:       'evoting_students',
  ELECTION_DATA:  'evoting_election_data',   // grouped by position
  VOTES:          'evoting_votes',
  ACTIVE_SESSION: 'evoting_active_session',
};

// ──────────────────────────────────────────────
// Default Demo Data
// ──────────────────────────────────────────────

const DEFAULT_STUDENTS = [
  { rollNo: '001', admissionNo: 'ADM2024001', name: 'Aryan Sharma',   classNo: '10', division: 'A', gender: 'male',   hasVoted: false },
  { rollNo: '002', admissionNo: 'ADM2024002', name: 'Priya Nair',     classNo: '10', division: 'A', gender: 'female', hasVoted: false },
  { rollNo: '003', admissionNo: 'ADM2024003', name: 'Rahul Menon',    classNo: '10', division: 'A', gender: 'male',   hasVoted: false },
  { rollNo: '004', admissionNo: 'ADM2024004', name: 'Sneha Pillai',   classNo: '10', division: 'B', gender: 'female', hasVoted: false },
  { rollNo: '005', admissionNo: 'ADM2024005', name: 'Akash Verma',    classNo: '10', division: 'B', gender: 'male',   hasVoted: false },
  { rollNo: '006', admissionNo: 'ADM2024006', name: 'Divya Krishnan', classNo: '10', division: 'B', gender: 'female', hasVoted: false },
  { rollNo: '007', admissionNo: 'ADM2024007', name: 'Rohan Das',      classNo: '9',  division: 'A', gender: 'male',   hasVoted: false },
  { rollNo: '008', admissionNo: 'ADM2024008', name: 'Meera Patel',    classNo: '9',  division: 'A', gender: 'female', hasVoted: false },
  { rollNo: '009', admissionNo: 'ADM2024009', name: 'Kiran Reddy',    classNo: '9',  division: 'B', gender: 'male',   hasVoted: false },
  { rollNo: '010', admissionNo: 'ADM2024010', name: 'Anjali Singh',   classNo: '9',  division: 'B', gender: 'female', hasVoted: false },
];

/**
 * Election data grouped by position.
 * Each position has:
 *   position  — display name
 *   icon      — emoji shown in UI
 *   candidates — array of { id, name, classNo, division, symbol, photo, votes }
 *
 * photo: path relative to project root (in photos/ folder)
 *        Leave "" to display initials avatar fallback.
 */
const DEFAULT_ELECTION_DATA = [
  {
    position: 'School President',
    icon: '👑',
    candidates: [
      { id: 'C101', name: 'Aarav Mehta',    classNo: '10', division: 'A', symbol: '⭐', photo: 'photos/m1.png', votes: 0 },
      { id: 'C102', name: 'Priya Sharma',   classNo: '10', division: 'B', symbol: '🌟', photo: 'photos/f1.png', votes: 0 },
      { id: 'C103', name: 'Rahul Nair',     classNo: '10', division: 'C', symbol: '🔥', photo: 'photos/m2.png', votes: 0 },
    ]
  },
  {
    position: 'Vice President',
    icon: '🌟',
    candidates: [
      { id: 'C201', name: 'Sneha Patel',    classNo: '9',  division: 'A', symbol: '💎', photo: 'photos/f2.png', votes: 0 },
      { id: 'C202', name: 'Kiran Das',      classNo: '9',  division: 'B', symbol: '🚀', photo: 'photos/m3.png', votes: 0 },
      { id: 'C203', name: 'Aisha Khan',     classNo: '9',  division: 'C', symbol: '🎯', photo: 'photos/f3.png', votes: 0 },
    ]
  },
  {
    position: 'General Secretary',
    icon: '📋',
    candidates: [
      { id: 'C301', name: 'Dev Pillai',     classNo: '9',  division: 'A', symbol: '📚', photo: 'photos/m4.png', votes: 0 },
      { id: 'C302', name: 'Meera Joshi',    classNo: '9',  division: 'B', symbol: '✏️', photo: 'photos/f4.png', votes: 0 },
    ]
  },
  {
    position: 'Treasurer',
    icon: '💰',
    candidates: [
      { id: 'C401', name: 'Rohan Verma',    classNo: '8',  division: 'A', symbol: '💡', photo: 'photos/m1.png', votes: 0 },
      { id: 'C402', name: 'Fatima Zahra',   classNo: '8',  division: 'B', symbol: '🏅', photo: 'photos/f1.png', votes: 0 },
      { id: 'C403', name: 'Nikhil Gupta',   classNo: '8',  division: 'C', symbol: '🎖️', photo: 'photos/m2.png', votes: 0 },
    ]
  },
  {
    position: 'Sports Captain',
    icon: '🏆',
    candidates: [
      { id: 'C501', name: 'Ayesha Reddy',   classNo: '10', division: 'A', symbol: '⚽', photo: 'photos/f2.png', votes: 0 },
      { id: 'C502', name: 'Samir Bose',     classNo: '10', division: 'B', symbol: '🏀', photo: 'photos/m3.png', votes: 0 },
    ]
  },
  {
    position: 'Cultural Secretary',
    icon: '🎭',
    candidates: [
      { id: 'C601', name: 'Tanvi Iyer',     classNo: '9',  division: 'C', symbol: '🎨', photo: 'photos/f3.png', votes: 0 },
      { id: 'C602', name: 'Zara Ahmed',     classNo: '9',  division: 'A', symbol: '🎵', photo: 'photos/f4.png', votes: 0 },
      { id: 'C603', name: 'Ishaan Roy',     classNo: '9',  division: 'B', symbol: '🎬', photo: 'photos/m4.png', votes: 0 },
    ]
  },
];

/** The predefined positions available in the admin dropdown. */
const POSITIONS = DEFAULT_ELECTION_DATA.map(p => ({ position: p.position, icon: p.icon }));

// ──────────────────────────────────────────────
// Election Data Access
// ──────────────────────────────────────────────

function loadElectionData() {
  const data = localStorage.getItem(STORAGE_KEYS.ELECTION_DATA);
  return data ? JSON.parse(data) : JSON.parse(JSON.stringify(DEFAULT_ELECTION_DATA));
}

function saveElectionData(electionData) {
  localStorage.setItem(STORAGE_KEYS.ELECTION_DATA, JSON.stringify(electionData));
}

/**
 * Flattens election data into a single array of candidates (for admin results).
 * Each candidate gets a `positionLabel` and `positionIcon` field added.
 */
function flattenCandidates(electionData) {
  return electionData.flatMap(section =>
    section.candidates.map(c => ({
      ...c,
      position: section.position,
      positionIcon: section.icon,
    }))
  );
}

// ──────────────────────────────────────────────
// Student Access
// ──────────────────────────────────────────────

function loadStudents() {
  const data = localStorage.getItem(STORAGE_KEYS.STUDENTS);
  return data ? JSON.parse(data) : [...DEFAULT_STUDENTS];
}

function saveStudents(students) {
  localStorage.setItem(STORAGE_KEYS.STUDENTS, JSON.stringify(students));
}

// ──────────────────────────────────────────────
// Vote Access
// ──────────────────────────────────────────────

function loadVotes() {
  const data = localStorage.getItem(STORAGE_KEYS.VOTES);
  return data ? JSON.parse(data) : {};
}

function saveVotes(votes) {
  localStorage.setItem(STORAGE_KEYS.VOTES, JSON.stringify(votes));
}

// ──────────────────────────────────────────────
// Active Session
// ──────────────────────────────────────────────

function getActiveSession() {
  const data = localStorage.getItem(STORAGE_KEYS.ACTIVE_SESSION);
  return data ? JSON.parse(data) : null;
}

function setActiveSession(session) {
  if (session) {
    localStorage.setItem(STORAGE_KEYS.ACTIVE_SESSION, JSON.stringify(session));
  } else {
    localStorage.removeItem(STORAGE_KEYS.ACTIVE_SESSION);
  }
}

// ──────────────────────────────────────────────
// Storage Init
// ──────────────────────────────────────────────

function initStorage() {
  if (!localStorage.getItem(STORAGE_KEYS.STUDENTS)) {
    saveStudents(DEFAULT_STUDENTS);
  }
  if (!localStorage.getItem(STORAGE_KEYS.ELECTION_DATA)) {
    saveElectionData(DEFAULT_ELECTION_DATA);
  }
  if (!localStorage.getItem(STORAGE_KEYS.VOTES)) {
    saveVotes({});
  }
}
