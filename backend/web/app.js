/**
 * Team Raynex: FSOC PAT Mission Control & Security Dashboard
 * Operator-centric Web Controller & 60FPS Multi-Terminal Visualizer
 */

// Global Application State
let currentView = 'arena'; // 'arena', 'sensor', 'camera'
let latestData = null;
let eventSource = null;
let isPlaying = true;
let cameraRefreshInterval = null;
let testPollInterval = null;

// Disturbance Local States
let disturbanceStates = {
  cloud: false,
  turbulence: false,
  vibration: false,
  severe: false
};

// Trajectory history for the target terminal
const terminalBHistory = [];
// Trajectory history for non-target terminals { [terminalId]: [ {x, y}, ... ] }
let nonTargetHistories = {};

// =============================================================================
// DOM References
// =============================================================================
const arenaCanvas = document.getElementById('arenaCanvas');
const sensorCanvas = document.getElementById('sensorCanvas');
const arenaCtx = arenaCanvas ? arenaCanvas.getContext('2d') : null;
const sensorCtx = sensorCanvas ? sensorCanvas.getContext('2d') : null;

// Arena Viewport Zoom Controls
const btnZoomOut = document.getElementById('btnZoomOut');
const btnZoomIn = document.getElementById('btnZoomIn');
const btnZoomReset = document.getElementById('btnZoomReset');
const zoomLevelDisplay = document.getElementById('zoomLevelDisplay');
let currentZoom = 1.0;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.0;

// Top Bar Elements
const topTargetTerminal = document.getElementById('topTargetTerminal');
const topIdentBadge = document.getElementById('topIdentBadge');
const topAuthBadge = document.getElementById('topAuthBadge');
const topOpticalLinkBadge = document.getElementById('topOpticalLinkBadge');
const topFsocStatusBadge = document.getElementById('topFsocStatusBadge');
const connectionStatus = document.getElementById('connectionStatus');

// Configuration Elements
const inputNumTerminals = document.getElementById('inputNumTerminals');
const selectTargetTerminal = document.getElementById('selectTargetTerminal');
const configStatusBadge = document.getElementById('configStatusBadge');
const terminalsTableBody = document.getElementById('terminalsTableBody');
const tableTargetHighlight = document.getElementById('tableTargetHighlight');
const rfDiscCountText = document.getElementById('rfDiscCountText');
const rfDiscStatusBadge = document.getElementById('rfDiscStatusBadge');

// Lifecycle Pipeline Elements
const currentStageText = document.getElementById('currentStageText');
const currentRecoveryTag = document.getElementById('currentRecoveryTag');
const primaryPipeline = document.getElementById('primaryPipeline');
const recoveryPipeline = document.getElementById('recoveryPipeline');

// Communication Status Elements
const commTargetTerminal = document.getElementById('commTargetTerminal');
const commRfStatus = document.getElementById('commRfStatus');
const commIdentStatus = document.getElementById('commIdentStatus');
const commAuthStatus = document.getElementById('commAuthStatus');
const commOpticalScanStatus = document.getElementById('commOpticalScanStatus');
const commOpticalLinkStatus = document.getElementById('commOpticalLinkStatus');
const commFsocBadge = document.getElementById('commFsocBadge');
const commFsocCard = document.getElementById('commFsocCard');
const commRecoveryMechanism = document.getElementById('commRecoveryMechanism');
const commStatusOverallBadge = document.getElementById('commStatusOverallBadge');

// Security Elements
const secTargetName = document.getElementById('secTargetName');
const secStatusHeaderBadge = document.getElementById('secStatusHeaderBadge');
const identResultText = document.getElementById('identResultText');
const authResultText = document.getElementById('authResultText');
const cryptoNonceText = document.getElementById('cryptoNonceText');
const cryptoHmacText = document.getElementById('cryptoHmacText');

// Overlay Elements
const overlayTargetName = document.getElementById('overlayTargetName');
const overlayOpticalStatus = document.getElementById('overlayOpticalStatus');
const overlayFsocState = document.getElementById('overlayFsocState');
const camDetectedText = document.getElementById('camDetectedText');

// Disturbance Buttons
const btnCloudOff = document.getElementById('btnCloudOff');
const btnCloudOn = document.getElementById('btnCloudOn');
const btnTurbOff = document.getElementById('btnTurbOff');
const btnTurbOn = document.getElementById('btnTurbOn');
const btnVibOff = document.getElementById('btnVibOff');
const btnVibOn = document.getElementById('btnVibOn');
const btnSevOff = document.getElementById('btnSevOff');
const btnSevOn = document.getElementById('btnSevOn');

// Advanced Telemetry Elements
const telemRadialError = document.getElementById('telemRadialError');
const telemAngularError = document.getElementById('telemAngularError');
const telemCameraAngle = document.getElementById('telemCameraAngle');
const telemConfidence = document.getElementById('telemConfidence');
const telemMissCount = document.getElementById('telemMissCount');
const telemCovTrace = document.getElementById('telemCovTrace');
const telemFlightKinematics = document.getElementById('telemFlightKinematics');
const telemRssi = document.getElementById('telemRssi');
const telemCentroidCoords = document.getElementById('telemCentroidCoords');

// Controls & Event Log
const simClockText = document.getElementById('simClockText');
const eventLogBox = document.getElementById('eventLogBox');
const playPauseIcon = document.getElementById('playPauseIcon');
const playPauseText = document.getElementById('playPauseText');

// Test Suite Elements
const btnRunTests = document.getElementById('btnRunTests');
const runTestsIcon = document.getElementById('runTestsIcon');
const runTestsText = document.getElementById('runTestsText');
const testProgressFill = document.getElementById('testProgressFill');
const testProgressLabel = document.getElementById('testProgressLabel');
const testTotalScore = document.getElementById('testTotalScore');

// =============================================================================
// App Startup & Event Handlers
// =============================================================================
window.addEventListener('DOMContentLoaded', () => {
  initZoomControls();
  fetchTerminalsConfig();
  fetchTestStatus();
  initSSE();
  startRenderLoop();
});

// =============================================================================
// Full-Workspace Viewport Zoom Controller (50% - 200%)
// =============================================================================
function setWorkspaceZoom(val) {
  currentZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(val * 100) / 100));

  // Update all zoom level displays across top bar and visualizer header
  document.querySelectorAll('.zoom-level-display').forEach(el => {
    el.textContent = `${Math.round(currentZoom * 100)}%`;
  });

  const scalable = document.getElementById('workspaceScalable');
  const viewport = document.getElementById('workspaceViewport');
  if (!scalable) return;

  // Primary: Native CSS zoom for smooth document flow and natural scrollbars
  // Fallback: CSS transform scale
  if ('zoom' in document.documentElement.style) {
    scalable.style.zoom = currentZoom;
    scalable.style.transform = '';
  } else {
    scalable.style.transform = `scale(${currentZoom})`;
    scalable.style.transformOrigin = 'top center';
    if (viewport) {
      if (currentZoom > 1.0) {
        viewport.style.minHeight = `${scalable.offsetHeight * currentZoom}px`;
      } else {
        viewport.style.minHeight = '';
      }
    }
  }
}

window.stepZoom = function(delta) {
  setWorkspaceZoom(currentZoom + delta);
};

