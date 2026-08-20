// LoHP Maze Simulator — 3D walkthrough client.
//
// The maze is a TWO-STORY, OPEN-FACED structure (street view IS the street
// elevation): ground-floor and upper-floor rooms all face the street like a
// dollhouse. Visitors climb UP in Guy Line Climb and DOWN in Vertical Moop
// March. The default "street" view shows the whole facade at once — the way
// the real piece reads on playa (hiddenplaya.art).
//
// It talks to the REAL server exactly like production hardware does:
//   - virtual sensors fire the same HTTP POSTs the Pi/ESP32 triggers fire (:5000)
//   - the page connects as an audio "unit" over the WebSocket protocol (:8765)
//   - light state arrives as raw DMX universe frames (:5001/sim/dmx) and each
//     virtual fixture decodes its own channels from its configured start
//     address — so real-world addressing bugs reproduce here visually.

import * as THREE from './vendor/three.module.js';

const HOST = location.hostname;
const SIM = `http://${HOST}:${location.port || 5001}`;
let API = `http://${HOST}:5000`;
let AUDIO_WS = `ws://${HOST}:8765`;

// first-person eye line: our visitors stand ≈5'11" (1.80 m), eyes at 1.69 m
const EYE = 1.69;

const S = {
  cfg: null,
  frame: new Uint8Array(352),
  seq: -1,
  levelHeight: 3.2,
  fixtures: [],            // {room, addr, channels, level, light, lens, cone, cell}
  roomsMeshes: {},         // room -> {slab, center(Vector3 at room level), level}
  canvasMats: {},          // room -> [backdrop materials], emissive-tinted by the room's light
  sensors: [],             // {name, kind, room, action, seg?, zone?, wasInside?, level, meshes, lastFired}
  ladders: [],             // {room, x, z} climb points
  interactables: [],       // meshes with .userData.{sensor|ladder}
  piezoAttempts: 0,
  projection: null,        // planned Cuddle floor-projection rig (layout `projection` key)
  vidBase: true,           // experiment: AI base loop instead of the static base (btn-vidbase)
  sign: null,              // Camp Sign live-DMX letter zones (layout `camp_sign` key)
  eye: null,               // Cuddle orb — Waveshare ESP32-S3 round display (layout `eye` key)
  mode: 'street',
  keys: {},
  pos: new THREE.Vector3(11.7, EYE, 4.5),
  level: 0,
  prev2: { x: 11.7, z: 4.5 },
  yaw: 0, pitch: 0,
  pointerLocked: false,
  audio: { on: false, ws: null, ctx: null, rooms: new Map(), beds: new Map(), maze: null, buffers: new Map(), earRoom: null },
  dmxWs: null,
  teleporting: false,
};
// Headless test hooks: module scope hides these from playwright-driven
// checks (sim tests, bench verification) otherwise.
window.S = S;
window.setMode = setMode;
window.SIM = S; // debug handle: inspect live sim state from the console

const $ = (id) => document.getElementById(id);
const clock = new THREE.Clock();
window.SIM = S; // dev/test hook: inspect state, drive the avatar from the console

// ---------------------------------------------------------------- logging/UI
function log(kind, msg) {
  const el = document.createElement('div');
  el.className = kind;
  const t = new Date().toTimeString().slice(0, 8);
  el.innerHTML = `<span class="t">${t}</span>${escapeHtml(msg)}`;
  const box = $('log');
  box.prepend(el);
  while (box.children.length > 100) box.lastChild.remove();
}
function escapeHtml(s) { return String(s).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c])); }
function setDot(which, ok) { $(`dot-${which}`).className = 'dot ' + (ok === null ? '' : ok === 'warn' ? 'warn' : ok ? 'ok' : 'err'); }
let toastTimer = null;
function toast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  el.style.opacity = 1;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.style.opacity = 0; setTimeout(() => el.classList.add('hidden'), 350); }, 1800);
}

async function post(path, data, source) {
  log('info', `${path} ← ${JSON.stringify(data || {}).slice(0, 60)}${source ? ' (' + source + ')' : ''}`);
  try {
    const res = await fetch(API + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data || {}),
    });
    let body = {};
    try { body = await res.json(); } catch (e) { /* non-json */ }
    setDot('api', true);
    log(res.ok ? 'ok' : 'err', `${path} → ${res.status} ${body.message || ''}`);
    return res.ok;
  } catch (e) {
    setDot('api', false);
    log('err', `${path} failed: ${e.message}`);
    return false;
  }
}

// Production server Pi watchdog — the sim backend probes the real box
// (sim_ui.py /sim/rpi_status, host from RPI_HOST) and the RPI header dot
// mirrors it: green = server answering, amber = box up but server not
// running (booted, not yet deployed), red = unreachable.
let rpiLastState = null;
async function pollRpiStatus() {
  try {
    const st = await fetch(`${SIM}/sim/rpi_status`).then(r => r.json());
    if (st.state === 'disabled') { setDot('rpi', null); $('dot-rpi').title = 'RPi probe disabled (RPI_HOST=)'; return; }
    const label = { server_up: 'server UP', host_up: 'host up, server not running', down: 'unreachable' }[st.state] || st.state;
    setDot('rpi', st.state === 'server_up' ? true : st.state === 'host_up' ? 'warn' : false);
    $('dot-rpi').title = `RPi ${st.host}: ${label}${st.latency_ms != null ? ` — ${st.latency_ms} ms` : ''}`;
    if (st.state !== rpiLastState) {
      log(st.state === 'server_up' ? 'ok' : st.state === 'host_up' ? 'info' : 'err', `RPi ${st.host}: ${label}`);
      rpiLastState = st.state;
    }
  } catch (e) { setDot('rpi', null); }
  setTimeout(pollRpiStatus, 5000);
}

// ---------------------------------------------------------------- three setup
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0c18);
scene.fog = new THREE.Fog(0x141020, 25, 95);

// --- playa environment: gradient sky dome + stars. Night by default, with a
// day mode toggle (N / the ☀ button) — the piece reads differently at 3pm.
const ENV = { day: false };
function skyTexture(stops) {
  const c = document.createElement('canvas');
  c.width = 4; c.height = 256;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, 256);
  for (const [p, col] of stops) grad.addColorStop(p, col);
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 256);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
{
  ENV.nightTex = skyTexture([[0.0, '#05060f'], [0.55, '#0d1024'],   // zenith
    [0.78, '#2a2038'],                                              // dusty horizon glow
    [0.86, '#3b2b33'], [1.0, '#191410']]);                          // below horizon
  ENV.dayTex = skyTexture([[0.0, '#3e77c2'], [0.5, '#7ba6d9'],      // deep blue zenith
    [0.8, '#ccd2d1'],                                               // hazy dust band
    [0.88, '#ddd3bd'], [1.0, '#b7a488']]);                          // alkali flats
  ENV.dome = new THREE.Mesh(new THREE.SphereGeometry(150, 24, 16),
    new THREE.MeshBasicMaterial({ map: ENV.nightTex, side: THREE.BackSide, fog: false, depthWrite: false }));
  ENV.dome.position.set(10, 0, 5);
  scene.add(ENV.dome);

  const starPos = [];
  for (let i = 0; i < 900; i++) {
    const az = Math.random() * Math.PI * 2;
    const el = Math.asin(Math.random() * 0.92 + 0.06); // keep off the horizon band
    const r = 140;
    starPos.push(10 + r * Math.cos(el) * Math.cos(az), r * Math.sin(el), 5 + r * Math.cos(el) * Math.sin(az));
  }
  const starGeo = new THREE.BufferGeometry();
  starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
  ENV.stars = new THREE.Points(starGeo, new THREE.PointsMaterial({
    color: 0xcdd6ff, size: 0.55, sizeAttenuation: true, transparent: true, opacity: 0.85, fog: false,
  }));
  scene.add(ENV.stars);
}

const camera = new THREE.PerspectiveCamera(74, innerWidth / innerHeight, 0.1, 300);
camera.rotation.order = 'YXZ';
const streetCam = new THREE.PerspectiveCamera(52, innerWidth / innerHeight, 0.1, 300);
let topCam = null;
let topYaw = 0; // overhead-plan spin (E/R keys); 0 = street side at the bottom

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
// AgX, not ACESFilmic: ACES tone-maps each RGB channel independently, so an
// over-bright SATURATED colour clips red first and skews orange → yellow →
// white on nearby lit surfaces (three.js issue #27862 territory; the r160
// release added AgX specifically to keep hue stable through over-exposure).
// With ACES the fixture data was orange on the wire while the room rendered
// yellow-white — verified 2026-08-17 with a held (255,120,20) channel test.
renderer.toneMapping = THREE.AgXToneMapping;
renderer.toneMappingExposure = 1.6; // AgX sits darker than ACES; compensate
$('scene').appendChild(renderer.domElement);

ENV.amb = new THREE.AmbientLight(0x9895b0, 0.2);
ENV.hemi = new THREE.HemisphereLight(0x252b4e, 0x54462f, 0.5); // night sky over warm dust bounce
ENV.sun = new THREE.DirectionalLight(0xfff3dd, 0);             // day mode only
ENV.sun.position.set(40, 55, 38);
scene.add(ENV.amb, ENV.hemi, ENV.sun);

function setDayNight(day) {
  ENV.day = day;
  ENV.dome.material.map = day ? ENV.dayTex : ENV.nightTex;
  ENV.stars.visible = !day;
  ENV.amb.color.set(day ? 0xcdd3de : 0x9895b0);
  ENV.amb.intensity = day ? 0.5 : 0.2;
  ENV.hemi.color.set(day ? 0xbdd2ee : 0x252b4e);
  ENV.hemi.groundColor.set(day ? 0xb29c76 : 0x54462f);
  ENV.hemi.intensity = day ? 1.25 : 0.5;
  ENV.sun.intensity = day ? 1.7 : 0;
  scene.background.set(day ? 0x9db6d6 : 0x0a0c18);
  scene.fog.color.set(day ? 0xc9c2b0 : 0x141020);
  scene.fog.near = day ? 60 : 25;
  scene.fog.far = day ? 260 : 95;
  renderer.toneMappingExposure = day ? 1.4 : 1.6; // AgX-compensated (was 1.0/1.15 under ACES)
  $('btn-daynight').textContent = day ? '☾ Night' : '☀ Day'; // shows what a click switches TO
  try { localStorage.setItem('lohp-sim-day', day ? '1' : '0'); } catch (e) { /* private mode */ }
}
try { setDayNight(localStorage.getItem('lohp-sim-day') === '1'); } catch (e) { setDayNight(false); }

// level groups: 0 = ground rooms, 1 = upper rooms, 2 = shared (street, shells, ladders)
const levelGroups = [new THREE.Group(), new THREE.Group(), new THREE.Group()];
levelGroups.forEach(g => scene.add(g));
const grp = (level) => levelGroups[level === 1 ? 1 : level === 0 ? 0 : 2];
const roofGroup = new THREE.Group(); // hidden in overhead view so the plan stays readable
scene.add(roofGroup);
const matRoof = new THREE.MeshStandardMaterial({ color: 0x1a1b21, roughness: 0.95, side: THREE.DoubleSide });

// custom deck steel (the cad-items/*.svg weldments, baked into deck_steel.js by
// tools/deck_steel_from_cad.py). Normally buried under the ply, so it lives in
// its own groups behind the Steel button: off / deck / roof / both, ghosting
// the hex ply while shown so the members read against the scaffold.
const steelGroups = { deck: new THREE.Group(), roof: new THREE.Group() };
scene.add(steelGroups.deck, steelGroups.roof);
const steelGhosts = []; // hex ply materials faded while steel is shown
let steelMode = 'off';
const STEEL_MODES = ['off', 'deck', 'roof', 'both'];
const STEEL_LABEL = { off: 'Steel ✕', deck: 'Steel: deck', roof: 'Steel: roof', both: 'Steel ✓' };
function setSteelMode(mode) {
  steelMode = mode;
  steelGroups.deck.visible = mode === 'deck' || mode === 'both';
  steelGroups.roof.visible = mode === 'roof' || mode === 'both';
  const ghost = mode !== 'off';
  for (const m of steelGhosts) {
    m.transparent = ghost;
    m.opacity = ghost ? 0.22 : 1;
    m.depthWrite = !ghost;
    m.needsUpdate = true;
  }
  $('btn-steel').textContent = STEEL_LABEL[mode];
  try { localStorage.setItem('lohp-sim-steel', mode); } catch (e) { /* private mode */ }
}

const raycaster = new THREE.Raycaster();

function makeLabel(text, scale = 1) {
  const c = document.createElement('canvas');
  const meas = c.getContext('2d');
  meas.font = '600 42px system-ui, sans-serif';
  const w = Math.ceil(meas.measureText(text).width) + 28;
  c.width = w; c.height = 64;
  const ctx2 = c.getContext('2d');
  ctx2.font = '600 42px system-ui, sans-serif';
  ctx2.fillStyle = 'rgba(8,10,16,0.55)';
  ctx2.fillRect(0, 0, w, 64);
  ctx2.fillStyle = '#cdd4ea';
  ctx2.fillText(text, 14, 46);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0.9 }));
  sprite.scale.set((w / 64) * 0.8 * scale, 0.8 * scale, 1);
  return sprite;
}

// ---------------------------------------------------------------- maze build
const matFloorBase = () => new THREE.MeshStandardMaterial({ color: 0x1f2027, roughness: 0.95 });
const matWall = new THREE.MeshStandardMaterial({ color: 0x3a3b44, roughness: 0.9, metalness: 0.02 });
const matPost = new THREE.MeshStandardMaterial({ color: 0x23242c, roughness: 0.7, metalness: 0.25 });
const matGalv = new THREE.MeshStandardMaterial({ color: 0x8f959d, roughness: 0.35, metalness: 0.7 });
const matStrap = new THREE.MeshStandardMaterial({ color: 0xc65f1e, roughness: 0.85, metalness: 0.05 });
// tower wrap: same shade cloth as the maze walls, but the towers carry no
// fixtures, so a whisper of emissive keeps their silhouette readable at night
const matTowerSkin = new THREE.MeshStandardMaterial({ color: 0x3a3b44, roughness: 0.9, metalness: 0.02, emissive: 0x0e0f16 });
const matPly = new THREE.MeshStandardMaterial({ color: 0x9a7b52, roughness: 0.85, metalness: 0.02 });
const matFramePaint = [
  new THREE.MeshStandardMaterial({ color: 0x2666b8, roughness: 0.5, metalness: 0.25 }), // our blue
  new THREE.MeshStandardMaterial({ color: 0x2f9e57, roughness: 0.5, metalness: 0.25 }), // our green
];

// Printed-canvas backdrops (the real prints in Background-images/, resized
// into web/img/backgrounds/ — paths come from maze_layout.json). Each hangs
// on its room's back wall; standard material so the DMX fixtures genuinely
// light it, plus a per-room emissive tint (set every frame in updateFixtures)
// so the art stays readable at night and glows with the room's effect color.
// Hex/tower canvases pass a uRange to show one slice of a shared print.
const texLoader = new THREE.TextureLoader();
const texCache = new Map();
function canvasTexture(url) {
  if (!texCache.has(url)) {
    texCache.set(url, new Promise((resolve, reject) => texLoader.load(url, (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
      resolve(tex);
    }, undefined, reject)));
  }
  return texCache.get(url);
}

// Map the plane's UVs to its [u0,u1] slice of the print, cover-cropped so the
// whole print fills the whole span (planeW/(u1-u0) x planeH) w/o stretching.
function applyCanvasUVs(geo, img, planeW, planeH, [u0, u1]) {
  const spanAspect = (planeW / (u1 - u0)) / planeH;
  const imgAspect = img.width / img.height;
  let cu = [0, 1], cv = [0, 1];
  if (imgAspect > spanAspect) {
    const f = spanAspect / imgAspect;
    cu = [(1 - f) / 2, (1 + f) / 2];
  } else {
    const f = imgAspect / spanAspect;
    cv = [(1 - f) / 2, (1 + f) / 2];
  }
  const U0 = cu[0] + (cu[1] - cu[0]) * u0, U1 = cu[0] + (cu[1] - cu[0]) * u1;
  const uv = geo.attributes.uv, pos = geo.attributes.position;
  for (let i = 0; i < uv.count; i++) {
    uv.setXY(i, pos.getX(i) < 0 ? U0 : U1, pos.getY(i) < 0 ? cv[0] : cv[1]);
  }
  uv.needsUpdate = true;
}

function mountCanvas(url, w, h, pos, rotY, parent, room, uRange = [0, 1]) {
  const geo = new THREE.PlaneGeometry(w, h);
  const mat = new THREE.MeshStandardMaterial({ roughness: 0.92, metalness: 0 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.visible = false; // until the texture arrives
  mesh.position.copy(pos);
  mesh.rotation.y = rotY;
  parent.add(mesh);
  canvasTexture(url).then((tex) => {
    applyCanvasUVs(geo, tex.image, w, h, uRange);
    mat.map = tex;
    mat.emissiveMap = tex;
    mat.needsUpdate = true;
    mesh.visible = true;
  }).catch(() => log('err', `backdrop missing: ${url}`));
  if (room) (S.canvasMats[room] = S.canvasMats[room] || []).push(mat);
  else mat.emissive.setRGB(0.07, 0.07, 0.08); // no room light feed (towers): faint static glow
  return mat;
}

// One 5' x 6'4" S-style walk-thru frame (ScaffoldExpress PSV-610 — our
// PSV-K610-7 sets): 1.69" OD legs with 9" coupling pins under 1" collars,
// top rail over a full-width header tied by three short stubs, doorway
// tubes hanging from the header that candy-cane out into the legs ~12" up,
// two ladder rungs per side, and brace studs on each leg 8.5" down from
// the top and 4' below that (where the 7'x4' cross braces pin on).
function buildFrameSeg(ax, az, bx, bz, yBase, mat) {
  const H = 1.93, R = 0.0215;               // 6'4" tall, 1.6925" OD tube
  const RAIL_Y = H - 0.075, HEAD_Y = H - 0.19;
  const INSET = 0.29;                       // doorway tube ~11.5" in from leg
  const dx = bx - ax, dz = bz - az;
  const len = Math.hypot(dx, dz);
  const fg = new THREE.Group();
  fg.position.set((ax + bx) / 2, yBase, (az + bz) / 2);
  fg.rotation.y = -Math.atan2(dz, dx);

  const addCyl = (r, h, x, y, z = 0, rotZ = 0, rotX = 0, material = mat) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h), material);
    m.position.set(x, y, z);
    m.rotation.set(rotX, 0, rotZ);
    fg.add(m);
    return m;
  };

  for (const s of [-1, 1]) {
    const lx = s * (len / 2);
    const tx = s * (len / 2 - INSET);       // doorway tube line
    addCyl(R, H, lx, H / 2);                                       // leg
    addCyl(0.016, 0.115, lx, H + 0.0475, 0, 0, 0, matGalv);        // coupling pin
    addCyl(0.026, 0.016, lx, H + 0.008, 0, 0, 0, matGalv);         // 1" collar
    // brace studs (both faces): 8.5" down from the top, then 4' below
    for (const sy of [1.7145, 0.4953]) {
      for (const sz of [-1, 1]) addCyl(0.006, 0.05, lx, sy, sz * 0.038, 0, Math.PI / 2, matGalv);
    }
    // doorway tube: hangs from the header, candy-canes out into the leg
    addCyl(0.017, HEAD_Y - 0.50, tx, (HEAD_Y + 0.50) / 2);
    const cane = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(tx, 0.50, 0),
      new THREE.Vector3(tx, 0.30, 0),
      new THREE.Vector3(lx - s * R, 0.30, 0));
    fg.add(new THREE.Mesh(new THREE.TubeGeometry(cane, 12, 0.017, 8), mat));
    // ladder rungs between the leg and the doorway tube
    for (const ry of [0.84, 1.30]) {
      addCyl(0.010, INSET, s * (len / 2 - INSET / 2), ry, 0, Math.PI / 2);
    }
  }
  addCyl(0.019, len - 0.02, 0, RAIL_Y, 0, Math.PI / 2);            // top rail
  addCyl(0.019, len - 0.02, 0, HEAD_Y, 0, Math.PI / 2);            // header
  // three short stubs tie rail to header: over each doorway tube + center
  for (const sx of [-(len / 2 - INSET), 0, len / 2 - INSET]) {
    addCyl(0.010, RAIL_Y - HEAD_Y, sx, (RAIL_Y + HEAD_Y) / 2);
  }
  return fg;
}

// One 3' x 4' ladder frame — the little end frames from the same fleet as the
// walk-thru sets: identical 1.69" OD tube and coupling-pin tops, two legs, a
// top rail and two rungs, no doorway arch. Used by the entrance towers.
function buildMiniFrameSeg(ax, az, bx, bz, yBase, mat, opts = {}) {
  const H = opts.h || 1.2192, R = 0.0215;
  const dx = bx - ax, dz = bz - az;
  const len = Math.hypot(dx, dz);
  const fg = new THREE.Group();
  fg.position.set((ax + bx) / 2, yBase, (az + bz) / 2);
  fg.rotation.y = -Math.atan2(dz, dx);
  const addCyl = (r, h, x, y, rotZ = 0, material = mat) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h), material);
    m.position.set(x, y, 0);
    m.rotation.z = rotZ;
    fg.add(m);
  };
  for (const s of [-1, 1]) {
    const lx = s * (len / 2);
    addCyl(R, H, lx, H / 2);
    addCyl(0.016, 0.115, lx, H + 0.0475, 0, matGalv);   // coupling pin
    addCyl(0.026, 0.016, lx, H + 0.008, 0, matGalv);    // 1" collar
  }
  for (const ry of [H - 0.035, H * 0.62, H * 0.3]) {    // top rail + two rungs
    addCyl(0.015, len - 0.02, 0, ry, Math.PI / 2);
  }
  return fg;
}

function carve(a0, a1, gaps) {
  let segs = [[a0, a1]];
  for (const [g0, g1] of gaps) {
    const out = [];
    for (const [s, e] of segs) {
      if (g1 <= s || g0 >= e) { out.push([s, e]); continue; }
      if (g0 > s) out.push([s, g0]);
      if (g1 < e) out.push([g1, e]);
    }
    segs = out;
  }
  return segs.filter(([s, e]) => e - s > 0.06);
}

function roomLevels(r) { return r.floor === 'both' ? [0, 1] : [r.floor || 0]; }

// The 12 V day-power bus, drawn from layout audio_power: battery/distribution
// at the maze center line, 14 AWG bus running both directions between floors,
// inline +/− terminal blocks per room, quadrant USB chargers for 10 ft USB
// drops, RUT140 on 12 V, and Pi power via a 12 V→PoE adapter.
function buildAudioPowerLayer(L) {
  const cfg = L.audio_power;
  if (!cfg || cfg.enabled === false) return;
  const power = new THREE.Group();
  power.name = 'backside audio + day power';
  levelGroups[2].add(power);

  const batteryMat = new THREE.MeshStandardMaterial({ color: 0x26352d, roughness: 0.72, metalness: 0.08 });
  const chargerMat = new THREE.MeshStandardMaterial({ color: 0x222936, roughness: 0.62, metalness: 0.16 });
  // 14/2 marine duplex is black-jacketed; drawn oxide red so the run reads
  // against the night ground (same license as the strap orange)
  const cableMat = new THREE.MeshStandardMaterial({ color: 0x86301a, roughness: 0.8, metalness: 0.05, emissive: 0x2a0a05 });
  const convMat = new THREE.MeshStandardMaterial({ color: 0x3d4652, roughness: 0.45, metalness: 0.55 });
  const gearMat = new THREE.MeshStandardMaterial({ color: 0x14171c, roughness: 0.55, metalness: 0.3 });
  const terminalMat = new THREE.MeshStandardMaterial({ color: 0xddd3bd, roughness: 0.65, metalness: 0.04 });
  const usbMat = new THREE.MeshStandardMaterial({ color: 0x0f253f, roughness: 0.75, metalness: 0.04, emissive: 0x03101c });
  const busY = cfg.bus_y || 0.2;
  const backZ = cfg.back_z || 0.28;
  const J = cfg.bus_bars && cfg.bus_bars.pos;
  const Jy = cfg.bus_bars && cfg.bus_bars.y != null ? cfg.bus_bars.y : busY;

  const cable = (ax, ay, az, bx, by, bz, r = 0.012, material = cableMat) => {
    const a = new THREE.Vector3(ax, ay, az);
    const d = new THREE.Vector3(bx - ax, by - ay, bz - az);
    const len = d.length();
    if (len < 0.02) return;
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 6), material);
    m.position.copy(a).addScaledVector(d, 0.5);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize());
    power.add(m);
  };
  const tag = (text, x, y, z, scale) => {
    const s = makeLabel(text, scale || 0.13);
    s.position.set(x, y, z);
    power.add(s);
  };

  if (cfg.battery) {
    const d = cfg.battery.dim_m || [0.34, 0.19, 0.22];
    const [x, z] = cfg.battery.pos;
    const b = new THREE.Mesh(new THREE.BoxGeometry(d[0], d[2], d[1]), batteryMat);
    b.position.set(x, d[2] / 2, z);
    power.add(b);
    tag(cfg.battery.label || '12V 100Ah', x, d[2] + 0.22, z, 0.15);
  }
  if (cfg.charger) {
    const d = cfg.charger.dim_m || [0.18, 0.06, 0.08];
    const [x, z] = cfg.charger.pos;
    const c = new THREE.Mesh(new THREE.BoxGeometry(d[0], d[2], d[1]), chargerMat);
    c.position.set(x, d[2] / 2, z);
    power.add(c);
    tag('charger', x + 0.14, d[2] + 0.14, z, 0.11);
  }

  // battery(+) jumper up to the breaker/bus bars on the hex corner frame
  if (J) {
    if (cfg.battery) {
      const bd = cfg.battery.dim_m || [0.34, 0.19, 0.22];
      cable(cfg.battery.pos[0], bd[2], cfg.battery.pos[1], J[0], Jy + 0.14, J[1], 0.009);
    }
    const brk = new THREE.Mesh(new THREE.BoxGeometry(0.075, 0.05, 0.04), gearMat);
    brk.position.set(J[0], Jy + 0.16, J[1]);
    power.add(brk);
    tag(cfg.bus_bars.label || '15 A → bus bars', J[0], Jy + 0.44, J[1], 0.12);
  }

  // the two 14/2 legs (polylines at bus height)
  for (const route of (cfg.bus_routes || [])) {
    for (let i = 0; i + 1 < route.length; i++) {
      cable(route[i][0], busY, route[i][1], route[i + 1][0], busY, route[i + 1][1]);
    }
  }
  if (cfg.bus_routes && cfg.bus_routes.length) {
    tag('12 V day bus', 4.46, busY + 0.26, backZ, 0.15);
  }

  // rack riser (west-leg tap at the hex SW corner up the shared frame)
  if (cfg.riser) {
    const R = cfg.riser;
    cable(R.x, R.y0 != null ? R.y0 : busY, R.z, R.x, R.y1, R.z, 0.009);
  }

  // one 4-port buck per stacked bay pair + the hex and rack stations;
  // each gets its input pigtail back to where it actually taps
  const cd = (cfg.converter && cfg.converter.dim_m) || [0.11, 0.06, 0.035];
  for (const cv of (cfg.converters || [])) {
    const y = cv.y != null ? cv.y : 0.72;
    const box = new THREE.Mesh(new THREE.BoxGeometry(cd[0], cd[2], cd[1]), convMat);
    box.position.set(cv.pos[0], y, cv.pos[1]);
    box.rotation.y = (cv.yaw_deg || 0) * Math.PI / 180;
    power.add(box);
    tag(cv.id, cv.pos[0], y + 0.15, cv.pos[1], 0.11);
    if (cv.feed === 'bus_bars' && J) {
      cable(J[0], Jy, J[1], cv.pos[0], y - 0.02, cv.pos[1], 0.007);
    } else if (cv.tap) {
      cable(cv.tap[0], busY, cv.tap[1], cv.pos[0], y - 0.02, cv.pos[1], 0.007);
    } else if (cv.feed === 'riser' && cfg.riser) {
      cable(cfg.riser.x, y, cfg.riser.z, cv.pos[0], y, cv.pos[1], 0.007);
    } else {
      cable(cv.pos[0], busY, backZ, cv.pos[0], y - 0.02, cv.pos[1], 0.007);
    }
  }

  // inline +/− terminal blocks, ring-connected in series on the 14 AWG bus
  const td = (cfg.terminal_block && cfg.terminal_block.dim_m) || [0.09, 0.035, 0.045];
  for (const tb of (cfg.terminal_blocks || [])) {
    const y = tb.y != null ? tb.y : busY;
    const [x, z] = tb.pos;
    const block = new THREE.Mesh(new THREE.BoxGeometry(td[0], td[1], td[2]), terminalMat);
    block.position.set(x, y, z);
    power.add(block);
    tag('+/- TERM', x, y + 0.13, z, 0.085);
  }

  // 10 ft USB drops from the quadrant chargers to each ESP32 enclosure
  const groups = [
    ['USB-Q1', ['Vertical Moop March', 'Monkey Room', 'Bike Lock Room']],
    ['USB-Q2', ['Temple Room', 'Deep Playa Handshake', 'No Friends Monday', 'Photo Bomb Room']],
    ['USB-Q3', ['Exit', 'Entrance', 'Cuddle Cross', 'Cop Dodge']],
    ['USB-Q4', ['Porto Room', 'Gate', 'Sparkle Pony Room', 'Guy Line Climb']],
  ];
  const convById = new Map((cfg.converters || []).map(c => [c.id, c]));
  for (const [cid, rooms] of groups) {
    const cv = convById.get(cid);
    if (!cv) continue;
    const cy = cv.y != null ? cv.y : busY;
    for (const roomName of rooms) {
      const enc = L.rooms[roomName] && L.rooms[roomName].enclosure;
      if (!enc) continue;
      const lv = enc.level != null ? enc.level : ((L.rooms[roomName].floor || 0) === 1 ? 1 : 0);
      cable(cv.pos[0], cy, cv.pos[1], enc.pos[0], lv * (L.level_height || 1.93) + (enc.h || 1.55), enc.pos[1], 0.004, usbMat);
    }
  }

  // RUT140 on 12 V at the top of the riser, antenna up
  if (cfg.rut140) {
    const [x, z] = cfg.rut140.pos;
    const r = new THREE.Mesh(new THREE.BoxGeometry(0.10, 0.083, 0.03), gearMat);
    r.position.set(x, cfg.rut140.y, z);
    power.add(r);
    const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.11, 6), gearMat);
    ant.position.set(x + 0.04, cfg.rut140.y + 0.095, z);
    power.add(ant);
    tag(cfg.rut140.label || 'RUT140', x, cfg.rut140.y + 0.24, z, 0.12);
    if (J) cable(J[0], Jy, J[1], x, cfg.rut140.y, z, 0.006);
  }
  if (cfg.poe_adapter) {
    const [x, z] = cfg.poe_adapter.pos;
    const y = cfg.poe_adapter.y != null ? cfg.poe_adapter.y : 0.45;
    const p = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.045, 0.055), gearMat);
    p.position.set(x, y, z);
    power.add(p);
    tag(cfg.poe_adapter.label || '12V→PoE', x, y + 0.19, z, 0.11);
    if (J) cable(J[0], Jy, J[1], x, y, z, 0.006);
    if (L.server_rack) cable(x, y, z, L.server_rack.pos[0], (L.server_rack.h || 0.28), L.server_rack.pos[1], 0.005, usbMat);
  }
}

