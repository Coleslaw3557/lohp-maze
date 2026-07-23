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

const MODES = ['street', 'first', 'top'];
const MODE_LABEL = { street: 'Street view', first: 'First-person', top: 'Overhead plan' };

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
  sign: null,              // Camp Sign live-DMX letter zones (layout `camp_sign` key)
  eye: null,               // Cuddle orb — Waveshare ESP32-S3 round display (layout `eye` key)
  mode: 'street',
  keys: {},
  pos: new THREE.Vector3(11.7, EYE, 4.5),
  level: 0,
  prev2: { x: 11.7, z: 4.5 },
  yaw: 0, pitch: 0,
  pointerLocked: false,
  audio: { on: false, ws: null, ctx: null, rooms: new Map(), music: null, buffers: new Map() },
  dmxWs: null,
  teleporting: false,
};
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

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
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
  renderer.toneMappingExposure = day ? 1.0 : 1.15;
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
    const lbl = makeLabel(lad.label || 'Climb (E)', 0.32);
    lbl.position.set(lx, S.levelHeight + 1.25, lz);
    ladder.add(lbl);
    levelGroups[2].add(ladder);
  }

  // server box: the RPi + USB-DMX enclosure mounts on the OUTSIDE of the
  // back wall, behind Cuddle Cross on the shared frame between Cuddle Cross
  // and Photo Bomb Room — not inside the hex
  if (L.server_rack) {
    const [rx, rz] = L.server_rack.pos;
    const lv = L.server_rack.level || 0;
    const yBase = lv * LH;
    const box = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.46, 0.16),
      new THREE.MeshStandardMaterial({ color: 0x101318, roughness: 0.6, metalness: 0.4 }));
    box.position.set(rx, yBase + 1.05, rz);
    grp(lv).add(box);
    const led = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, 0.02),
      new THREE.MeshBasicMaterial({ color: 0x33ff66 }));
    led.position.set(rx + 0.1, yBase + 1.2, rz - 0.085); // faces out the back
    grp(lv).add(led);
    const lbl = makeLabel(L.server_rack.label || 'SERVER', 0.3);
    lbl.position.set(rx, yBase + 1.48, rz);
    grp(lv).add(lbl);
  }

  // per-room node enclosures — the wooden sensor boxes from
  // wiring-guides/room-node-enclosure-plan.md (XIAO C3 + the room's radar or
  // ToF + power), hose-clamped to a frame member: wing bays on the ENTRY-side
  // front leg at 1.55 m with the radar window (local +z) aimed at the
  // diagonally-opposite back corner; ToF rooms' windows face their aim. The
  // room's sensor wedge/boresight is drawn by buildSensors from the matching
  // `sensors` entry; pos/aim here come from the per-room "enclosure" entries.
  for (const r of Object.values(L.rooms)) {
    const enc = r.enclosure;
    if (!enc) continue;
    const lv = enc.level != null ? enc.level : (r.floor === 1 ? 1 : 0);
    const eg = new THREE.Group();
    eg.position.set(enc.pos[0], lv * LH + (enc.h || 1.55), enc.pos[1]);
    eg.rotation.y = (enc.yaw_deg || 0) * Math.PI / 180;
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
    S.roomsMeshes[room] = { slab, center: c, level: 0, room: L.rooms[room] };
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
  // hose-clamp blocks around each corner's leg pair
  for (const [vx, vz] of V) {
    for (const cy of [0.35, 1.05, 1.7, LH + 0.35, LH + 1.05, LH + 1.7]) {
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
    const { R, G, B } = z.addr ? decodeFixture(z, t) : { R: 0, G: 0, B: 0 };
    // faint idle floor so the sign stays findable when dark; the LED color
    // rides the halo behind each raised letter (additive) or glows through
    // the logo's gap mask (emissive) — the wood itself never lights up
    const fR = Math.max(R, SIGN_UNLIT * 0.4), fG = Math.max(G, SIGN_UNLIT * 0.35), fB = Math.max(B, SIGN_UNLIT * 0.3);
    if (z.isLogo) z.mat.emissive.setRGB(fR, fG, fB);
    else z.mat.color.setRGB(fR, fG, fB);
    if (cells && z.cell) {
      z.cell.style.background = `rgb(${(R * 255) | 0},${(G * 255) | 0},${(B * 255) | 0})`;
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

  let R = Math.min(1, (r + w * 0.92) / 255) * master;
  let G = Math.min(1, (g + w * 0.92) / 255) * master;
  let B = Math.min(1, (b + w * 0.85) / 255) * master;
  if (strobe > 5) {
    const hz = 1 + (strobe / 255) * 11;
    if ((t * hz) % 1 > 0.5) { R = G = B = 0; }
  }
  return { R, G, B, lum: Math.max(R, G, B) };
}

const roomTint = new Map();
function updateFixtures(t) {
  roomTint.clear();
  for (const fx of S.fixtures) {
    const { R, G, B, lum } = decodeFixture(fx, t);
    fx.light.color.setRGB(R, G, B);
    fx.light.intensity = lum * (fx.isSpot ? 18 : 11);
    // faint idle glow so every fixture is visible even when dark
    fx.lens.material.color.setRGB(Math.min(1, R * 1.6 + 0.07), Math.min(1, G * 1.6 + 0.07), Math.min(1, B * 1.6 + 0.09));
    fx.cone.material.color.setRGB(R, G, B);
    fx.cone.material.opacity = 0.05 + lum * 0.22;
    const acc = roomTint.get(fx.room) || [0, 0, 0, 0];
    acc[0] += R; acc[1] += G; acc[2] += B; acc[3] += 1;
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
    const { R, G, B } = decodeFixture(fx, t);
    fx.cell.style.background = `rgb(${(R * 255) | 0},${(G * 255) | 0},${(B * 255) | 0})`;
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

  // labels are wider than the button spacing at stations (hex 4-button row,
  // Porto knock pads) — alternate clustered labels between two rows so the
  // words don't overlap
  const labelSpots = [];
  const labelRow = (x, y, z) => {
    const n = labelSpots.filter(p => Math.abs(p.x - x) < 1.3
      && Math.abs(p.y - y) < 0.5 && Math.abs(p.z - z) < 0.5).length;
    labelSpots.push({ x, y, z });
    return (n % 2) * 0.26;
  };

  for (const trig of cfg.triggers) {
    const geo = byName[trig.name] || {};
    // geo.level 0 is a real value — the || fallback once swallowed it and the
    // pos[1] height guess then misread zone sensors' [x,z] pos as [x,y]
    const level = geo.level != null ? geo.level
      : (geo.pos && geo.pos[1] > S.levelHeight ? 1 : 0);
    const sensor = {
      name: trig.name, kind: geo.kind || trig.type, room: trig.room, level,
      action: trig.action, type: trig.type, game: trig.game || null,
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
      // zone sensor firing from inside the room's node box: horizontal wedge
      // = detection footprint (range/fov/clip), boresight line = exact aim
      // (yaw + down-tilt). Radar detects presence in the wedge; the ToF cone
      // is a range-gated tripwire — same enter-the-zone trigger model.
      const range = geo.range_m || (geo.kind === 'radar' ? 3.0 : 2.0);
      const fov = geo.fov_deg || (geo.kind === 'radar' ? 120 : 27);
      const yaw = geo.yaw_deg || 0;
      const yawR = yaw * Math.PI / 180;
      sensor.zone = {
        x: geo.pos[0], z: geo.pos[1], yaw, fov, range, clip: geo.clip || null,
        // thin ToF cones get a boresight seg-cross backstop; wide radar wedges
        // don't need one (and their 3 m bore can graze the neighboring bay)
        bore: geo.kind === 'tof'
          ? [[geo.pos[0], geo.pos[1]],
            [geo.pos[0] + range * Math.sin(yawR), geo.pos[1] + range * Math.cos(yawR)]]
          : null,
      };
      const color = geo.kind === 'radar' ? 0x37ffb0 : 0xff2b2b;
      const zg = new THREE.Group();
      zg.position.set(geo.pos[0], level * S.levelHeight + (geo.h || 1.55), geo.pos[1]);
      zg.rotation.y = yawR;
      const fovR = fov * Math.PI / 180;
      const wedge = new THREE.Mesh(
        new THREE.CircleGeometry(range, 48, Math.PI / 2 - fovR / 2, fovR),
        new THREE.MeshBasicMaterial({ color, transparent: true, side: THREE.DoubleSide,
          opacity: geo.kind === 'radar' ? 0.07 : 0.16, depthWrite: false }));
      wedge.rotation.x = Math.PI / 2; // lay flat, opening along local +z (the box window)
      zg.add(wedge);
      const boreG = new THREE.Group();
      boreG.rotation.x = -(geo.tilt_deg || 0) * Math.PI / 180; // -10° tilt = aim below horizon
      const bore = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(
          [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, range)]),
        new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.65 }));
      boreG.add(bore);
      zg.add(boreG);
      grp(level).add(zg);
      sensor.meshes.push(wedge, bore);
    } else if (geo.kind === 'button' && geo.pos) {
      const colors = { 'Button 1': 0x3d7bff, 'Button 2': 0xffc93d, 'Button 3': 0x3dff70, 'Button 4': 0xff4d4d };
      const bcol = geo.color ? parseInt(geo.color, 16) : (colors[trig.name] || 0xcccccc);
      const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.05, 24),
        new THREE.MeshStandardMaterial({ color: bcol, roughness: 0.4, emissive: bcol, emissiveIntensity: 0.25 }));
      btn.rotation.x = Math.PI / 2;
      btn.position.set(geo.pos[0], geo.pos[1], geo.pos[2]);
      btn.userData.sensor = sensor;
      grp(level).add(btn);
      // label_off ([dx,dy,dz] in the layout) places the label beside the
      // button — used by vertical rail stacks; default sits above, row-staggered
      const off = geo.label_off
        || [0, 0.19 + labelRow(geo.pos[0], geo.pos[1], geo.pos[2]), 0.04];
      const lbl = makeLabel(geo.label || trig.name, 0.24);
      lbl.position.set(geo.pos[0] + off[0], geo.pos[1] + off[1], geo.pos[2] + off[2]);
      grp(level).add(lbl);
      sensor.meshes.push(btn);
      S.interactables.push(btn);
    } else if (geo.kind === 'knock' && geo.pos) {
      const pad = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.04),
        new THREE.MeshStandardMaterial({ color: 0x6a5232, roughness: 0.8, emissive: 0x2a1f10, emissiveIntensity: 0.4 }));
      pad.position.set(geo.pos[0], geo.pos[1], geo.pos[2]);
      pad.userData.sensor = sensor;
      grp(level).add(pad);
      const off = geo.label_off
        || [0, 0.22 + labelRow(geo.pos[0], geo.pos[1], geo.pos[2]), 0.04];
      const lbl = makeLabel(geo.label || trig.name, 0.24);
      lbl.position.set(geo.pos[0] + off[0], geo.pos[1] + off[1], geo.pos[2] + off[2]);
      grp(level).add(lbl);
      sensor.meshes.push(pad);
      S.interactables.push(pad);
    }

    const b = document.createElement('button');
    const isPlaceholder = trig.room && placeholders.has(trig.room)
      && (trig.action.data || {}).effect_name === 'Lightning';
    b.textContent = trig.name + (isPlaceholder ? ' ⚠' : '');
    b.title = `${trig.type} → ${JSON.stringify(trig.action.data)}`
      + (sensor.zone ? `\n${geo.kind === 'radar' ? 'LD2410C radar' : 'VL53L1X ToF'} in the `
        + `${trig.room} node box — yaw ${sensor.zone.yaw}°, tilt ${geo.tilt_deg || 0}°, `
        + `fov ${sensor.zone.fov}°, reach ${sensor.zone.range} m` : '')
      + (isPlaceholder ? '\n⚠ placeholder: no bespoke effect designed for this room yet' : '');
    b.onclick = () => fireSensor(sensor, true);
    triggerList.appendChild(b);

    S.sensors.push(sensor);
  }
}