window.resetZoom = function() {
  setWorkspaceZoom(1.0);
};

function initZoomControls() {
  // Bind top bar controls
  const btnInTop = document.getElementById('btnZoomInTop');
  const btnOutTop = document.getElementById('btnZoomOutTop');
  const btnResetTop = document.getElementById('btnZoomResetTop');

  if (btnInTop) btnInTop.addEventListener('click', (e) => { e.preventDefault(); setWorkspaceZoom(currentZoom + 0.15); });
  if (btnOutTop) btnOutTop.addEventListener('click', (e) => { e.preventDefault(); setWorkspaceZoom(currentZoom - 0.15); });
  if (btnResetTop) btnResetTop.addEventListener('click', (e) => { e.preventDefault(); setWorkspaceZoom(1.0); });

  // Bind arena visualizer controls
  if (btnZoomIn) btnZoomIn.addEventListener('click', (e) => { e.preventDefault(); setWorkspaceZoom(currentZoom + 0.15); });
  if (btnZoomOut) btnZoomOut.addEventListener('click', (e) => { e.preventDefault(); setWorkspaceZoom(currentZoom - 0.15); });
  if (btnZoomReset) btnZoomReset.addEventListener('click', (e) => { e.preventDefault(); setWorkspaceZoom(1.0); });

  // Mouse-wheel zoom on canvas
  const canvasBox = document.getElementById('canvasContainer') || arenaCanvas;
  if (canvasBox) {
    canvasBox.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.08 : -0.08;
      setWorkspaceZoom(currentZoom + delta);
    }, { passive: false });
  }

  // Ctrl/Cmd + Wheel on entire workspace
  const workspaceViewport = document.getElementById('workspaceViewport');
  if (workspaceViewport) {
    workspaceViewport.addEventListener('wheel', (e) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY < 0 ? 0.08 : -0.08;
        setWorkspaceZoom(currentZoom + delta);
      }
    }, { passive: false });
  }

  // Initialize at 100%
  setWorkspaceZoom(1.0);
}

// =============================================================================
// Collapsible Accordion Controller
// =============================================================================
const accordionIds = {
  terminalDetails: { card: 'accordionTerminalDetails', body: 'bodyTerminalDetails', chevron: 'chevronTerminalDetails' },
  opticalTracking: { card: 'accordionOpticalTracking', body: 'bodyOpticalTracking', chevron: 'chevronOpticalTracking' },
  recovery: { card: 'accordionRecovery', body: 'bodyRecovery', chevron: 'chevronRecovery' },
  security: { card: 'accordionSecurity', body: 'bodySecurity', chevron: 'chevronSecurity' },
  tests: { card: 'accordionTests', body: 'bodyTests', chevron: 'chevronTests' },
  systemDetails: { card: 'accordionSystemDetails', body: 'bodySystemDetails', chevron: 'chevronSystemDetails' },
  eventLog: { card: 'accordionEventLog', body: 'bodyEventLog', chevron: 'chevronEventLog' }
};

window.toggleAccordion = function(key) {
  const cfg = accordionIds[key];
  if (!cfg) return;
  const card = document.getElementById(cfg.card);
  const body = document.getElementById(cfg.body);
  const chevron = document.getElementById(cfg.chevron);
  if (!body) return;

  const isClosed = body.style.display === 'none' || body.style.display === '';
  if (isClosed) {
    body.style.display = 'block';
    if (card) card.classList.add('is-open');
    if (chevron) chevron.textContent = '▲';
  } else {
    body.style.display = 'none';
    if (card) card.classList.remove('is-open');
    if (chevron) chevron.textContent = '▼';
  }
};

// =============================================================================
// 1. Terminal Configuration Management
// =============================================================================
async function fetchTerminalsConfig() {
  try {
    const res = await fetch('/api/terminals');
    if (!res.ok) return;
    const data = await res.json();
    renderTerminalsConfig(data);
  } catch (err) {
    console.warn('Failed to fetch terminals config:', err);
  }
}

let lastTableSignature = '';

function renderTerminalsConfig(data) {
  const num = data.num_terminals || 5;
  const targetId = data.target_terminal || 'TERMINAL_03';
  const pool = data.available_pool || [];
  const overview = data.overview || [];

  if (inputNumTerminals) {
    inputNumTerminals.value = num;
  }

  // Populate Target Terminal dropdown dynamically up to the terminal count
  if (selectTargetTerminal) {
    const prevVal = selectTargetTerminal.value || targetId;
    selectTargetTerminal.innerHTML = '';
    
    // Always include terminals up to num (plus target if outside range)
    const activeCount = Math.max(num, 2);
    const optionsList = [];
    for (let i = 1; i <= activeCount; i++) {
      const tid = `TERMINAL_${String(i).padStart(2, '0')}`;
      const name = `Terminal-${String(i).padStart(2, '0')}`;
      optionsList.push({ id: tid, name: name });
    }
    if (!optionsList.some(t => t.id === targetId)) {
      const targetObj = pool.find(t => t.id === targetId);
      optionsList.push({ id: targetId, name: targetObj ? targetObj.name : targetId });
    }

    optionsList.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = t.name;
      if (t.id === targetId || t.id === prevVal) opt.selected = true;
      selectTargetTerminal.appendChild(opt);
    });

    if (!selectTargetTerminal.value && selectTargetTerminal.options.length > 0) {
      selectTargetTerminal.value = targetId;
    }
  }

  // Update Status Badge
  const targetObj = pool.find(t => t.id === targetId);
  const targetName = targetObj ? targetObj.name : (targetId ? targetId.replace('_', '-').title() : 'Terminal-03');
  if (configStatusBadge) {
    configStatusBadge.textContent = `${overview.length || num} Terminals in Sector • Target: ${targetName}`;
  }
  if (tableTargetHighlight) {
    tableTargetHighlight.textContent = targetName;
  }

  // Populate Remote Terminals Overview Table
  renderTerminalsTable(overview, targetId);
}

function renderTerminalsTable(overview, targetId) {
  if (!terminalsTableBody || !overview || !overview.length) return;

  const currentTarget = targetId || (latestData ? latestData.target_terminal : 'TERMINAL_03');
  const sig = overview.map(t => `${t.id}:${t.status}:${t.rf_status}:${t.role}`).join('|') + '|' + currentTarget;
  if (sig === lastTableSignature) return;
  lastTableSignature = sig;

  terminalsTableBody.innerHTML = '';

  overview.forEach(t => {
    const isTarget = (t.id === currentTarget || t.role === 'Target' || t.is_target);
    const tr = document.createElement('tr');
    if (isTarget) {
      tr.className = 'row-target';
    }

    const isDiscovered = (t.rf_status === 'DISCOVERED');
    const rfClass = isDiscovered ? 'pill-detected' : 'pill-transmitting';
    const rfLabel = isDiscovered ? '✓ DISCOVERED' : '⟳ TRANSMITTING';

    const roleLabel = isTarget ? 'Target' : 'Other';
    const roleClass = isTarget ? 'role-target' : 'role-other';

    tr.innerHTML = `
      <td>${isTarget ? `<strong>◎ ${t.name}</strong>` : `● ${t.name}`}</td>
      <td>
        <span class="status-pill ${rfClass}">
          ${rfLabel}
        </span>
      </td>
      <td>
        <span class="motion-pill">
          ● Moving
        </span>
      </td>
      <td>
        <span class="role-pill ${roleClass}">
          ${roleLabel}
        </span>
      </td>
    `;
    terminalsTableBody.appendChild(tr);
  });
}