function buildMaze(cfg) {
  const L = cfg.layout;
  const LH = S.levelHeight = L.level_height || 3.2;
  const CH = L.ceiling_height || 3.0;
  const T = L.wall_thickness || 0.12;
  // doorway openings to carve out of the shared wing walls. These used to be
  // implied by the break-beam sensor segs; the sensors live inside the room
  // node boxes now, so L.doorways declares the arches explicitly (any future
  // beam-kind sensor still carves for back-compat).
  const beams = (L.doorways || []).map(d => ({ seg: d.seg, level: d.level || 0 }))
    .concat(Object.entries(L.sensors)
      .filter(([, s]) => s.kind === 'beam' && s.seg)
      .map(([, s]) => ({ seg: s.seg, level: s.level || 0 })));

  // playa dust — pale alkali flat, dimly moonlit
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(320, 320),
    new THREE.MeshStandardMaterial({ color: 0x8d7f68, roughness: 1, metalness: 0 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(10, 0, 8);
  ground.userData.ground = true;
  ground.userData.level = 0;
  levelGroups[2].add(ground);

  const hexRooms = new Set(Object.values((L.hex_center || {}).rooms || {}));

  // far ends of the maze strip: there the skin hangs on the OUTSIDE of the
  // end frames — the inside stays bare scaffold so visitors climb the frame
  // rungs up (Guy Line Climb) and down (Vertical Moop March)
  const wings = Object.entries(L.rooms).filter(([n]) => !hexRooms.has(n)).map(([, r]) => r);
  const endW = Math.min(...wings.map(r => r.x));
  const endE = Math.max(...wings.map(r => r.x + r.w));

  for (const [name, r] of Object.entries(L.rooms)) {
    if (hexRooms.has(name)) continue; // built by buildHexCenter below
    const isBoth = r.floor === 'both';
    const baseLevel = isBoth ? 0 : (r.floor || 0);
    const yBase = baseLevel * LH;

    // floor slab (upper rooms get a real slab you stand on; 'both' rooms one at ground)
    const slab = new THREE.Mesh(new THREE.BoxGeometry(r.w, 0.14, r.d), matFloorBase());
    slab.position.set(r.x + r.w / 2, yBase + 0.07, r.z + r.d / 2);
    slab.userData.ground = true;
    slab.userData.level = baseLevel;
    grp(isBoth ? 'both' : baseLevel).add(slab);

    const center = new THREE.Vector3(r.x + r.w / 2, yBase + 1.5, r.z + r.d / 2);
    S.roomsMeshes[name] = { slab, center, level: baseLevel, room: r };

    // roof over the top of the structure (real build has one)
    if (baseLevel === 1 || isBoth) {
      const roof = new THREE.Mesh(new THREE.BoxGeometry(r.w, 0.05, r.d), matRoof);
      roof.position.set(r.x + r.w / 2, LH + CH + 0.06, r.z + r.d / 2);
      roofGroup.add(roof);
    }

    // room label above its open face (like the elevation drawing)
    const label = makeLabel(name, 0.24);
    const labelLevel = isBoth ? 1 : baseLevel;
    label.position.set(r.x + r.w / 2, labelLevel * LH + CH + 0.14, r.z + r.d + 0.08);
    grp(isBoth ? 'both' : baseLevel).add(label);

    // printed-canvas backdrop on the back wall ('both' rooms: one tall print
    // spanning both stories, like the real full-height climb-shaft canvases)
    if (r.background) {
      const bh = (isBoth ? LH + CH : CH) - 0.24;
      mountCanvas(r.background, r.w - 0.12, bh,
        new THREE.Vector3(r.x + r.w / 2, yBase + 0.16 + bh / 2, r.z + T / 2 + 0.012),
        0, grp(isBoth ? 'both' : baseLevel), name);
    }

    // walls per level: back (north) + west + east. NO street wall — open face.
    const wallHeight = isBoth ? LH + CH : CH;
    const wallLevels = isBoth ? [{ y: 0, h: LH + CH, lv: 'both' }]
      : [{ y: yBase, h: CH, lv: baseLevel }];
    for (const wl of wallLevels) {
      // adjacent rooms share one scaffold frame: nudge west/east panels inward
      // so both rooms' panels abut at the shared boundary without z-fighting.
      // At the maze's far ends the panel flips OUTSIDE the end frame instead,
      // leaving the frame's rungs exposed to the room for the climb.
      const skin = T / 2 + 0.004;
      const walls = [
        ['x', r.z, r.x, r.x + r.w, 0],                                        // back wall (north)
        ['z', r.x, r.z, r.z + r.d, r.x - endW < 0.01 ? -skin : skin],         // west
        ['z', r.x + r.w, r.z, r.z + r.d, endE - (r.x + r.w) < 0.01 ? skin : -skin], // east
      ];
      for (const [axis, fixed0, s0, s1, off] of walls) {
        const fixed = fixed0 + (off || 0);
        const gaps = [];
        for (const b of beams) {
          const [[x1, z1], [x2, z2]] = b.seg;
          // carve only if the beam belongs to a level this wall spans
          const beamBase = b.level * LH;
          if (beamBase + 0.5 < wl.y || beamBase > wl.y + wl.h) continue;
          if (axis === 'x' && Math.abs(z1 - z2) < 0.01 && Math.abs(z1 - fixed) <= 0.85) {
            const lo = Math.min(x1, x2), hi = Math.max(x1, x2);
            if (hi > s0 && lo < s1) gaps.push([lo - 0.15, hi + 0.15, b.level]);
          } else if (axis === 'z' && Math.abs(x1 - x2) < 0.01 && Math.abs(x1 - fixed) <= 0.85) {
            const lo = Math.min(z1, z2), hi = Math.max(z1, z2);
            if (hi > s0 && lo < s1) gaps.push([lo - 0.15, hi + 0.15, b.level]);
          }
        }
        if (!gaps.length) {
          const len = s1 - s0;
          const wall = new THREE.Mesh(
            new THREE.BoxGeometry(axis === 'x' ? len : T, wl.h, axis === 'x' ? T : len), matWall);
          wall.position.set(axis === 'x' ? s0 + len / 2 : fixed, wl.y + wl.h / 2,
            axis === 'x' ? fixed : s0 + len / 2);
          grp(wl.lv === 'both' ? 'both' : wl.lv).add(wall);
          continue;
        }
        // build per-level bands so a door on one floor doesn't hole the other
        const bands = wl.lv === 'both'
          ? [{ y: 0, h: LH, lv: 0 }, { y: LH, h: CH, lv: 1 }]
          : [{ y: wl.y, h: wl.h, lv: wl.lv }];
        for (const band of bands) {
          const bandGaps = gaps.filter(g => g[2] * LH >= band.y - 0.1 && g[2] * LH < band.y + band.h)
            .map(g => [g[0], g[1]]);
          for (const [w0, w1] of carve(s0, s1, bandGaps)) {
            const len = w1 - w0;
            const wall = new THREE.Mesh(
              new THREE.BoxGeometry(axis === 'x' ? len : T, band.h, axis === 'x' ? T : len), matWall);
            wall.position.set(axis === 'x' ? w0 + len / 2 : fixed, band.y + band.h / 2,
              axis === 'x' ? fixed : w0 + len / 2);
            grp(wl.lv === 'both' ? 'both' : band.lv).add(wall);
          }
        }
      }
    }

  }

  // scaffold cross members: end-frame rungs at every shared boundary, and
  // X-braces on each bay's back plane per level — the mounting surfaces for
  // lights and sensors
  {
    const sample = Object.entries(L.rooms).find(([n]) => !hexRooms.has(n))[1];
    const rz = sample.z, rd = sample.d;
    const boundaries = new Set();
    for (const [name, r] of Object.entries(L.rooms)) {
      if (hexRooms.has(name)) continue;
      boundaries.add(+r.x.toFixed(2));
      boundaries.add(+(r.x + r.w).toFixed(2));
    }
    const bs = [...boundaries].sort((a, b) => a - b);
    // one painted walk-thru frame per boundary per level (shared between bays);
    // blue/green alternate like our repainted mixed fleet. The wings' hex-side
    // ends land ON the hexagon's flat east/west frames — one shared frame in
    // reality (the wing bays' braces pin straight to it), already drawn by
    // buildHexCenter, so skip the coincident boundary here.
    const hexC = L.hex_center;
    const hexFaceX = hexC ? [hexC.cx - hexC.side * Math.cos(Math.PI / 6),
      hexC.cx + hexC.side * Math.cos(Math.PI / 6)] : [];
    bs.forEach((bx, i) => {
      if (hexFaceX.some(f => Math.abs(bx - f) < 0.02)) return;
      for (const lv of [0, 1]) {
        const frame = buildFrameSeg(bx, rz + 0.045, bx, rz + rd - 0.045, lv * LH,
          matFramePaint[(i + lv) % 2]);
        grp(lv).add(frame);
      }
    });
    // 7' x 4' tube cross braces (PSV-303): a riveted scissor pinned to the
    // leg studs — top stud 8.5" down from the frame top, bottom stud 4'
    // below — so the X leans leg-to-leg across the full 7' bay and crosses
    // above mid-height, exactly like the set photo
    const STUD_TOP = 1.7145, STUD_BOT = 0.4953;
    for (let i = 0; i < bs.length - 1; i++) {
      const x0 = bs[i], x1 = bs[i + 1];
      if (x1 - x0 > 2.2) continue; // hexagon span, no wing bay here
      const dx = x1 - x0;
      const len = Math.hypot(dx, STUD_TOP - STUD_BOT);
      for (const lv of [0, 1]) {
        for (const zb of [rz + 0.085, rz + rd - 0.085]) { // back AND front planes
          for (const dir of [1, -1]) {
            const brace = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, len), matGalv);
            // scissor halves sit a tube apart at the center rivet
            brace.position.set((x0 + x1) / 2, lv * LH + (STUD_TOP + STUD_BOT) / 2, zb + dir * 0.012);
            brace.rotation.z = Math.atan2(dir * (STUD_TOP - STUD_BOT), dx) - Math.PI / 2;
            grp(lv).add(brace);
          }
        }
      }
    }
    // flat plywood discs screwed to a bay's brace scissor at the center rivet
    // (per-room `brace_disc` key): Sparkle Pony's 3 ft circle on the rear plane.
    // A bay IS its room's x-span, so the rivet sits at the room's x center.
    for (const [name, r] of Object.entries(L.rooms)) {
      const bd = r.brace_disc;
      if (!bd || hexRooms.has(name)) continue;
      const lv = bd.level != null ? bd.level : (r.floor === 1 ? 1 : 0);
      const side = bd.plane === 'front' ? -1 : 1;   // which way the room lies
      const zb = bd.plane === 'front' ? r.z + r.d - 0.085 : r.z + 0.085;
      const rad = ((bd.diameter_ft || 2) * 0.3048) / 2;
      const disc = new THREE.Mesh(new THREE.CylinderGeometry(rad, rad, 0.018, 48), matPly);
      disc.rotation.x = Math.PI / 2;
      // back face flush on the room-side scissor half: half offset + tube R + half ply
      disc.position.set(r.x + r.w / 2, lv * LH + (STUD_TOP + STUD_BOT) / 2,
        zb + side * (0.012 + 0.011 + 0.009));
      grp(lv).add(disc);
    }
  }

  if (L.hex_center) buildHexCenter(L);
  if (L.entrance_towers) buildEntranceTowers(L);
  buildCampLayout();

  // ladders (climb points between floors)
  for (const lad of (L.ladders || [])) {
    const [lx, lz] = lad.pos;
    const ladder = new THREE.Group();
    for (const dx of [-0.25, 0.25]) {
      const rail = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, S.levelHeight + 1.0), matGalv);
      rail.position.set(lx + dx, (S.levelHeight + 1.0) / 2, lz);
      ladder.add(rail);
    }
    for (let i = 1; i <= 8; i++) {
      const rung = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.5), matGalv);
      rung.rotation.z = Math.PI / 2;
      rung.position.set(lx, i * (S.levelHeight / 8), lz);
      ladder.add(rung);
    }
    const hit = new THREE.Mesh(new THREE.BoxGeometry(1.3, S.levelHeight + 1, 1.3),
      new THREE.MeshBasicMaterial({ visible: false }));
    hit.position.set(lx, (S.levelHeight + 1) / 2, lz);
    hit.userData.ladder = { room: lad.room, x: lx, z: lz };
    ladder.add(hit);
    S.interactables.push(hit);
    S.ladders.push({ room: lad.room, x: lx, z: lz });
    levelGroups[2].add(ladder);
  }

  // server box: the RPi + USB-DMX enclosure mounts on the OUTSIDE of the
  // back wall, behind Cuddle Cross on the shared frame between Cuddle Cross
  // and Photo Bomb Room — not inside the hex
  if (L.server_rack) {
    const [rx, rz] = L.server_rack.pos;
    const lv = L.server_rack.level || 0;
    const yBase = lv * LH;
    const rh = L.server_rack.h != null ? L.server_rack.h : 1.05;
    const box = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.46, 0.16),
      new THREE.MeshStandardMaterial({ color: 0x101318, roughness: 0.6, metalness: 0.4 }));
    box.position.set(rx, yBase + rh, rz);
    grp(lv).add(box);
    const led = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, 0.02),
      new THREE.MeshBasicMaterial({ color: 0x33ff66 }));
    led.position.set(rx + 0.1, yBase + (L.server_rack.h != null ? L.server_rack.h : 1.05) + 0.15, rz - 0.085); // faces out the back
    grp(lv).add(led);
  }

  // per-room node enclosures — the wooden sensor boxes from
  // wiring-guides/room-node-enclosure-plan.md (XIAO C3 + the room's ranging
  // sensor + power), hose-clamped to a frame member: wing bays on the ENTRY-side
  // front leg at 1.55 m with the radar window (local +z) aimed at the
  // diagonally-opposite back corner. The two shafts carry `tilt_deg: -90` — box
  // at the TOP of the room with the window facing straight down. Radar boxes are
  // sealed (mmWave passes plywood); Entrance/Exit are the only two with an
  // aperture, because 940 nm doesn't. The room's sensor
  // wedge/boresight is drawn by buildSensors from the matching `sensors` entry;
  // pos/aim here come from the per-room "enclosure" entries.
  for (const r of Object.values(L.rooms)) {
    const enc = r.enclosure;
    if (!enc) continue;
    const lv = enc.level != null ? enc.level : (r.floor === 1 ? 1 : 0);
    const eg = new THREE.Group();
    eg.position.set(enc.pos[0], lv * LH + (enc.h || 1.55), enc.pos[1]);
    eg.rotation.y = (enc.yaw_deg || 0) * Math.PI / 180;
    eg.rotation.x = -(enc.tilt_deg || 0) * Math.PI / 180;
    const box = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.22, 0.10), matPly);
    eg.add(box);
    // thinned window panel the radar looks through
    const win = new THREE.Mesh(new THREE.PlaneGeometry(0.07, 0.07),
      new THREE.MeshStandardMaterial({ color: 0x23242b, roughness: 0.5 }));
    win.position.z = 0.0505;
    eg.add(win);
    const led = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.012, 0.006),
      new THREE.MeshBasicMaterial({ color: 0x33ff66 }));
    led.position.set(0.06, 0.085, 0.0505);
    eg.add(led);
    grp(lv).add(eg);
  }

  // Photo Bomb webcam: metal standoff arm from open face, camera outside looking inward
  for (const r of Object.values(L.rooms)) {
    const cm = r.camera_mount;
    if (!cm) continue;
    const lv = cm.level != null ? cm.level : (r.floor === 1 ? 1 : 0);
    const y = lv * LH + (cm.h || 1.45);
    const [x, z] = cm.pos;
    const armLen = cm.arm_len || 0.4;
    const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, armLen, 10), matGalv);
    arm.position.set(x, y, z + armLen / 2);
    arm.rotation.x = Math.PI / 2;
    grp(lv).add(arm);
    const cam = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.07, 0.06),
      new THREE.MeshStandardMaterial({ color: 0x0c1018, roughness: 0.45, metalness: 0.35 }));
    cam.position.set(x, y, z + armLen);
    cam.rotation.y = (cm.yaw_deg || 180) * Math.PI / 180;
    grp(lv).add(cam);
  }

  buildAudioPowerLayer(L);
}

// ---------------------------------------------------------------- hex center
// The center is a hexagon of SIX complete 5' walk-thru frames per level (12
// total) — real pieces only, hose-clamped in pairs at every corner, NO cross
// braces. A CORNER points at the street: the two angled street frames meeting
// at it are the split entry (START, east) and exit (FINISH, west) — each
// frame's walk-thru arch is one door. The flat east/west frames' arches are
// how the side rooms walk into the center. The two back frames are skinned.
// Ground: Exit (west half) + Entrance (east half). Upper deck: Cuddle Cross.
function buildHexCenter(L) {
  const H = L.hex_center;
  const LH = L.level_height || 2.03, CH = L.ceiling_height || 1.98;
  const cx = H.cx, cz = H.cz, R = H.side;
  const V = [];
  for (let k = 0; k < 6; k++) {
    const a = Math.PI / 6 + k * Math.PI / 3; // 30,90,...: corners to street/back, flats to the wings
    V.push([cx + R * Math.cos(a), cz + R * Math.sin(a)]);
  }
  // V[1]=front corner (street), V[4]=back corner; faces: [V0,V1]=entry,
  // [V1,V2]=exit, [V2,V3]=west wing door, [V3,V4]/[V4,V5]=back, [V5,V0]=east wing door

  const slabShape = (pts, holePts) => {
    const sh = new THREE.Shape();
    pts.forEach(([x, z], i) => i ? sh.lineTo(x, -z) : sh.moveTo(x, -z)); // shape-y = -world-z
    if (holePts) {
      const hp = new THREE.Path();
      holePts.forEach(([x, z], i) => i ? hp.lineTo(x, -z) : hp.moveTo(x, -z));
      sh.holes.push(hp); // ExtrudeGeometry normalizes hole winding itself
    }
    const geo = new THREE.ExtrudeGeometry(sh, { depth: 0.14, bevelEnabled: false });
    geo.rotateX(-Math.PI / 2); // lie flat: extrusion becomes +y
    return geo;
  };
  // the wings end a hair past the hex flats — bridge the sliver so the floor
  // runs continuous through the wing doorways
  const wingW = L.rooms[H.rooms.ground_west].x;
  const geRoom = L.rooms[H.rooms.ground_east];
  const wingE = geRoom.x + geRoom.w;
  const halves = {
    [H.rooms.ground_west]: [V[1], V[2], [wingW, V[2][1]], [wingW, V[3][1]], V[3], V[4]],
    [H.rooms.ground_east]: [V[1], V[4], V[5], [wingE, V[5][1]], [wingE, V[0][1]], V[0]],
  };
  const deck = [V[1], V[2], [wingW, V[2][1]], [wingW, V[3][1]], V[3], V[4],
    V[5], [wingE, V[5][1]], [wingE, V[0][1]], V[0]];
  for (const [room, pts] of Object.entries(halves)) {
    const slab = new THREE.Mesh(slabShape(pts), matFloorBase());
    slab.userData.ground = true; slab.userData.level = 0;
    levelGroups[0].add(slab);
    const xs = pts.map(p => p[0]);
    const c = new THREE.Vector3((Math.min(...xs) + Math.max(...xs)) / 2, 1.0, cz);
    S.roomsMeshes[room] = { slab, center: c, level: 0, room: L.rooms[room], poly: pts };
    // label above the half's angled street frame
    const sf = room === H.rooms.ground_east ? [V[0], V[1]] : [V[1], V[2]];
    const lbl = makeLabel(room, 0.24);
    lbl.position.set((sf[0][0] + sf[1][0]) / 2, CH + 0.14, (sf[0][1] + sf[1][1]) / 2 + 0.15);
    levelGroups[0].add(lbl);
  }
  // the Cuddle deck reads as what it really is: plywood over the deck steel
  // (own instance — effects tint its emissive, the Steel button ghosts it)
  const matDeckPly = new THREE.MeshStandardMaterial({ color: 0x8d7148, roughness: 0.9, metalness: 0.02 });
  const upSlab = new THREE.Mesh(slabShape(deck), matDeckPly);
  upSlab.position.y = LH;
  upSlab.userData.ground = true; upSlab.userData.level = 1;
  steelGhosts.push(upSlab.material); // fade the ply while the deck steel shows
  levelGroups[1].add(upSlab);
  S.roomsMeshes[H.rooms.upper] = {
    slab: upSlab, center: new THREE.Vector3(cx, LH + 1, cz), level: 1, room: L.rooms[H.rooms.upper],
    poly: deck,
  };
  const upLbl = makeLabel(H.rooms.upper, 0.24);
  upLbl.position.set(cx, LH + CH + 0.14, V[1][1] + 0.12);
  levelGroups[1].add(upLbl);

  // skin: only the two back faces are walled; the four street/wing faces
  // stay open — their frames' arches are the doors
  for (const lv of [0, 1]) {
    for (const [a, b] of [[V[3], V[4]], [V[4], V[5]]]) {
      const dx = b[0] - a[0], dz = b[1] - a[1];
      const wall = new THREE.Mesh(new THREE.BoxGeometry(Math.hypot(dx, dz), CH, 0.05), matWall);
      wall.position.set((a[0] + b[0]) / 2, lv * LH + CH / 2, (a[1] + b[1]) / 2);
      wall.rotation.y = -Math.atan2(dz, dx);
      levelGroups[lv].add(wall);
    }
    // Exit | Entrance divider on the ground floor only: back corner to front
    // corner, so the split lands exactly where the two street frames meet
    // and the halves only connect through the wings
    if (lv === 0) {
      const div = new THREE.Mesh(new THREE.BoxGeometry(0.05, CH, R * 2 - 0.08), matWall);
      div.position.set(cx, CH / 2, cz);
      levelGroups[0].add(div);
    }
  }

  // the two wide printed canvases: each spans BOTH skinned back faces — the
  // west face shows the left half, the east face the right half, continuous
  // across the shared back corner (ground: Exit|Entrance, upper: Cuddle Cross)
  const BGS = H.backgrounds || {};
  for (const [lv, url, bgRooms] of [
    [0, BGS.ground, [H.rooms.ground_west, H.rooms.ground_east]],
    [1, BGS.upper, [H.rooms.upper, H.rooms.upper]],
  ]) {
    if (!url) continue;
    [[V[3], V[4]], [V[4], V[5]]].forEach(([a, b], fi) => {
      const dx = b[0] - a[0], dz = b[1] - a[1];
      const len = Math.hypot(dx, dz);
      const nx = -dz / len, nz = dx / len; // inward, toward the hex center
      const bh = CH - 0.24;
      mountCanvas(url, len - 0.1, bh,
        new THREE.Vector3((a[0] + b[0]) / 2 + nx * 0.05, lv * LH + 0.16 + bh / 2,
          (a[1] + b[1]) / 2 + nz * 0.05),
        Math.atan2(nx, nz), levelGroups[lv], bgRooms[fi], [fi * 0.5, fi * 0.5 + 0.5]);
    });
  }

  // hex roof (covers the wing-doorway slivers too) — with the real climb-out
  // hole in its SW corner wedge (the rear corner beside the Photo Bomb arch):
  // roof steel and ply stop short there, so the corner legs are the ladder up.
  // Outline comes from the fab drawing via deck_steel.js.
  const DS = window.DECK_STEEL, IN = 0.0254;
  const kSteel = DS ? (R * Math.cos(Math.PI / 6)) / (DS.cad_apothem_in * IN) : 1;
  const roofHole = DS && DS.roof_hole.map(([hx, hz]) => [cx + hx * IN * kSteel, cz + hz * IN * kSteel]);
  const matHexRoof = matRoof.clone();
  const roof = new THREE.Mesh(slabShape(deck, roofHole), matHexRoof);
  roof.position.y = LH + CH + 0.02;
  roofGroup.add(roof);
  steelGhosts.push(matHexRoof);

  // six complete walk-thru frames per level: legs at BOTH ends, nudged a hair
  // in from each corner so the two neighbouring frames' legs stand side by
  // side inside one clamp — how the real (welded) frames actually join
  const EPS = 0.026;
  for (let k = 0; k < 6; k++) {
    const a = V[k], b = V[(k + 1) % 6];
    const ux = (b[0] - a[0]) / R, uz = (b[1] - a[1]) / R;
    for (const lv of [0, 1]) {
      grp(lv).add(buildFrameSeg(a[0] + ux * EPS, a[1] + uz * EPS,
        b[0] - ux * EPS, b[1] - uz * EPS, lv * LH, matFramePaint[(k + lv) % 2]));
    }
  }
  // hose-clamp blocks around each corner's leg pair — except the TOP block
  // at the projection rig's corner: the rig's arm bracket is the hardware
  // there, and the decorative block (33 mm radius on the idealized vertex;
  // real legs stand in pairs OUTSIDE the V point) would poke through the
  // drawn projector body, which hangs with its rear face 15 mm off the legs
  const PJ = ((L.projection || {}).projector || {}).pos;
  for (const [vx, vz] of V) {
    for (const cy of [0.35, 1.05, 1.7, LH + 0.35, LH + 1.05, LH + 1.7]) {
      if (PJ && cy > LH + 1.6 && Math.hypot(vx - PJ[0], vz - PJ[1]) < 0.25) continue;
      const clamp = new THREE.Mesh(new THREE.CylinderGeometry(0.033, 0.033, 0.06), matGalv);
      clamp.position.set(vx, cy, vz);
      grp(cy > LH ? 1 : 0).add(clamp);
    }
  }

  // the center mast: a SINGLE continuous 20 ft stick of 3" schedule 40 pipe
  // (3.5" OD) standing at the exact hex center — up from the ground where
  // the Exit|Entrance divider meets the middle, through the Cuddle Cross
  // deck and the hex roof, straight to the sky ~7 ft above the structure.
  // One piece, no joints; the deck and roof penetrations brace it. Lives in
  // the shared group so it shows on both floor filters.
  if (H.center_pole) {
    const pr = (H.center_pole.od || 0.0889) / 2;
    const ph = H.center_pole.height || 6.096;
    const mast = new THREE.Mesh(new THREE.CylinderGeometry(pr, pr, ph, 24), matGalv);
    mast.position.set(cx, ph / 2, cz);
    levelGroups[2].add(mast);
    if (H.beacon) buildBeacon(H, cx, cz);
  }

  // START / FINISH ply signs over the two street arches, angled with their
  // frames so they meet at the front corner like the photo
  for (const [txt, bgc, a, b] of [['START', '#7cc25e', V[0], V[1]], ['FINISH', '#e0679c', V[1], V[2]]]) {
    const mx = (a[0] + b[0]) / 2, mz = (a[1] + b[1]) / 2;
    const nx = mx - cx, nz = mz - cz;
    const nl = Math.hypot(nx, nz);
    const sign = makePaintedSign(txt, bgc);
    sign.position.set(mx + (nx / nl) * 0.07, 1.56, mz + (nz / nl) * 0.07);
    sign.lookAt(mx + nx, 1.56, mz + nz);
    levelGroups[0].add(sign);
  }

  buildDeckSteel(H, LH, kSteel);
  // steel shows by default — Tim wants the metal visible through the floor
  // and roof; the Steel button cycles it away and the choice sticks
  let savedSteel = null;
  try { savedSteel = localStorage.getItem('lohp-sim-steel'); } catch (e) { /* private mode */ }
  setSteelMode(STEEL_MODES.includes(savedSteel) ? savedSteel : 'both');
}

