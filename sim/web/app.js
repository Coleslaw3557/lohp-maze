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

const S = {
  cfg: null,
  frame: new Uint8Array(168),
  seq: -1,
  levelHeight: 3.2,
  fixtures: [],            // {room, addr, channels, level, light, lens, cone, cell}
  roomsMeshes: {},         // room -> {slab, center(Vector3 at room level), level}
  canvasMats: {},          // room -> [backdrop materials], emissive-tinted by the room's light
  sensors: [],             // {name, kind, room, action, seg?, level, meshes, lastFired}
  ladders: [],             // {room, x, z} climb points
  interactables: [],       // meshes with .userData.{sensor|ladder}
  piezoAttempts: 0,
  mode: 'street',
  keys: {},
  pos: new THREE.Vector3(11.7, 1.6, 4.5),
  level: 0,
  prev2: { x: 11.7, z: 4.5 },
  yaw: 0, pitch: 0,
  pointerLocked: false,
  audio: { on: false, ws: null, ctx: null, rooms: new Map(), music: null, buffers: new Map() },
  dmxWs: null,
  teleporting: false,
};

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
function setDot(which, ok) { $(`dot-${which}`).className = 'dot ' + (ok === null ? '' : ok ? 'ok' : 'err'); }
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
  const beams = Object.entries(L.sensors)
    .filter(([, s]) => s.kind === 'beam')
    .map(([, s]) => ({ seg: s.seg, level: s.level || 0 }));

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
    // blue/green alternate like our repainted mixed fleet
    bs.forEach((bx, i) => {
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

  const slabShape = (pts) => {
    const sh = new THREE.Shape();
    pts.forEach(([x, z], i) => i ? sh.lineTo(x, -z) : sh.moveTo(x, -z)); // shape-y = -world-z
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
  const upSlab = new THREE.Mesh(slabShape(deck), matFloorBase());
  upSlab.position.y = LH;
  upSlab.userData.ground = true; upSlab.userData.level = 1;
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

  // hex roof (covers the wing-doorway slivers too)
  const roof = new THREE.Mesh(slabShape(deck), matRoof);
  roof.position.y = LH + CH + 0.02;
  roofGroup.add(roof);

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

  // the painted-ply sign arching between the tower tops
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

// ---------------------------------------------------------------- fixtures
function fixtureLevel(cfgRoom, posEntry) {
  if (posEntry && posEntry.length > 2) return posEntry[2];
  return cfgRoom.floor === 'both' ? 1 : (cfgRoom.floor || 0);
}

function buildFixtures(cfg) {
  const grid = $('fixture-grid');
  for (const [room, lights] of Object.entries(cfg.room_layout)) {
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

  for (const trig of cfg.triggers) {
    const geo = byName[trig.name] || {};
    const level = geo.level || (geo.pos && geo.pos[1] > S.levelHeight ? 1 : 0);
    const sensor = {
      name: trig.name, kind: geo.kind || trig.type, room: trig.room, level,
      action: trig.action, type: trig.type, lastFired: -1e9, meshes: [], seg: geo.seg || null,
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
    } else if (geo.kind === 'button' && geo.pos) {
      const colors = { 'Button 1': 0x3d7bff, 'Button 2': 0xffc93d, 'Button 3': 0x3dff70, 'Button 4': 0xff4d4d };
      const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.05, 24),
        new THREE.MeshStandardMaterial({ color: colors[trig.name] || 0xcccccc, roughness: 0.4, emissive: colors[trig.name] || 0x333333, emissiveIntensity: 0.25 }));
      btn.rotation.x = Math.PI / 2;
      btn.position.set(geo.pos[0], geo.pos[1], geo.pos[2]);
      btn.userData.sensor = sensor;
      grp(level).add(btn);
      const lbl = makeLabel(geo.label || trig.name, 0.24);
      lbl.position.set(geo.pos[0], geo.pos[1] + 0.19, geo.pos[2] + 0.04);
      grp(level).add(lbl);
      sensor.meshes.push(btn);
      S.interactables.push(btn);
    } else if (geo.kind === 'knock' && geo.pos) {
      const pad = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.04),
        new THREE.MeshStandardMaterial({ color: 0x6a5232, roughness: 0.8, emissive: 0x2a1f10, emissiveIntensity: 0.4 }));
      pad.position.set(geo.pos[0], geo.pos[1], geo.pos[2]);
      pad.userData.sensor = sensor;
      grp(level).add(pad);
      const lbl = makeLabel(geo.label || trig.name, 0.24);
      lbl.position.set(geo.pos[0], geo.pos[1] + 0.22, geo.pos[2] + 0.04);
      grp(level).add(lbl);
      sensor.meshes.push(pad);
      S.interactables.push(pad);
    }

    const b = document.createElement('button');
    const isPlaceholder = trig.room && placeholders.has(trig.room)
      && (trig.action.data || {}).effect_name === 'Lightning';
    b.textContent = trig.name + (isPlaceholder ? ' ⚠' : '');
    b.title = `${trig.type} → ${JSON.stringify(trig.action.data)}`
      + (isPlaceholder ? '\n⚠ placeholder: no bespoke effect designed for this room yet' : '');
    b.onclick = () => fireSensor(sensor, true);
    triggerList.appendChild(b);

    S.sensors.push(sensor);
  }
}

function fireSensor(sensor, manual) {
  const now = clock.getElapsedTime();
  if (now - sensor.lastFired < COOLDOWN_S) {
    if (manual) toast(`${sensor.name}: cooling down`);
    return;
  }
  sensor.lastFired = now;
  const source = manual ? 'click' : 'walkthrough';

  if (sensor.type === 'piezo') {
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

function checkBeamCrossings() {
  if (S.teleporting) { S.teleporting = false; S.prev2 = { x: S.pos.x, z: S.pos.z }; return; }
  const { x: px, z: pz } = S.prev2;
  const { x, z } = S.pos;
  if (px === x && pz === z) return;
  for (const sensor of S.sensors) {
    if (!sensor.seg || sensor.level !== S.level) continue;
    const [[x1, z1], [x2, z2]] = sensor.seg;
    if (segCross(px, pz, x, z, x1, z1, x2, z2)) fireSensor(sensor, false);
  }
  S.prev2 = { x, z };
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
      topCam.zoom = Math.max(0.4, Math.min(6, topCam.zoom * (ev.deltaY > 0 ? 0.9 : 1.11)));
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
  $('btn-respawn').onclick = () => {
    const sp = cfg.layout.spawn;
    S.pos.set(sp.pos[0], 1.6, sp.pos[1]);
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
  S.pos.y = 1.6 + S.level * S.levelHeight; // eye height under the 6.5ft ceiling
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
  S.frame = new Uint8Array(cfg.num_channels || 168);

  buildMaze(cfg);
  buildFixtures(cfg);
  buildSensors(cfg);
  buildAvatar();

  const sp = cfg.layout.spawn;
  S.pos.set(sp.pos[0], 1.6, sp.pos[1]);
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

  log('info', `sim ready — ${S.fixtures.length} fixtures, ${S.sensors.length} sensors, ${Object.keys(cfg.room_layout).length} rooms, two stories`);
  log('info', 'note: lights/audio also react to OTHER clients & test scripts — this log only shows YOUR actions');
  animate();
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  const t = clock.getElapsedTime();

  if (S.mode === 'first') updateMovement(dt);
  checkBeamCrossings();
  updateFixtures(t);
  updateFixtureGrid(t);
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