function updateTargetDropdownOptions(num) {
  if (!selectTargetTerminal) return;
  const currentSel = selectTargetTerminal.value;
  selectTargetTerminal.innerHTML = '';
  for (let i = 1; i <= num; i++) {
    const tid = `TERMINAL_${String(i).padStart(2, '0')}`;
    const name = `Terminal-${String(i).padStart(2, '0')}`;
    const opt = document.createElement('option');
    opt.value = tid;
    opt.textContent = name;
    if (tid === currentSel) opt.selected = true;
    selectTargetTerminal.appendChild(opt);
  }
  if (!selectTargetTerminal.value && selectTargetTerminal.options.length > 0) {
    selectTargetTerminal.selectedIndex = 0;
  }
  if (tableTargetHighlight && selectTargetTerminal.selectedOptions.length > 0) {
    tableTargetHighlight.textContent = selectTargetTerminal.selectedOptions[0].textContent;
  }
}

function stepTerminalCount(delta) {
  if (!inputNumTerminals) return;
  let val = parseInt(inputNumTerminals.value, 10) || 5;
  val = Math.max(2, Math.min(12, val + delta));
  inputNumTerminals.value = val;
  updateTargetDropdownOptions(val);
}

function onTargetTerminalSelect(val) {
  if (tableTargetHighlight && selectTargetTerminal && selectTargetTerminal.selectedOptions.length > 0) {
    tableTargetHighlight.textContent = selectTargetTerminal.selectedOptions[0].textContent;
  }
}

async function applyTerminalConfiguration() {
  const num = parseInt(inputNumTerminals ? inputNumTerminals.value : '5', 10) || 5;
  const targetId = selectTargetTerminal ? selectTargetTerminal.value : 'TERMINAL_03';

  try {
    const res = await fetch('/api/terminals/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        num_terminals: num,
        target_terminal: targetId
      })
    });
    if (res.ok) {
      terminalBHistory.length = 0;
      nonTargetHistories = {};
      const data = await res.json();
      renderTerminalsConfig(data);
    }
  } catch (err) {
    console.error('Error updating terminal configuration:', err);
  }
}

// =============================================================================
// 2. Server-Sent Events (SSE) Real-Time Telemetry Feed
// =============================================================================
function initSSE() {
  if (eventSource) {
    eventSource.close();
  }

  eventSource = new EventSource('/api/stream');

  eventSource.onopen = () => {
    if (connectionStatus) {
      connectionStatus.className = 'connection-indicator connected';
      connectionStatus.querySelector('.conn-text').textContent = 'LIVE (30Hz)';
    }
  };

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      latestData = data;
      updateUI(data);
    } catch (err) {
      console.error('Error parsing SSE data frame:', err);
    }
  };

  eventSource.onerror = () => {
    if (connectionStatus) {
      connectionStatus.className = 'connection-indicator disconnected';
      connectionStatus.querySelector('.conn-text').textContent = 'RECONNECTING';
    }
  };
}