// The custom steel decks from the fab drawings (cad-items/main-floor.svg and
// top-floor.svg, baked into deck_steel.js by tools/deck_steel_from_cad.py):
// a 2" channel along each edge seated on the frame top rails, 1" bars kept
// top-flush with the channels — spoke pairs running from a collar around the
// mast out to each corner leg cluster, plus a joist bay per side under the
// ply seams — and the roof deck's cut-away SW corner wedge. The drawing's leg
// ring is ~3% wider than the sim's idealized hex (real corner legs stand in
// pairs OUTSIDE the V points), so members fit-scale onto the sim's rail line;
// true sizes live in the drawings.
// enough self-glow to read under the night sky against the ghosted ply —
// it's a reveal overlay, so softly luminous steel is the point, day or night
const matSteelChan = new THREE.MeshStandardMaterial({ color: 0x9aa2ad, roughness: 0.38, metalness: 0.7, emissive: 0x3a414c });
const matSteelBar = new THREE.MeshStandardMaterial({ color: 0x757c87, roughness: 0.5, metalness: 0.6, emissive: 0x2e343e });
function buildDeckSteel(H, LH, k) {
  const DS = window.DECK_STEEL;
  if (!DS) return;
  const IN = 0.0254;
  const RAIL_TOP = 1.874; // buildFrameSeg: top rail center 1.855 + 0.019 tube radius
  for (const [key, members, yBase] of [['deck', DS.main, 0], ['roof', DS.top, LH]]) {
    const g = steelGroups[key];
    const topY = yBase + RAIL_TOP + DS.chan_h_in * IN; // the ply bearing plane
    for (const m of members) {
      const h = (m.kind === 'chan' ? DS.chan_h_in : DS.bar_h_in) * IN;
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(m.len * IN * k, h, m.w * IN * k),
        m.kind === 'chan' ? matSteelChan : matSteelBar);
      mesh.position.set(H.cx + m.x * IN * k, topY - h / 2, H.cz + m.z * IN * k);
      mesh.rotation.y = -m.ang * Math.PI / 180;
      g.add(mesh);
    }
    // collar ring around the mast — true size, its bore hugs the 3.5" pipe
    const ring = new THREE.Shape();
    ring.absarc(0, 0, (DS.collar.od_in / 2) * IN, 0, Math.PI * 2, false);
    const bore = new THREE.Path();
    bore.absarc(0, 0, (DS.collar.id_in / 2) * IN, 0, Math.PI * 2, true);
    ring.holes.push(bore);
    const geo = new THREE.ExtrudeGeometry(ring, { depth: DS.bar_h_in * IN, bevelEnabled: false, curveSegments: 24 });
    geo.rotateX(-Math.PI / 2); // extrusion becomes +y
    const collar = new THREE.Mesh(geo, matSteelBar);
    collar.position.set(H.cx, topY - DS.bar_h_in * IN, H.cz);
    g.add(collar);
  }
}

// Painted-ply sign (the START / FINISH boards over the hex street doors);
// slight emissive so they read at night like the arch sign.
function makePaintedSign(text, bg, w = 0.62, h = 0.28) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = Math.round(256 * h / w);
  const g = c.getContext('2d');
  g.fillStyle = bg;
  g.fillRect(0, 0, c.width, c.height);
  g.strokeStyle = 'rgba(30,20,10,0.85)';
  g.lineWidth = 10;
  g.strokeRect(5, 5, c.width - 10, c.height - 10);
  g.fillStyle = '#241c10';
  g.font = `700 ${Math.round(c.height * 0.58)}px Georgia, 'Times New Roman', serif`;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(text, c.width / 2, c.height / 2 + 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshStandardMaterial({
      map: tex, side: THREE.DoubleSide, roughness: 0.9,
      emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: 0.18,
    }));
}