// --- room game logic (mirrors the node firmware; spec: wiring-guides/room-games-plan.md) ---
const GAME = { gateStage: 0, gateAt: -1e9, dphWinner: Math.floor(Math.random() * 5), bike: {}, lamps: null };

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

function chimeThen(sensor, finalEffect, source) {
  // maze-wide victory chime, then the room's big effect once the chime lands
  post(sensor.action.path, Object.assign({}, sensor.action.data, { effect_name: 'CorrectAnswer' }), source);
  setTimeout(() => post(sensor.action.path,
    Object.assign({}, sensor.action.data, { effect_name: finalEffect }), source), 2500);
}

// Returns {effect} to POST, null when the game already POSTed, or 'silent'.
function resolveGame(sensor, source) {
  const g = sensor.game;
  const now = clock.getElapsedTime();
  switch (g.id) {
    case 'gate': {
      // sim stand-in: one click = the whole bank pressed at once (the real
      // node requires all 3 pads of a bank held within its 350ms window)
      if (GAME.gateStage === 1 && now - GAME.gateAt > 30) GAME.gateStage = 0;
      if (g.bank === 1) {
        GAME.gateStage = 1; GAME.gateAt = now;
        toast('Gate: first three hit — now the far three!');
        return { effect: 'CorrectAnswer' };
      }
      if (GAME.gateStage === 1) {
        GAME.gateStage = 0;
        toast('Gate complete!');
        return { effect: 'GateInspection' };
      }
      toast('Gate: hit pads 1-3 first');
      return { effect: 'WrongAnswer' };
    }
    case 'dph': {
      if (g.index === GAME.dphWinner) {
        GAME.dphWinner = Math.floor(Math.random() * 5);
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
    case 'moop':  // standalone pucks; game rule TBD — every press chimes
      return { effect: 'CorrectAnswer' };
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
  const cooldown = sensor.game ? (sensor.game.id === 'lightsout' ? 0.4 : 1.5) : COOLDOWN_S;
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
      post(sensor.action.path, Object.assign({}, sensor.action.data, { effect_name: r.effect }), source);
    }
  } else if (sensor.type === 'piezo') {
    const ps = S.cfg.piezo_settings;
    S.piezoAttempts += 1;
    let effect = 'WrongAnswer';
    if (S.piezoAttempts >= (ps.attempts_required || 3)) {
      S.piezoAttempts = 0;
      if (Math.random() < (ps.correct_answer_probability || 0.25)) effect = 'CorrectAnswer';
    }
    const data = Object.assign({}, sensor.action.data, { effect_name: effect });
    toast(`${sensor.name} → ${effect}`);
    post(sensor.action.path, data, source);
  } else {
    toast(`${sensor.name}${sensor.room ? ' → ' + (sensor.action.data.effect_name || '') : ''}`);
    post(sensor.action.path, sensor.action.data, source);
  }
  if (S.projection && sensor.name === S.projection.cfg.cue) projectionCue('cue: ' + sensor.name);

  for (const m of sensor.meshes) {
    if (m.material && m.material.color) {
      const orig = m.userData.origColor || (m.userData.origColor = m.material.color.clone());
      m.material.color.set(0xffffff);
      setTimeout(() => m.material.color.copy(orig), 250);
      setTimeout(() => { m.material.color.set(0x555555); }, 300);
      setTimeout(() => m.material.color.copy(orig), COOLDOWN_S * 1000);
    }
  }
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
      // fire on entering the detection wedge (teleports re-seat state without
      // firing, like beams); a ToF boresight seg-cross is the fast-mover
      // backstop so a sprint through the thin cone can't step over it
      const inside = sensor.level === S.level && zoneContains(sensor.zone, x, z);
      if (!tele && ((inside && !sensor.wasInside)
        || (moved && sensor.zone.bore && sensor.level === S.level
          && segCross(px, pz, x, z,
            sensor.zone.bore[0][0], sensor.zone.bore[0][1],
            sensor.zone.bore[1][0], sensor.zone.bore[1][1])))) fireSensor(sensor, false);
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
// a face-down short-throw projector on a stub arm at the hex NE corner
// paints a reactive playfield on the deck; an LD2450 in the node box tracks walker
// positions. The sim's walker IS the target — filtered through the tracker's
// real coverage wedge and first-order latency so the interactivity previews
// how the hardware will feel. Content comes from the shared floor engine
// (projection_engine.py, LAVA or JUNGLE theme — the Floor button switches it
// for every tab). Delete the layout key to remove the whole rig. No
// production config is involved.
const FLOOR_THEMES = ['lava', 'jungle'];
const FLOOR_LABEL = { lava: 'Floor: Lava', jungle: 'Floor: Jungle' };
function buildProjection(cfg) {
  const P = cfg.layout.projection;
  if (!P) return;
  const LH = S.levelHeight;
  const yDeck = P.level * LH + 0.145; // hair above the deck slab
  const g = new THREE.Group();

  // projector body + mount arm back to its frame; yaw_deg spins the rig
  // (0 = throws +z; -90 = throws -x as on the old rear-leg mount; -120 =
  // throws SW down the long diagonal from the NE corner arm)
  const [bw, bh, bd] = P.projector.body || [0.37, 0.11, 0.29];
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
  // mount arm from the body back to its supporting frame (arm_deg = absolute
  // world direction to the support; default = opposite the throw)
  const armDeg = P.projector.arm_deg != null ? P.projector.arm_deg
    : (P.projector.yaw_deg || 0) + 180;
  const armG = new THREE.Group();
  armG.position.set(P.projector.pos[0], yProj, P.projector.pos[1]);
  armG.rotation.y = armDeg * Math.PI / 180;
  const armLen = P.projector.arm_len || 0.5;
  const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, armLen), matGalv);
  arm.rotation.x = Math.PI / 2;
  arm.position.z = bd / 2 - 0.07 + armLen / 2;
  armG.add(arm);
  g.add(armG);
  const lbl = makeLabel(P.projector.label || 'floor projection (planned)', 0.22);
  lbl.position.set(P.projector.pos[0], yProj + 0.34, P.projector.pos[1]);
  g.add(lbl);

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

  // beam edges from the projection window to the image corners
  const win = new THREE.Vector3(P.projector.pos[0] + fwd[0] * (bd / 2 - 0.03),
    yProj - bh / 2,
    P.projector.pos[1] + fwd[1] * (bd / 2 - 0.03));
  for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
    const corner = new THREE.Vector3(
      P.image.center[0] + lat[0] * sx * P.image.w / 2 + fwd[0] * sz * P.image.d / 2,
      yDeck + 0.005,
      P.image.center[1] + lat[1] * sx * P.image.w / 2 + fwd[1] * sz * P.image.d / 2);
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([win, corner]),
      new THREE.LineBasicMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.22 })));
  }

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

  S.projection = { cfg: P, canvas, ctx: canvas.getContext('2d'), tex, plane,
    cw, ch: chp, ppm, toPx, mast, winPx, deckPath, active: false, fade: 0,
    lastPresence: -1e9, smooth: null, accum: 0,
    // floor engine link (projection_engine.py stepped by sim_ui, streamed
    // over /sim/projection): the page renders engine STATE — scalar field,
    // stones/snakes/tiki, events — and sends back the lagged radar position.
    // It computes nothing. `theme` mirrors the server's active show.
    ws: null, grid: null, lut: null, heatCanvas: null, heatImg: null,
    heatStep: 2, theme: null, stones: [], snakes: [], snakeMeta: {}, flies: [],
    glyphs: [], glyphGlint: {}, tiki: null, tikiImg: null,
    tracksPx: [], fx: [], engineFade: 0, lastTrackSend: 0 };
  connectProjection();
}