// =============================================================================
// 3. Telemetry UI Real-Time Updates
// =============================================================================
function updateUI(data) {
  const telem = data.telemetry || {};
  const arena = data.arena || {};
  const sec = data.security || {};
  const state = telem.current_state || 'IDLE';

  const targetName = telem.target_terminal_name || (telem.target_terminal ? telem.target_terminal.replace('_', '-').title() : 'Terminal-03');
  const isTargetIdentified = telem.identification_status === 'IDENTIFIED' || state === 'FSOC_ACTIVE' || state === 'OPTICAL_TRACKING';
  const isTargetAuth = (sec.valid && (sec.stage === 'AUTHENTICATED' || telem.authentication_status === 'AUTHENTICATED'));
  const isOpticalAligned = (state === 'FSOC_ACTIVE' || state === 'FINE_ALIGNMENT') && telem.beacon_detected;
  const isFsocActive = (telem.fsoc_status === 'ESTABLISHED' || telem.fsoc_status === 'ACTIVE' || state === 'FSOC_ACTIVE');

  // --- Real-time Remote Terminals Table Update ---
  if (data.terminals && data.terminals.length) {
    renderTerminalsTable(data.terminals, data.target_terminal);
  }

  // --- Header Top Bar Metrics ---
  if (topTargetTerminal) topTargetTerminal.textContent = targetName;
  if (topIdentBadge) {
    topIdentBadge.textContent = isTargetIdentified ? '✓ IDENTIFIED' : 'SEARCHING...';
    topIdentBadge.className = 'badge ' + (isTargetIdentified ? 'text-emerald' : 'text-amber');
  }
  if (topAuthBadge) {
    if (state === 'RECOVERY_FAILED') {
      topAuthBadge.textContent = '✗ REJECTED';
      topAuthBadge.className = 'badge text-crimson';
    } else {
      topAuthBadge.textContent = isTargetAuth ? '✓ HMAC-SHA256' : 'VERIFYING';
      topAuthBadge.className = 'badge ' + (isTargetAuth ? 'text-emerald' : 'text-amber');
    }
  }
  if (topOpticalLinkBadge) {
    topOpticalLinkBadge.textContent = isOpticalAligned ? '✓ ALIGNED' : (telem.beacon_detected ? 'TRACKING' : 'LOST');
    topOpticalLinkBadge.className = 'badge link-badge ' + (isOpticalAligned ? 'link-active' : (telem.beacon_detected ? 'link-searching' : 'link-down'));
  }
  if (topFsocStatusBadge) {
    if (isFsocActive) {
      topFsocStatusBadge.textContent = '● ACTIVE';
      topFsocStatusBadge.className = 'badge state-badge';
    } else if (state === 'RECOVERY_FAILED') {
      topFsocStatusBadge.textContent = '✗ FAILED';
      topFsocStatusBadge.className = 'badge link-badge link-down';
    } else {
      topFsocStatusBadge.textContent = 'REACQUIRING...';
      topFsocStatusBadge.className = 'badge link-badge link-searching';
    }
  }

  // --- Communication Status Panel & RF Discovery Indicators ---
  const totalCount = telem.rf_total_count || (data.terminals ? data.terminals.length : 5);
  const discCount = telem.rf_discovered_count !== undefined ? telem.rf_discovered_count : (data.terminals ? data.terminals.filter(x => x.rf_status === 'DISCOVERED').length : totalCount);

  if (rfDiscCountText) {
    rfDiscCountText.textContent = `${discCount} / ${totalCount} DISCOVERED`;
  }
  if (rfDiscStatusBadge) {
    if (state === 'RF_DISCOVERY' && discCount < totalCount) {
      rfDiscStatusBadge.textContent = '⟳ DISCOVERING...';
      rfDiscStatusBadge.className = 'status-pill pill-transmitting';
    } else {
      rfDiscStatusBadge.textContent = '✓ COMPLETE';
      rfDiscStatusBadge.className = 'status-pill pill-detected';
    }
  }

  if (commTargetTerminal) commTargetTerminal.textContent = targetName;
  if (commRfStatus) {
    if (state === 'RF_DISCOVERY' && discCount < totalCount) {
      commRfStatus.textContent = `⟳ ${discCount} / ${totalCount} DISCOVERING`;
      commRfStatus.className = 'item-badge text-amber';
    } else {
      commRfStatus.textContent = `✓ ${totalCount} / ${totalCount} DISCOVERED`;
      commRfStatus.className = 'item-badge text-emerald';
    }
  }
  if (commIdentStatus) {
    commIdentStatus.textContent = isTargetIdentified ? '✓ IDENTIFIED' : 'SCANNING';
    commIdentStatus.className = 'item-badge ' + (isTargetIdentified ? 'text-emerald' : 'text-amber');
  }
  if (commAuthStatus) {
    if (state === 'RECOVERY_FAILED') {
      commAuthStatus.textContent = '✗ CRYPTOGRAPHIC REJECTION';
      commAuthStatus.className = 'item-badge text-crimson';
    } else {
      commAuthStatus.textContent = isTargetAuth ? '✓ HMAC-SHA256 AUTHENTICATED' : 'VERIFYING SIGNATURE';
      commAuthStatus.className = 'item-badge ' + (isTargetAuth ? 'text-emerald' : 'text-amber');
    }
  }
  if (commOpticalScanStatus) {
    if (state === 'OPTICAL_SEARCH') {
      commOpticalScanStatus.textContent = '⟳ 360° AREA SCANNING...';
      commOpticalScanStatus.className = 'item-badge text-amber';
    } else if (state === 'RF_DISCOVERY' || state === 'RF_AUTHENTICATION' || state === 'IDLE') {
      commOpticalScanStatus.textContent = 'STANDBY';
      commOpticalScanStatus.className = 'item-badge text-muted';
    } else {
      commOpticalScanStatus.textContent = '✓ TARGET ACQUIRED';
      commOpticalScanStatus.className = 'item-badge text-emerald';
    }
  }
  if (commOpticalLinkStatus) {
    commOpticalLinkStatus.textContent = isOpticalAligned ? '✓ ALIGNED' : (telem.beacon_detected ? 'REACQUIRING...' : '⚠ LOST');
    commOpticalLinkStatus.className = 'item-badge ' + (isOpticalAligned ? 'text-emerald' : 'text-amber');
  }
  if (commFsocBadge) {
    if (isFsocActive) {
      commFsocBadge.textContent = '● ACTIVE';
      commFsocBadge.className = 'fsoc-badge-pill text-emerald';
      commFsocCard.className = 'status-item-card card-fsoc-active';
    } else if (state === 'RECOVERY_FAILED') {
      commFsocBadge.textContent = '● HALTED';
      commFsocBadge.className = 'fsoc-badge-pill text-crimson';
      commFsocCard.className = 'status-item-card';
    } else {
      commFsocBadge.textContent = '● REACQUIRING';
      commFsocBadge.className = 'fsoc-badge-pill text-amber';
      commFsocCard.className = 'status-item-card';
    }
  }
  if (commRecoveryMechanism) {
    const recMech = telem.recovery_mechanism || 'NONE';
    commRecoveryMechanism.textContent = (recMech === 'NONE' && isFsocActive) ? 'NONE (NOMINAL)' : recMech.replace('_', ' ');
  }
  if (commStatusOverallBadge) {
    commStatusOverallBadge.textContent = isFsocActive ? 'NOMINAL' : (state === 'RECOVERY_FAILED' ? 'ALERT' : 'RECOVERING');
    commStatusOverallBadge.className = 'badge ' + (isFsocActive ? 'state-badge' : (state === 'RECOVERY_FAILED' ? 'link-down' : 'link-searching'));
  }

  // --- Terminal Security (HMAC-SHA256) Panel ---
  if (secTargetName) secTargetName.textContent = targetName;
  if (secStatusHeaderBadge) {
    secStatusHeaderBadge.textContent = (state === 'RECOVERY_FAILED') ? '✗ REJECTED' : '✓ VERIFIED';
    secStatusHeaderBadge.className = 'badge ' + (state === 'RECOVERY_FAILED' ? 'text-crimson' : 'text-emerald');
  }
  if (identResultText) {
    identResultText.textContent = isTargetIdentified ? '✓ IDENTIFIED' : 'SEARCHING';
    identResultText.className = 'concept-result ' + (isTargetIdentified ? 'text-emerald' : 'text-amber');
  }
  if (authResultText) {
    if (state === 'RECOVERY_FAILED') {
      authResultText.textContent = '✗ ROGUE SPOOF REJECTED';
      authResultText.className = 'concept-result text-crimson';
    } else {
      authResultText.textContent = isTargetAuth ? '✓ AUTHENTICATED' : 'VERIFYING';
      authResultText.className = 'concept-result ' + (isTargetAuth ? 'text-emerald' : 'text-amber');
    }
  }
  if (cryptoNonceText) {
    cryptoNonceText.textContent = sec.challenge_nonce || '8f4e19b2...c0';
  }
  if (cryptoHmacText) {
    cryptoHmacText.textContent = sec.hmac_sample || '3a7fd90e...a1';
  }

  // --- Visual Viewport Overlays ---
  if (overlayTargetName) overlayTargetName.textContent = targetName;
  if (overlayOpticalStatus) {
    overlayOpticalStatus.textContent = isOpticalAligned ? '✓ ALIGNED' : (telem.beacon_detected ? 'TRACKING' : 'LOST');
    overlayOpticalStatus.className = 'clean-val ' + (isOpticalAligned ? 'text-emerald' : 'text-amber');
  }
  if (overlayFsocState) {
    overlayFsocState.textContent = isFsocActive ? '● ACTIVE' : 'RECOVERING';
    overlayFsocState.className = 'clean-val ' + (isFsocActive ? 'text-emerald' : 'text-amber');
  }
  if (camDetectedText) {
    camDetectedText.textContent = telem.beacon_detected ? 'BEACON: LOCKED' : 'BEACON: UNLOCKED';
    camDetectedText.className = telem.beacon_detected ? 'text-emerald' : 'text-crimson';
  }

  // --- Lifecycle Flow Highlighting ---
  updateLifecycleFlows(state, telem.recovery_mechanism);

  // --- Update Accordion Summary Badges ---
  const terminalDetailsSummary = document.getElementById('terminalDetailsSummary');
  if (terminalDetailsSummary) {
    terminalDetailsSummary.textContent = `${totalCount} Active Terminals • Target: ${targetName}`;
  }
  const opticalTrackingSummary = document.getElementById('opticalTrackingSummary');
  if (opticalTrackingSummary) {
    opticalTrackingSummary.textContent = `${isOpticalAligned ? 'Boresight Aligned' : 'Searching / Tracking'} • ${state}`;
  }
  const recoverySummaryBadge = document.getElementById('recoverySummaryBadge');
  if (recoverySummaryBadge) {
    const recMech = telem.recovery_mechanism || 'NONE';
    recoverySummaryBadge.textContent = `Recovery: ${(recMech === 'NONE' && isFsocActive) ? 'NONE (Nominal)' : recMech.replace('_', ' ')}`;
  }

  // --- Advanced Telemetry Accordion (When Expanded) ---
  const radErr = telem.pointing_error_px !== null && telem.pointing_error_px !== undefined ? telem.pointing_error_px : null;
  const angErr = telem.pointing_error_deg !== null && telem.pointing_error_deg !== undefined ? telem.pointing_error_deg : null;
  if (telemRadialError) telemRadialError.textContent = radErr !== null ? `${radErr.toFixed(2)} px` : '--';
  if (telemAngularError) telemAngularError.textContent = angErr !== null ? `${angErr.toFixed(3)}°` : '--';
  if (telemCameraAngle) telemCameraAngle.textContent = `${(telem.camera_orientation_deg || 0).toFixed(1)}°`;
  if (telemConfidence) telemConfidence.textContent = `${Math.round((telem.tracking_confidence || 1.0) * 100)}%`;
  if (telemMissCount) telemMissCount.textContent = telem.miss_count || 0;
  if (telemCovTrace) telemCovTrace.textContent = (arena.kalman_cov_trace || 0).toFixed(2);
  if (telemCentroidCoords) {
    telemCentroidCoords.textContent = telem.beacon_position ? `(${telem.beacon_position[0].toFixed(1)}, ${telem.beacon_position[1].toFixed(1)})` : '--';
  }
  if (telemFlightKinematics) {
    const spd = telem.terminal_velocity ? Math.hypot(telem.terminal_velocity[0], telem.terminal_velocity[1]) : 0;
    telemFlightKinematics.textContent = `${spd.toFixed(1)} px/s @ ${(telem.terminal_heading || 0).toFixed(1)}°`;
  }
  if (telemRssi) {
    telemRssi.textContent = telem.rf_rssi !== null && telem.rf_rssi !== undefined ? `${telem.rf_rssi.toFixed(1)} dBm` : '--';
  }

  // --- Sim Clock & Log ---
  if (simClockText) {
    const step = arena.sim_step || 0;
    const timeSec = (step * 0.04).toFixed(1);
    simClockText.textContent = `SIM TIME: ${timeSec}s | STEP: ${step} | TARGET: ${targetName}`;
  }

  if (data.events && data.events.length > 0) {
    updateEventLog(data.events);
  }
}