// ---------------------------------------------------------------- the beacon
// Four laser-cut tiki heads boxed square around the mast top, panel tops
// flush with the pole tip. Textures come from the REAL xTool cut files
// (cad-items/tiki-*.svg, served at /cad/): each SVG is one green rect
// (cls-1, the painted panel) plus one line-work path (cls-2) — the path is
// what the laser cuts THROUGH, so the sim recolors cls-1 to the forest-green
// paint and cls-2 to the LED backing color, and rasterizes a second
// black/white pass as the emissive mask so the cutouts read as light coming
// through the panel, not light paint on it.
const tikiSvgCache = new Map();
function tikiTexture(url, bg, fg, w = 640, h = 960) {
  if (!tikiSvgCache.has(url)) {
    tikiSvgCache.set(url, fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url}: ${r.status}`);
      return r.text();
    }));
  }
  return tikiSvgCache.get(url).then((svg) => new Promise((resolve, reject) => {
    const recolored = svg.replace(/<style>[\s\S]*?<\/style>/,
      `<style>.cls-1{fill:${bg};}.cls-2{fill:${fg};stroke:${fg};stroke-miterlimit:10;stroke-width:8px;}</style>`);
    const blobUrl = URL.createObjectURL(new Blob([recolored], { type: 'image/svg+xml' }));
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(blobUrl);
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      c.getContext('2d').drawImage(img, 0, 0, w, h);
      const tex = new THREE.CanvasTexture(c);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
      resolve(tex);
    };
    img.onerror = () => { URL.revokeObjectURL(blobUrl); reject(new Error(url)); };
    img.src = blobUrl;
  }));
}

function buildBeacon(H, cx, cz) {
  const B = H.beacon;
  const ph = H.center_pole.height || 6.096;
  const w = B.panel_w || 0.6096, h = B.panel_h || 0.9144;
  const paint = B.paint || '#228b22', led = B.led || '#ffd9a3';
  (B.faces || []).forEach((url, i) => {
    const yaw = i * Math.PI / 2;                     // street, east, back, west
    const nx = Math.sin(yaw), nz = Math.cos(yaw);
    const mat = new THREE.MeshStandardMaterial({
      roughness: 0.88, metalness: 0, side: THREE.DoubleSide,
      emissive: new THREE.Color(led),
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
    mesh.visible = false; // until the textures arrive
    mesh.position.set(cx + nx * w / 2, ph - h / 2, cz + nz * w / 2);
    mesh.rotation.y = yaw;
    levelGroups[2].add(mesh); // on the mast: shows in every floor filter
    Promise.all([tikiTexture(url, paint, led), tikiTexture(url, '#000000', '#ffffff')])
      .then(([map, mask]) => {
        mat.map = map;
        mat.emissiveMap = mask;
        mat.emissiveIntensity = 1.25;
        mat.needsUpdate = true;
        mesh.visible = true;
      })
      .catch(() => log('err', `beacon face missing: ${url}`));
  });
}

// ---------------------------------------------------------- entrance towers
// Two decorative towers flank the street path out front (maze-1.jpeg) with
// the "Legends of the Hidden Playa" sign arching between them. Each tower is
// three 3'x4' ladder frames hose-clamped into a triangle in plan — flat face
// to the street, apex toward the maze — stacked two tiers tall, skinned on
// the outside like the maze walls and guyed to playa stakes with orange
// ratchet straps. Purely decorative: no DMX fixtures, no sensors, no lights.
// The whole assembly lives in one group so the Towers button can hide it
// (it blocks part of the facade in street view).
let towersGroup = null;
function setTowersVisible(on) {
  if (!towersGroup) return;
  towersGroup.visible = on;
  $('btn-towers').textContent = on ? 'Towers ✓' : 'Towers ✕';
  try { localStorage.setItem('lohp-sim-towers', on ? '1' : '0'); } catch (e) { /* private mode */ }
}

function buildEntranceTowers(L) {
  const ET = L.entrance_towers;
  const FW = ET.frame_w, FH = ET.frame_h, TIERS = ET.tiers || 2;
  const towerH = FH * TIERS;
  const apexZ = ET.front_z - FW * Math.sin(Math.PI / 3);
  towersGroup = new THREE.Group();
  levelGroups[2].add(towersGroup); // street furniture: visible in every floor filter
  const g = towersGroup;

  for (const sx of [-1, 1]) {
    const cx = ET.cx + sx * (ET.spacing / 2);
    const V = [[cx - FW / 2, ET.front_z], [cx + FW / 2, ET.front_z], [cx, apexZ]];
    // three complete frames per tier, legs nudged a hair in from each corner
    // so neighbouring frames' legs stand side by side inside one clamp
    for (let k = 0; k < 3; k++) {
      const a = V[k], b = V[(k + 1) % 3];
      const ux = (b[0] - a[0]) / FW, uz = (b[1] - a[1]) / FW;
      for (let t = 0; t < TIERS; t++) {
        g.add(buildMiniFrameSeg(a[0] + ux * 0.026, a[1] + uz * 0.026,
          b[0] - ux * 0.026, b[1] - uz * 0.026, t * FH,
          matFramePaint[(k + t) % 2], { h: FH }));
      }
      // hose-clamp sleeves at the corner joint
      for (let t = 0; t < TIERS; t++) {
        for (const cy of [t * FH + 0.28, t * FH + 0.86]) {
          const clamp = new THREE.Mesh(new THREE.CylinderGeometry(0.033, 0.033, 0.06), matGalv);
          clamp.position.set(a[0], cy, a[1]);
          g.add(clamp);
        }
      }
    }
    // skin panels hang on the outside of all three faces
    const cz3 = (2 * ET.front_z + apexZ) / 3;
    for (let k = 0; k < 3; k++) {
      const a = V[k], b = V[(k + 1) % 3];
      const mx = (a[0] + b[0]) / 2, mz = (a[1] + b[1]) / 2;
      const nl = Math.hypot(mx - cx, mz - cz3);
      const skin = new THREE.Mesh(new THREE.BoxGeometry(FW + 0.05, towerH - 0.05, 0.03), matTowerSkin);
      skin.position.set(mx + ((mx - cx) / nl) * 0.055, towerH / 2, mz + ((mz - cz3) / nl) * 0.055);
      skin.rotation.y = -Math.atan2(b[1] - a[1], b[0] - a[0]);
      g.add(skin);
    }
    // the Towers print wraps the three outside faces: middle third on the
    // street face, continuing around each corner so the u-seam hides at the
    // back apex (which faces the maze, not the street)
    if (ET.skin_image) {
      const slices = [[1 / 3, 2 / 3], [2 / 3, 1], [0, 1 / 3]];
      for (let k = 0; k < 3; k++) {
        const a = V[k], b = V[(k + 1) % 3];
        const nx = -(b[1] - a[1]) / FW, nz = (b[0] - a[0]) / FW; // outward
        mountCanvas(ET.skin_image, FW + 0.02, towerH - 0.1,
          new THREE.Vector3((a[0] + b[0]) / 2 + nx * 0.075, towerH / 2, (a[1] + b[1]) / 2 + nz * 0.075),
          Math.atan2(nx, nz), g, null, slices[k]);
      }
    }
    // ratchet-strap guys: top front corners down to stakes on the opposite
    // side, crossing in front of the skin the way they do in the photo
    for (const s of [-1, 1]) {
      const top = new THREE.Vector3(cx + s * FW / 2, towerH - 0.03, ET.front_z + 0.075);
      const stake = new THREE.Vector3(cx - s * (FW / 2 + 1.15), 0.09, ET.front_z + 0.65);
      const dir = stake.clone().sub(top);
      const strap = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, dir.length()), matStrap);
      strap.position.copy(top).add(stake).multiplyScalar(0.5);
      strap.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
      g.add(strap);
      const stakeM = new THREE.Mesh(new THREE.CylinderGeometry(0.013, 0.013, 0.35), matGalv);
      stakeM.position.set(stake.x, 0.08, stake.z);
      stakeM.rotation.set(0.15, 0, -s * 0.2);
      g.add(stakeM);
    }
  }

  // the old painted-ply arch sign — only if the real DMX camp_sign isn't
  // configured (buildCampSign supersedes it; delete the layout key to revert)
  if (!L.camp_sign) {
    const sg = ET.sign || {};
    const band = sg.band || 0.58, medR = sg.medallion_r || 0.52;
    const endY = towerH + 0.02;               // band centerline where it meets the towers
    const apexY = endY + (sg.rise || 0.95);
    const y1 = apexY + medR + 0.06, y0 = endY - band / 2 - 0.10;
    const opts = {
      W: ET.spacing + 0.6, H: y1 - y0, y1, a: ET.spacing / 2, endY, apexY, band, medR,
      textLeft: sg.text_left || 'LEGENDS OF THE', textRight: sg.text_right || 'HIDDEN PLAYA',
    };
    for (const [withText, rotY, dz] of [[true, 0, 0.012], [false, Math.PI, -0.012]]) {
      const tex = makeArchSignTexture(Object.assign({ withText }, opts));
      const m = new THREE.Mesh(new THREE.PlaneGeometry(opts.W, opts.H),
        new THREE.MeshStandardMaterial({
          map: tex, alphaTest: 0.5, roughness: 0.85,
          emissive: 0xffffff, emissiveMap: tex, emissiveIntensity: 0.2,
        }));
      m.position.set(ET.cx, (y0 + y1) / 2, ET.front_z + 0.1 + dz);
      m.rotation.y = rotY;
      g.add(m);
    }
  }

  let show = true;
  try { show = localStorage.getItem('lohp-sim-towers') !== '0'; } catch (e) { /* private mode */ }
  setTowersVisible(show);
}

// ------------------------------------------------------------- camp layout
// The whole 4:30 & B camp lot around the maze (Jen's LotHP-26-v3.svg). ALL
// rendering lives in the separate camp_layout.js module — keep it there.
let campGroup = null;
function setCampVisible(on) {
  if (!campGroup) return;
  campGroup.visible = on;
  $('btn-camp').textContent = on ? 'Camp ✓' : 'Camp ✕';
  try { localStorage.setItem('lohp-sim-camp', on ? '1' : '0'); } catch (e) { /* private mode */ }
}

function buildCampLayout() {
  if (!window.CAMP_LAYOUT || !window.CAMP_DATA) return;
  campGroup = window.CAMP_LAYOUT.build(THREE);
  levelGroups[2].add(campGroup); // site plan: visible in every floor filter
  let show = true;
  try { show = localStorage.getItem('lohp-sim-camp') !== '0'; } catch (e) { /* private mode */ }
  setCampVisible(show);
}

// The arch sign as a canvas texture (same trick as makeLabel): a gold band
// along a circular arc through the tower tops and the apex, "LEGENDS OF THE"
// / "HIDDEN PLAYA" set along the curve, and the round medallion at the peak.
// withText=false renders the plain plywood back.
function makeArchSignTexture(o) {
  const K = 256; // px per meter
  const c = document.createElement('canvas');
  c.width = Math.ceil(o.W * K); c.height = Math.ceil(o.H * K);
  const g = c.getContext('2d');
  const X = (mx) => (mx + o.W / 2) * K;
  const Y = (my) => (o.y1 - my) * K;        // world meters -> px, y flipped
  // band centerline: the circle through the two end points and the apex
  const yc = (o.apexY * o.apexY - o.endY * o.endY - o.a * o.a) / (2 * (o.apexY - o.endY));
  const R = o.apexY - yc;
  const thEnd = Math.acos(Math.min(1, (o.a + 0.18) / R)); // ends tuck past the tower centers
  g.beginPath();
  g.arc(X(0), Y(yc), (R + o.band / 2) * K, -(Math.PI - thEnd), -thEnd, false);
  g.arc(X(0), Y(yc), (R - o.band / 2) * K, -thEnd, -(Math.PI - thEnd), true);
  g.closePath();
  if (o.withText) {
    const grad = g.createLinearGradient(0, Y(o.apexY + o.band / 2), 0, Y(o.endY - o.band / 2));
    grad.addColorStop(0, '#d6ac60'); grad.addColorStop(1, '#b18441');
    g.fillStyle = grad;
  } else {
    g.fillStyle = '#8a6b43';
  }
  g.fill();
  g.lineWidth = 0.028 * K;
  g.strokeStyle = o.withText ? '#5c4520' : '#54401f';
  g.stroke();

  const medCx = X(0), medCy = Y(o.apexY);
  if (!o.withText) { // plain disc backs the medallion; done
    g.beginPath(); g.arc(medCx, medCy, o.medR * K, 0, Math.PI * 2);
    g.fillStyle = '#8a6b43'; g.fill(); g.stroke();
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }

  // hand-painted lettering along the band centerline: measure both strings at
  // the base size, then shrink to the tighter side's fit so they match
  g.fillStyle = '#241c10';
  g.textAlign = 'center'; g.textBaseline = 'middle';
  const track = 0.012;
  const font = (px) => { g.font = `700 ${Math.round(px)}px Georgia, 'Times New Roman', serif`; };
  const seg = (text, x0, x1) => {
    const t0 = Math.acos(Math.max(-1, Math.min(1, x0 / R)));
    const t1 = Math.acos(Math.max(-1, Math.min(1, x1 / R)));
    return { text, t0, A: (t0 - t1) * R };
  };
  const segs = [seg(o.textLeft, -o.a + 0.22, -(o.medR + 0.14)),
    seg(o.textRight, o.medR + 0.14, o.a - 0.22)];
  const base = 0.34 * K;
  font(base);
  const natural = (t) => [...t].map(ch => g.measureText(ch).width / K).reduce((p, q) => p + q, 0)
    + track * (t.length - 1);
  font(base * Math.min(1, ...segs.map(sg => sg.A * 0.97 / natural(sg.text))));
  for (const sg of segs) {
    const ws = [...sg.text].map(ch => g.measureText(ch).width / K);
    let s = (sg.A - ws.reduce((p, q) => p + q, 0) - track * (sg.text.length - 1)) / 2;
    [...sg.text].forEach((ch, i) => {
      const th = sg.t0 - (s + ws[i] / 2) / R;
      g.save();
      g.translate(X(R * Math.cos(th)), Y(yc + R * Math.sin(th)));
      g.rotate(Math.PI / 2 - th);
      g.fillText(ch, 0, 0);
      g.restore();
      s += ws[i] + track;
    });
  }

  // the medallion: gold ring of dots around a dark disc with the ziggurat
  g.beginPath(); g.arc(medCx, medCy, o.medR * K, 0, Math.PI * 2);
  g.fillStyle = '#c9a052'; g.fill();
  g.lineWidth = 0.03 * K; g.strokeStyle = '#5c4520'; g.stroke();
  g.fillStyle = '#5c4520';
  for (let i = 0; i < 26; i++) {
    const a2 = (i / 26) * Math.PI * 2;
    g.beginPath();
    g.arc(medCx + Math.cos(a2) * (o.medR - 0.075) * K, medCy + Math.sin(a2) * (o.medR - 0.075) * K, 0.014 * K, 0, Math.PI * 2);
    g.fill();
  }
  g.beginPath(); g.arc(medCx, medCy, (o.medR - 0.15) * K, 0, Math.PI * 2);
  g.fillStyle = '#332c1c'; g.fill();
  g.fillStyle = '#c9a052';
  const steps = [[0.46, -0.155], [0.34, -0.08], [0.22, -0.005], [0.11, 0.07]]; // ziggurat
  for (const [w, yb] of steps) {
    g.fillRect(X(-w / 2), Y(o.apexY + yb + 0.075), w * K, 0.075 * K);
  }
  g.fillStyle = '#332c1c';
  g.fillRect(X(-0.035), Y(o.apexY - 0.075), 0.07 * K, 0.08 * K); // doorway

  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

// --------------------------------------------------------------- camp sign
// The REAL front sign (cad-items/camp-sign.svg → layout `camp_sign` key): a
// 14 ft arched band whose ends land flush on the two tower tops, carrying 23
// letters + the logo disc. Every letter/logo is one 8ch DMX zone from
// light_config.json room "Camp Sign" — on the build an ESP32 DMX bridge maps
// each zone to that letter's WS2811 pixels (wiring-guides/camp-sign-plan.md).
// Construction (letters-raised.jpg): each letter is a separate wood cut-out
// standing off the solid band on spacers, strip serpentined on its back with
// the LEDs facing the band — so here the DMX color drives an additive halo
// plane BEHIND an opaque scene-lit wood face, and themes/effects preview
// per-letter exactly as the wire will carry them. The CAD condenses its type
// to fit (scale(0.65 1) / (0.56 1)); the walk below does the same by
// narrowing glyphs to the available arc, never shrinking height.
let signGroup = null;
function setSignVisible(on) {
  if (!signGroup) return;
  signGroup.visible = on;
  $('btn-sign').textContent = on ? 'Sign ✓' : 'Sign ✕';
  try { localStorage.setItem('lohp-sim-sign', on ? '1' : '0'); } catch (e) { /* private mode */ }
}

const SIGN_UNLIT = 0.14; // unlit-LED gray floor

function buildCampSign(cfg) {
  const L = cfg.layout, CS = L.camp_sign, ET = L.entrance_towers;
  if (!CS || !ET) return;
  const lights = cfg.room_layout[CS.room] || [];
  if (!lights.length) log('err', `camp sign: room "${CS.room}" missing from light_config.json — zones stay dark`);
  const channels = lights.length ? cfg.light_models[lights[0].model].channels : {};

  const towerH = ET.frame_h * (ET.tiers || 2);
  const a = ET.spacing / 2 + ET.frame_w / 2;   // band ends at the tower OUTER edges = 14 ft overall
  const band = CS.band || 0.5486;
  const logoR = CS.logo_r || 0.3658;
  const endY = towerH - band / 2;              // band top flush with the tower tops at the ends
  const apexY = endY + (CS.rise || 0.4839);
  // centerline: the circle through (±a, endY) and (0, apexY) — same
  // construction as the old painted arch
  const yc = (apexY * apexY - endY * endY - a * a) / (2 * (apexY - endY));
  const R = apexY - yc;
  const thEnd = Math.acos(a / R);
  const zBand = ET.front_z + 0.09;             // just in front of the tower skins

  signGroup = new THREE.Group();
  levelGroups[2].add(signGroup); // street furniture: visible in every floor filter

  // dark stained-ply band the LED letters pop against
  const shape = new THREE.Shape();
  shape.absarc(0, 0, R + band / 2, Math.PI - thEnd, thEnd, true);
  shape.absarc(0, 0, R - band / 2, thEnd, Math.PI - thEnd, false);
  const bandMesh = new THREE.Mesh(new THREE.ShapeGeometry(shape, 48),
    new THREE.MeshStandardMaterial({ color: 0x241d18, roughness: 0.9, side: THREE.DoubleSide }));
  bandMesh.position.set(ET.cx, yc, zBand);
  signGroup.add(bandMesh);

  // glyph list in reading order; each word carries its em (letter height as a
  // fraction of the band, from the CAD's 33px/15px type)
  const glyphs = [];
  for (const w of (CS.words || [])) {
    if (w.logo) { glyphs.push({ logo: true }); continue; }
    if (glyphs.length && !glyphs[glyphs.length - 1].logo) glyphs.push({ gap: true, em: w.em || 0.62 });
    for (const ch of w.text) glyphs.push(ch === ' ' ? { gap: true, em: w.em || 0.62 } : { ch, em: w.em || 0.62 });
  }
  const iLogo = glyphs.findIndex(g => g.logo);

  const meas = document.createElement('canvas').getContext('2d');
  const FONT = (px) => `700 ${px}px 'JFRockSolid', Georgia, 'Times New Roman', serif`;
  const MPX = 128;
  const wOf = (g) => { // natural advance in meters (before condensing)
    const em = band * (g.em || 0.62);
    if (g.gap) return em * 0.42;
    meas.font = FONT(MPX);
    return (meas.measureText(g.ch).width / MPX) * em;
  };
  const TRACK = 0.05; // tracking, in em

  const glyphTex = (ch, fill) => {
    const px = 180;
    const c = document.createElement('canvas');
    const g2 = c.getContext('2d');
    g2.font = FONT(px);
    const wpx = Math.max(24, Math.ceil(g2.measureText(ch).width)) + 18;
    c.width = wpx; c.height = Math.ceil(px * 1.3);
    g2.font = FONT(px); // canvas resize resets the ctx
    g2.fillStyle = fill || '#ffffff';
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.fillText(ch, wpx / 2, c.height * 0.52);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return { tex, aspect: wpx / c.height, hScale: c.height / px };
  };

  // the glow that escapes around a raised letter (letters-raised.jpg: strip
  // serpentined on the letter's back, LEDs facing the band): the same glyph
  // blurred out well past its outline
  const haloTex = (ch) => {
    const px = 180, pad = Math.ceil(px * 0.45);
    const c = document.createElement('canvas');
    const g2 = c.getContext('2d');
    g2.font = FONT(px);
    const wpx = Math.max(24, Math.ceil(g2.measureText(ch).width)) + pad * 2;
    c.width = wpx; c.height = Math.ceil(px * 1.3) + pad * 2;
    g2.font = FONT(px);
    g2.textAlign = 'center'; g2.textBaseline = 'middle';
    g2.shadowColor = '#ffffff';
    g2.shadowBlur = px * 0.26;
    g2.fillStyle = '#ffffff';
    for (let i = 0; i < 3; i++) g2.fillText(ch, wpx / 2, c.height * 0.51); // build up the glow
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return { tex, aspect: wpx / c.height, hScale: c.height / px };
  };

  const zones = [];
  // lay one side's glyphs along the centerline arc between the band end and
  // the logo margin, condensing widths to fit exactly like the CAD does
  const laySide = (sideGlyphs, side) => {
    const thOut = Math.acos((a - 0.12) / R), thIn = Math.acos((logoR + 0.1) / R);
    const avail = R * (thIn - thOut);
    const natural = sideGlyphs.reduce((p, g) => p + wOf(g) + TRACK * band * (g.em || 0.62), 0);
    const squeeze = Math.min(1, avail / natural);
    let s = 0; // arc-length cursor; reading order walks outer→inner on the
    for (const g of sideGlyphs) { // left side, inner→outer on the right
      const em = band * (g.em || 0.62);
      const w = (wOf(g) + TRACK * em) * squeeze;
      if (!g.gap) {
        const th = (side < 0 ? Math.PI - thOut : thIn) - (s + w / 2) / R;
        const x = ET.cx + R * Math.cos(th), y = yc + R * Math.sin(th);
        const rot = th - Math.PI / 2;
        // the raised letter is halo-lit (letters-raised.jpg): the DMX color
        // lives in the additive glow BEHIND the letter, spilling around it
        // onto the band; the letter face itself is opaque wood, never lit
        // by its own LEDs
        const ht = haloTex(g.ch);
        const haloMat = new THREE.MeshBasicMaterial({
          map: ht.tex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
        });
        haloMat.color.setScalar(SIGN_UNLIT * 0.4);
        const halo = new THREE.Mesh(
          new THREE.PlaneGeometry(ht.aspect * em * ht.hScale * squeeze, em * ht.hScale), haloMat);
        halo.position.set(x, y, zBand + 0.008);
        halo.rotation.z = rot;
        halo.renderOrder = 1;
        signGroup.add(halo);
        const gt = glyphTex(g.ch, '#8a6b43'); // stained-ply face, scene-lit
        const face = new THREE.Mesh(
          new THREE.PlaneGeometry(gt.aspect * em * gt.hScale * squeeze, em * gt.hScale),
          new THREE.MeshStandardMaterial({ map: gt.tex, transparent: true, roughness: 0.85 }));
        face.position.set(x, y, zBand + 0.016);
        face.rotation.z = rot;
        face.renderOrder = 2;
        signGroup.add(face);
        zones.push({ label: g.ch, mat: haloMat, channels });
      }
      s += w;
    }
  };
  laySide(glyphs.slice(0, iLogo), -1);

  // the logo disc at the crest — laser-cut piece-work like the tikis:
  // cad-items/logo.svg is 91 wood pieces (its letters/numbers are assembly
  // labels, stripped here) mounted with the design living in the GAPS between
  // them; the LED strip behind the disc glows through the gaps and the wood
  // blocks. Two rasters, same trick as tikiTexture: a wood color pass and a
  // white-gaps-on-black mask driven as emissive by the zone-12 DMX color.
  const LOGO_PX = 640;
  const logoMat = new THREE.MeshStandardMaterial({
    roughness: 0.85, emissive: new THREE.Color(0, 0, 0), emissiveIntensity: 1.35,
  });
  const discMesh = new THREE.Mesh(new THREE.CircleGeometry(logoR, 48), logoMat);
  discMesh.position.set(ET.cx, apexY, zBand + 0.01);
  discMesh.visible = false; // until the rasters arrive
  signGroup.add(discMesh);
  fetch(CS.logo_svg).then((r) => {
    if (!r.ok) throw new Error(`${CS.logo_svg}: ${r.status}`);
    return r.text();
  }).then((src) => {
    const noText = src.replace(/<text[\s\S]*?<\/text>/g, '');
    const raster = (fill, discBg) => new Promise((resolve, reject) => {
      const restyled = noText.replace(/<style>[\s\S]*?<\/style>/, `<style>.cls-1{fill:${fill};}</style>`);
      const url = URL.createObjectURL(new Blob([restyled], { type: 'image/svg+xml' }));
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        const c = document.createElement('canvas');
        c.width = c.height = LOGO_PX;
        const g2 = c.getContext('2d');
        g2.fillStyle = '#000';
        g2.fillRect(0, 0, LOGO_PX, LOGO_PX);
        g2.fillStyle = discBg; // the gap channels, clipped to the disc
        g2.beginPath(); g2.arc(LOGO_PX / 2, LOGO_PX / 2, LOGO_PX / 2, 0, Math.PI * 2); g2.fill();
        g2.drawImage(img, 0, 0, LOGO_PX, LOGO_PX);
        const tex = new THREE.CanvasTexture(c);
        tex.colorSpace = THREE.SRGBColorSpace;
        resolve(tex);
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('logo raster')); };
      img.src = url;
    });
    return Promise.all([
      raster('#8a6b43', '#17120e'), // wood pieces over dark gap channels
      raster('#000000', '#ffffff'), // emissive mask: gaps glow, wood blocks
    ]);
  }).then(([mapTex, maskTex]) => {
    logoMat.map = mapTex;
    logoMat.emissiveMap = maskTex;
    logoMat.needsUpdate = true;
    discMesh.visible = true;
  }).catch(() => {
    log('err', `camp sign: logo art failed (${CS.logo_svg}) — plain disc`);
    logoMat.color.set(0xc9a052);
    discMesh.visible = true;
  });
  zones.push({ label: '◉', isLogo: true, mat: logoMat, channels });

  laySide(glyphs.slice(iLogo + 1), 1);

  zones.forEach((z, i) => { z.addr = lights[i] ? lights[i].start_address : null; });
  if (lights.length && lights.length !== zones.length) {
    log('err', `camp sign: ${zones.length} zones vs ${lights.length} lights in light_config room "${CS.room}"`);
  }

  // per-letter swatch strip above the fixture grid
  const strip = $('sign-strip');
  if (strip) {
    strip.innerHTML = '';
    for (const z of zones) {
      const cell = document.createElement('div');
      cell.className = 'sign-cell';
      cell.textContent = z.label;
      strip.appendChild(cell);
      z.cell = cell;
    }
  }
  S.sign = { room: CS.room, zones };

  let show = true;
  try { show = localStorage.getItem('lohp-sim-sign') !== '0'; } catch (e) { /* private mode */ }
  setSignVisible(show);
}

let signGridTimer = 0;
function updateCampSign(t) {
  if (!S.sign) return;
  const cells = t - signGridTimer >= 0.2;
  if (cells) signGridTimer = t;
  for (const z of S.sign.zones) {
    const { R, G, B, lum } = z.addr ? decodeFixture(z, t) : { R: 0, G: 0, B: 0, lum: 0 };
    const litR = R * lum, litG = G * lum, litB = B * lum;
    // faint idle floor so the sign stays findable when dark; the LED color
    // rides the halo behind each raised letter (additive) or glows through
    // the logo's gap mask (emissive) — the wood itself never lights up
    const fR = Math.max(litR, SIGN_UNLIT * 0.4), fG = Math.max(litG, SIGN_UNLIT * 0.35), fB = Math.max(litB, SIGN_UNLIT * 0.3);
    if (z.isLogo) z.mat.emissive.setRGB(fR, fG, fB);
    else z.mat.color.setRGB(fR, fG, fB);
    if (cells && z.cell) {
      z.cell.style.background = `rgb(${(litR * 255) | 0},${(litG * 255) | 0},${(litB * 255) | 0})`;
      if (z.addr) {
        const a2 = z.addr - 1;
        z.cell.title = `Camp Sign "${z.label}" @${z.addr}\nraw: ${Array.from(S.frame.slice(a2, a2 + 8)).join(' ')}`;
      }
    }
  }
}

// ---------------------------------------------------------------- fixtures
function fixtureLevel(cfgRoom, posEntry) {
  if (posEntry && posEntry.length > 2) return posEntry[2];
  return cfgRoom.floor === 'both' ? 1 : (cfgRoom.floor || 0);
}

function buildFixtures(cfg) {
  const grid = $('fixture-grid');
  const signRoom = (cfg.layout.camp_sign || {}).room;
  for (const [room, lights] of Object.entries(cfg.room_layout)) {
    if (room === signRoom) continue; // letter zones render via buildCampSign, not as pars
    const layoutRoom = cfg.layout.rooms[room];
    lights.forEach((f, i) => {
      let x, z, posEntry = null;
      if (layoutRoom && layoutRoom.fixture_positions && layoutRoom.fixture_positions[i]) {
        posEntry = layoutRoom.fixture_positions[i];
        [x, z] = posEntry;
      } else if (layoutRoom) {
        x = layoutRoom.x + ((i + 1) / (lights.length + 1)) * layoutRoom.w;
        z = layoutRoom.z + layoutRoom.d / 2;
      } else { x = 0; z = 0; }
      const level = layoutRoom ? fixtureLevel(layoutRoom, posEntry) : 0;
      const yBase = level * S.levelHeight;

      const g = new THREE.Group();
      g.position.set(x, yBase, z);

      // flashlight icons in the retired maze-diagram.drawio = the U'King DMX spotlights
      // (narrow barrel); bulb icons = the circular par pucks. All fixtures
      // bracket-mount on the back scaffolding / cross members and tilt down
      // into the room — nothing hangs from poles.
      const isSpot = /ZQ07010/.test(f.model);
      const CH = (S.cfg.layout.ceiling_height || 1.98);
      const coneH = CH - 0.45;
      const mountY = CH - 0.16;
      const metal = new THREE.MeshStandardMaterial({ color: 0x0a0a0e, roughness: 0.55, metalness: 0.5 });

      const rc = (S.roomsMeshes[room] || {}).center || new THREE.Vector3(x, 0, z + 0.6);
      const head = new THREE.Group();
      head.position.y = mountY;
      head.rotation.order = 'YXZ';
      head.rotation.y = Math.atan2(rc.x - x, rc.z - z); // aim into the room
      head.rotation.x = -0.62;                          // ~35° down-tilt
      g.add(head);

      const bracket = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, 0.16), metal);
      bracket.position.set(0, mountY, -0.08);
      g.add(bracket);
      const yoke = new THREE.Mesh(new THREE.BoxGeometry(isSpot ? 0.12 : 0.22, 0.02, 0.03), metal);
      yoke.position.y = 0.02;
      head.add(yoke);

      const body = isSpot
        ? new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.055, 0.26, 20), metal)    // spot barrel
        : new THREE.Mesh(new THREE.CylinderGeometry(0.095, 0.105, 0.09, 24), metal);  // circular par puck
      body.position.y = isSpot ? -0.11 : -0.045;
      head.add(body);

      const lens = new THREE.Mesh(new THREE.CircleGeometry(isSpot ? 0.045 : 0.085, 24),
        new THREE.MeshBasicMaterial({ color: 0x000000 }));
      lens.rotation.x = -Math.PI / 2;
      lens.position.y = isSpot ? -0.245 : -0.095;
      head.add(lens);

      const cone = new THREE.Mesh(new THREE.ConeGeometry(isSpot ? 0.3 : 0.75, coneH, 28, 1, true),
        new THREE.MeshBasicMaterial({
          color: 0x000000, transparent: true, opacity: 0,
          blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide,
        }));
      cone.position.y = (isSpot ? -0.245 : -0.095) - coneH / 2;
      head.add(cone);

      let light;
      if (isSpot) {
        light = new THREE.SpotLight(0x000000, 0, 5.5, 0.34, 0.45, 1.5);
        light.position.y = -0.2;
        const target = new THREE.Object3D();
        target.position.y = -3;
        head.add(target);
        light.target = target;
      } else {
        light = new THREE.PointLight(0x000000, 0, 4.2, 1.6);
        light.position.y = -0.42;
      }
      head.add(light);

      grp(level).add(g);

      const cell = document.createElement('div');
      cell.className = 'fixture-cell';
      cell.innerHTML = `<span class="addr">@${f.start_address}</span> ${isSpot ? '🔦 ' : ''}${escapeHtml(room)}${level ? ' ▲' : ''}`;
      grid.appendChild(cell);

      S.fixtures.push({
        room, addr: f.start_address, model: f.model, level, isSpot, wx: x, wz: z,
        channels: cfg.light_models[f.model].channels,
        light, lens, cone, cell,
      });
    });
  }
}

function decodeFixture(fx, t) {
  const a = fx.addr - 1;
  const ch = fx.channels;
  const v = (name) => (name in ch) ? (S.frame[a + ch[name]] || 0) : null;
  const master = ((v('total_dimming') !== null ? v('total_dimming') : v('master_dimmer')) || 0) / 255;
  const r = (v('r_dimming') !== null ? v('r_dimming') : v('red')) || 0;
  const g = (v('g_dimming') !== null ? v('g_dimming') : v('green')) || 0;
  const b = (v('b_dimming') !== null ? v('b_dimming') : v('blue')) || 0;
  const w = (v('w_dimming') !== null ? v('w_dimming') : v('white')) || 0;
  const strobe = v('total_strobe') || 0;

  const rawR = r + w * 0.92;
  const rawG = g + w * 0.92;
  const rawB = b + w * 0.85;
  const rawMax = Math.max(rawR, rawG, rawB);
  let lum = rawMax > 0 ? Math.min(1, rawMax / 255) * master : 0;
  let R = rawMax > 0 ? rawR / rawMax : 0;
  let G = rawMax > 0 ? rawG / rawMax : 0;
  let B = rawMax > 0 ? rawB / rawMax : 0;
  if (strobe > 5) {
    const hz = 1 + (strobe / 255) * 11;
    if ((t * hz) % 1 > 0.5) { R = G = B = lum = 0; }
  }
  return { R, G, B, lum };
}

const roomTint = new Map();
function updateFixtures(t) {
  roomTint.clear();
  for (const fx of S.fixtures) {
    const { R, G, B, lum } = decodeFixture(fx, t);
    const litR = R * lum, litG = G * lum, litB = B * lum;
    fx.light.color.setRGB(R, G, B);
    fx.light.intensity = lum * (fx.isSpot ? 12 : 7);  // hue survives over-range now that tone mapping is AgX (ACES skewed saturated orange to yellow-white)
    // faint idle glow so every fixture is visible even when dark. ONE shared
    // scale for all three channels: the old per-channel `min(1, lit*1.6)`
    // clipped R before G on warm colours, so an orange bulb rendered yellow.
    const lensS = 0.09 + lum * 0.88;
    fx.lens.material.color.setRGB(R * lensS + 0.06, G * lensS + 0.06, B * lensS + 0.07);
    fx.cone.material.color.setRGB(R, G, B);
    fx.cone.material.opacity = 0.05 + lum * 0.22;
    const acc = roomTint.get(fx.room) || [0, 0, 0, 0];
    acc[0] += litR; acc[1] += litG; acc[2] += litB; acc[3] += 1;
    roomTint.set(fx.room, acc);
  }
  for (const [room, rm] of Object.entries(S.roomsMeshes)) {
    const acc = roomTint.get(room);
    if (acc) rm.slab.material.emissive.setRGB((acc[0] / acc[3]) * 0.13, (acc[1] / acc[3]) * 0.13, (acc[2] / acc[3]) * 0.13);
  }
  // canvas backdrops: a readability floor at night, plus the room's light color
  for (const [room, mats] of Object.entries(S.canvasMats)) {
    const acc = roomTint.get(room);
    const r = acc ? acc[0] / acc[3] : 0, g = acc ? acc[1] / acc[3] : 0, b = acc ? acc[2] / acc[3] : 0;
    for (const m of mats) {
      m.emissive.setRGB(Math.min(1, 0.12 + r * 0.5), Math.min(1, 0.12 + g * 0.5), Math.min(1, 0.13 + b * 0.5));
    }
  }
}

let gridTimer = 0;
function updateFixtureGrid(t) {
  if (t - gridTimer < 0.2) return;
  gridTimer = t;
  for (const fx of S.fixtures) {
    const { R, G, B, lum } = decodeFixture(fx, t);
    fx.cell.style.background = `rgb(${(R * lum * 255) | 0},${(G * lum * 255) | 0},${(B * lum * 255) | 0})`;
    const a = fx.addr - 1;
    fx.cell.title = `${fx.model} @${fx.addr}${fx.isSpot ? ' [SPOTLIGHT]' : ''} (${fx.level ? 'upper' : 'ground'} floor)\nraw: ${Array.from(S.frame.slice(a, a + 8)).join(' ')}`;
  }
}

// ---------------------------------------------------------------- sensors
const COOLDOWN_S = 5; // trigger_manager default cooldown_period

function buildSensors(cfg) {
  const byName = cfg.layout.sensors || {};
  const placeholders = new Set((cfg.layout.placeholder_effects || {}).rooms || []);
  const triggerList = $('trigger-list');

  for (const trig of cfg.triggers) {
    const geo = byName[trig.name] || {};
    // geo.level 0 is a real value — the || fallback once swallowed it and the
    // pos[1] height guess then misread zone sensors' [x,z] pos as [x,y]
    const level = geo.level != null ? geo.level
      : (geo.pos && geo.pos[1] > S.levelHeight ? 1 : 0);
    const sensor = {
      name: trig.name, kind: geo.kind || trig.type, room: trig.room, level,
      action: trig.action, type: trig.type, game: trig.game || null,
      // The other half of a radar presence trigger's occupancy pair: fired when
      // the walker leaves the detection zone (triggers.json leave_action). ToF
      // zones are trigger-only, so they intentionally have no leave action.
      leaveAction: trig.leave_action || null, occupied: false,
      lastFired: -1e9, meshes: [], seg: geo.seg || null,
    };

    if (geo.kind === 'beam' && geo.seg) {
      const [[x1, z1], [x2, z2]] = geo.seg;
      const yBase = level * S.levelHeight;
      const len = Math.hypot(x2 - x1, z2 - z1);
      const beam = new THREE.Mesh(new THREE.BoxGeometry(len, 0.02, 0.02),
        new THREE.MeshBasicMaterial({ color: 0xff2b2b, transparent: true, opacity: 0.85 }));
      beam.position.set((x1 + x2) / 2, yBase + 0.85, (z1 + z2) / 2);
      beam.rotation.y = -Math.atan2(z2 - z1, x2 - x1);
      grp(level).add(beam);
      // emitter/receiver pucks on the scaffold at each end — nothing on the floor
      for (const [px, pz] of [[x1, z1], [x2, z2]]) {
        const emitter = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.06, 0.05),
          new THREE.MeshStandardMaterial({ color: 0x15161c, roughness: 0.5 }));
        emitter.position.set(px, yBase + 0.85, pz);
        grp(level).add(emitter);
      }
      sensor.meshes.push(beam);
    } else if ((geo.kind === 'radar' || geo.kind === 'tof') && geo.pos) {
      // Zone sensor firing from the room's node box: 13 rooms carry an LD2410C
      // presence radar, Entrance and Exit a TOF200C ToF (they cannot use radar —
      // it would see through their shared divider, and the foil fix was ruled out
      // 2026-07-30). Horizontal wedge = detection footprint (range/fov/clip),
      // boresight line = exact aim (yaw + down-tilt).
      const isRadar = geo.kind === 'radar';
      const range = geo.range_m || (isRadar ? 3.0 : 2.1);
      const fov = geo.fov_deg || (isRadar ? 120 : 27);
      const yaw = geo.yaw_deg || 0;
      const yawR = yaw * Math.PI / 180;
      const h = geo.h || 1.55;
      // The two shafts mount the radar at the TOP pointed straight down; fov 360
      // + tilt -90 means the "wedge" is the floor footprint under it, so draw the
      // disc on the deck and run the boresight down to meet it.
      const topDown = (geo.tilt_deg || 0) <= -85;
      sensor.zone = {
        x: geo.pos[0], z: geo.pos[1], yaw, fov, range, clip: geo.clip || null,
        // Thin ToF cones get a boresight seg-cross backstop so a sprint through
        // can't step over the zone between frames; wide radar wedges don't need
        // one (and their 3 m bore can graze the neighbouring bay).
        bore: isRadar ? null
          : [[geo.pos[0], geo.pos[1]],
            [geo.pos[0] + range * Math.sin(yawR), geo.pos[1] + range * Math.cos(yawR)]],
      };
      const color = isRadar ? 0x37ffb0 : 0xff2b2b;
      const zg = new THREE.Group();
      zg.position.set(geo.pos[0], level * S.levelHeight + h, geo.pos[1]);
      zg.rotation.y = yawR;
      const fovR = fov * Math.PI / 180;
      const wedge = new THREE.Mesh(
        new THREE.CircleGeometry(range, 48, Math.PI / 2 - fovR / 2, fovR),
        new THREE.MeshBasicMaterial({ color, transparent: true, side: THREE.DoubleSide,
          opacity: isRadar ? 0.07 : 0.16, depthWrite: false }));
      wedge.rotation.x = Math.PI / 2; // lay flat, opening along local +z (the box window)
      if (topDown) wedge.position.y = -(h - 0.02);  // the footprint is on the deck
      zg.add(wedge);
      const boreG = new THREE.Group();
      boreG.rotation.x = -(geo.tilt_deg || 0) * Math.PI / 180; // -10° tilt = aim below horizon
      const bore = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(
          [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, topDown ? h : range)]),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.65 }));
      boreG.add(bore);
      zg.add(boreG);
      grp(level).add(zg);
      sensor.meshes.push(wedge, bore);
    } else if (geo.kind === 'button' && geo.pos) {
      const bcol = geo.color ? parseInt(geo.color, 16) : 0xcccccc;
      const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.05, 24),
        new THREE.MeshStandardMaterial({ color: bcol, roughness: 0.4, emissive: bcol, emissiveIntensity: 0.25 }));
      btn.rotation.x = Math.PI / 2;
      btn.position.set(geo.pos[0], geo.pos[1], geo.pos[2]);
      btn.userData.sensor = sensor;
      grp(level).add(btn);
      sensor.meshes.push(btn);
      S.interactables.push(btn);
    } else if (geo.kind === 'knock' && geo.pos) {
      const pad = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.04),
        new THREE.MeshStandardMaterial({ color: 0x6a5232, roughness: 0.8, emissive: 0x2a1f10, emissiveIntensity: 0.4 }));
      pad.position.set(geo.pos[0], geo.pos[1], geo.pos[2]);
      pad.userData.sensor = sensor;
      grp(level).add(pad);
      sensor.meshes.push(pad);
      S.interactables.push(pad);
    }

    const b = document.createElement('button');
    const isPlaceholder = trig.room && placeholders.has(trig.room)
      && (trig.action.data || {}).effect_name === 'Lightning';
    b.textContent = trig.name + (isPlaceholder ? ' ⚠' : '');
    b.title = `${trig.type} → ${JSON.stringify(trig.action.data)}`
      + (sensor.zone ? `\n${geo.kind === 'radar' ? 'LD2410C radar' : 'TOF200C ToF'} ${(geo.tilt_deg || 0) <= -85
        ? `at the top of ${trig.room}, pointed straight down`
        : `in the ${trig.room} node box`} — yaw ${sensor.zone.yaw}°, `
        + `tilt ${geo.tilt_deg || 0}°, fov ${sensor.zone.fov}°, reach ${sensor.zone.range} m` : '')
      + (sensor.leaveAction ? `\nleave -> ${sensor.leaveAction.path}` : '')
      + (isPlaceholder ? '\n⚠ placeholder: no bespoke effect designed for this room yet' : '');
    b.onclick = () => fireSensor(sensor, true);
    triggerList.appendChild(b);

    S.sensors.push(sensor);
  }
}

// --- room game logic (mirrors the node firmware; spec: wiring-guides/room-games-plan.md) ---
const GAME = {
  gate: { stage: 0, at: -1e9, pads: Array(7).fill(false), timers: Array(7).fill(null) },
  portoWinner: Math.floor(Math.random() * 3),
  portoAttempts: 0,
  portoSolved: false,
  dphWinner: Math.floor(Math.random() * 5),
  bike: {},
  moop: { pressed: new Set(), at: null, timer: null },
  lamps: null,
};

function lampSensors() {
  return S.sensors.filter(s => s.game && s.game.id === 'lightsout')
    .sort((a, b) => a.game.index - b.game.index);
}

function paintLamps() {
  for (const s of lampSensors()) {
    const on = GAME.lamps ? GAME.lamps[s.game.index] : false;
    for (const m of s.meshes) {
      if (!m.material) continue;
      m.userData.origColor = null; // lamp state owns the colour; skip flash restores
      m.material.color.set(on ? 0xffe27a : 0x3a3a3a);
      m.material.emissive.set(on ? 0xffe27a : 0x111111);
      m.material.emissiveIntensity = on ? 0.95 : 0.12;
    }
  }
}

function scrambleLamps() {
  GAME.lamps = [];
  do {
    for (let i = 0; i < 5; i++) GAME.lamps[i] = Math.random() < 0.5;
  } while (GAME.lamps.every(Boolean));  // never start solved
  paintLamps();
}

function actionData(sensor, effect) {
  const data = Object.assign({}, sensor.action.data || {});
  if (effect) data.effect_name = effect;
  if (sensor.name) data.trigger_name = sensor.name;
  return data;
}

function chimeThen(sensor, finalEffect, source) {
  // maze-wide victory chime, then the room's big effect once the chime lands
  post(sensor.action.path, actionData(sensor, 'CorrectAnswer'), source);
  setTimeout(() => post(sensor.action.path,
    actionData(sensor, finalEffect), source), 2500);
}

function gatePadNumber(sensor) {
  const m = /^Gate Pad ([1-6])$/.exec(sensor.name || '');
  return m ? parseInt(m[1], 10) : null;
}

function resetGateGame() {
  for (const timer of GAME.gate.timers) if (timer) clearTimeout(timer);
  GAME.gate = { stage: 0, at: -1e9, pads: Array(7).fill(false), timers: Array(7).fill(null) };
}

function resetMoopGame() {
  if (GAME.moop.timer) clearTimeout(GAME.moop.timer);
  GAME.moop = { pressed: new Set(), at: null, timer: null };
}

// Returns {effect} to POST, null when the game already POSTed, or 'silent'.
function resolveGame(sensor, source) {
  const g = sensor.game;
  const now = clock.getElapsedTime();
  switch (g.id) {
    case 'gate': {
      // Mirror the node firmware: a single pad press is silent. A bank only
      // resolves when all three pads in that bank are held within the 350 ms
      // delayed-off window.
      if (GAME.gate.stage === 1 && now - GAME.gate.at > 30) resetGateGame();
      const pad = gatePadNumber(sensor);
      if (!pad) return 'silent';
      GAME.gate.pads[pad] = true;
      if (GAME.gate.timers[pad]) clearTimeout(GAME.gate.timers[pad]);
      GAME.gate.timers[pad] = setTimeout(() => { GAME.gate.pads[pad] = false; }, 350);

      const bank1 = GAME.gate.pads[1] && GAME.gate.pads[2] && GAME.gate.pads[3];
      const bank2 = GAME.gate.pads[4] && GAME.gate.pads[5] && GAME.gate.pads[6];
      if (g.bank === 1 && GAME.gate.stage === 0 && bank1) {
        GAME.gate.stage = 1; GAME.gate.at = now;
        GAME.gate.pads[1] = GAME.gate.pads[2] = GAME.gate.pads[3] = false;
        toast('Gate: bank 1 victory — now press 4-6');
        return { effect: 'CorrectAnswer' };
      }
      if (g.bank === 2 && bank2) {
        GAME.gate.pads[4] = GAME.gate.pads[5] = GAME.gate.pads[6] = false;
        if (GAME.gate.stage === 1) {
          resetGateGame();
          toast('Gate: bank 2 victory — leave the room');
          return { effect: 'CorrectAnswer' };
        }
        toast('Gate: bank 1 first');
        return { effect: 'WrongAnswer' };
      }
      return 'silent';
    }
    case 'porto': {
      if (GAME.portoSolved) {
        toast('Porto: already passed');
        return { effect: 'CorrectAnswer' };
      }
      GAME.portoAttempts += 1;
      if (GAME.portoAttempts >= 2
        && (g.index === GAME.portoWinner || GAME.portoAttempts >= 4)) {
        GAME.portoSolved = true;
        toast(`Porto: pass on attempt ${GAME.portoAttempts}`);
        return { effect: 'CorrectAnswer' };
      }
      toast(`Porto: occupied (${GAME.portoAttempts}/4)`);
      return { effect: 'PortoHit' };
    }
    case 'dph': {
      if (g.index === GAME.dphWinner) {
        toast('Handshake: WINNER!');
        return { effect: 'CorrectAnswer' };
      }
      toast('Handshake: not this one…');
      return { effect: 'WrongAnswer' };
    }
    case 'bike': {
      if (GAME.bike.at && now - GAME.bike.at > 60) GAME.bike = {};
      if (!g.correct) {
        GAME.bike = {};
        toast(`Bike Q${g.question}: wrong — start over`);
        return { effect: 'WrongAnswer' };
      }
      GAME.bike['q' + g.question] = true;
      GAME.bike.at = now;
      if (GAME.bike.q1 && GAME.bike.q2) {
        GAME.bike = {};
        toast('Bike: both questions right!');
        chimeThen(sensor, 'BikeLockRoom', source);
        return null;
      }
      toast(`Bike Q${g.question}: correct`);
      return { effect: 'CorrectAnswer' };
    }
    case 'moop': {
      // Mirror game_moop.yaml on the room node: first press opens a 60s
      // round, all four unique buttons -> chime then the right-answer pool,
      // timeout on a partial set -> the wrong-answer pool.
      if (!GAME.moop.at || now - GAME.moop.at > 60) {
        resetMoopGame();
        GAME.moop.at = now;
        GAME.moop.timer = setTimeout(() => {
          if (GAME.moop.pressed.size > 0 && GAME.moop.pressed.size < 4) {
            toast('Moop: timed out — wrong answer');
            post(sensor.action.path,
              actionData(sensor, 'VerticalMoopMarch-WrongAnswer'), source);
          }
          resetMoopGame();
        }, 60000);
      }
      GAME.moop.pressed.add(sensor.name || `Moop Button ${g.index + 1}`);
      const count = GAME.moop.pressed.size;
      if (count >= 4) {
        resetMoopGame();
        toast('Moop: all buttons — right answer');
        chimeThen(sensor, 'VerticalMoopMarch-RightAnswer', source);
        return null;
      }
      toast(`Moop: ${count}/4 buttons`);
      return { effect: 'CorrectAnswer' };
    }
    case 'lightsout': {
      if (!GAME.lamps) scrambleLamps();
      for (const j of [g.index - 1, g.index, g.index + 1])
        if (j >= 0 && j < 5) GAME.lamps[j] = !GAME.lamps[j];
      paintLamps();
      if (GAME.lamps.every(Boolean)) {
        toast('Truck: LIGHTS ON — solved!');
        GAME.lamps = null;
        setTimeout(scrambleLamps, 4000);
        chimeThen(sensor, 'NoFriendsMonday', source);
        return null;
      }
      return 'silent';  // toggles don't fire effects; only the solve does
    }
  }
  return { effect: sensor.action.data.effect_name };
}

function fireSensor(sensor, manual) {
  const now = clock.getElapsedTime();
  // Arm the room's occupancy latch BEFORE the cooldown gate, exactly like the
  // node firmware (tripwire on_press sets room_occupied unconditionally, then
  // hands off to fire_effect whose mode:single may swallow the run): someone who
  // walks in during a cooldown is still in the room and must still produce a
  // leave when they walk out.
  if (sensor.leaveAction) {
    const entering = !sensor.occupied;
    sensor.occupied = true;
    if (entering && sensor.room === 'Porto Room') {
      GAME.portoWinner = Math.floor(Math.random() * 3);
      GAME.portoAttempts = 0;
      GAME.portoSolved = false;
      toast('Porto: pads randomized');
    } else if (entering && sensor.room === 'Deep Playa Handshake') {
      GAME.dphWinner = Math.floor(Math.random() * 5);
      toast('Handshake: buttons randomized');
    } else if (entering && sensor.room === 'Gate') {
      resetGateGame();
    }
  }
  const cooldown = sensor.game
    ? (sensor.game.id === 'lightsout' ? 0.4 : sensor.game.id === 'porto' ? 0.6 : 1.5)
    : COOLDOWN_S;
  if (now - sensor.lastFired < cooldown) {
    if (manual) toast(`${sensor.name}: cooling down`);
    return;
  }
  sensor.lastFired = now;
  const source = manual ? 'click' : 'walkthrough';

  if (sensor.game) {
    const r = resolveGame(sensor, source);
    if (r === 'silent') return;  // lamp paint owns the button look; no flash
    if (r && r.effect) {
      toast(`${sensor.name} → ${r.effect}`);
      post(sensor.action.path, actionData(sensor, r.effect), source);
    }
  } else if (sensor.type === 'piezo') {
    const ps = S.cfg.piezo_settings;
    S.piezoAttempts += 1;
    let effect = 'WrongAnswer';
    if (S.piezoAttempts >= (ps.attempts_required || 3)) {
      S.piezoAttempts = 0;
        if (Math.random() < (ps.correct_answer_probability || 0.25)) effect = 'CorrectAnswer';
    }
    const data = actionData(sensor, effect);
    toast(`${sensor.name} → ${effect}`);
    post(sensor.action.path, data, source);
  } else {
    toast(`${sensor.name}${sensor.room ? ' → ' + (sensor.action.data.effect_name || '') : ''}`);
    post(sensor.action.path, actionData(sensor), source);
  }
  if (S.projection && sensor.name === S.projection.cfg.cue) projectionCue('cue: ' + sensor.name);

  for (const m of sensor.meshes) {
    if (m.material && m.material.color) {
      const orig = m.userData.origColor || (m.userData.origColor = m.material.color.clone());
      // fired-flash: bright warm red, NOT 0xffffff — the doorway beam bar is
      // right in the walker's eye line, and a white blink on entry read as
      // "the room went white" (Tim, 2026-08-17)
      m.material.color.set(0xff5533);
      setTimeout(() => m.material.color.copy(orig), 250);
      setTimeout(() => { m.material.color.set(0x555555); }, 300);
      setTimeout(() => m.material.color.copy(orig), COOLDOWN_S * 1000);
    }
  }
}

// The leave half of a presence trigger. No cooldown and no game/piezo logic —
// a leave is one fact, and the `occupied` latch makes a repeat a no-op, matching
// the room_vacated script in packages/tripwire.yaml. Only an enter that actually
// armed the latch can produce a leave, so a walker who never triggered the room
// can't tell the server to tear it down.
function fireLeave(sensor, manual) {
  if (!sensor.leaveAction || !sensor.occupied) return;
  sensor.occupied = false;
  if (sensor.room === 'Gate') resetGateGame();
  toast(`${sensor.name}: room vacated`);
  post(sensor.leaveAction.path, sensor.leaveAction.data, manual ? 'click' : 'walkthrough');
}

function segCross(ax, az, bx, bz, cx, cz, dx, dz) {
  const d = (bx - ax) * (dz - cz) - (bz - az) * (dx - cx);
  if (Math.abs(d) < 1e-9) return false;
  const t = ((cx - ax) * (dz - cz) - (cz - az) * (dx - cx)) / d;
  const u = ((cx - ax) * (bz - az) - (cz - az) * (bx - ax)) / d;
  return t >= 0 && t <= 1 && u >= 0 && u <= 1;
}

function zoneContains(zone, x, z) {
  if (zone.clip) {
    if (x < zone.clip.x[0] || x > zone.clip.x[1]
      || z < zone.clip.z[0] || z > zone.clip.z[1]) return false;
  }
  const dx = x - zone.x, dz = z - zone.z;
  if (Math.hypot(dx, dz) > zone.range) return false;
  const a = ((Math.atan2(dx, dz) * 180 / Math.PI - zone.yaw + 540) % 360) - 180;
  return Math.abs(a) <= zone.fov / 2;
}

function checkSensorTriggers() {
  const { x, z } = S.pos;
  const tele = S.teleporting;
  if (tele) { S.teleporting = false; S.prev2 = { x, z }; }
  const { x: px, z: pz } = S.prev2;
  const moved = px !== x || pz !== z;
  for (const sensor of S.sensors) {
    if (sensor.zone) {
      // Radar occupancy pair, both edges of the detection wedge: entering fires
      // the room's effect, leaving fires leave_action so the server stops
      // whatever is still running and hands the room back to the theme. ToF
      // zones only fire on entry; clearing that narrow beam must not stop the
      // room routine. Teleports re-seat state without firing either, like beams.
      const inside = sensor.level === S.level && zoneContains(sensor.zone, x, z);
      if (!tele && ((inside && !sensor.wasInside)
        || (moved && sensor.zone.bore && sensor.level === S.level
          && segCross(px, pz, x, z,
            sensor.zone.bore[0][0], sensor.zone.bore[0][1],
            sensor.zone.bore[1][0], sensor.zone.bore[1][1])))) fireSensor(sensor, false);
      if (!tele && sensor.kind !== 'tof' && !inside && sensor.wasInside) fireLeave(sensor, false);
      sensor.wasInside = inside;
    } else if (sensor.seg && sensor.level === S.level && !tele && moved) {
      const [[x1, z1], [x2, z2]] = sensor.seg;
      if (segCross(px, pz, x, z, x1, z1, x2, z2)) fireSensor(sensor, false);
    }
  }
  S.prev2 = { x, z };
}

// ------------------------------------------------- planned projection rig (sim preview)
// The PLANNED Cuddle Cross floor projection from the layout's `projection` key:
// a face-down short-throw projector on a VIVO ceiling mount off the corner
// legs at the hex NE corner
// paints a reactive playfield on the deck; an LD2450 in the node box tracks walker
// positions. The sim's walker IS the target — filtered through the tracker's
// real coverage wedge and first-order latency so the interactivity previews
// how the hardware will feel. Content comes from the shared floor engine
// (projection_engine.py, LAVA or JUNGLE theme — the Floor button switches it
// for every tab). Delete the layout key to remove the whole rig. No
// production config is involved.
const FLOOR_THEMES = ['lava', 'jungle', 'temple', 'water', 'chamber'];
const FLOOR_LABEL = { lava: 'Floor: Lava', jungle: 'Floor: Jungle', temple: 'Floor: Temple', water: 'Floor: Water', chamber: 'Floor: Chamber' };
function buildProjection(cfg) {
  const P = cfg.layout.projection;
  if (!P) return;
  const LH = S.levelHeight;
  const yDeck = P.level * LH + 0.145; // hair above the deck slab
  const g = new THREE.Group();

  // projector body + mount rig back to its frame; yaw_deg spins the rig
  // (0 = throws +z; -90 = throws -x as on the old rear-leg mount; -120 =
  // throws SW down the long diagonal from the NE corner arm)
  const [bw, bh, bd] = P.projector.body || [0.3837, 0.2915, 0.1477];
  const yaw = (P.projector.yaw_deg || 0) * Math.PI / 180;
  const fwd = [Math.sin(yaw), Math.cos(yaw)];
  const yProj = P.level * LH + 0.14 + (P.projector.h || 0.6);
  const rig = new THREE.Group();
  rig.position.set(P.projector.pos[0], yProj, P.projector.pos[1]);
  rig.rotation.y = yaw;
  const body = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, bd),
    new THREE.MeshStandardMaterial({ color: 0xe8e4dc, roughness: 0.55 }));
  rig.add(body);
  g.add(rig);
  // the mount hardware (yoke / arm / shroud) draws further down, once the
  // hex vertices exist to hang it off — see "mount assembly"
  // projected image: live canvas on the deck, additive like thrown light.
  // w = the lateral (long, 4:3-width) axis, d = the along-throw (short)
  // axis; the plane rides in a group yawed with the projector so diagonal
  // throws render true
  const cw = 640, chp = Math.round(cw * P.image.d / P.image.w);
  const canvas = document.createElement('canvas');
  canvas.width = cw; canvas.height = chp;
  const tex = new THREE.CanvasTexture(canvas);
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(P.image.w, P.image.d),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false }));
  plane.rotation.x = -Math.PI / 2;
  const planeG = new THREE.Group();
  planeG.position.set(P.image.center[0], yDeck, P.image.center[1]);
  planeG.rotation.y = yaw;
  planeG.add(plane);
  g.add(planeG);

  // world (x,z) -> image canvas px, honoring the throw yaw: canvas +x runs
  // along the image's lateral axis, canvas +y from near edge to far edge
  const ppm = cw / P.image.w;
  const lat = [Math.cos(yaw), -Math.sin(yaw)];
  const toPx = (wx, wz) => {
    const dx = wx - P.image.center[0], dz = wz - P.image.center[1];
    return { x: (dx * lat[0] + dz * lat[1] + P.image.w / 2) * ppm,
             y: (dx * fwd[0] + dz * fwd[1] + P.image.d / 2) * ppm };
  };

  // the projection window (bottom face; lens assumed CENTERED along-throw
  // on the real 147.7 mm face — MEASURE from the unit, guide gives no lens
  // offsets) — beam linework draws below, after the deck outline exists to
  // clip against
  const lensAhead = 0;   // lens center ahead of body center, along-throw (m)
  const win = new THREE.Vector3(P.projector.pos[0] + fwd[0] * lensAhead,
    yProj - bh / 2,
    P.projector.pos[1] + fwd[1] * lensAhead);

  // LD2450 tracker wedge — faint blue, just under the LD2410 trigger wedge
  const T = P.tracker;
  const fovR = (T.fov_deg || 120) * Math.PI / 180;
  const wedge = new THREE.Mesh(
    new THREE.CircleGeometry(Math.min(T.range_m || 6, 3.0), 48, Math.PI / 2 - fovR / 2, fovR),
    new THREE.MeshBasicMaterial({ color: 0x37b6ff, transparent: true, opacity: 0.05,
      side: THREE.DoubleSide, depthWrite: false }));
  wedge.rotation.x = Math.PI / 2;
  const wg = new THREE.Group();
  wg.position.set(T.pos[0], P.level * LH + (T.h || 1.38), T.pos[1]);
  wg.rotation.y = (T.yaw_deg || 0) * Math.PI / 180;
  wg.add(wedge);
  g.add(wg);
  grp(P.level).add(g);

  // mast base in image pixels: content island + shadow direction (the
  // window's position in image pixels sets which way the shadow falls)
  const pole = (cfg.layout.hex_center || {}).center_pole || {};
  const mast = { ...toPx(cfg.layout.hex_center.cx, cfg.layout.hex_center.cz),
    r: ((pole.od || 0.09) / 2 + 0.05) * ppm };
  const winPx = toPx(win.x, win.z);

  // projection-mapping mask: the deck outline (hex + door slivers) in image
  // pixels — the projected rectangle overdrives past the deck edges, and
  // everything off-deck stays black, exactly like the real software mask
  const H = cfg.layout.hex_center, room = cfg.layout.rooms[P.room] || {};
  const V = [];
  for (let k = 0; k < 6; k++) {
    const a = Math.PI / 6 + k * Math.PI / 3;
    V.push([H.cx + H.side * Math.cos(a), H.cz + H.side * Math.sin(a)]);
  }
  const wW = room.x != null ? room.x : V[2][0], wE = room.x != null ? room.x + room.w : V[0][0];
  const deckPts = [V[1], V[2], [wW, V[2][1]], [wW, V[3][1]], V[3], V[4], V[5],
    [wE, V[5][1]], [wE, V[0][1]], V[0]];
  const deckPath = new Path2D();
  deckPts.forEach(([wx, wz], i) => {
    const { x, y } = toPx(wx, wz);
    if (i) deckPath.lineTo(x, y); else deckPath.moveTo(x, y);
  });
  deckPath.closePath();

  // beam linework — TWO distinct things, so light never appears to cross
  // steel it cannot touch in reality:
  //  1) the LIT cone: the deck outline clipped to the image rectangle — the
  //     exact footprint the software mask leaves lit. Solid rays + outline.
  //     Every one of these rays clears the scaffold (that is what the
  //     inboard-of-the-legs placement bought).
  //  2) the masked SPILL: the full rectangle the optics throw. All four of
  //     its corners land OFF-deck and render black on the real rig (a DLP's
  //     black still leaks faint gray, and the shroud aperture must clear
  //     this whole frustum, so it stays drawn) — faint and dashed. The
  //     edges that cross the east arch / street frame live here: dead rays.
  const toImg = ([wx, wz]) => [
    lat[0] * (wx - P.image.center[0]) + lat[1] * (wz - P.image.center[1]),
    fwd[0] * (wx - P.image.center[0]) + fwd[1] * (wz - P.image.center[1])];
  const toWorldImg = ([u, v]) => [
    P.image.center[0] + lat[0] * u + fwd[0] * v,
    P.image.center[1] + lat[1] * u + fwd[1] * v];
  let lit = deckPts.map(toImg);
  for (const [ax, sn, lim] of [[0, 1, P.image.w / 2], [0, -1, P.image.w / 2],
    [1, 1, P.image.d / 2], [1, -1, P.image.d / 2]]) {
    const prev = lit;
    lit = [];
    for (let i = 0; i < prev.length; i++) {
      const a = prev[i], b = prev[(i + 1) % prev.length];
      const ia = sn * a[ax] <= lim, ib = sn * b[ax] <= lim;
      if (ia) lit.push(a);
      if (ia !== ib) {
        const t = (lim - sn * a[ax]) / (sn * b[ax] - sn * a[ax]);
        lit.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
      }
    }
  }
  const litPts = lit.map(toWorldImg).map(([wx, wz]) => new THREE.Vector3(wx, yDeck + 0.007, wz));
  const shoelace = (pts) => Math.abs(pts.reduce((s, p, i) => {
    const q = pts[(i + 1) % pts.length];
    return s + p[0] * q[1] - q[0] * p[1];
  }, 0)) / 2;
  const litPct = Math.round(shoelace(lit) / shoelace(deckPts.map(toImg)) * 1000) / 10;
  const matBeam = new THREE.LineBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.22 });
  for (const p of litPts) {
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([win, p]), matBeam));
  }
  g.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(litPts),
    new THREE.LineBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.35 })));
  const matSpill = new THREE.LineDashedMaterial({ color: 0x9fd8ff, transparent: true,
    opacity: 0.09, dashSize: 0.05, gapSize: 0.06 });
  const rectPts = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sz]) => {
    const [wx, wz] = toWorldImg([sx * P.image.w / 2, sz * P.image.d / 2]);
    return new THREE.Vector3(wx, yDeck + 0.004, wz);
  });
  for (const p of rectPts) {
    const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints([win, p]), matSpill);
    l.computeLineDistances();
    g.add(l);
  }
  const rectLoop = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(rectPts), matSpill);
  rectLoop.computeLineDistances();
  g.add(rectLoop);

  // the clamp corner = the hex vertex nearest the body; the string line runs
  // to the opposite vertex (the throw diagonal). Shared by the mount
  // assembly and the Mount dimension overlay.
  let ci = 0;
  for (let k = 1; k < 6; k++) {
    if (Math.hypot(V[k][0] - P.projector.pos[0], V[k][1] - P.projector.pos[1])
      < Math.hypot(V[ci][0] - P.projector.pos[0], V[ci][1] - P.projector.pos[1])) ci = k;
  }
  const C = V[ci], F = V[(ci + 3) % 6];

  // ---- mount assembly (2026-08-11 VIVO revision): the REAL planned
  // hardware, to scale — a COTS VIVO MOUNT-VP01B universal projector mount
  // replaces the plywood corner arm. Spider feet sandwich the shroud rear
  // wall onto the chassis bosses (M4 through the ply); pole horizontal on
  // the corner bisector; ceiling plate hose-clamped to the paired legs on
  // two standoff blocks at the member-free bands. The fixed 6 in / 152 mm
  // profile + the header band sitting at pole height both demand the
  // standoff; the REAL leg ring stands ~40 mm outside the idealized vertex
  // so real blocks run ~40 mm — the drawn legs sit AT the vertex, so the
  // drawn blocks render thin. Cut files: enclosure/projector-shroud.scad;
  // build spec: wiring-guides/cuddle-projector-mount.md.
  {
    const legTop = (P.level + 1) * LH;      // top of the corner legs
    const bands = [legTop - 0.245, legTop - 0.145];  // block/clamp bands
    const asm = new THREE.Group();
    asm.position.set(P.projector.pos[0], yProj, P.projector.pos[1]);
    asm.rotation.y = (P.projector.arm_deg != null ? P.projector.arm_deg
      : (P.projector.yaw_deg || 0) + 180) * Math.PI / 180;
    const zCorner = Math.hypot(C[0] - P.projector.pos[0], C[1] - P.projector.pos[1]);
    const matShroud = new THREE.MeshStandardMaterial({ color: 0x9a7b52, roughness: 0.85,
      metalness: 0.02, transparent: true, opacity: 0.55, depthWrite: false });
    const boxAt = (w, h, dpt, x, y, z, mat) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, dpt), mat);
      m.position.set(x, y, z);
      asm.add(m);
    };
    // shroud sleeve: 4 walls + top, OPEN bottom (beam and dust both exit)
    // (2026-08-01: inner cavity re-sized to the official 383.7 x 147.7 plan)
    const iw = 0.3917, id = 0.1561, t = 0.006;
    boxAt(iw + 2 * t, bh + 0.006, t, 0, 0.0015, -(id / 2 + t / 2), matShroud);
    boxAt(iw + 2 * t, bh + 0.006, t, 0, 0.0015, id / 2 + t / 2, matShroud);
    for (const sx of [-1, 1]) boxAt(t, bh + 0.006, id + 2 * t, sx * (iw / 2 + t / 2), 0.0015, 0, matShroud);
    boxAt(iw + 2 * t, t, id + 2 * t, 0, bh / 2 + 0.006, 0, matShroud);
    // VP01B (152 mm profile is published; plate/hub/spider eyeballed from
    // photos): feet at the 223 x 150 boss corners outside the rear wall,
    // spider plane, hub, pole, plate, standoff blocks, clamps
    const zWall = id / 2 + t;               // rear wall outer face
    const zPlate = bd / 2 + 0.152;          // fixed 6 in profile off the bosses
    for (const sx of [-1, 1]) for (const sy of [-1, 1])
      boxAt(0.024, 0.012, 0.006, sx * 0.1115, sy * 0.075, zWall + 0.003, matGalv);
    boxAt(0.24, 0.165, 0.004, 0, 0, zWall + 0.008, matGalv);         // spider arms
    boxAt(0.07, 0.07, 0.03, 0, 0, zWall + 0.027, matGalv);           // hub + ball
    boxAt(0.035, 0.035, zPlate - zWall - 0.042, 0, 0,
      (zPlate + zWall + 0.042) / 2, matGalv);                        // pole
    boxAt(0.13, 0.13, 0.004, 0, 0, zPlate + 0.002, matGalv);         // ceiling plate
    // standoff blocks plate->legs at the two bands (thin here — see above)
    const blockD = Math.max(0.008, zCorner - 0.0215 - zPlate - 0.004);
    for (const bandY of bands)
      boxAt(0.06, 0.04, blockD, 0, bandY - yProj, zPlate + 0.004 + blockD / 2, matPly);
    // hose clamps wrap leg + block + plate at both bands
    for (const sx of [-1, 1]) {
      for (const bandY of bands) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.0245, 0.004, 8, 20), matGalv);
        ring.rotation.x = Math.PI / 2;
        ring.position.set(sx * 0.0225, bandY - yProj, zCorner);
        asm.add(ring);
      }
    }
    g.add(asm);
  }

  // ---- Mount overlay (header Mount button): the CALCULATED real-world rig
  // position for the arm/enclosure build, dimensioned off datums a tape
  // measure can find on the finished deck — the corner the arm clamps to
  // (the paired legs stand just outside the deck corner), the corner-to-
  // corner string line, and the deck surface. Every number derives from the
  // same layout values that draw the rig, so the callouts can never drift
  // from the picture. Build spec: wiring-guides/cuddle-projector-mount.md.
  const mountG = new THREE.Group();
  {
    const ySlab = P.level * LH + 0.14;   // deck ply top — the height datum
    const yDim = ySlab + 0.018;          // deck linework, above the show plane
    const mm = (v) => `${Math.round(v * 1000)} mm`;
    const dimMat = new THREE.LineBasicMaterial({ color: 0xffc966, transparent: true, opacity: 0.95, depthWrite: false });
    const dimDash = new THREE.LineDashedMaterial({ color: 0xffc966, transparent: true, opacity: 0.8, dashSize: 0.07, gapSize: 0.05, depthWrite: false });
    const vec = (x, y, z) => new THREE.Vector3(x, y, z);
    const seg = (a, b, mat) => {
      const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), mat || dimMat);
      if ((mat || dimMat).isLineDashedMaterial) l.computeLineDistances();
      mountG.add(l);
    };
    const note = () => {};
    const ring = (x, z, r) => {
      const m = new THREE.Mesh(new THREE.RingGeometry(r * 0.8, r, 40),
        new THREE.MeshBasicMaterial({ color: 0xffc966, transparent: true, opacity: 0.95, side: THREE.DoubleSide, depthWrite: false }));
      m.rotation.x = -Math.PI / 2;
      m.position.set(x, yDim, z);
      mountG.add(m);
    };
    const tick = (x, z, half = 0.09) => seg(vec(x - lat[0] * half, yDim, z - lat[1] * half),
      vec(x + lat[0] * half, yDim, z + lat[1] * half));
    const dAt = (x, z) => Math.hypot(x - C[0], z - C[1]);
    const winH = win.y - ySlab, topH = winH + bh;
    const roofH = LH + (cfg.layout.ceiling_height || 1.88) + 0.02 - ySlab;
    seg(vec(C[0], yDim, C[1]), vec(F[0], yDim, F[1]), dimDash);
    ring(C[0], C[1], 0.055);
    // labels spread in PLAN (out over the void / along the axes) — in the
    // overhead view height separation collapses, so each note hangs beside
    // its feature, never on top of the pile at the corner
    const outL = Math.hypot(C[0] - H.cx, C[1] - H.cz);
    const out = [(C[0] - H.cx) / outL, (C[1] - H.cz) / outL];
    note('corner legs — datum 0', C[0] + out[0] * 0.45, ySlab + 0.16, C[1] + out[1] * 0.45, 0.13);
    // lens plumb: deck target, vertical plumb line, height dimension
    ring(win.x, win.z, 0.075);
    tick(win.x, win.z);
    seg(vec(win.x, yDim, win.z), vec(win.x, win.y, win.z), dimDash);
    note(`lens plumb — ${mm(dAt(win.x, win.z))} in from the corner, ON the line`,
      win.x + fwd[0] * 0.6, ySlab + 0.42, win.z + fwd[1] * 0.6);
    note(`window ${mm(winH)} above deck`, win.x + lat[0] * 0.32, ySlab + winH * 0.56, win.z + lat[1] * 0.32);
    // body heights + the gap back to the legs (VP01B profile is FIXED at
    // 152 mm — radial position = standoff-block thickness, cut on-site)
    const rearX = P.projector.pos[0] - fwd[0] * bd / 2, rearZ = P.projector.pos[1] - fwd[1] * bd / 2;
    note(`body top ${mm(topH)} — ${mm(roofH - topH)} under the roof slab`,
      P.projector.pos[0] + lat[0] * 0.55, ySlab + topH, P.projector.pos[1] + lat[1] * 0.55, 0.13);
    note(`rear face ${mm(dAt(rearX, rearZ))} off the corner — VP01B 152 mm profile + ~40 mm blocks`,
      rearX - lat[0] * 0.5, ySlab + winH + 0.06, rearZ - lat[1] * 0.5, 0.13);
    // arm-angle callout: the arm bisects the 120° corner — 60° to each face
    const thDiag = Math.atan2(F[1] - C[1], F[0] - C[0]);
    const arcPts = [];
    for (let i = 0; i <= 32; i++) {
      const th = thDiag - Math.PI / 3 + (i / 32) * (2 * Math.PI / 3);
      arcPts.push(vec(C[0] + Math.cos(th) * 0.42, yDim, C[1] + Math.sin(th) * 0.42));
    }
    mountG.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(arcPts), dimMat));
    note('60° + 60° — pole on the corner bisector', C[0] + Math.cos(thDiag) * 0.66,
      ySlab + 0.30, C[1] + Math.sin(thDiag) * 0.66, 0.13);
    // mount hardware callouts (heights above deck; the standoff blocks sit
    // in the member-free bands so the plate never touches the header ends)
    note(`plate on the leg pair — blocks + clamps ~${mm((P.level + 1) * LH - 0.245 - ySlab)} & ~${mm((P.level + 1) * LH - 0.145 - ySlab)} above deck`,
      C[0], ySlab + 1.32, C[1], 0.13);
    note('pole axis in the HEADER band — blocks stand the plate off the steel', C[0] + fwd[0] * 0.35, ySlab + 1.62, C[1] + fwd[1] * 0.35, 0.13);
    note(`lit footprint ${litPct}% of deck — block thickness trues the near edge on-site`,
      P.image.center[0], ySlab + 0.55, P.image.center[1], 0.13);
    // image edges as deck tape marks: verify the mapping with a tape from
    // the corner before locking the arm
    const near = [P.image.center[0] - fwd[0] * P.image.d / 2, P.image.center[1] - fwd[1] * P.image.d / 2];
    const far = [P.image.center[0] + fwd[0] * P.image.d / 2, P.image.center[1] + fwd[1] * P.image.d / 2];
    tick(near[0], near[1]);
    tick(far[0], far[1]);
    note(`image near edge — ${mm(dAt(near[0], near[1]))} from the corner`, near[0], ySlab + 0.2, near[1], 0.13);
    note(`image far edge — ${mm(dAt(far[0], far[1]))} from the corner (${mm(Math.hypot(F[0] - far[0], F[1] - far[1]))} shy of the far corner)`,
      far[0], ySlab + 0.2, far[1], 0.13);
    // beam legend: solid = lit cone (never touches steel); dashed = the
    // optics' full rectangle, masked black — size the shroud aperture to it
    note('solid beam = LIT cone · faint dashed = masked spill (renders black)',
      win.x + fwd[0] * 1.0, ySlab + winH * 0.32, win.z + fwd[1] * 1.0, 0.13);
    mountG.visible = false;
    g.add(mountG);
  }

  S.projection = { cfg: P, mountG, canvas, ctx: canvas.getContext('2d'), tex, plane,
    cw, ch: chp, ppm, toPx, mast, winPx, deckPath, active: false, fade: 0,
    lastPresence: -1e9, smooth: null, accum: 0,
    // floor engine link (projection_engine.py stepped by sim_ui, streamed
    // over /sim/projection): the page renders engine STATE — scalar field,
    // stones/snakes/tiki, events — and sends back the lagged radar position.
    // It computes nothing. `theme` mirrors the server's active show.
    ws: null, grid: null, lut: null, heatCanvas: null, heatImg: null,
    heatStep: 2, theme: null, stones: [], snakes: [], snakeMeta: {}, flies: [],
    glyphs: [], glyphGlint: {}, scarabs: [],
    tracksPx: [], fx: [], engineFade: 0, lastTrackSend: 0 };
  let savedMount = null;
  try { savedMount = localStorage.getItem('lohp-sim-mount'); } catch (e) { /* private mode */ }
  setMountDims(savedMount === '1');
  connectProjection();
}

// Mount button: show/hide the calculated projector build-position dimensions
// (mountG linework built in buildProjection); the choice sticks per browser
function setMountDims(on) {
  const pr = S.projection;
  if (!pr || !pr.mountG) return;
  pr.mountG.visible = on;
  $('btn-mount').textContent = on ? 'Mount ✓' : 'Mount ✕';
  try { localStorage.setItem('lohp-sim-mount', on ? '1' : '0'); } catch (e) { /* private mode */ }
}

function connectProjection() {
  const pr = S.projection;
  if (!pr) return;
  window.simDebug = { pr, S };  // bench console access to live projection state
  const ws = new WebSocket(`ws://${HOST}:${location.port || 5001}/sim/projection`);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.error) { log('err', `projection: ${m.error}`); return; }
    if (m.hello) {
      pr.grid = m.hello.grid;
      pr.lut = m.hello.palette;
      pr.vidLut = m.hello.video_palette || null;
      pr.videoOwns = m.hello.video_owns || [];
      pr.heatStep = m.hello.heat_step || 2;
      const hc = document.createElement('canvas');
      hc.width = Math.floor(pr.grid[0] / pr.heatStep);
      hc.height = Math.floor(pr.grid[1] / pr.heatStep);
      pr.heatCanvas = hc;
      pr.heatImg = hc.getContext('2d').createImageData(hc.width, hc.height);
      // theme reset: a re-hello (theme switch) must not leak the other
      // show's entities into this one
      pr.theme = m.hello.theme || 'lava';
      pr.stoneImg = null; pr.monsterImg = null; pr.monsterHi = null; pr.baseImg = null;
      pr.spiderImgs = null; pr.spiderHi = null;
      pr.stones = []; pr.monster = null; pr.snakes = []; pr.snakeMeta = {};
      pr.flies = []; pr.glyphs = []; pr.glyphGlint = {};
      pr.traps = []; pr.trapMeta = {}; pr.sand = null; pr.sandMeta = null;
      pr.leaves = []; pr.motes = [];
      pr.fx = [];
      const fb = $('btn-floor');
      if (fb) fb.textContent = FLOOR_LABEL[pr.theme] || `Floor: ${pr.theme}`;
      // experiment: AI-generated base loop, served from experiments/video-base
      // when one exists for this theme; plays hidden, drawn instead of baseImg
      const bl = m.hello.base_loop || null;
      if (bl && (!pr.baseVid || pr.baseVid.dataset.src !== bl)) {
        const v = document.createElement('video');
        v.muted = true; v.loop = true; v.playsInline = true; v.preload = 'auto';
        v.src = bl; v.dataset.src = bl;
        // adopt only once frames exist — the old theme's video keeps the
        // floor textured through the switch instead of a light-only flash
        v.addEventListener('loadeddata', () => { pr.baseVid = v; }, { once: true });
        v.play().catch(() => {});
        if (!pr.baseVid) pr.baseVid = v;
      }
      if (!bl) pr.baseVid = null;
      const vb = $('btn-vidbase');
      if (vb) {
        vb.hidden = !bl;
        vb.textContent = S.vidBase ? 'Base: Video' : 'Base: Static';
      }
      if (m.hello.textures) {
        // the engine's precomputed artwork — the page draws the SAME pixels
        // production projects (numeral glyphs, cracks, the altar, the mask)
        const mk = (t) => {
          const c = document.createElement('canvas');
          c.width = t.w; c.height = t.h;
          const bytes = Uint8Array.from(atob(t.rgba), ch => ch.charCodeAt(0));
          c.getContext('2d').putImageData(
            new ImageData(new Uint8ClampedArray(bytes.buffer), t.w, t.h), 0, 0);
          return c;
        };
        const tex2 = m.hello.textures;
        if (tex2.stones) {
          pr.stoneImg = {};
          for (const t of tex2.stones) pr.stoneImg[t.id] = mk(t);
        }
        pr.stonesHi = null;
        if (tex2.stones_hi) {
          pr.stonesHi = { gridW: tex2.stones_hi.grid_w, imgs: {} };
          for (const t of tex2.stones_hi.frames) pr.stonesHi.imgs[t.id] = mk(t);
        }
        if (tex2.base) pr.baseImg = mk(tex2.base);
        if (tex2.spider) pr.spiderImgs = tex2.spider.map(mk);
        pr.spiderHi = tex2.spider_hi
          ? { imgs: tex2.spider_hi.frames.map(mk), gridW: tex2.spider_hi.grid_w }
          : null;
        pr.islandImg = mk(tex2.island);
        pr.islandPos = tex2.island;
        if (tex2.monster) pr.monsterImg = mk(tex2.monster);
        pr.monsterHi = tex2.monster_hi
          ? { img: mk(tex2.monster_hi.frame), gridW: tex2.monster_hi.grid_w }
          : null;
        if (tex2.glyphs) pr.glyphs = tex2.glyphs.map(t => ({ id: t.id, x: t.x, y: t.y, glow: t.glow || 0, gw: t.gw || 0, img: mk(t) }));
        if (tex2.snakes) for (const s of tex2.snakes) pr.snakeMeta[s.id] = s;
        // chamber: per-trap slab/pit sprites + the quicksand pool's dry patch
        if (tex2.traps) for (const t of tex2.traps) {
          pr.trapMeta[t.id] = { x: t.x, y: t.y, dir: t.dir, slide: t.slide,
            slab: mk(t.slab), pit: mk(t.pit) };
        }
        if (tex2.sand) pr.sandMeta = { x: tex2.sand.x, y: tex2.sand.y, r: tex2.sand.r,
          x0: tex2.sand.x0, y0: tex2.sand.y0, img: mk(tex2.sand.patch) };
      }
      pr.ws = ws;
      log('info', `projection: floor engine connected — ${pr.theme.toUpperCase()} (${pr.grid[0]}×${pr.grid[1]})`);
      return;
    }
    pr.engineFade = m.fade || 0;
    pr.stones = m.stones || [];
    pr.tracksPx = m.tracks || [];
    pr.monster = m.monster || null;
    pr.snakes = m.snakes || [];
    pr.flies = m.flies || [];
    pr.glyphGlint = {};
    for (const g of m.glyphs || []) pr.glyphGlint[g.id] = g.glint;
    pr.scarabs = m.scarabs || [];
    pr.spider = m.spider || null;
    pr.web = m.web || null;
    pr.traps = m.traps || [];
    pr.sand = m.sand || null;
    pr.leaves = m.leaves || [];
    pr.motes = m.motes || [];
    if (m.heat && pr.heatCanvas) paintHeat(pr, m.heat);
    for (const e of m.events || []) {
      // events the video loop portrays itself (baked serpent, baked bursts)
      // neither ring nor narrate while that loop is what's showing
      const owned = pr.vidActive && pr.videoOwns
        && ((e.e === 'pop' && pr.videoOwns.includes('pops'))
            || (e.e.startsWith('monster_') && pr.videoOwns.includes('monster')));
      if (e.x != null && !owned) pr.fx.push({ ...e, t0: clock.getElapsedTime() });
      if (owned) continue;
      if (e.e === 'sink') log('info', `projection: stone ${e.id} sinks underfoot`);
      if (e.e === 'rise') log('info', `projection: stone ${e.id} rises`);
      if (e.e === 'monster_swim') log('info', pr.theme === 'water' ? 'projection: something big glides beneath the water…' : 'projection: something moves beneath the lava…');
      if (e.e === 'monster_breach') log('ok', pr.theme === 'water' ? 'projection: the CROCODILE breaches!' : 'projection: KUKULKAN breaches!');
      if (e.e === 'monster_sink') log('info', pr.theme === 'water' ? 'projection: it slides back under the current' : 'projection: Kukulkan slips back under');
      if (e.e === 'spider_scurry') log('ok', 'projection: the spider SCURRIES away!');
      if (e.e === 'spider_catch') log('ok', 'projection: the spider SNATCHES a scarab!');
      if (e.e === 'spider_web') log('info', 'projection: the spider spins a web…');
      if (e.e === 'spider_web_gone') log('info', 'projection: the spider takes down its web');
      if (e.e === 'scarab_erupt') log('ok', 'projection: SCARABS pour from the cracks!');
      if (e.e === 'scarab_drain') log('info', 'projection: the scarabs drain away between the stones');
      if (e.e === 'snake_flee') {
        const kind = pr.snakeMeta[e.id] && pr.snakeMeta[e.id].kind;
        log('info', kind === 'rattler'
          ? 'projection: the rattlesnake RATTLES away from your feet!'
          : 'projection: a snake darts away from your feet');
      }
      if (e.e === 'trap_tremble') log('info', 'projection: the slab underfoot SHUDDERS…');
      if (e.e === 'trap_open') log('ok', e.slam ? 'projection: the trap door SLAMS open under your feet!' : 'projection: the TRAP DOOR grinds open!');
      if (e.e === 'trap_eyes') log('ok', 'projection: eyes open in the dark below…');
      if (e.e === 'trap_shut') log('info', 'projection: the slab grinds shut');
      if (e.e === 'sand_grip') log('ok', 'projection: the floor turns to QUICKSAND underfoot…');
      if (e.e === 'sand_release') log('info', 'projection: the quicksand lets go and settles still');
    }
  };
  ws.onclose = () => { pr.ws = null; setTimeout(connectProjection, 2500); };
  ws.onerror = () => ws.close();
}