function connectProjection() {
  const pr = S.projection;
  if (!pr) return;
  const ws = new WebSocket(`ws://${HOST}:${location.port || 5001}/sim/projection`);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.error) { log('err', `projection: ${m.error}`); return; }
    if (m.hello) {
      pr.grid = m.hello.grid;
      pr.lut = m.hello.palette;
      pr.heatStep = m.hello.heat_step || 2;
      const hc = document.createElement('canvas');
      hc.width = Math.floor(pr.grid[0] / pr.heatStep);
      hc.height = Math.floor(pr.grid[1] / pr.heatStep);
      pr.heatCanvas = hc;
      pr.heatImg = hc.getContext('2d').createImageData(hc.width, hc.height);
      // theme reset: a re-hello (theme switch) must not leak the other
      // show's entities into this one
      pr.theme = m.hello.theme || 'lava';
      pr.stoneImg = null; pr.monsterImg = null; pr.tikiImg = null;
      pr.stones = []; pr.monster = null; pr.snakes = []; pr.snakeMeta = {};
      pr.flies = []; pr.glyphs = []; pr.glyphGlint = {}; pr.tiki = null;
      pr.fx = [];
      const fb = $('btn-floor');
      if (fb) fb.textContent = FLOOR_LABEL[pr.theme] || `Floor: ${pr.theme}`;
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
        pr.islandImg = mk(tex2.island);
        pr.islandPos = tex2.island;
        if (tex2.monster) pr.monsterImg = mk(tex2.monster);
        if (tex2.tiki) pr.tikiImg = mk(tex2.tiki);
        if (tex2.glyphs) pr.glyphs = tex2.glyphs.map(t => ({ id: t.id, x: t.x, y: t.y, img: mk(t) }));
        if (tex2.snakes) for (const s of tex2.snakes) pr.snakeMeta[s.id] = s;
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
    pr.tiki = m.tiki || null;
    pr.glyphGlint = {};
    for (const g of m.glyphs || []) pr.glyphGlint[g.id] = g.glint;
    if (m.heat && pr.heatCanvas) paintHeat(pr, m.heat);
    for (const e of m.events || []) {
      if (e.x != null) pr.fx.push({ ...e, t0: clock.getElapsedTime() });
      if (e.e === 'sink') log('info', `projection: stone ${e.id} sinks underfoot`);
      if (e.e === 'rise') log('info', `projection: stone ${e.id} rises`);
      if (e.e === 'monster_swim') log('info', 'projection: something moves beneath the lava…');
      if (e.e === 'monster_breach') log('ok', 'projection: KUKULKAN breaches!');
      if (e.e === 'monster_sink') log('info', 'projection: Kukulkan slips back under');
      if (e.e === 'snake_flee') log('info', 'projection: a snake darts away from your feet');
      if (e.e === 'tiki_arrive') log('ok', 'projection: the tiki mask floats in (aku aku!)');
      if (e.e === 'tiki_spin') log('info', 'projection: the tiki mask SPINS');
      if (e.e === 'tiki_leave') log('info', 'projection: the tiki mask drifts off into the canopy');
    }
  };
  ws.onclose = () => { pr.ws = null; setTimeout(connectProjection, 2500); };
  ws.onerror = () => ws.close();
}