// =============================================================================
// 4. Lifecycle Flow Pipeline Active Node Highlighting
// =============================================================================
function updateLifecycleFlows(state, recoveryMechanism) {
  if (currentStageText) currentStageText.textContent = state.replace(/_/g, ' ');
  if (currentRecoveryTag) {
    currentRecoveryTag.textContent = `RECOVERY: ${recoveryMechanism || 'NONE'}`;
  }

  const primarySteps = primaryPipeline ? primaryPipeline.querySelectorAll('.pipe-step') : [];
  const recoverySteps = recoveryPipeline ? recoveryPipeline.querySelectorAll('.pipe-step') : [];

  // Reset active classes
  primarySteps.forEach(s => s.classList.remove('active'));
  recoverySteps.forEach(s => s.classList.remove('active'));

  // Map backend SystemState to primary pipeline nodes
  const primaryStateMap = {
    'IDLE': 'DEPLOY_TERMINALS',
    'RF_DISCOVERY': 'RF_DISCOVERY',
    'RF_AUTHENTICATION': 'HMAC_AUTHENTICATION',
    'OPTICAL_SEARCH': 'OPTICAL_SEARCH',
    'OPTICAL_REACQUISITION': 'OPTICAL_SEARCH',
    'OPTICAL_TRACKING': 'OPTICAL_TRACKING',
    'FINE_ALIGNMENT': 'FINE_ALIGNMENT',
    'FSOC_ACTIVE': 'FSOC_ACTIVE'
  };

  const activePrimaryTag = primaryStateMap[state];
  if (primaryPipeline) {
    if (state === 'RF_DISCOVERY') {
      const rfTx = primaryPipeline.querySelector('[data-step="RF_TRANSMISSION"]');
      if (rfTx) rfTx.classList.add('active');
    }
    if (activePrimaryTag) {
      const activeNode = primaryPipeline.querySelector(`[data-step="${activePrimaryTag}"]`);
      if (activeNode) activeNode.classList.add('active');
    }
  }

  // Map recovery pipeline nodes
  const recoveryStateMap = {
    'PREDICTIVE_RECOVERY': 'PREDICTIVE_RECOVERY',
    'LOCAL_REACQUISITION': 'LOCAL_REACQUISITION',
    'OPTICAL_SEARCH': 'OPTICAL_SEARCH',
    'RF_DISCOVERY': 'RF_DISCOVERY_REC',
    'RF_AUTHENTICATION': 'HMAC_AUTH_REC',
    'RF_DIRECTION_RECOVERY': 'RF_DIRECTION_REC',
    'OPTICAL_REACQUISITION': 'OPTICAL_REACQUISITION',
    'FINE_ALIGNMENT': 'FINE_ALIGNMENT_REC',
    'FSOC_ACTIVE': 'FSOC_ACTIVE_RESTORED'
  };

  if (state !== 'FSOC_ACTIVE' && state !== 'IDLE') {
    const activeRecTag = recoveryStateMap[state];
    if (activeRecTag && recoveryPipeline) {
      const recNode = recoveryPipeline.querySelector(`[data-step="${activeRecTag}"]`);
      if (recNode) recNode.classList.add('active');
    }
  } else if (state === 'FSOC_ACTIVE') {
    const baseNode = recoveryPipeline ? recoveryPipeline.querySelector('[data-step="FSOC_ACTIVE_BASE"]') : null;
    if (baseNode) baseNode.classList.add('active');
  }
}

// =============================================================================
// 5. System Test Execution & Live Scorecard
// =============================================================================
async function fetchTestStatus() {
  try {
    const res = await fetch('/api/tests/status');
    if (!res.ok) return;
    const data = await res.json();
    renderTestStatus(data);
  } catch (err) {
    console.warn('Failed to fetch test status:', err);
  }
}

function renderTestStatus(data) {
  if (testTotalScore) {
    testTotalScore.textContent = `${data.total_tests} Tests • Passed: ${data.passed_tests} • Failed: ${data.failed_tests}`;
  }
  if (testProgressFill) {
    testProgressFill.style.width = `${data.progress_pct}%`;
  }
  if (testProgressLabel) {
    testProgressLabel.textContent = data.current_step;
    testProgressLabel.className = 'test-progress-label ' + (data.failed_tests > 0 ? 'text-crimson' : 'text-emerald');
  }

  // Render individual category badges
  if (data.categories) {
    data.categories.forEach(cat => {
      const badgeElem = document.getElementById(`cat${cat.id.charAt(0).toUpperCase() + cat.id.slice(1)}Badge`);
      if (badgeElem) {
        badgeElem.textContent = `✓ ${cat.passed}/${cat.total} PASSED`;
        badgeElem.className = 'cat-badge ' + (cat.status === 'PASSED' ? 'text-emerald' : 'text-crimson');
      }
    });
  }
}