function paintHeat(pr, b64) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const d = pr.heatImg.data;
  // over a video base the field is a LIGHT ramp, not the picture — lava and
  // water swap in a near-neutral LUT so the footage keeps its own color
  const lut = (pr.vidActive && pr.vidLut) ? pr.vidLut : pr.lut;
  for (let i = 0; i < bytes.length; i++) {
    const c = lut[bytes[i]] || [0, 0, 0];
    d[i * 4] = c[0]; d[i * 4 + 1] = c[1]; d[i * 4 + 2] = c[2]; d[i * 4 + 3] = 255;
  }
  pr.heatCanvas.getContext('2d').putImageData(pr.heatImg, 0, 0);
}

function projectionCue(source) {
  const pr = S.projection;
  if (!pr) return;
  pr.lastPresence = clock.getElapsedTime();
  if (pr.ws && pr.ws.readyState === 1) pr.ws.send(JSON.stringify({ cue: source }));
  if (!pr.active) {
    pr.active = true;
    log('info', `projection: floor show ON (${source})`);
  }
}

function updateProjection(dt) {
  const pr = S.projection;
  if (!pr) return;
  const P = pr.cfg, T = P.tracker, now = clock.getElapsedTime();

  // what the LD2450 sees: the walker, on the deck, inside its wedge
  const seen = S.level === P.level && zoneContains({ x: T.pos[0], z: T.pos[1],
    yaw: T.yaw_deg || 0, fov: T.fov_deg || 120, range: T.range_m || 6,
    clip: T.clip || null }, S.pos.x, S.pos.z);
  if (seen) {
    if (!pr.active) projectionCue('presence');
    pr.lastPresence = now;
    // first-order lag ≈ radar cadence + render pipeline
    const k = 1 - Math.exp(-dt / ((T.latency_ms || 150) / 1000));
    if (!pr.smooth) pr.smooth = { x: S.pos.x, z: S.pos.z };
    pr.smooth.x += (S.pos.x - pr.smooth.x) * k;
    pr.smooth.z += (S.pos.z - pr.smooth.z) * k;
  } else {
    pr.smooth = null;
    if (pr.active && now - pr.lastPresence > (P.timeout_s || 60)) {
      pr.active = false;
      log('info', 'projection: absence timeout — floor show off');
    }
  }

  // feed the engine the lagged radar position at ~10 Hz (null = unseen);
  // while the engine is connected its fade is the truth — the show is shared
  // state across every viewer, like the real deck
  if (pr.ws && pr.ws.readyState === 1 && now - pr.lastTrackSend > 0.1) {
    pr.lastTrackSend = now;
    pr.ws.send(JSON.stringify({ track: pr.smooth ? [pr.smooth.x, pr.smooth.z] : null }));
  }
  pr.fade = Math.max(0, Math.min(1, pr.fade + (pr.active ? dt : -dt) * 1.5));
  if (pr.ws && pr.ws.readyState === 1) pr.fade = pr.engineFade;
  pr.plane.material.opacity = 0.95 * pr.fade;
  if (pr.fade <= 0) return;
  pr.accum += dt;
  if (pr.accum < 0.05) return; // ~20 fps content is plenty
  drawProjection(pr, Math.min(pr.accum, 0.25), now);
  pr.accum = 0;
}