function paintHeat(pr, b64) {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const d = pr.heatImg.data;
  for (let i = 0; i < bytes.length; i++) {
    const c = pr.lut[bytes[i]] || [0, 0, 0];
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
    // the engine's lava heat field, palette-mapped in paintHeat, upscaled
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(pr.heatCanvas, 0, 0, cw, ch);
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
  for (const s of pr.stones) {
    if (s.state === 'down' || s.phase < 0) continue;
    let scale = 1, heat = 0;  // grey rock; hot only mid-transition (engine rules)
    if (s.state === 'sinking') { scale = 1 - 0.55 * s.phase; heat = s.phase; }
    else if (s.state === 'rising') { scale = 0.45 + 0.55 * s.phase; heat = (1 - s.phase) * 0.8; }
    const r = s.r * gs * scale;
    const img = pr.stoneImg && pr.stoneImg[s.id];
    if (img) {
      const w = img.width * gs * scale, h = img.height * gs * scale;
      ctx.drawImage(img, s.x * gs - w / 2, s.y * gs - h / 2, w, h);
      if (heat > 0.02) {          // melting: whole rock heats over
        ctx.globalAlpha = Math.min(1, heat);
        ctx.fillStyle = 'rgb(255,120,20)';
        ctx.beginPath(); ctx.arc(s.x * gs, s.y * gs, r, 0, 7); ctx.fill();
        ctx.globalAlpha = 1;
      } else if (s.glint > 0.05) { // glyph notices an approaching walker
        ctx.globalAlpha = s.glint * 0.35;
        ctx.strokeStyle = 'rgb(255,196,96)';
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

  // jungle: fallen glyph stones (mossy ruins; carve glints when noticed)
  for (const g of pr.glyphs) {
    const w = g.img.width * gs, h = g.img.height * gs;
    ctx.drawImage(g.img, g.x * gs - w / 2, g.y * gs - h / 2, w, h);
    const gl = pr.glyphGlint[g.id] || 0;
    if (gl > 0.05) {
      ctx.globalAlpha = gl * 0.35;
      ctx.strokeStyle = 'rgb(205,235,130)';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(g.x * gs, g.y * gs, g.img.width * gs * 0.34, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
    }
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
    ctx.fillStyle = 'rgb(250,214,90)';
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
  }

  // jungle: fireflies (the engine also glows the field under each one)
  for (const f of pr.flies) {
    ctx.fillStyle = 'rgba(255,240,170,0.9)';
    ctx.beginPath(); ctx.arc(f.x * gs, f.y * gs, 2.5, 0, 7); ctx.fill();
    ctx.fillStyle = 'rgba(220,230,120,0.25)';
    ctx.beginPath(); ctx.arc(f.x * gs, f.y * gs, 7, 0, 7); ctx.fill();
  }

  // Kukulkan, rotated to his heading (image points +x; engine pose drives)
  if (pr.monster && pr.monsterImg) {
    const mo = pr.monster;
    ctx.save();
    ctx.translate(mo.x * gs, mo.y * gs);
    ctx.rotate(mo.rot);
    const w = pr.monsterImg.width * gs * mo.scale, h = pr.monsterImg.height * gs * mo.scale;
    ctx.drawImage(pr.monsterImg, -w / 2, -h / 2, w, h);
    ctx.restore();
    if (mo.glow > 0.1) {
      ctx.globalAlpha = mo.glow * 0.18;
      ctx.strokeStyle = 'rgb(255,200,90)';
      ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(mo.x * gs, mo.y * gs, pr.monsterImg.width * gs * 0.62, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }

  // jungle: the flying tiki mask, rotated to its heading (image points +x);
  // hollow eyes get a soft pulse aura, a spin gets motion rings
  if (pr.tiki && pr.tikiImg) {
    const tk = pr.tiki;
    ctx.save();
    ctx.translate(tk.x * gs, tk.y * gs);
    ctx.rotate(tk.rot);
    const w = pr.tikiImg.width * gs * tk.scale, h = pr.tikiImg.height * gs * tk.scale;
    ctx.drawImage(pr.tikiImg, -w / 2, -h / 2, w, h);
    ctx.restore();
    if (tk.glow > 0.1) {
      ctx.globalAlpha = tk.glow * 0.14;
      ctx.strokeStyle = 'rgb(255,226,130)';
      ctx.lineWidth = 4;
      ctx.beginPath(); ctx.arc(tk.x * gs, tk.y * gs, pr.tikiImg.width * gs * 0.5, 0, 7); ctx.stroke();
      ctx.globalAlpha = 1;
    }
    if (tk.spin) {
      ctx.strokeStyle = 'rgba(255,226,130,0.5)';
      ctx.lineWidth = 2.5;
      for (const rr of [0.62, 0.78]) {
        ctx.beginPath();
        ctx.arc(tk.x * gs, tk.y * gs, pr.tikiImg.width * gs * rr,
          now * 9 + rr * 4, now * 9 + rr * 4 + 2.2);
        ctx.stroke();
      }
    }
  }

  // engine events as short-lived rings: bubble pops / snake flees small,
  // sink/rise big, monster + tiki biggest; jungle rings go leaf-gold
  pr.fx = pr.fx.filter(e => now - e.t0 < 0.6);
  for (const e of pr.fx) {
    const a = (now - e.t0) / 0.6;
    const base = e.e === 'pop' ? 6 : e.e === 'snake_flee' ? 9
      : (e.e.startsWith('monster') || e.e.startsWith('tiki')) ? 24 : 14;
    const col = pr.theme === 'jungle' ? '205,235,130' : '255,180,60';
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
// The gestures the real orb sends (tap=next theme, long-press=storm all)
// hit the REST API directly — see wiring-guides/cuddle-orb-plan.md.
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
  const lbl = makeLabel(E.label || 'Cuddle orb (Guition S3 · sim)', 0.16);
  lbl.position.y = D / 2 + 0.06;
  g.add(lbl);
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
      case 'start_background_music':
        playMusic((msg.data || {}).music_file);
        break;
      case 'stop_background_music':
        stopMusic();
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

async function getBuffer(file) {
  const a = S.audio;
  if (a.buffers.has(file)) return a.buffers.get(file);
  const res = await fetch(`${API}/api/audio/${encodeURIComponent(file)}`);
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
    stopEffectAudio(room);
    const src = a.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = !!loop;
    const gain = a.ctx.createGain();
    gain.gain.value = volume == null ? 0.8 : volume;
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
    a.rooms.set(room || '__all__', { src, gain });
    log('info', `♪ ${effectName || ''} ${file}${room ? ' @ ' + room : ''}`);
  } catch (e) {
    log('err', `audio play failed: ${e.message}`);
  }
}

function stopEffectAudio(room) {
  const a = S.audio;
  const stopOne = (key) => {
    const v = a.rooms.get(key);
    if (v) { try { v.src.stop(); } catch (e) { /* already stopped */ } a.rooms.delete(key); }
  };
  if (room == null) { for (const key of Array.from(a.rooms.keys())) stopOne(key); }
  else stopOne(room);
}

async function playMusic(file) {
  const a = S.audio;
  if (!a.ctx || !file) return;
  try {
    const buf = await getBuffer(file);
    stopMusic();
    const src = a.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    const gain = a.ctx.createGain();
    gain.gain.value = 0.4;
    src.connect(gain).connect(a.ctx.destination);
    src.start();
    a.music = { src, gain };
    log('info', `♫ background music: ${file}`);
  } catch (e) {
    log('err', `music failed: ${e.message}`);
  }
}

function stopMusic() {
  const a = S.audio;
  if (a.music) { try { a.music.src.stop(); } catch (e) { /* noop */ } a.music = null; }
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
}

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
    if (ev.code === 'KeyM') setMode(MODES[(MODES.indexOf(S.mode) + 1) % MODES.length]);
    if (ev.code === 'KeyN') setDayNight(!ENV.day);
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
      topCam.position.x -= dx * k * (innerWidth / innerHeight) * 0.6;
      topCam.position.z -= dy * k;
    } else if (S.mode === 'street') {
      streetCam.position.x = Math.max(-3, Math.min(23, streetCam.position.x - dx * 0.018));
      streetCam.position.y = Math.max(0.9, Math.min(8, streetCam.position.y + dy * 0.012));
    }
  });

  $('btn-view').onclick = () => setMode(MODES[(MODES.indexOf(S.mode) + 1) % MODES.length]);
  $('btn-daynight').onclick = () => setDayNight(!ENV.day);
  $('btn-towers').onclick = () => setTowersVisible(!(towersGroup && towersGroup.visible));
  $('btn-sign').onclick = () => setSignVisible(!(signGroup && signGroup.visible));
  $('btn-steel').onclick = () => setSteelMode(STEEL_MODES[(STEEL_MODES.indexOf(steelMode) + 1) % STEEL_MODES.length]);
  $('btn-eye').onclick = () => setEyeSkin(EYE_MODES[(EYE_MODES.indexOf(S.eyeSkin) + 1) % EYE_MODES.length]);
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
  $('btn-respawn').onclick = () => {
    const sp = cfg.layout.spawn;
    S.pos.set(sp.pos[0], EYE, sp.pos[1]);
    S.level = sp.level || 0;
    S.yaw = (sp.yaw_deg || 0) * Math.PI / 180;
    S.pitch = 0;
    S.teleporting = true;
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
  const speed = (S.keys.ShiftLeft || S.keys.ShiftRight) ? 3.6 : 1.7; // human scale in 7ft bays
  const forward = new THREE.Vector3(-Math.sin(S.yaw), 0, -Math.cos(S.yaw));
  const right = new THREE.Vector3(-forward.z, 0, forward.x);
  const move = new THREE.Vector3();
  if (S.keys.KeyW) move.add(forward);
  if (S.keys.KeyS) move.sub(forward);
  if (S.keys.KeyD) move.add(right);
  if (S.keys.KeyA) move.sub(right);
  if (move.lengthSq() > 0) {
    move.normalize().multiplyScalar(speed * dt);
    S.pos.add(move);
  }
  S.pos.y = EYE + S.level * S.levelHeight; // a 5'11" visitor's eyes under the 6'2" ceiling
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

  $('btn-music-start').onclick = () => post('/api/start_music', {});
  $('btn-music-stop').onclick = () => post('/api/stop_music', {});
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
  topCam.lookAt((minX + maxX) / 2, 0, (minZ + maxZ) / 2);
  topCam.zoom = 4.2;
  topCam.updateProjectionMatrix();

  setupControls(cfg);
  await wireUi(cfg);
  connectDmx();
  pollRpiStatus();
  setMode('street');

  $('enter-btn').onclick = () => {
    S.audio.on = true;
    S.audio.ctx = new (window.AudioContext || window.webkitAudioContext)();
    connectAudio();
    $('enter-overlay').classList.add('hidden');
  };
  $('enter-muted-btn').onclick = () => {
    $('enter-overlay').classList.add('hidden');
  };

  log('info', `sim ready — ${S.fixtures.length} fixtures${S.sign ? `, ${S.sign.zones.length} sign zones` : ''}, ${S.sensors.length} sensors, ${Object.keys(cfg.room_layout).length} rooms, two stories`);
  log('info', 'note: lights/audio also react to OTHER clients & test scripts — this log only shows YOUR actions');
  animate();
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  const t = clock.getElapsedTime();

  if (S.mode === 'first') updateMovement(dt);
  checkSensorTriggers();
  updateProjection(dt);
  updateEye(dt);
  updateFixtures(t);
  updateFixtureGrid(t);
  updateCampSign(t);
  updateInteractHint();
  updateListener();

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