async function triggerSystemTests() {
  if (!btnRunTests) return;
  btnRunTests.disabled = true;
  if (runTestsIcon) runTestsIcon.textContent = '⏳';
  if (runTestsText) runTestsText.textContent = 'RUNNING TESTS...';

  try {
    const res = await fetch('/api/tests/run', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      renderTestStatus(data);
      
      // Start live polling every 300ms
      if (testPollInterval) clearInterval(testPollInterval);
      testPollInterval = setInterval(async () => {
        const pollRes = await fetch('/api/tests/status');
        if (pollRes.ok) {
          const status = await pollRes.json();
          renderTestStatus(status);
          if (!status.is_running) {
            clearInterval(testPollInterval);
            testPollInterval = null;
            btnRunTests.disabled = false;
            if (runTestsIcon) runTestsIcon.textContent = '▶';
            if (runTestsText) runTestsText.textContent = 'RUN SYSTEM TESTS';
          }
        }
      }, 300);
    }
  } catch (err) {
    console.error('Error triggering system tests:', err);
    btnRunTests.disabled = false;
    if (runTestsIcon) runTestsIcon.textContent = '▶';
    if (runTestsText) runTestsText.textContent = 'RUN SYSTEM TESTS';
  }
}

// =============================================================================
// 6. Live Disturbance & Scenario Controls
// =============================================================================
async function toggleCloud(val) {
  disturbanceStates.cloud = val;
  updateDisturbanceButtons();
  await sendDisturbanceAPI({ cloud: val });
}

async function toggleTurbulence(val) {
  disturbanceStates.turbulence = val;
  updateDisturbanceButtons();
  await sendDisturbanceAPI({ turbulence: val ? 'HIGH' : 'OFF' });
}

async function toggleVibration(val) {
  disturbanceStates.vibration = val;
  updateDisturbanceButtons();
  await sendDisturbanceAPI({ vibration: val ? 3.5 : 0.0 });
}

async function toggleSevere(val) {
  disturbanceStates.severe = val;
  if (val) {
    disturbanceStates.cloud = true;
    disturbanceStates.turbulence = true;
    disturbanceStates.vibration = true;
  }
  updateDisturbanceButtons();
  await sendDisturbanceAPI({ severe: val });
}

function updateDisturbanceButtons() {
  if (btnCloudOff && btnCloudOn) {
    btnCloudOff.classList.toggle('active', !disturbanceStates.cloud);
    btnCloudOn.classList.toggle('active', disturbanceStates.cloud);
  }
  if (btnTurbOff && btnTurbOn) {
    btnTurbOff.classList.toggle('active', !disturbanceStates.turbulence);
    btnTurbOn.classList.toggle('active', disturbanceStates.turbulence);
  }
  if (btnVibOff && btnVibOn) {
    btnVibOff.classList.toggle('active', !disturbanceStates.vibration);
    btnVibOn.classList.toggle('active', disturbanceStates.vibration);
  }
  if (btnSevOff && btnSevOn) {
    btnSevOff.classList.toggle('active', !disturbanceStates.severe);
    btnSevOn.classList.toggle('active', disturbanceStates.severe);
  }
}

async function sendDisturbanceAPI(payload) {
  try {
    const res = await fetch('/api/disturbance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      disturbanceStates.cloud = data.cloud;
      disturbanceStates.turbulence = data.is_turbulent;
      disturbanceStates.vibration = data.is_vibrating;
      disturbanceStates.severe = data.severe;
      updateDisturbanceButtons();
    }
  } catch (err) {
    console.error('Error sending disturbance API:', err);
  }
}

async function triggerScenario(scen) {
  document.querySelectorAll('.btn-scenario').forEach(btn => btn.classList.remove('active'));
  const btnMap = {
    'normal': 'btnScenNormal',
    'temporary-loss': 'btnScenTempLoss',
    'deep-loss': 'btnScenDeepLoss',
    'rogue-auth': 'btnScenRogue'
  };
  const activeBtn = document.getElementById(btnMap[scen]);
  if (activeBtn) activeBtn.classList.add('active');

  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'scenario', scenario: scen })
    });
  } catch (err) {
    console.error('Error triggering scenario:', err);
  }
}

async function togglePlayPause() {
  isPlaying = !isPlaying;
  const act = isPlaying ? 'resume' : 'pause';
  if (playPauseIcon) playPauseIcon.textContent = isPlaying ? '⏸' : '▶';
  if (playPauseText) playPauseText.textContent = isPlaying ? 'Pause' : 'Play';
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: act })
    });
  } catch (err) {
    console.error('Error toggling play/pause:', err);
  }
}

async function stepSimulation() {
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'step' })
    });
  } catch (err) {
    console.error('Error stepping simulation:', err);
  }
}

async function resetSimulation() {
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'reset' })
    });
  } catch (err) {
    console.error('Error resetting simulation:', err);
  }
}

async function changeSpeed(val) {
  try {
    await fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'speed', speed: parseFloat(val) })
    });
  } catch (err) {
    console.error('Error changing speed:', err);
  }
}

// =============================================================================
// 7. Advanced Telemetry Collapsible Accordion
// =============================================================================
function toggleTelemetryAccordion() {
  const content = document.getElementById('telemetryAccordionContent');
  const arrow = document.getElementById('accordionArrow');
  if (!content) return;

  const isHidden = content.style.display === 'none';
  content.style.display = isHidden ? 'block' : 'none';
  if (arrow) {
    arrow.textContent = isHidden ? '▲ Click to Collapse' : '▼ Click to Expand';
  }
}

// =============================================================================
// 8. Event Log Stream
// =============================================================================
function updateEventLog(events) {
  if (!eventLogBox) return;
  eventLogBox.innerHTML = '';
  events.forEach(ev => {
    const row = document.createElement('div');
    row.className = 'log-entry';
    if (ev.includes('[PART 1]')) row.classList.add('log-part1');
    else if (ev.includes('[PART 2]')) row.classList.add('log-part2');
    else if (ev.includes('[PART 3]')) row.classList.add('log-part3');
    else if (ev.includes('[PART 4]')) row.classList.add('log-part4');
    
    if (ev.includes('failed') || ev.includes('interrupted') || ev.includes('lost') || ev.includes('RECOVERY_FAILED')) {
      row.classList.add('log-alert');
    }
    row.textContent = ev;
    eventLogBox.appendChild(row);
  });
  eventLogBox.scrollTop = eventLogBox.scrollHeight;
}

function clearEventLog() {
  if (eventLogBox) eventLogBox.innerHTML = '';
}

// =============================================================================
// 9. Viewport Mode Switching
// =============================================================================
function switchView(mode) {
  currentView = mode;
  document.getElementById('tabArena').classList.toggle('active', mode === 'arena');
  document.getElementById('tabSensor').classList.toggle('active', mode === 'sensor');
  document.getElementById('tabCamera').classList.toggle('active', mode === 'camera');

  arenaCanvas.classList.toggle('active', mode === 'arena');
  sensorCanvas.classList.toggle('active', mode === 'sensor');
  document.getElementById('cameraFeedContainer').classList.toggle('active', mode === 'camera');

  const badge = document.getElementById('viewModeBadge');
  if (badge) {
    if (mode === 'arena') badge.textContent = '2D KINEMATIC ARENA';
    else if (mode === 'sensor') badge.textContent = 'BORESIGHT SENSOR VIEW';
    else badge.textContent = 'CAMERA SENSOR FEED (RAW)';
  }

  if (mode === 'camera') {
    if (!cameraRefreshInterval) {
      cameraRefreshInterval = setInterval(() => {
        const img = document.getElementById('cameraFeedImg');
        if (img) img.src = `/api/camera_frame?t=${Date.now()}`;
      }, 100);
    }
  } else {
    if (cameraRefreshInterval) {
      clearInterval(cameraRefreshInterval);
      cameraRefreshInterval = null;
    }
  }
}