function drawProjection(pr, dt, now) {
  const { ctx, cw, ch, mast, ppm } = pr;
  ctx.clearRect(0, 0, cw, ch);
  // everything renders inside the deck-outline mask; off-deck pixels stay
  // black (masked), so the wash reads deck-shaped, not rectangular
  ctx.save();
  ctx.clip(pr.deckPath);
  if (pr.heatCanvas && pr.engineFade > 0) {
    ctx.imageSmoothingEnabled = true;
    const vsrc = (S.vidBase && pr.baseVid && pr.baseVid.readyState >= 2)
      ? pr.baseVid : null;
    pr.vidActive = !!vsrc;
    if (pr.baseImg || vsrc) {
      // textured floor (jungle leaves / temple flags): the base with the
      // palette-mapped LIGHT field multiplied over it — mirrors the engine.
      // Base = the AI loop video when toggled on (falls back to the static
      // texture until the video has data), else the production static base.
      ctx.drawImage(vsrc || pr.baseImg, 0, 0, cw, ch);
      ctx.globalCompositeOperation = 'multiply';
      ctx.drawImage(pr.heatCanvas, 0, 0, cw, ch);
      ctx.globalCompositeOperation = 'source-over';
    } else {
      // the field IS the picture (lava), palette-mapped in paintHeat
      ctx.drawImage(pr.heatCanvas, 0, 0, cw, ch);
    }
  } else {
    ctx.fillStyle = '#03150b'; // engine offline: dim wash = visible projected area
    ctx.fillRect(0, 0, cw, ch);
  }

  // mast island + its real shadow: cast away from the projection window,
  // spreading like the penumbra of a pole taller than the light source
  const wp = pr.winPx;
  const sdx = mast.x - wp.x, sdy = mast.y - wp.y;
  const sd = Math.hypot(sdx, sdy) || 1;
  const ux = sdx / sd, uy = sdy / sd, vx = -uy, vy = ux;
  const L = cw + ch, far = mast.r * (1 + L / sd);
  ctx.fillStyle = 'rgba(0,0,0,0.8)';
  ctx.beginPath();
  ctx.moveTo(mast.x - vx * mast.r, mast.y - vy * mast.r);
  ctx.lineTo(mast.x + vx * mast.r, mast.y + vy * mast.r);
  ctx.lineTo(mast.x + ux * L + vx * far, mast.y + uy * L + vy * far);
  ctx.lineTo(mast.x + ux * L - vx * far, mast.y + uy * L - vy * far);
  ctx.closePath(); ctx.fill();
  const gs = cw / (pr.grid ? pr.grid[0] : cw);
  if (pr.islandImg) {
    // the carved sun-stone altar around the mast base, from the engine
    const iw = pr.islandImg.width * gs, ih = pr.islandImg.height * gs;
    ctx.drawImage(pr.islandImg, pr.islandPos.x * gs - iw / 2, pr.islandPos.y * gs - ih / 2, iw, ih);
  } else {
    ctx.fillStyle = '#0d3320';
    ctx.beginPath(); ctx.arc(mast.x, mast.y, mast.r + 10, 0, 7); ctx.fill();
    ctx.strokeStyle = '#2c7a4c'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(mast.x, mast.y, mast.r + 10, 0, 7); ctx.stroke();
  }

  // tracked walker: pulsing ring at the (lagged) radar position
  let tgt = null;
  if (pr.smooth) {
    const { x: tx, y: ty } = pr.toPx(pr.smooth.x, pr.smooth.z);
    if (tx > -80 && tx < cw + 80 && ty > -80 && ty < ch + 80) {
      tgt = { x: tx, y: ty };
      ctx.strokeStyle = 'rgba(120,255,170,0.5)';
      ctx.lineWidth = 3;
      const rr = 24 + 10 * Math.sin(now * 5);
      ctx.beginPath(); ctx.arc(tx, ty, rr, 0, 7); ctx.stroke();
    }
  }

  // stepping stones from the engine (grid px → canvas px). Visual rules
  // mirror projection_engine._draw_stone: sinking shrinks + heats, rising
  // grows + cools, phase < 0 = the suspense beat before a riser surfaces.
  const stonesOwned = pr.vidActive && pr.videoOwns && pr.videoOwns.includes('stones');
  for (const s of pr.stones) {
    if (s.state === 'down' || s.phase < 0) {
      if (stonesOwned && s.state === 'down') {
        // the loop's baked understudy boulder sits in the footage under this
        // spot, and the multiply light can never brighten it into melt —
        // paint the molten pool over it live
        const rr = s.r * gs * 1.28;
        const flick = 0.8 + 0.2 * Math.sin(now * 7 + s.id * 2.1);
        const pool = ctx.createRadialGradient(s.x * gs, s.y * gs, rr * 0.15,
          s.x * gs, s.y * gs, rr);
        if (pr.theme === 'water') {  // closed water swirls over the spot
          pool.addColorStop(0, `rgba(196,232,228,${0.95 * flick})`);
          pool.addColorStop(0.6, `rgba(110,172,170,${0.85 * flick})`);
          pool.addColorStop(1, 'rgba(20,60,66,0)');
        } else {                     // melt floods the vacated gap
          pool.addColorStop(0, `rgba(255,196,70,${0.95 * flick})`);
          pool.addColorStop(0.55, `rgba(255,122,22,${0.88 * flick})`);
          pool.addColorStop(1, 'rgba(150,36,8,0)');
        }
        ctx.fillStyle = pool;
        ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs, rr, 0, 7); ctx.fill();
      }
      continue;
    }
    let scale = 1, heat = 0;  // grey rock; hot only mid-transition (engine rules)
    if (s.state === 'sinking') { scale = 1 - 0.55 * s.phase; heat = s.phase; }
    else if (s.state === 'rising') { scale = 0.45 + 0.55 * s.phase; heat = (1 - s.phase) * 0.8; }
    const r = s.r * gs * scale;
    // soft contact shadow grounds the stone on the floor footage
    const sr = r * 1.3;
    const sh = ctx.createRadialGradient(s.x * gs, s.y * gs + r * 0.14, r * 0.35,
      s.x * gs, s.y * gs + r * 0.14, sr);
    sh.addColorStop(0, 'rgba(0,0,0,0.40)');
    sh.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = sh;
    ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs + r * 0.14, sr, 0, 7); ctx.fill();
    const hi = pr.stonesHi && pr.stonesHi.imgs[s.id];
    const img = hi || (pr.stoneImg && pr.stoneImg[s.id]);
    if (img) {
      // hi = generated skin at source res (sized by the engine's grid_w);
      // else the grid-res patch sized by its own pixel box
      const w = hi ? pr.stonesHi.gridW * gs * scale : img.width * gs * scale;
      const h = hi ? w : img.height * gs * scale;
      ctx.drawImage(img, s.x * gs - w / 2, s.y * gs - h / 2, w, h);
      if (heat > 0.02) {          // melting / splashing: whole rock heats over
        ctx.globalAlpha = Math.min(1, heat);
        ctx.fillStyle = pr.theme === 'water' ? 'rgb(196,232,228)' : 'rgb(255,120,20)';
        ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs, r, 0, 7); ctx.fill();
        ctx.globalAlpha = 1;
      } else if (s.glint > 0.05) { // stone notices an approaching walker
        ctx.globalAlpha = s.glint * 0.35;
        ctx.strokeStyle = pr.theme === 'water' ? 'rgb(190,235,230)' : 'rgb(255,196,96)';
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs, r * 0.55, 0, 7); ctx.stroke();
        ctx.globalAlpha = 1;
      }
    } else {  // texture not arrived yet: plain grey stand-in
      const mix = (a, b) => (a + (b - a) * heat) | 0;
      ctx.fillStyle = `rgb(${mix(128, 255)},${mix(128, 120)},${mix(132, 20)})`;
      ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs, r, 0, 7); ctx.fill();
      ctx.strokeStyle = heat > 0.05 ? `rgba(255,140,30,${0.3 + 0.6 * heat})` : 'rgba(58,58,64,0.9)';
      ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs, r, 0, 7); ctx.stroke();
    }
  }

  // glyphs: jungle = mossy stones drawn always (+ glint ring); temple =
  // gold carve sprites drawn AT the streamed glint alpha (invisible idle)
  for (const g of pr.glyphs) {
    const w = (g.gw || g.img.width) * gs, h = (g.gw || g.img.height) * gs;
    const gl = pr.glyphGlint[g.id] || 0;
    if (g.glow) {
      // carve glints register onto the STATIC base's carved flagstones —
      // over a video base those stones don't exist and the gold reads as
      // floating ring artifacts, so they stay off while the video is up
      if (!pr.vidActive && gl > 0.03) {
        ctx.globalAlpha = gl;
        ctx.drawImage(g.img, g.x * gs - w / 2, g.y * gs - h / 2, w, h);
        ctx.globalAlpha = 1;
      }
      continue;
    }
    ctx.drawImage(g.img, g.x * gs - w / 2, g.y * gs - h / 2, w, h);
    if (gl > 0.05) {
      ctx.globalAlpha = gl * 0.35;
      ctx.strokeStyle = 'rgb(205,235,130)';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(g.x * gs, g.y * gs, g.img.width * gs * 0.34, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  // chamber: the quicksand pool — dry patch always (it lives OVER the base
  // and the video, like the trap slabs), then the live grip show on top
  if (pr.sandMeta) {
    const sm = pr.sandMeta;
    ctx.drawImage(sm.img, sm.x0 * gs, sm.y0 * gs, sm.img.width * gs, sm.img.height * gs);
    const sd = pr.sand;
    if (sd && sd.act > 0.02) {
      const scx = sm.x * gs, scy = sm.y * gs, R = sm.r * gs, act = sd.act;
      ctx.fillStyle = `rgba(112,90,60,${0.5 * act})`;
      ctx.beginPath(); ctx.arc(scx, scy, R, 0, 7); ctx.fill();
      for (let k = 0; k < 3; k++) {  // contracting rings: the surface pulls inward
        const f = (now * 0.30 + k / 3) % 1;
        ctx.strokeStyle = `rgba(81,65,43,${0.30 * act * Math.min(1, f * 3)})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath(); ctx.arc(scx, scy, Math.max(2, (1 - f) * R), 0, 7); ctx.stroke();
      }
      ctx.strokeStyle = `rgba(67,54,36,${0.35 * act})`;  // slow spiral streaks
      ctx.lineWidth = 3;
      for (let k = 0; k < 3; k++) {
        const a0 = -sd.sw * 0.87 + k * 2.094;
        ctx.beginPath(); ctx.arc(scx, scy, R * 0.55, a0, a0 + 0.9); ctx.stroke();
      }
      if (sd.grip) {  // the sink mark under the feet, a tide ring around it
        const gx = sd.grip[0] * gs, gy = sd.grip[1] * gs;
        const rr = (0.09 + 0.07 * act) * pr.ppm;
        ctx.fillStyle = 'rgba(64,52,36,0.75)';
        ctx.beginPath(); ctx.arc(gx, gy, rr, 0, 7); ctx.fill();
        ctx.strokeStyle = `rgba(206,188,148,${0.35 * act})`;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(gx, gy, rr + 2.5, 0, 7); ctx.stroke();
      }
      for (const [bx, by, age] of sd.bubs || []) {
        const bf = age / 0.9;
        ctx.strokeStyle = `rgba(84,68,45,${0.5 * (1 - bf)})`;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(bx * gs, by * gs, (0.02 + 0.05 * bf) * pr.ppm, 0, 7); ctx.stroke();
      }
    }
  }

  // chamber: trap doors — pit + blinking eyes under a sliding slab; the
  // slab draws at rest too (it carries the seam + ring pull art)
  for (const t of pr.traps) {
    const tm = pr.trapMeta[t.id];
    if (!tm) continue;
    const tw = tm.slab.width * gs, th = tm.slab.height * gs;
    const tcx = tm.x * gs, tcy = tm.y * gs;
    if (t.ph > 0.02) {
      ctx.globalAlpha = Math.min(1, t.ph * 1.4);
      ctx.drawImage(tm.pit, tcx - tw / 2, tcy - th / 2, tw, th);
      ctx.globalAlpha = 1;
      if (t.eyes > 0.02) {
        const blink = Math.sin(now * 4.4 + t.id * 2.3) > 0.96 ? 0.1 : 1;
        const ea = t.eyes * blink;
        const off = 0.055 * pr.ppm;
        for (const sv of [-1, 1]) {
          const ex = tcx + tm.dir[1] * sv * off - tm.dir[0] * 1.5 * gs;
          const ey = tcy + tm.dir[0] * sv * off - tm.dir[1] * 1.5 * gs;
          ctx.fillStyle = `rgba(255,200,90,${0.9 * ea})`;
          ctx.beginPath(); ctx.arc(ex, ey, Math.max(1.6, 0.014 * pr.ppm), 0, 7); ctx.fill();
          ctx.fillStyle = `rgba(255,246,204,${0.9 * ea})`;
          ctx.beginPath(); ctx.arc(ex, ey, Math.max(0.8, 0.006 * pr.ppm), 0, 7); ctx.fill();
        }
      }
    }
    const jit = (t.st === 'shut' && t.arm > 0) ? Math.sin(now * 42) * 1.2 * t.arm : 0;
    const slide = tm.slide * t.ph + jit;
    const am = t.ph < 0.7 ? 1 : Math.max(0, 1 - (t.ph - 0.7) / 0.3);
    if (am > 0) {
      ctx.globalAlpha = am;
      ctx.drawImage(tm.slab, (tm.x + tm.dir[0] * slide) * gs - tw / 2,
        (tm.y + tm.dir[1] * slide) * gs - th / 2, tw, th);
      ctx.globalAlpha = 1;
    }
  }

  // chamber: leaves spiraling down the sun-shaft + drifting dust motes
  for (const [lx, ly, rot, lk, la] of pr.leaves) {
    if (la <= 0.02) continue;
    ctx.save();
    ctx.translate(lx * gs, ly * gs);
    ctx.rotate(rot);
    const LL = 0.085 * pr.ppm;
    ctx.globalAlpha = la;
    ctx.fillStyle = lk ? 'rgb(124,74,30)' : 'rgb(96,88,34)';
    ctx.beginPath(); ctx.ellipse(0, 0, LL, LL * 0.42, 0, 0, 7); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.25)';
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(-LL * 0.8, 0); ctx.lineTo(LL * 0.8, 0); ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.restore();
  }
  for (const [mx, my, ma] of pr.motes) {
    ctx.fillStyle = `rgba(255,250,214,${0.7 * ma})`;
    ctx.beginPath(); ctx.arc(mx * gs, my * gs, 1.6, 0, 7); ctx.fill();
  }

  // jungle: snakes — a smooth tapered body built from the engine spine: one
  // colored quad per span between per-point width offsets (shared offset
  // points → no seams), matching the production distance-field renderer.
  // colors/w come per spine index in the hello meta.
  for (const sn of pr.snakes) {
    const meta = pr.snakeMeta[sn.id];
    if (!meta || !meta.w || sn.pts.length < 2) continue;
    const P = sn.pts, n = P.length;
    const nrm = [];   // per-point normals from averaged neighbor directions
    for (let i = 0; i < n; i++) {
      const a = P[Math.max(0, i - 1)], b = P[Math.min(n - 1, i + 1)];
      const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
      nrm.push([-dy / l, dx / l]);
    }
    const wAt = i => (meta.w[Math.min(i, meta.w.length - 1)] || 2) * gs;
    for (let i = 0; i < n - 1; i++) {
      const c = meta.colors[Math.min(i, meta.colors.length - 1)];
      const w0 = wAt(i), w1 = wAt(i + 1);
      ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
      ctx.strokeStyle = ctx.fillStyle;
      ctx.lineWidth = 0.8;   // paints over antialias seams between quads
      ctx.beginPath();
      ctx.moveTo(P[i][0] * gs + nrm[i][0] * w0, P[i][1] * gs + nrm[i][1] * w0);
      ctx.lineTo(P[i + 1][0] * gs + nrm[i + 1][0] * w1, P[i + 1][1] * gs + nrm[i + 1][1] * w1);
      ctx.lineTo(P[i + 1][0] * gs - nrm[i + 1][0] * w1, P[i + 1][1] * gs - nrm[i + 1][1] * w1);
      ctx.lineTo(P[i][0] * gs - nrm[i][0] * w0, P[i][1] * gs - nrm[i][1] * w0);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
    // soft dorsal sheen down the spine
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineCap = ctx.lineJoin = 'round';
    ctx.lineWidth = Math.max(1, wAt(Math.floor(n / 2)) * 0.9);
    ctx.beginPath();
    ctx.moveTo(P[0][0] * gs, P[0][1] * gs);
    for (let i = 1; i < n; i++) ctx.lineTo(P[i][0] * gs, P[i][1] * gs);
    ctx.stroke();
    // eyes on the spade sides (index 1 sits on the widest head arc), tongue
    const [hx, hy] = P[0];
    const a = Math.atan2(hy - P[1][1], hx - P[1][0]);
    const ca = Math.cos(a), sa = Math.sin(a);
    const hw = meta.w[Math.min(1, meta.w.length - 1)];
    ctx.fillStyle = 'rgb(250,214,90)'; // amber eyes on all three (mirrors the engine)
    for (const sv of [-1, 1]) {
      ctx.beginPath();
      ctx.arc((P[1][0] + nrm[1][0] * sv * hw * 0.72) * gs,
        (P[1][1] + nrm[1][1] * sv * hw * 0.72) * gs,
        Math.max(1.2, hw * gs * 0.20), 0, 7);
      ctx.fill();
    }
    if (sn.tongue) {
      const tip = hw * 0.35;
      ctx.strokeStyle = 'rgb(205,62,48)';
      ctx.lineWidth = Math.max(1.5, hw * gs * 0.16);
      for (const sv of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo((hx + ca * tip) * gs, (hy + sa * tip) * gs);
        ctx.lineTo((hx + ca * (tip + 2.6) - sa * sv * 1.1) * gs,
          (hy + sa * (tip + 2.6) + ca * sv * 1.1) * gs);
        ctx.stroke();
      }
    }
    if (meta.kind === 'rattler' && sn.flee) {
      // the rattle buzzes: flickering halo at the tail tip
      const [tx2, ty2] = P[n - 1];
      ctx.globalAlpha = 0.25 + 0.25 * Math.sin(now * 50);
      ctx.strokeStyle = 'rgb(202,182,144)';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(tx2 * gs, ty2 * gs, 7, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  // temple: the spider's web — nine spokes + a light spiral, alpha rides
  // the build/teardown progress streamed from the engine
  if (pr.web) {
    const wb = pr.web;
    ctx.save();
    ctx.translate(wb.x * gs, wb.y * gs);
    ctx.rotate(wb.rot);
    ctx.strokeStyle = `rgba(205,210,215,${0.38 * wb.p})`;
    ctx.lineWidth = 1;
    const R = wb.r * gs;
    for (let k = 0; k < 9; k++) {
      const a = k * Math.PI * 2 / 9;
      ctx.beginPath(); ctx.moveTo(0, 0);
      ctx.lineTo(Math.cos(a) * R, Math.sin(a) * R); ctx.stroke();
    }
    for (let k = 1; k <= 4; k++) {
      ctx.beginPath(); ctx.arc(0, 0, R * (0.16 + 0.84 * k / 4) - R * 0.08, 0, 7);
      ctx.stroke();
    }
    ctx.restore();
  }

  // temple: the resident spider (rotate to heading, gait frame from state).
  // The video-keyed skin's source frames (spiderHi) draw at full res —
  // rotate + DOWNscale beats upscaling the grid-res sprite.
  if (pr.spider && (pr.spiderHi || pr.spiderImgs)) {
    const spd = pr.spider;
    ctx.save();
    ctx.translate(spd.x * gs, spd.y * gs);
    ctx.rotate(spd.ang);
    if (pr.spiderHi) {
      const im = pr.spiderHi.imgs[Math.min(spd.gait, pr.spiderHi.imgs.length - 1)];
      const w = pr.spiderHi.gridW * gs;
      ctx.drawImage(im, -w / 2, -w / 2, w, w);
    } else {
      const img = pr.spiderImgs[Math.min(spd.gait, pr.spiderImgs.length - 1)];
      const w = img.width * gs, h = img.height * gs;
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
    }
    ctx.restore();
  }

  // temple: the scarab swarm — tiny dark ovals with a bronze-green sheen,
  // skittering (positions + headings straight from the engine)
  for (const [x, y, a] of pr.scarabs) {
    ctx.save();
    ctx.translate(x * gs, y * gs);
    ctx.rotate(a);
    const L = 0.035 * pr.ppm, W = L * 0.62;  // pr.ppm = canvas px per meter
    ctx.fillStyle = 'rgb(26,20,13)';
    ctx.beginPath(); ctx.ellipse(0, 0, L, W, 0, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(96,128,72,0.8)';
    ctx.beginPath(); ctx.ellipse(L * 0.35, 0, L * 0.3, W * 0.45, 0, 0, 7); ctx.fill();
    ctx.restore();
  }

  // jungle: fireflies (the engine also glows the field under each one)
  for (const f of pr.flies) {
    ctx.fillStyle = 'rgba(255,240,170,0.9)';
    ctx.beginPath(); ctx.arc(f.x * gs, f.y * gs, 2.5, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(220,230,120,0.25)';
    ctx.beginPath(); ctx.arc(f.x * gs, f.y * gs, 7, 0, 7); ctx.fill();
  }

  // Kukulkan, rotated to his heading (image points +x; engine pose drives)
  if (pr.monster && (pr.monsterHi || pr.monsterImg)
      && !(pr.vidActive && pr.videoOwns && pr.videoOwns.includes('monster'))) {
    const mo = pr.monster;
    ctx.save();
    ctx.translate(mo.x * gs, mo.y * gs);
    ctx.rotate(mo.rot);
    if (pr.monsterHi) {
      // skin frame at source res: rotate + downscale, sized by the engine
      const w = pr.monsterHi.gridW * gs * mo.scale;
      ctx.drawImage(pr.monsterHi.img, -w / 2, -w / 2, w, w);
    } else {
      const w = pr.monsterImg.width * gs * mo.scale, h = pr.monsterImg.height * gs * mo.scale;
      ctx.drawImage(pr.monsterImg, -w / 2, -h / 2, w, h);
    }
    ctx.restore();
    if (mo.glow > 0.1) {
      const gr = (pr.monsterHi ? pr.monsterHi.gridW * 0.5 : pr.monsterImg.width * 0.62);
      ctx.globalAlpha = mo.glow * 0.18;
      ctx.strokeStyle = 'rgb(255,200,90)';
      ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(mo.x * gs, mo.y * gs, gr * gs, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  // engine events as short-lived rings: bubble pops / snake flees small,
  // sink/rise big, monster + tiki biggest; jungle rings go leaf-gold
  pr.fx = pr.fx.filter(e => now - e.t0 < 0.6);
  for (const e of pr.fx) {
    const a = (now - e.t0) / 0.6;
    const base = e.e === 'pop' ? 6 : e.e === 'snake_flee' ? 9
      : e.e === 'trap_open' ? 20 : e.e === 'sand_bubble' ? 5
        : e.e.startsWith('monster') ? 24 : 14;
    const col = pr.theme === 'jungle' ? '205,235,130'
      : pr.theme === 'chamber' ? '226,232,164'
        : pr.theme === 'water' ? '210,240,236' : '255,180,60';
    ctx.strokeStyle = `rgba(${col},${0.7 * (1 - a)})`;
    ctx.lineWidth = 2 + 3 * (1 - a);
    ctx.beginPath();
    ctx.arc(e.x * gs, e.y * gs, base + 30 * a, 0, 7);
    ctx.stroke();
  }

  // every walker the engine is tracking (other tabs included — shared show)
  for (const t of pr.tracksPx) {
    ctx.strokeStyle = 'rgba(255,220,150,0.25)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(t.x * gs, t.y * gs, 18, 0, 7); ctx.stroke();
  }
  ctx.restore(); // end deck mask
  pr.tex.needsUpdate = true;
}

// ------------------------------------------------- Cuddle orb (sim preview)
// The Guition JC3636W518C round display (360x360 ST77916), rear of Cuddle
// Cross: a carved Olmec colossal head whose ember eyes track whoever the
// room's LD2450 reports (the SAME node-box radar the floor projection reads),
// with a first-order lag so the gaze previews how the hardware will feel.
// The device renderer (firmware/orb/face_olmec.h, per-pixel shaded stone) is
// authoritative; this canvas port matches its character, not its pixels.
// Real panel is a 47 mm (1.8") disc; drawn bigger here so the face reads
// across the deck. Layout `eye` key drives it; the Eye button toggles it.
// Touching the real orb opens a carved five-wedge action menu (firmware
// menu_olmec.h: lights / ambience / storm-hold-to-charge / floor theme / calm —
// the orb IS the Cuddle control surface, no wall buttons there) that hits
// the REST API directly — see wiring-guides/cuddle-orb-plan.md. The sim
// preview shows the idle face only; preview the menu art with
// firmware/orb/tools/preview_face --menu.
const EYE_MODES = ['off', 'olmec'];
const EYE_LABEL = { off: 'Eye ✕', olmec: 'Eye: Olmec' };

function buildEye(cfg) {
  const E = cfg.layout.eye;
  if (!E) return;
  const LH = S.levelHeight, D = E.diameter || 0.12;   // real panel Ø 0.0325
  const g = new THREE.Group();
  g.position.set(E.mount[0], (E.level || 0) * LH + (E.h || 1.5), E.mount[1]);
  g.rotation.y = (E.yaw_deg || 0) * Math.PI / 180;    // 0 = faces the street

  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(D / 2 + 0.006, D / 2 + 0.006, 0.022, 40),
    new THREE.MeshStandardMaterial({ color: 0x17191c, roughness: 0.5, metalness: 0.2 }));
  body.rotation.x = Math.PI / 2;                       // round face -> local +z
  g.add(body);
  const bezel = new THREE.Mesh(new THREE.RingGeometry(D / 2 - 0.001, D / 2 + 0.006, 40),
    new THREE.MeshStandardMaterial({ color: 0x2a2d31, roughness: 0.4, metalness: 0.6,
      side: THREE.DoubleSide }));
  bezel.position.z = 0.0115;
  g.add(bezel);

  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 360;                 // native ST77916 pixels
  const tex = new THREE.CanvasTexture(canvas);
  const disc = new THREE.Mesh(new THREE.CircleGeometry(D / 2, 48),
    new THREE.MeshBasicMaterial({ map: tex }));       // unlit: it's a screen
  disc.position.z = 0.012;
  g.add(disc);
  grp(E.level || 0).add(g);

  let saved = null; try { saved = localStorage.getItem('lohp-sim-eye'); } catch (e) { /**/ }
  S.eye = { cfg: E, group: g, canvas, ctx: canvas.getContext('2d'), tex,
    pupil: { x: 0, y: 0 }, dil: 0.5, smooth: null, awake: 0, lastSeen: -1e9,
    blinkT: 2.5, blink: 0, accum: 0, drift: Math.random() * 6.28 };
  setEyeSkin(EYE_MODES.includes(saved) ? saved : (E.skin || 'olmec'));
}

function setEyeSkin(mode) {
  S.eyeSkin = mode;
  if (S.eye) S.eye.group.visible = mode !== 'off';
  $('btn-eye').textContent = EYE_LABEL[mode] || 'Eye ✕';
  try { localStorage.setItem('lohp-sim-eye', mode); } catch (e) { /* private mode */ }
}

function updateEye(dt) {
  const ey = S.eye;
  if (!ey || S.eyeSkin === 'off') return;
  const E = ey.cfg, T = E.tracker, now = clock.getElapsedTime();

  // what the LD2450 sees: the walker, on this deck, inside the node-box wedge
  const seen = T && S.level === (E.level || 0) && zoneContains({ x: T.pos[0], z: T.pos[1],
    yaw: T.yaw_deg || 0, fov: T.fov_deg || 120, range: T.range_m || 6,
    clip: T.clip || null }, S.pos.x, S.pos.z);

  let gx, gy, near = 0;
  if (seen) {
    ey.lastSeen = now;
    const k = 1 - Math.exp(-dt / ((T.latency_ms || 150) / 1000));
    if (!ey.smooth) ey.smooth = { x: S.pos.x, z: S.pos.z };
    ey.smooth.x += (S.pos.x - ey.smooth.x) * k;
    ey.smooth.z += (S.pos.z - ey.smooth.z) * k;
    // target in the orb's frame: local +z = facing, +x = the orb's right
    const yaw = (E.yaw_deg || 0) * Math.PI / 180;
    const dx = ey.smooth.x - E.mount[0], dz = ey.smooth.z - E.mount[1];
    const fwd = dx * Math.sin(yaw) + dz * Math.cos(yaw);
    const rgt = dx * Math.cos(yaw) - dz * Math.sin(yaw);
    const horiz = Math.hypot(dx, dz) || 0.01;
    // +rgt (person on the orb's right) reads as the viewer's left, which the
    // disc mirrors back — so screen-x follows rgt (flip if gaze reads reversed)
    gx = Math.max(-1, Math.min(1, Math.sin(Math.atan2(rgt, Math.max(fwd, 0.05))) * 1.3));
    // the orb rides above chest height and looks down at people on the deck
    const orbY = (E.level || 0) * S.levelHeight + (E.h || 1.5);
    gy = Math.max(-0.4, Math.min(1,
      Math.atan2(orbY - ((E.level || 0) * S.levelHeight + 1.0), horiz) / 0.9));
    near = Math.max(0, Math.min(1, 1 - horiz / (T.range_m || 6)));
  } else {
    ey.smooth = null;                                 // idle drift, ease to center
    ey.drift += dt * 0.5;
    gx = Math.sin(ey.drift) * 0.32;
    gy = Math.sin(ey.drift * 0.7 + 1.3) * 0.2;
  }

  const ease = 1 - Math.exp(-dt / 0.12);
  ey.pupil.x += (gx - ey.pupil.x) * ease;
  ey.pupil.y += (gy - ey.pupil.y) * ease;
  ey.awake += ((now - ey.lastSeen < 4 ? 1 : 0) - ey.awake) * (1 - Math.exp(-dt / 0.4));
  ey.dil += ((0.35 + 0.5 * near) - ey.dil) * ease;    // pupil size 0..1

  ey.blinkT -= dt;                                     // blink cadence
  if (ey.blinkT <= 0 && ey.blink === 0) ey.blink = 0.001;
  if (ey.blink > 0) {
    ey.blink += dt / 0.16;                             // ~160 ms close+open
    if (ey.blink >= 2) { ey.blink = 0; ey.blinkT = 2.5 + Math.random() * 4.5; }
  }

  ey.accum += dt;
  if (ey.accum < 0.033) return;                        // ~30 fps content
  drawEye(ey, now);
  ey.accum = 0;
}

function drawEye(ey, now) {
  const ctx = ey.ctx;
  const blink = ey.blink > 1 ? 2 - ey.blink : ey.blink; // 0 -> 1 -> 0
  ctx.clearRect(0, 0, 360, 360);
  ctx.save();
  ctx.beginPath(); ctx.arc(180, 180, 180, 0, 7); ctx.clip(); // round panel
  drawOlmecFace(ctx, ey, blink, now);
  ctx.restore();
  ey.tex.needsUpdate = true;
}

// Carved basalt Olmec colossal head. Geometry mirrors firmware/orb/face_olmec.h
// (face coords x SCALE 165, center 180): helmet band + bosses, brow ridges,
// deep sockets with ember eyes that track, broad nose with breathing nostrils,
// thick slightly-frowning lips. Canvas gradients stand in for the per-pixel
// stone shader; the device render is the reference.
function drawOlmecFace(ctx, ey, blink, now) {
  // Legends of the Hidden Temple-style talking stone head (homage) —
  // terracotta, stepped headdress with teal inlays, ear spools, big white
  // glowing eyes, and a jaw slab that slides open in its slot to "speak".
  const breath = 0.5 + 0.5 * Math.sin(now * 1.21);
  const glow = ey.awake * (0.8 + 0.2 * Math.sin(now * 2.9));
  let jaw = 0, talkGlow = 0;                          // stateless chatter
  const cyc = now % 26;
  if (cyc < 2.0) {
    const env = Math.sin(Math.PI * Math.min(cyc / 2.0 * 1.15, 1));
    jaw = env * (0.25 + 0.75 * Math.abs(Math.sin(now * 13.2)));
    talkGlow = env;
  }

  const dome = ctx.createRadialGradient(140, 130, 30, 180, 190, 210);
  dome.addColorStop(0, '#c9a26b'); dome.addColorStop(0.55, '#a37e50');
  dome.addColorStop(0.85, '#5c4630'); dome.addColorStop(1, '#0b0a08');
  ctx.fillStyle = dome; ctx.fillRect(0, 0, 360, 360);

  // stepped headdress: block tier with teal fret gaps, medallion, crown ledge
  const tierG = ctx.createLinearGradient(50, 0, 310, 0);
  tierG.addColorStop(0, 'rgba(63,118,105,0)'); tierG.addColorStop(0.15, 'rgba(63,118,105,0.55)');
  tierG.addColorStop(0.85, 'rgba(63,118,105,0.55)'); tierG.addColorStop(1, 'rgba(63,118,105,0)');
  ctx.fillStyle = tierG; ctx.fillRect(50, 71, 260, 26);
  for (let i = 0; i < 4; i++) {                        // raised blocks
    const bx = 180 + (-0.54 + 0.36 * i) * 165;
    ctx.fillStyle = '#b08a58';
    ctx.beginPath(); ctx.ellipse(bx, 84, 15, 10, 0, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(255,240,210,0.18)';
    ctx.beginPath(); ctx.ellipse(bx - 2, 80, 11, 5, 0, 0, 7); ctx.fill();
  }
  ctx.fillStyle = '#ba9260';                           // central medallion
  ctx.beginPath(); ctx.arc(180, 88, 15, 0, 7); ctx.fill();
  ctx.fillStyle = '#8a6a40';
  ctx.beginPath(); ctx.arc(180, 88, 6, 0, 7); ctx.fill();
  ctx.fillStyle = 'rgba(150,116,74,0.9)';              // crown ledge
  ctx.fillRect(58, 106, 244, 12);
  ctx.fillStyle = 'rgba(40,30,20,0.35)'; ctx.fillRect(58, 117, 244, 3);

  // single heavy brow ledge
  ctx.fillStyle = '#9d7a4c'; ctx.fillRect(97, 132, 166, 9);
  ctx.fillStyle = 'rgba(35,26,17,0.5)'; ctx.fillRect(97, 141, 166, 5);

  // sockets, then the big glowing eyes
  for (const s of [-1, 1]) {
    ctx.fillStyle = 'rgba(30,22,14,0.35)';
    ctx.beginPath(); ctx.ellipse(180 + s * 46.2, 159, 36, 23, 0, 0, 7); ctx.fill();
  }
  for (const s of [-1, 1]) {
    const ecx = 180 + s * 46.2, ecy = 158.5;
    if (glow > 0.05) {                                 // lit-up halo
      const halo = ctx.createRadialGradient(ecx, ecy, 20, ecx, ecy, 44);
      halo.addColorStop(0, `rgba(255,190,90,${0.30 * glow})`);
      halo.addColorStop(1, 'rgba(255,150,40,0)');
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(ecx, ecy, 44, 0, 7); ctx.fill();
    }
    ctx.fillStyle = `rgb(${Math.round(226 + 29 * glow)},${Math.round(212 + 20 * glow)},${Math.round(184 + 2 * glow)})`;
    ctx.beginPath(); ctx.ellipse(ecx, ecy, 32, 20, 0, 0, 7); ctx.fill();
    const px = ecx + ey.pupil.x * 16, py = ecy + ey.pupil.y * 9;
    const ir = 12 + 3 * ey.dil;
    ctx.fillStyle = '#50321e';
    ctx.beginPath(); ctx.arc(px, py, ir, 0, 7); ctx.fill();
    ctx.fillStyle = '#100b09';
    ctx.beginPath(); ctx.arc(px, py, ir * 0.62, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(245,238,220,0.9)';
    ctx.beginPath(); ctx.arc(px - 4, py - 4, 2, 0, 7); ctx.fill();
  }

  // broad nose: lit ridge, wide base, alae, breathing nostrils
  ctx.strokeStyle = 'rgba(220,182,128,0.8)'; ctx.lineWidth = 7; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(175, 146); ctx.lineTo(175, 196); ctx.stroke();
  ctx.strokeStyle = 'rgba(70,52,34,0.55)'; ctx.lineWidth = 8;
  ctx.beginPath(); ctx.moveTo(187, 152); ctx.lineTo(188, 198); ctx.stroke();
  for (const s of [-1, 1]) {
    ctx.fillStyle = '#b48c58';
    ctx.beginPath(); ctx.ellipse(180 + s * 26.4, 201, 13, 10, 0, 0, 7); ctx.fill();
    ctx.fillStyle = `rgba(20,13,9,${0.55 + 0.3 * breath})`;
    ctx.beginPath(); ctx.ellipse(180 + s * 17.3, 209, 6.5, 4.5, 0, 0, 7); ctx.fill();
  }

  // upper lip ledge, then the jaw slot + sliding slab
  ctx.fillStyle = '#a88150'; ctx.fillRect(115, 224, 130, 10);
  ctx.fillStyle = 'rgba(35,25,16,0.5)'; ctx.fillRect(115, 233, 130, 3);
  ctx.fillStyle = '#1a0f0b';                           // the void
  ctx.fillRect(117, 235, 126, 46);
  if (talkGlow > 0.02) {
    const vg = ctx.createLinearGradient(0, 235, 0, 281);
    vg.addColorStop(0, `rgba(150,60,20,${0.2 * talkGlow})`);
    vg.addColorStop(1, `rgba(220,95,30,${0.55 * talkGlow})`);
    ctx.fillStyle = vg; ctx.fillRect(117, 235, 126, 46);
  }
  ctx.fillStyle = 'rgba(25,17,11,0.7)';                // slot grooves
  ctx.fillRect(114, 235, 4, 62); ctx.fillRect(242, 235, 4, 62);
  const slabTop = 232 + jaw * 30;                      // the slab itself
  const slab = ctx.createLinearGradient(0, slabTop, 0, slabTop + 50);
  slab.addColorStop(0, '#c39a63'); slab.addColorStop(0.25, '#a37c4d');
  slab.addColorStop(1, '#7c5d3a');
  ctx.fillStyle = slab;
  ctx.beginPath(); ctx.roundRect(119, slabTop, 122, 50, [3, 3, 14, 14]); ctx.fill();
  ctx.fillStyle = 'rgba(255,235,200,0.25)';            // lower lip highlight
  ctx.fillRect(125, slabTop + 3, 110, 4);
  ctx.fillStyle = 'rgba(40,29,18,0.35)';               // lip/chin crease
  ctx.fillRect(127, slabTop + 17, 106, 3);
  ctx.fillStyle = 'rgba(255,235,200,0.14)';            // chin catch-light
  ctx.beginPath(); ctx.ellipse(180, slabTop + 36, 30, 9, 0, 0, 7); ctx.fill();

  // ear spools at the rim
  for (const s of [-1, 1]) {
    const ex = 180 + s * 122;
    ctx.fillStyle = '#ab855a';
    ctx.beginPath(); ctx.arc(ex, 190, 15, 0, 7); ctx.fill();
    ctx.fillStyle = '#6d5335';
    ctx.beginPath(); ctx.arc(ex, 190, 8, 0, 7); ctx.fill();
    ctx.fillStyle = '#bd955f';
    ctx.beginPath(); ctx.arc(ex, 190, 3.5, 0, 7); ctx.fill();
  }
}

// ---------------------------------------------------------------- audio unit
function connectAudio() {
  const a = S.audio;
  if (a.ws && (a.ws.readyState === WebSocket.OPEN || a.ws.readyState === WebSocket.CONNECTING)) return;
  a.ws = new WebSocket(AUDIO_WS);
  a.ws.onopen = () => {
    setDot('audio', true);
    a.ws.send(JSON.stringify({
      type: 'client_connected',
      data: { unit_name: 'LOHP-SIM-WEB', associated_rooms: Object.keys(S.cfg.room_layout) },
    }));
    log('info', 'audio unit connected (claimed all rooms)');
  };
  a.ws.onclose = () => {
    setDot('audio', false);
    if (a.on) setTimeout(connectAudio, 3000);
  };
  a.ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    switch (msg.type) {
      case 'play_effect_audio': {
        const d = msg.data || {};
        playEffectAudio(msg.room, d.file_name, d.volume, d.loop, d.effect_name);
        break;
      }
      case 'audio_stop':
        stopEffectAudio('room' in msg ? msg.room : null);
        break;
      case 'play_room_ambience': {
        const d = msg.data || {};
        playRoomAmbience(msg.room, d.file_name, d.volume, d.effect_name, d.loop, d.fade_s);
        break;
      }
      case 'stop_room_ambience':
        stopRoomAmbience('room' in msg ? msg.room : null);
        break;
      case 'start_maze_ambience': {
        const d = msg.data || {};
        playMazeAmbience(d.file_name, d.volume, d.loop, d.fade_s);
        break;
      }
      case 'stop_maze_ambience':
        stopMazeAmbience();
        break;
      case 'connection_response':
      case 'status_update_response':
      case 'audio_files_to_download':
        break;
      default:
        log('info', `audio ws: ${msg.type}`);
    }
  };
}

function startAudio() {
  const a = S.audio;
  if (!a.ctx) {
    try {
      a.ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
      setDot('audio', false);
      log('err', `audio unavailable: ${e.message}`);
      return;
    }
  }
  a.on = true;
  connectAudio();

  const resume = () => {
    if (a.ctx && a.ctx.state === 'suspended') a.ctx.resume().catch(() => {});
    removeEventListener('pointerdown', resume);
    removeEventListener('keydown', resume);
    removeEventListener('touchstart', resume);
  };
  if (a.ctx.state === 'suspended') {
    addEventListener('pointerdown', resume, { once: true });
    addEventListener('keydown', resume, { once: true });
    addEventListener('touchstart', resume, { once: true });
  }
}

async function getBuffer(file) {
  const a = S.audio;
  if (a.buffers.has(file)) return a.buffers.get(file);
  const audioPath = file.split('/').map(encodeURIComponent).join('/');
  const res = await fetch(`${API}/api/audio/${audioPath}`);
  if (!res.ok) throw new Error(`audio ${file}: ${res.status}`);
  const buf = await a.ctx.decodeAudioData(await res.arrayBuffer());
  a.buffers.set(file, buf);
  return buf;
}

async function playEffectAudio(room, file, volume, loop, effectName) {
  const a = S.audio;
  if (!a.ctx || !file) return;
  try {
    const buf = await getBuffer(file);
    const src = a.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = !!loop;
    const vol = volume == null ? 0.8 : volume;
    const gain = a.ctx.createGain();
    gain.gain.value = earCanHear(room || '__all__') ? vol : 0;
    const rm = room && S.roomsMeshes[room];
    if (rm) {
      const p = new PannerNode(a.ctx, {
        panningModel: 'HRTF', distanceModel: 'linear',
        refDistance: 1.5, maxDistance: 18, rolloffFactor: 1,
        positionX: rm.center.x, positionY: rm.center.y, positionZ: rm.center.z,
      });
      gain.connect(p).connect(a.ctx.destination);
    } else {
      gain.connect(a.ctx.destination);
    }
    src.connect(gain);
    src.start();
    const key = room || '__all__';
    const bucket = a.rooms.get(key) || [];
    const rec = { src, gain, vol };
    src.onended = () => {
      const items = a.rooms.get(key);
      if (!items) return;
      const ix = items.indexOf(rec);
      if (ix >= 0) items.splice(ix, 1);
      if (!items.length) a.rooms.delete(key);
    };
    bucket.push(rec);
    a.rooms.set(key, bucket);
    log('info', `♪ ${effectName || ''} ${file}${room ? ' @ ' + room : ''}`);
  } catch (e) {
    log('err', `audio play failed: ${e.message}`);
  }
}

function stopEffectAudio(room) {
  const a = S.audio;
  const stopOne = (key) => {
    const items = a.rooms.get(key) || [];
    for (const v of items) {
      try { v.src.stop(); } catch (e) { /* already stopped */ }
    }
    a.rooms.delete(key);
  };
  if (room == null) { for (const key of Array.from(a.rooms.keys())) stopOne(key); }
  else stopOne(room);
}

// Bed track changes fade out/in instead of hard-cutting. The ramp lives on a
// dedicated `fade` gain in series with the gating gain: updateAudioGating
// rewrites the gating gain every frame, so a ramp there would be clobbered.
// The server sends the configured fade in the payload (`fade_s`).
const AMBIENCE_FADE_S = 2.0;

function ambienceFadeS(fadeS) {
  const f = +fadeS;
  return Number.isFinite(f) && f >= 0 ? f : AMBIENCE_FADE_S;
}

function newFadeIn(fadeS) {
  const a = S.audio;
  const fade = a.ctx.createGain();
  if (fadeS > 0) {
    const t = a.ctx.currentTime;
    fade.gain.setValueAtTime(0, t);
    fade.gain.linearRampToValueAtTime(1, t + fadeS);
  }
  return fade;
}

// Ramp a detached bed record to silence, then stop its source.
function retireAmbience(rec, fadeS) {
  const a = S.audio;
  const t = a.ctx.currentTime;
  const f = Math.max(fadeS, 0.02);
  rec.fade.gain.cancelScheduledValues(t);
  rec.fade.gain.setValueAtTime(rec.fade.gain.value, t);
  rec.fade.gain.linearRampToValueAtTime(0, t + f);
  try { rec.src.stop(t + f + 0.05); } catch (e) { /* already stopped */ }
}

// Looping room bed (the Cuddle floor show's lava rumble). Kept in its own map
// so effect audio plays OVER it and audio_stop never cuts it — the same split
// the Pi client makes between effect players and ambience players.
async function playRoomAmbience(room, file, volume, effectName, loop = true, fadeS) {
  const a = S.audio;
  if (!a.ctx || !file) return;
  try {
    const f = ambienceFadeS(fadeS);
    const buf = await getBuffer(file);
    stopRoomAmbience(room, f);
    const src = a.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = loop !== false;
    const vol = volume == null ? 0.5 : volume;
    const fade = newFadeIn(f);
    const gain = a.ctx.createGain();
    gain.gain.value = earCanHear(room || '__all__') ? vol : 0;
    const rm = room && S.roomsMeshes[room];
    if (rm) {
      const p = new PannerNode(a.ctx, {
        panningModel: 'HRTF', distanceModel: 'linear',
        refDistance: 1.5, maxDistance: 18, rolloffFactor: 1,
        positionX: rm.center.x, positionY: rm.center.y, positionZ: rm.center.z,
      });
      gain.connect(p).connect(a.ctx.destination);
    } else {
      gain.connect(a.ctx.destination);
    }
    src.connect(fade).connect(gain);
    src.start();
    a.beds.set(room || '__all__', { src, gain, fade, vol, fadeS: f });
    log('info', `≈ bed ${effectName || ''} ${file}${room ? ' @ ' + room : ''}`);
  } catch (e) {
    log('err', `ambience play failed: ${e.message}`);
  }
}

function stopRoomAmbience(room, fadeS) {
  const a = S.audio;
  const stopOne = (key) => {
    const v = a.beds.get(key);
    if (v) { retireAmbience(v, fadeS == null ? v.fadeS : fadeS); a.beds.delete(key); }
  };
  if (room == null) { for (const key of Array.from(a.beds.keys())) stopOne(key); }
  else stopOne(room);
}

async function playMazeAmbience(file, volume, loop = true, fadeS) {
  const a = S.audio;
  if (!a.ctx || !file) return;
  if (a.maze && a.maze.file === file) {
    return;
  }
  try {
    const f = ambienceFadeS(fadeS);
    const buf = await getBuffer(file);
    stopMazeAmbience(f);
    const src = a.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = loop !== false;
    const fade = newFadeIn(f);
    const gain = a.ctx.createGain();
    const vol = volume == null ? 0.5 : volume;
    gain.gain.value = vol;
    src.connect(fade).connect(gain).connect(a.ctx.destination);
    src.start();
    a.maze = { src, gain, fade, vol, file, fadeS: f };
    log('info', `≈ maze ambience: ${file}`);
  } catch (e) {
    log('err', `maze ambience failed: ${e.message}`);
  }
}

function stopMazeAmbience(fadeS) {
  const a = S.audio;
  if (a.maze) { retireAmbience(a.maze, fadeS == null ? a.maze.fadeS : fadeS); a.maze = null; }
}

function updateListener() {
  const a = S.audio;
  if (!a.ctx) return;
  const l = a.ctx.listener;
  const cam = activeCamera();
  const dir = new THREE.Vector3();
  cam.getWorldDirection(dir);
  const p = S.mode === 'first' ? S.pos : cam.position;
  if (l.positionX) {
    l.positionX.value = p.x; l.positionY.value = p.y; l.positionZ.value = p.z;
    l.forwardX.value = dir.x; l.forwardY.value = dir.y; l.forwardZ.value = dir.z;
    l.upX.value = 0; l.upY.value = 1; l.upZ.value = 0;
  } else {
    l.setPosition(p.x, p.y, p.z);
    l.setOrientation(dir.x, dir.y, dir.z, 0, 1, 0);
  }
}

// ------------------------------------------------- who can hear what (2026-08-01)
// Real speakers sit in their rooms, so in first-person you only hear the room
// you are standing in (Tim). Fly-around modes (top/street) keep hearing
// everything — that's the operator view, and its panners already fade with
// distance. '__all__' = a broadcast to every speaker: wherever you stand, the
// local one plays it.
function pointInPoly(x, z, pts) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, zi] = pts[i], [xj, zj] = pts[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}

// The room the first-person ear is inside, or null (scaffold between rooms).
// Hex rooms carry their exact footprint polygons (Exit/Entrance halves, the
// Cuddle deck); wing rooms are their layout rects; 'both' rooms (the climb
// shafts) match either level.
function roomAtEar() {
  if (S.mode !== 'first') return null;
  const x = S.pos.x, z = S.pos.z;
  let rectHit = null;
  for (const [name, rm] of Object.entries(S.roomsMeshes)) {
    if (rm.poly) {
      if (rm.level === S.level && pointInPoly(x, z, rm.poly)) return name;
    } else if (!rectHit) {
      const r = rm.room;
      const levelOk = r.floor === 'both' || (r.floor || 0) === S.level;
      if (levelOk && x >= r.x && x <= r.x + r.w && z >= r.z && z <= r.z + r.d) rectHit = name;
    }
  }
  return rectHit;
}

function earCanHear(key) {
  return S.mode !== 'first' || key === '__all__' || key === S.audio.earRoom;
}

function updateAudioGating() {
  const a = S.audio;
  if (!a.ctx) return;
  const room = roomAtEar();
  if (room !== a.earRoom) {
    a.earRoom = room;
    if (S.mode === 'first') log('info', `ear: ${room || 'between rooms'}`);
  }
  const t = a.ctx.currentTime;
  const set = (g, vol) => g.gain.setTargetAtTime(vol, t, 0.08);
  for (const [key, items] of a.rooms) for (const v of items) set(v.gain, earCanHear(key) ? v.vol : 0);
  for (const [key, v] of a.beds) set(v.gain, earCanHear(key) ? v.vol : 0);
  if (a.maze) {
    // The maze bed is global. A local bed, normally Cuddle's floor-show bed,
    // owns that speaker while active; everywhere else the maze bed stays up.
    const bedHere = S.mode === 'first' && a.earRoom && a.beds.has(a.earRoom);
    set(a.maze.gain, bedHere ? 0 : a.maze.vol);
  }
}

// ---------------------------------------------------------------- DMX feed
function connectDmx() {
  const ws = new WebSocket(`ws://${HOST}:${location.port || 5001}/sim/dmx`);
  S.dmxWs = ws;
  ws.onopen = () => setDot('dmx', true);
  ws.onclose = () => { setDot('dmx', false); setTimeout(connectDmx, 2000); };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      S.frame = Uint8Array.from(msg.ch);
      S.seq = msg.seq;
    } catch (e) { /* ignore */ }
  };
}

// ---------------------------------------------------------------- controls
function activeCamera() {
  return S.mode === 'first' ? camera : (S.mode === 'top' ? topCam : streetCam);
}

// Frame the whole structure in street view with margin, keeping it inside the
// canvas area left of the side panel (which overlays the right ~324px).
function frameStreetView() {
  const b = S.bounds;
  if (!b) return;
  const cx = (b.minX + b.maxX) / 2;
  const hHalf = Math.atan(Math.tan(streetCam.fov * Math.PI / 360) * streetCam.aspect);
  const avail = Math.max(0.45, (innerWidth - 340) / innerWidth);
  const halfW = (b.maxX - b.minX) / 2 + 1.0;
  const dist = halfW / (Math.tan(hHalf) * avail);
  const shift = Math.tan(hHalf) * dist * (1 - avail);
  streetCam.position.set(cx + shift, 2.7, b.frontZ + dist);
  streetCam.lookAt(cx + shift, 1.85, b.frontZ);
  S.streetLook = { x: cx + shift, y: 1.85, z: b.frontZ }; // E/R orbit pivot
}

const MODES = ['street', 'first', 'top'];
const MODE_LABEL = { street: 'Street view', first: 'Noclip fly', top: 'Overhead plan' };
function setMode(mode) {
  S.mode = mode;
  const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
  $('btn-view').textContent = `View: ${MODE_LABEL[mode]} ▸ ${MODE_LABEL[next]}`;
  $('crosshair').classList.toggle('hidden', mode !== 'first' || !S.pointerLocked);
  $('floor-filter').classList.toggle('hidden', mode !== 'top');
  roofGroup.visible = mode !== 'top'; // keep the plan view readable
  if (mode !== 'top') setFloorFilter('both');
  if (mode !== 'first' && document.pointerLockElement) document.exitPointerLock();
}

function setFloorFilter(which) {
  levelGroups[0].visible = which !== 'upper';
  levelGroups[1].visible = which !== 'ground';
  for (const btn of document.querySelectorAll('#floor-filter button')) {
    btn.classList.toggle('active', btn.dataset.f === which);
  }
}

function climb(viaLadder) {
  S.level = S.level === 0 ? 1 : 0;
  S.pos.y = EYE + S.level * S.levelHeight; // hop the noclip eye to that floor
  S.teleporting = true;
  toast(S.level ? '↑ climbed to the upper floor' : '↓ climbed down to the ground floor');
  log('info', `climbed ${S.level ? 'up' : 'down'}${viaLadder ? ' (' + viaLadder.room + ')' : ''}`);
}

function clickWorld(ev, cam) {
  const ndc = new THREE.Vector2((ev.clientX / innerWidth) * 2 - 1, -(ev.clientY / innerHeight) * 2 + 1);
  raycaster.setFromCamera(ndc, cam);
  const hitsI = raycaster.intersectObjects(S.interactables, false);
  if (hitsI.length) {
    const ud = hitsI[0].object.userData;
    if (ud.sensor) { fireSensor(ud.sensor, true); return; }
    if (ud.ladder) { climb(ud.ladder); return; }
  }
  const grounds = [];
  scene.traverse(o => { if (o.userData && o.userData.ground && o.visible !== false) grounds.push(o); });
  const hits = raycaster.intersectObjects(grounds, false);
  if (hits.length) {
    S.pos.x = hits[0].point.x; S.pos.z = hits[0].point.z;
    S.pos.y = hits[0].point.y + EYE; // noclip: land the eye above the clicked slab
    S.level = hits[0].object.userData.level || 0;
    S.teleporting = true;
    toast(`Teleported (${S.level ? 'upper' : 'ground'} floor)`);
  }
}

function setupControls(cfg) {
  const el = renderer.domElement;

  el.addEventListener('click', (ev) => {
    if (S.mode === 'first') {
      if (!S.pointerLocked) el.requestPointerLock();
      else tryInteract();
    } else {
      if (dragMoved > 6) return; // was a pan, not a click
      clickWorld(ev, activeCamera());
    }
  });

  document.addEventListener('pointerlockchange', () => {
    S.pointerLocked = document.pointerLockElement === el;
    $('crosshair').classList.toggle('hidden', S.mode !== 'first' || !S.pointerLocked);
  });

  document.addEventListener('mousemove', (ev) => {
    if (!S.pointerLocked || S.mode !== 'first') return;
    S.yaw -= ev.movementX * 0.0024;
    S.pitch = Math.max(-1.45, Math.min(1.45, S.pitch - ev.movementY * 0.0024));
  });

  addEventListener('keydown', (ev) => {
    if (ev.target.tagName === 'INPUT' || ev.target.tagName === 'SELECT') return;
    S.keys[ev.code] = true;
    if (ev.code === 'Space' && S.mode === 'first') ev.preventDefault(); // fly up, not a UI click
    if (ev.code === 'KeyN') setDayNight(!ENV.day);
    if (ev.code === 'KeyM') setMode(MODES[(MODES.indexOf(S.mode) + 1) % MODES.length]);
    if (ev.code === 'KeyE' && S.mode === 'first') tryInteract();
  });
  addEventListener('keyup', (ev) => { S.keys[ev.code] = false; });

  // street dolly / top zoom
  el.addEventListener('wheel', (ev) => {
    if (S.mode === 'top' && topCam) {
      topCam.zoom = Math.max(0.4, Math.min(24, topCam.zoom * (ev.deltaY > 0 ? 0.9 : 1.11))); // deep enough to inspect the deck steel
      topCam.updateProjectionMatrix();
    } else if (S.mode === 'street') {
      streetCam.position.z = Math.max(4.5, Math.min(30, streetCam.position.z + (ev.deltaY > 0 ? 0.9 : -0.9)));
    }
  }, { passive: true });

  // drag panning (street: truck along x/y; top: pan x/z)
  let dragging = false, lastX = 0, lastY = 0;
  el.addEventListener('mousedown', (ev) => { dragging = true; dragMoved = 0; lastX = ev.clientX; lastY = ev.clientY; });
  addEventListener('mouseup', () => { dragging = false; });
  addEventListener('mousemove', (ev) => {
    if (!dragging) return;
    const dx = ev.clientX - lastX, dy = ev.clientY - lastY;
    dragMoved += Math.abs(dx) + Math.abs(dy);
    lastX = ev.clientX; lastY = ev.clientY;
    if (S.mode === 'top' && topCam) {
      const k = 0.045 / topCam.zoom;
      const kx = k * (innerWidth / innerHeight) * 0.6;
      const cy = Math.cos(topYaw), sy = Math.sin(topYaw); // pan in SCREEN axes
      topCam.position.x += -dx * kx * cy + dy * k * sy;
      topCam.position.z += -dx * kx * sy - dy * k * cy;
    } else if (S.mode === 'street') {
      streetCam.position.x = Math.max(-3, Math.min(23, streetCam.position.x - dx * 0.018));
      streetCam.position.y = Math.max(0.9, Math.min(8, streetCam.position.y + dy * 0.012));
    }
  });

  $('btn-view').onclick = () => setMode(MODES[(MODES.indexOf(S.mode) + 1) % MODES.length]);
  $('btn-respawn').onclick = () => {
    const sp = cfg.layout.spawn;
    S.pos.set(sp.pos[0], 1.6, sp.pos[1]);
    S.level = sp.level || 0;
    S.yaw = (sp.yaw_deg || 0) * Math.PI / 180;
    S.pitch = 0;
    S.teleporting = true;
    setMode('first');
  };
  $('btn-daynight').onclick = () => setDayNight(!ENV.day);
  $('btn-towers').onclick = () => setTowersVisible(!(towersGroup && towersGroup.visible));
  $('btn-camp').onclick = () => setCampVisible(!(campGroup && campGroup.visible));
  $('btn-sign').onclick = () => setSignVisible(!(signGroup && signGroup.visible));
  $('btn-steel').onclick = () => setSteelMode(STEEL_MODES[(STEEL_MODES.indexOf(steelMode) + 1) % STEEL_MODES.length]);
  $('btn-eye').onclick = () => setEyeSkin(EYE_MODES[(EYE_MODES.indexOf(S.eyeSkin) + 1) % EYE_MODES.length]);
  $('btn-mount').onclick = () => {
    if (!S.projection) { log('err', 'projection: rig not in the layout — no mount dims'); return; }
    setMountDims(!S.projection.mountG.visible);
  };
  $('btn-floor').onclick = () => {
    // server-side shared state, deliberately NOT localStorage: every tab (and
    // production, were it wired) shows one theme, like the one real deck
    const pr = S.projection;
    if (!pr || !pr.ws || pr.ws.readyState !== 1) {
      log('err', 'projection: floor engine not connected — cannot switch theme');
      return;
    }
    const next = FLOOR_THEMES[(FLOOR_THEMES.indexOf(pr.theme) + 1) % FLOOR_THEMES.length];
    pr.ws.send(JSON.stringify({ theme: next }));
    log('info', `projection: floor theme → ${next.toUpperCase()}`);
  };
  $('btn-vidbase').onclick = () => {
    S.vidBase = !S.vidBase;
    $('btn-vidbase').textContent = S.vidBase ? 'Base: Video' : 'Base: Static';
    const v = S.projection && S.projection.baseVid;
    if (S.vidBase && v) v.play().catch(() => {});
    log('info', `projection: base layer → ${S.vidBase ? 'AI VIDEO loop' : 'static texture'}`);
  };
  for (const btn of document.querySelectorAll('#floor-filter button')) {
    btn.onclick = () => setFloorFilter(btn.dataset.f);
  }

  addEventListener('resize', () => {
    for (const cam of [camera, streetCam]) {
      cam.aspect = innerWidth / innerHeight;
      cam.updateProjectionMatrix();
    }
    if (topCam) {
      const a = innerWidth / innerHeight;
      topCam.left = -36 * a; topCam.right = 36 * a;
      topCam.updateProjectionMatrix();
    }
    renderer.setSize(innerWidth, innerHeight);
    if (S.mode === 'street') frameStreetView();
  });
}
let dragMoved = 0;

function tryInteract() {
  raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
  const hits = raycaster.intersectObjects(S.interactables, false);
  if (hits.length && hits[0].distance <= 2.2) {
    const ud = hits[0].object.userData;
    if (ud.sensor) { fireSensor(ud.sensor, true); return; }
    if (ud.ladder) { climb(ud.ladder); return; }
  }
  // forgiving climb: standing near a ladder is enough, no aiming required
  const lad = nearestLadder(1.4);
  if (lad) climb(lad);
}

function updateInteractHint() {
  if (S.mode !== 'first' || !S.pointerLocked) { $('interact-hint').classList.add('hidden'); return; }
  const lad = nearestLadder(1.4);
  if (lad) {
    $('interact-hint').innerHTML = `Press <b>E</b> to climb ${S.level ? 'down' : 'up'}`;
    $('interact-hint').classList.remove('hidden');
    return;
  }
  raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
  const hits = raycaster.intersectObjects(S.interactables, false);
  const show = hits.length && hits[0].distance <= 2.2;
  if (show) $('interact-hint').innerHTML = 'Press <b>E</b>';
  $('interact-hint').classList.toggle('hidden', !show);
}

function updateMovement(dt) {
  // NOCLIP flight (Half-Life style): W/S along the full look vector (pitch
  // included), A/D strafe, Space/C straight up/down, Shift fast. No collision,
  // no gravity. The floor level is derived from altitude so doorway-beam
  // sensors, the audio ear and E-interactions keep working mid-flight.
  const speed = (S.keys.ShiftLeft || S.keys.ShiftRight) ? 9 : 2.4;
  const cp = Math.cos(S.pitch);
  const forward = new THREE.Vector3(-Math.sin(S.yaw) * cp, Math.sin(S.pitch), -Math.cos(S.yaw) * cp);
  const right = new THREE.Vector3(Math.cos(S.yaw), 0, -Math.sin(S.yaw));
  const move = new THREE.Vector3();
  if (S.keys.KeyW) move.add(forward);
  if (S.keys.KeyS) move.sub(forward);
  if (S.keys.KeyD) move.add(right);
  if (S.keys.KeyA) move.sub(right);
  if (S.keys.Space) move.y += 1;
  if (S.keys.KeyC) move.y -= 1;
  if (move.lengthSq() > 0) {
    move.normalize().multiplyScalar(speed * dt);
    S.pos.add(move);
    S.pos.y = Math.max(0.25, Math.min(80, S.pos.y));
  }
  S.level = S.pos.y > S.levelHeight ? 1 : 0;
}

function nearestLadder(maxDist) {
  let best = null, bestD = maxDist;
  for (const lad of S.ladders) {
    const d = Math.hypot(S.pos.x - lad.x, S.pos.z - lad.z);
    if (d < bestD) { bestD = d; best = lad; }
  }
  return best;
}

let avatarMarker = null;
function buildAvatar() {
  const gr = new THREE.Group();
  const cone = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.4, 4),
    new THREE.MeshBasicMaterial({ color: 0x53c7ff }));
  cone.rotation.x = Math.PI / 2;
  cone.position.y = 0.9;
  gr.add(cone);
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.18, 0.25, 24),
    new THREE.MeshBasicMaterial({ color: 0x53c7ff, transparent: true, opacity: 0.5, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.08;
  gr.add(ring);
  avatarMarker = gr;
  levelGroups[2].add(gr);
}

// ---------------------------------------------------------------- UI wiring
async function wireUi(cfg) {
  $('cp-link').href = `${API}/`;
  $('audio-link').href = `http://${HOST}:5055/`;  // audio console's default port

  // stamp which build of the sim code this tab is actually running — a
  // long-lived tab keeps executing the JS it loaded, so "nothing changed"
  // usually means "the tab never reloaded"; this line settles it instantly
  fetch('app.js', { method: 'HEAD' }).then((r) =>
    log('info', `sim code build: ${r.headers.get('last-modified') || 'unknown'}`)).catch(() => {});

  const themes = await fetch(`${API}/api/themes`).then(r => r.json()).catch(() => ({}));
  const themeNames = Array.isArray(themes) ? themes : Object.keys(themes);
  $('theme-select').innerHTML = themeNames.map(t => `<option>${escapeHtml(t)}</option>`).join('');
  setDot('api', themeNames.length > 0);

  const effects = await fetch(`${API}/api/effects_list`).then(r => r.json()).catch(() => ({}));
  const effectNames = Array.isArray(effects) ? effects : Object.keys(effects);
  $('effect-select').innerHTML = effectNames.map(t => `<option>${escapeHtml(t)}</option>`).join('');

  $('room-select').innerHTML = Object.keys(cfg.room_layout).map(r => `<option>${escapeHtml(r)}</option>`).join('');

  $('btn-theme-set').onclick = () => post('/api/set_theme', { theme_name: $('theme-select').value });
  $('btn-theme-next').onclick = () => post('/api/set_theme', { next_theme: true });
  $('btn-theme-off').onclick = () => post('/api/set_theme', { theme_name: 'notheme' });

  let brightTimer = null;
  $('brightness').oninput = (ev) => {
    clearTimeout(brightTimer);
    brightTimer = setTimeout(() => post('/api/set_master_brightness', { brightness: parseFloat(ev.target.value) }), 180);
  };

  $('btn-effect-run').onclick = () => post('/api/run_effect', { room: $('room-select').value, effect_name: $('effect-select').value });
  $('btn-effect-all').onclick = () => post('/api/run_effect_all_rooms', { effect_name: $('effect-select').value });
  $('btn-effect-stop').onclick = () => post('/api/stop_effect', { room: $('room-select').value });
  $('btn-effect-stopall').onclick = () => post('/api/stop_effect', {});

  $('btn-maze-ambience-start').onclick = () => post('/api/start_maze_ambience', {});
  $('btn-maze-ambience-stop').onclick = () => post('/api/stop_maze_ambience', {});

  // Attended/unattended sound mode — server-global like the floor theme
  // (every tab and, later, the entrance node's switch share ONE live mode),
  // so read the current mode from the server rather than assuming.
  let soundMode = 'unattended';
  const modeBtn = $('btn-sound-mode');
  const showSoundMode = (mode) => {
    soundMode = mode;
    modeBtn.textContent = mode === 'attended' ? 'Sounds: Attended (staff-run)' : 'Sounds: Unattended';
    modeBtn.classList.toggle('active', mode === 'attended');
  };
  showSoundMode(soundMode);
  fetch(`${API}/api/sound_mode`).then((r) => r.json())
    .then((s) => showSoundMode(s.mode)).catch(() => {});
  modeBtn.onclick = async () => {
    const want = soundMode === 'attended' ? 'unattended' : 'attended';
    if (await post('/api/sound_mode', { mode: want }, 'panel')) showSoundMode(want);
  };
}

// ---------------------------------------------------------------- boot
async function boot() {
  let cfg = null;
  while (!cfg) {
    try {
      cfg = await fetch(`${SIM}/sim/config`).then(r => r.json());
    } catch (e) {
      log('err', 'waiting for sim server…');
      await new Promise(res => setTimeout(res, 2500));
    }
  }
  S.cfg = cfg;
  API = `http://${HOST}:${cfg.ports.api}`;
  AUDIO_WS = `ws://${HOST}:${cfg.ports.audio_ws}`;
  S.frame = new Uint8Array(cfg.num_channels || 352);

  buildMaze(cfg);
  buildFixtures(cfg);
  buildSensors(cfg);
  buildProjection(cfg);
  buildEye(cfg);
  buildCampSign(cfg);
  buildAvatar();

  const sp = cfg.layout.spawn;
  S.pos.set(sp.pos[0], EYE, sp.pos[1]);
  S.level = sp.level || 0;
  S.yaw = (sp.yaw_deg || 0) * Math.PI / 180;
  S.prev2 = { x: S.pos.x, z: S.pos.z };

  const xs = Object.values(cfg.layout.rooms);
  const hexR = (cfg.layout.hex_center || {}).side || 0;
  S.bounds = {
    minX: Math.min(...xs.map(r => r.x)),
    maxX: Math.max(...xs.map(r => r.x + r.w)),
    frontZ: Math.max(...xs.map(r => r.z + r.d), cfg.layout.hex_center
      ? cfg.layout.hex_center.cz + hexR : 0), // hex front corner pokes furthest
  };
  frameStreetView();

  const minX = S.bounds.minX - 3, maxX = S.bounds.maxX + 3;
  const minZ = Math.min(...xs.map(r => r.z)) - 3, maxZ = Math.max(...xs.map(r => r.z + r.d)) + 8;
  const a = innerWidth / innerHeight;
  topCam = new THREE.OrthographicCamera(-36 * a, 36 * a, 24, -24, 0.1, 200);
  topCam.position.set((minX + maxX) / 2, 60, (minZ + maxZ) / 2);
  topCam.up.set(0, 0, -1); // street side at the bottom (topYaw 0)
  topCam.lookAt((minX + maxX) / 2, 0, (minZ + maxZ) / 2);
  topCam.zoom = 4.2;
  topCam.updateProjectionMatrix();

  setupControls(cfg);
  await wireUi(cfg);
  connectDmx();
  pollRpiStatus();
  setMode('first');
  startAudio();

  log('info', `sim ready — ${S.fixtures.length} fixtures${S.sign ? `, ${S.sign.zones.length} sign zones` : ''}, ${S.sensors.length} sensors, ${Object.keys(cfg.room_layout).length} rooms, two stories`);
  log('info', 'note: lights/audio also react to OTHER clients & test scripts — this log only shows YOUR actions');
  animate();
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  const t = clock.getElapsedTime();

  if (S.mode === 'first') updateMovement(dt);

  // E / R rotate the camera (plan: spin in place; street: orbit the facade).
  // First-person keeps E = interact and mouse-look for turning.
  if (S.mode !== 'first' && (S.keys.KeyE || S.keys.KeyR)) {
    const da = ((S.keys.KeyE ? 1 : 0) - (S.keys.KeyR ? 1 : 0)) * 1.3 * dt;
    if (S.mode === 'top' && topCam) {
      topYaw += da;
      topCam.up.set(Math.sin(topYaw), 0, -Math.cos(topYaw));
      topCam.lookAt(topCam.position.x, 0, topCam.position.z);
    } else if (S.mode === 'street' && S.streetLook) {
      const L = S.streetLook;
      const px = streetCam.position.x - L.x, pz = streetCam.position.z - L.z;
      const c = Math.cos(da), s = Math.sin(da);
      streetCam.position.x = L.x + px * c + pz * s;
      streetCam.position.z = L.z - px * s + pz * c;
      streetCam.lookAt(L.x, L.y, L.z);
    }
  }
  checkSensorTriggers();
  updateProjection(dt);
  updateEye(dt);
  updateFixtures(t);
  updateFixtureGrid(t);
  updateCampSign(t);
  updateInteractHint();
  updateListener();
  updateAudioGating();

  if (avatarMarker) {
    avatarMarker.position.set(S.pos.x, S.level * S.levelHeight, S.pos.z);
    avatarMarker.rotation.y = S.yaw;
    avatarMarker.visible = S.mode !== 'first';
  }

  if (S.mode === 'first') {
    camera.position.copy(S.pos);
    camera.rotation.set(S.pitch, S.yaw, 0);
  }
  renderer.render(scene, activeCamera());
}

boot();