// =============================================================================
// 10. Dual-Canvas 60FPS Render Loop & Multi-Terminal Drawing
// =============================================================================
function startRenderLoop() {
  function render() {
    if (latestData) {
      if (currentView === 'arena') {
        renderArenaCanvas(latestData);
      } else if (currentView === 'sensor') {
        renderSensorCanvas(latestData);
      }
    }
    requestAnimationFrame(render);
  }
  requestAnimationFrame(render);
}

function renderArenaCanvas(data) {
  if (!arenaCtx) return;
  const ctx = arenaCtx;
  const w = arenaCanvas.width;
  const h = arenaCanvas.height;
  const arena = data.arena || {};
  const telem = data.telemetry || {};
  const terminals = data.terminals || [];
  const targetId = data.target_terminal || 'TERMINAL_03';

  // Clear Background
  ctx.fillStyle = '#06090e';
  ctx.fillRect(0, 0, w, h);

  // Subtle Background Grid
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
  ctx.lineWidth = 1;
  const gridSize = 40;
  for (let x = 0; x < w; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // Terminals Data
  const termA = arena.terminal_a || { x: 180, y: 360, orientation_deg: 38, fov_deg: 35 };
  const termB = arena.terminal_b || { x: 650, y: 360, beacon_active: true, beacon_x: 650, beacon_y: 360 };

  const ax = termA.x;
  const ay = termA.y;
  const bx = termB.beacon_x !== undefined ? termB.beacon_x : termB.x;
  const by = termB.beacon_y !== undefined ? termB.beacon_y : termB.y;
  const camAngleRad = (termA.orientation_deg * Math.PI) / 180;
  const fovHalfRad = ((termA.fov_deg / 2) * Math.PI) / 180;
  const coneRadius = 650;

  // Record Target Terminal Trajectory
  if (bx && by) {
    terminalBHistory.push({ x: bx, y: by });
    if (terminalBHistory.length > 70) {
      terminalBHistory.shift();
    }
  }

  // Draw Smooth Curved Flight Trajectory Trail
  if (terminalBHistory.length > 1) {
    ctx.save();
    for (let i = 1; i < terminalBHistory.length; i++) {
      const p0 = terminalBHistory[i - 1];
      const p1 = terminalBHistory[i];
      const alpha = (i / terminalBHistory.length) * 0.45;
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.lineTo(p1.x, p1.y);
      ctx.strokeStyle = `rgba(245, 158, 11, ${alpha})`;
      ctx.lineWidth = 2.0;
      ctx.stroke();
    }
    ctx.restore();
  }

  // 1. Draw Auxiliary RF Omni-Broadcast Radius
  ctx.save();
  ctx.beginPath();
  ctx.arc(ax, ay, 400, 0, 2 * Math.PI);
  ctx.strokeStyle = 'rgba(6, 182, 212, 0.12)';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 6]);
  ctx.stroke();
  ctx.restore();

  // 2. Draw Camera Sensor FOV Cone (35°)
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.arc(ax, ay, coneRadius, camAngleRad - fovHalfRad, camAngleRad + fovHalfRad);
  ctx.closePath();
  const fovGrad = ctx.createRadialGradient(ax, ay, 30, ax, ay, coneRadius);
  fovGrad.addColorStop(0, 'rgba(6, 182, 212, 0.16)');
  fovGrad.addColorStop(0.7, 'rgba(6, 182, 212, 0.04)');
  fovGrad.addColorStop(1, 'rgba(6, 182, 212, 0.0)');
  ctx.fillStyle = fovGrad;
  ctx.fill();

  ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
  ctx.lineWidth = 1.2;
  ctx.stroke();
  ctx.restore();

  // 3. Draw Camera Central Boresight Axis
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(ax, ay);
  ctx.lineTo(ax + Math.cos(camAngleRad) * coneRadius, ay + Math.sin(camAngleRad) * coneRadius);
  ctx.strokeStyle = 'rgba(6, 182, 212, 0.6)';
  ctx.lineWidth = 1.2;
  ctx.setLineDash([4, 4]);
  ctx.stroke();
  ctx.restore();

  // 4. Concentric Expanding Animated RF Waves (from every live moving terminal)
  const isRfActive = Boolean(
    telem.rf_wave_active ||
    telem.rf_discovery_state === 'IN_PROGRESS' ||
    telem.current_state === 'RF_DISCOVERY' ||
    (terminals && terminals.some(t => t.rf_status === 'TRANSMITTING'))
  );

  const nowSec = performance.now() / 1000;

  if (isRfActive) {
    terminals.forEach((t, idx) => {
      const isTarget = (t.id === targetId || t.role === 'Target' || t.is_target);
      const posX = isTarget ? bx : (t.position ? t.position[0] : t.x);
      const posY = isTarget ? by : (t.position ? t.position[1] : t.y);
      if (posX === undefined || posY === undefined) return;

      const isDiscovered = (t.rf_status === 'DISCOVERED');

      ctx.save();
      // Draw 3 concentric expanding rings tracking terminal's live moving position
      for (let k = 0; k < 3; k++) {
        const prog = ((nowSec * 1.35) + (k / 3.0) + (idx * 0.16)) % 1.0;
        const radius = 10 + prog * 44;
        const alpha = (1.0 - prog) * (isDiscovered ? 0.35 : (isTarget ? 0.85 : 0.65));
        
        ctx.beginPath();
        ctx.arc(posX, posY, radius, 0, 2 * Math.PI);
        if (isDiscovered) {
          ctx.strokeStyle = `rgba(16, 185, 129, ${alpha})`;
        } else if (isTarget) {
          ctx.strokeStyle = `rgba(0, 242, 254, ${alpha})`;
        } else {
          ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
        }
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }

      // Radiating signal badge "))) RF ((("
      if (!isDiscovered) {
        ctx.fillStyle = isTarget ? 'rgba(0, 242, 254, 0.85)' : 'rgba(56, 189, 248, 0.75)';
        ctx.font = '700 8px monospace';
        ctx.textAlign = 'center';
        ctx.fillText('))) RF (((', posX, posY + 28);
      }
      ctx.restore();
    });
  }

  // 5. Draw Other Remote Terminals in Environment
  terminals.forEach(t => {
    if (t.id !== targetId && t.position) {
      const tx = t.position[0];
      const ty = t.position[1];
      const isDetected = String(t.status || '').toLowerCase() === 'detected';

      // Record trajectory history for non-target terminal
      if (!nonTargetHistories[t.id]) {
        nonTargetHistories[t.id] = [];
      }
      nonTargetHistories[t.id].push({ x: tx, y: ty });
      if (nonTargetHistories[t.id].length > 20) {
        nonTargetHistories[t.id].shift();
      }

      // Draw subtle short motion trail for non-target terminal
      const hist = nonTargetHistories[t.id];
      if (hist && hist.length > 1) {
        ctx.save();
        for (let i = 1; i < hist.length; i++) {
          const p0 = hist[i - 1];
          const p1 = hist[i];
          const alpha = (i / hist.length) * (isDetected ? 0.35 : 0.22);
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.strokeStyle = isDetected ? `rgba(16, 185, 129, ${alpha})` : `rgba(100, 116, 139, ${alpha})`;
          ctx.lineWidth = 1.4;
          ctx.stroke();
        }
        ctx.restore();
      }

      ctx.save();
      if (isDetected) {
        // Luminous emerald/cyan glow when detected by camera scan
        ctx.beginPath();
        ctx.arc(tx, ty, 13, 0, 2 * Math.PI);
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.45)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(tx, ty, 7, 0, 2 * Math.PI);
        ctx.fillStyle = '#064e3b';
        ctx.fill();
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2.0;
        ctx.stroke();
      } else {
        // Searching state (undiscovered node)
        ctx.beginPath();
        ctx.arc(tx, ty, 7, 0, 2 * Math.PI);
        ctx.fillStyle = '#1e293b';
        ctx.fill();
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      // Terminal Name Label (● Terminal-XX)
      ctx.fillStyle = isDetected ? '#a7f3d0' : '#94a3b8';
      ctx.font = '600 10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`● ${t.name}`, tx, ty - 13);

      // Status Pill Label
      const isDiscovered = (t.rf_status === 'DISCOVERED');
      ctx.fillStyle = isDetected ? '#10b981' : (isDiscovered ? '#38bdf8' : '#fbbf24');
      ctx.font = '700 8px Inter, sans-serif';
      const subLabel = isDetected ? '[Detected]' : (isDiscovered ? '[Discovered]' : '[Transmitting]');
      ctx.fillText(subLabel, tx, ty + 17);
      ctx.restore();
    }
  });

  // 6. Draw Optical FSOC Beam (If Active)
  const isBeamActive = (telem.fsoc_status === 'ESTABLISHED' || telem.fsoc_status === 'ACTIVE' || telem.current_state === 'FSOC_ACTIVE');
  if (isBeamActive && termB.beacon_active) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.85)';
    ctx.lineWidth = 3.0;
    ctx.shadowColor = '#10b981';
    ctx.shadowBlur = 14;
    ctx.stroke();

    // Central core beam
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.2;
    ctx.shadowBlur = 0;
    ctx.stroke();
    ctx.restore();
  }

  // 7. Draw Kalman Prediction Marker
  if (arena.kalman_pred && telem.tracking_status === 'PREDICTING') {
    const kx = arena.kalman_pred[0];
    const ky = arena.kalman_pred[1];
    ctx.save();
    ctx.beginPath();
    ctx.arc(kx, ky, 9, 0, 2 * Math.PI);
    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 2.0;
    ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.restore();
  }

  // 8. Draw Local Terminal A (Ground RX Station)
  ctx.save();
  ctx.beginPath();
  ctx.arc(ax, ay, 14, 0, 2 * Math.PI);
  ctx.fillStyle = '#0f172a';
  ctx.fill();
  ctx.strokeStyle = varColor('--color-cyan', '#06b6d4');
  ctx.lineWidth = 2.5;
  ctx.shadowColor = '#06b6d4';
  ctx.shadowBlur = 10;
  ctx.stroke();

  // Internal aperture dot
  ctx.beginPath();
  ctx.arc(ax, ay, 4, 0, 2 * Math.PI);
  ctx.fillStyle = '#fff';
  ctx.fill();

  ctx.fillStyle = '#fff';
  ctx.font = '600 11px Outfit, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('TERMINAL A (RX)', ax, ay + 28);
  ctx.restore();

  // 9. Draw Remote Target Terminal B (Dynamic Flight)
  ctx.save();
  const targetObj = terminals.find(t => t.id === targetId);
  const targetLabel = targetObj ? targetObj.name : targetId;

  // Beacon illumination halo
  if (termB.beacon_active) {
    const haloGrad = ctx.createRadialGradient(bx, by, 3, bx, by, 22);
    haloGrad.addColorStop(0, 'rgba(245, 158, 11, 0.9)');
    haloGrad.addColorStop(0.5, 'rgba(245, 158, 11, 0.35)');
    haloGrad.addColorStop(1, 'rgba(245, 158, 11, 0.0)');
    ctx.fillStyle = haloGrad;
    ctx.beginPath();
    ctx.arc(bx, by, 22, 0, 2 * Math.PI);
    ctx.fill();
  }

  // Target Node Concentric Ring (◎ marker design)
  ctx.beginPath();
  ctx.arc(bx, by, 14, 0, 2 * Math.PI);
  ctx.strokeStyle = 'rgba(0, 242, 254, 0.65)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Target Node Inner Core
  ctx.beginPath();
  ctx.arc(bx, by, 9, 0, 2 * Math.PI);
  ctx.fillStyle = termB.beacon_active ? '#f59e0b' : '#64748b';
  ctx.fill();
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 2.0;
  ctx.stroke();

  // Target Label Badge
  ctx.fillStyle = '#00f2fe';
  ctx.font = '700 11px Outfit, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`◎ ${targetLabel} [TARGET]`, bx, by - 18);

  const targetDiscovered = (targetObj && targetObj.rf_status === 'DISCOVERED') || (telem.rf_discovery_state === 'COMPLETE');
  ctx.fillStyle = (telem.current_state === 'FSOC_ACTIVE' || telem.current_state === 'FINE_ALIGNMENT') ? '#10b981' : (targetDiscovered ? '#00f2fe' : '#fbbf24');
  ctx.font = '700 8px Inter, sans-serif';
  const targetSubLabel = (telem.current_state === 'FSOC_ACTIVE') ? '[FSOC ACTIVE]' : (targetDiscovered ? '[Target Discovered]' : '[Transmitting]');
  ctx.fillText(targetSubLabel, bx, by + 26);

  ctx.restore();
}

function renderSensorCanvas(data) {
  if (!sensorCtx) return;
  const ctx = sensorCtx;
  const w = sensorCanvas.width;
  const h = sensorCanvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const telem = data.telemetry || {};

  // Clear Background
  ctx.fillStyle = '#06090e';
  ctx.fillRect(0, 0, w, h);

  // Concentric Alignment Rings
  ctx.save();
  [40, 80, 140, 220].forEach((r, idx) => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, 2 * Math.PI);
    ctx.strokeStyle = idx === 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(6, 182, 212, 0.18)';
    ctx.lineWidth = idx === 0 ? 1.5 : 1.0;
    ctx.stroke();
  });

  // Crosshairs
  ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx - 260, cy);
  ctx.lineTo(cx + 260, cy);
  ctx.moveTo(cx, cy - 260);
  ctx.lineTo(cx, cy + 260);
  ctx.stroke();

  // Draw Detected Beacon Centroid
  if (telem.beacon_detected && telem.beacon_position) {
    const bx = telem.beacon_position[0];
    const by = telem.beacon_position[1];

    ctx.beginPath();
    ctx.arc(bx, by, 12, 0, 2 * Math.PI);
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2.0;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(bx, by, 4, 0, 2 * Math.PI);
    ctx.fillStyle = '#fff';
    ctx.fill();

    // Alignment vector from center to beacon
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(bx, by);
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.6)';
    ctx.setLineDash([4, 4]);
    ctx.stroke();
  }
  ctx.restore();
}

function varColor(cssVar, fallback) {
  return fallback;
}
