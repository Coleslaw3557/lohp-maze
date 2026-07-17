// LoHP Maze Simulator — 3D walkthrough client.
//
// The maze is a TWO-STORY, OPEN-FACED structure (rooms.png is the street
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

// --- playa night environment: gradient sky dome + stars ---
{
  const c = document.createElement('canvas');
  c.width = 4; c.height = 256;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0.0, '#05060f');   // zenith
  grad.addColorStop(0.55, '#0d1024');
  grad.addColorStop(0.78, '#2a2038');  // dusty horizon glow
  grad.addColorStop(0.86, '#3b2b33');
  grad.addColorStop(1.0, '#191410');   // below horizon
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 256);
  const skyTex = new THREE.CanvasTexture(c);
  skyTex.colorSpace = THREE.SRGBColorSpace;
  const dome = new THREE.Mesh(new THREE.SphereGeometry(150, 24, 16),
    new THREE.MeshBasicMaterial({ map: skyTex, side: THREE.BackSide, fog: false, depthWrite: false }));
  dome.position.set(10, 0, 5);
  scene.add(dome);

  const starPos = [];
  for (let i = 0; i < 900; i++) {
    const az = Math.random() * Math.PI * 2;
    const el = Math.asin(Math.random() * 0.92 + 0.06); // keep off the horizon band
    const r = 140;
    starPos.push(10 + r * Math.cos(el) * Math.cos(az), r * Math.sin(el), 5 + r * Math.cos(el) * Math.sin(az));
  }
  const starGeo = new THREE.BufferGeometry();
  starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({
    color: 0xcdd6ff, size: 0.55, sizeAttenuation: true, transparent: true, opacity: 0.85, fog: false,
  }));
  scene.add(stars);
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

scene.add(new THREE.AmbientLight(0x9895b0, 0.2));
scene.add(new THREE.HemisphereLight(0x252b4e, 0x54462f, 0.5)); // night sky over warm dust bounce

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
const matFramePaint = [
  new THREE.MeshStandardMaterial({ color: 0x2666b8, roughness: 0.5, metalness: 0.25 }), // our blue
  new THREE.MeshStandardMaterial({ color: 0x2f9e57, roughness: 0.5, metalness: 0.25 }), // our green
];

// One 6'4" walk-thru frame (ScaffoldMart/ScaffoldsSupply pattern) between two
// points: legs w/ coupling spigots, double-rail top band with spacers,
// candy-cane curves into the legs, and the 3-rung ladder section on each leg.
function buildFrameSeg(ax, az, bx, bz, yBase, mat, opts = {}) {
  const H = 1.93, R = 0.0214;
  const dx = bx - ax, dz = bz - az;
  const len = Math.hypot(dx, dz);
  const fg = new THREE.Group();
  fg.position.set((ax + bx) / 2, yBase, (az + bz) / 2);
  fg.rotation.y = -Math.atan2(dz, dx);

  const cylY = (r, h) => new THREE.CylinderGeometry(r, r, h);
  const addCyl = (r, h, x, y, rotZ = 0, material = mat) => {
    const m = new THREE.Mesh(cylY(r, h), material);
    m.position.set(x, y, 0);
    if (rotZ) m.rotation.z = rotZ;
    fg.add(m);
    return m;
  };

  for (const s of [-1, 1]) {
    if ((s < 0 && opts.skipLegA) || (s > 0 && opts.skipLegB)) continue;
    const lx = s * (len / 2);
    addCyl(R, H, lx, H / 2);                       // leg
    addCyl(0.013, 0.14, lx, H + 0.06, 0, matGalv); // coupling-pin spigot
    // ladder section: inner stub + 3 rungs
    const ix = lx - s * 0.20;
    addCyl(0.014, 1.2, ix, 0.85);
    for (const ry of [0.45, 0.85, 1.25]) addCyl(0.011, 0.19, lx - s * 0.10, ry, Math.PI / 2);
  }
  addCyl(0.019, len - 0.02, 0, H - 0.025, Math.PI / 2);        // top rail
  const rail2 = len - 0.56;
  addCyl(0.019, rail2, 0, H - 0.30, Math.PI / 2);              // second rail
  for (let k = 1; k <= 4; k++) {                                // spacers
    addCyl(0.010, 0.25, -rail2 / 2 + k * rail2 / 5, H - 0.165);
  }
  for (const s of [-1, 1]) {                                    // candy-cane curves
    if ((s < 0 && opts.skipLegA) || (s > 0 && opts.skipLegB)) continue;
    const stub = addCyl(0.019, 0.34, s * (rail2 / 2 + 0.13), H - 0.395, s * 0.95);
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

    // walls per level: back (north) + west + east. NO street wall — open face.
    const wallHeight = isBoth ? LH + CH : CH;
    const wallLevels = isBoth ? [{ y: 0, h: LH + CH, lv: 'both' }]
      : [{ y: yBase, h: CH, lv: baseLevel }];
    for (const wl of wallLevels) {
      // adjacent rooms share one scaffold frame: nudge west/east panels inward
      // so both rooms' panels abut at the shared boundary without z-fighting
      const walls = [
        ['x', r.z, r.x, r.x + r.w, 0],               // back wall (north)
        ['z', r.x, r.z, r.z + r.d, T / 2 + 0.004],   // west
        ['z', r.x + r.w, r.z, r.z + r.d, -(T / 2 + 0.004)], // east
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
    // 7' x 4' cross braces (ScaffoldsSupply spec: "4' Lock Span"): the scissor
    // spans the 7' bay with a 4' (1.22m) vertical spread between brace studs —
    // a wide flat X crossing at mid-bay, not corner-to-corner
    const STUD_SPREAD = 1.219;
    const braceMidY = 0.97; // studs sit symmetrically on the 6'4" frame legs
    for (let i = 0; i < bs.length - 1; i++) {
      const x0 = bs[i], x1 = bs[i + 1];
      if (x1 - x0 > 2.2) continue; // hexagon span, no wing bay here
      const dx = x1 - x0 - 0.12;
      const len = Math.hypot(dx, STUD_SPREAD);
      for (const lv of [0, 1]) {
        for (const zb of [rz + 0.085, rz + rd - 0.085]) { // back AND front planes
          for (const dir of [1, -1]) {
            const brace = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, len), matGalv);
            brace.position.set((x0 + x1) / 2, lv * LH + braceMidY, zb);
            brace.rotation.z = Math.atan2(dir * STUD_SPREAD, dx) - Math.PI / 2;
            grp(lv).add(brace);
          }
        }
      }
    }
  }

  if (L.hex_center) buildHexCenter(L);


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

  // server rack
  if (L.server_rack) {
    const [rx, rz] = L.server_rack.pos;
    const rack = new THREE.Mesh(new THREE.BoxGeometry(0.38, 1.1, 0.3),
      new THREE.MeshStandardMaterial({ color: 0x101318, roughness: 0.6, metalness: 0.4 }));
    rack.position.set(rx, 0.55, rz);
    levelGroups[0].add(rack);
    const led = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.02),
      new THREE.MeshBasicMaterial({ color: 0x33ff66 }));
    led.position.set(rx + 0.09, 0.92, rz + 0.16);
    levelGroups[0].add(led);
    const lbl = makeLabel(L.server_rack.label || 'SERVER', 0.3);
    lbl.position.set(rx, 1.35, rz + 0.2);
    levelGroups[0].add(lbl);
  }
}

// ---------------------------------------------------------------- hex center
// The center is a hexagon of the same 7ft scaffold pieces (side = one bay).
// East/west vertices kiss the wings; front flat face is open to the street.
// Ground: Exit (west half) + Entrance (east half). Upper deck: Cuddle Cross.
function buildHexCenter(L) {
  const H = L.hex_center;
  const LH = L.level_height || 2.03, CH = L.ceiling_height || 1.98;
  const cx = H.cx, cz = H.cz, R = H.side;
  const V = [];
  for (let k = 0; k < 6; k++) {
    const a = k * Math.PI / 3; // 0,60,...: flat front/back, pointy east/west
    V.push([cx + R * Math.cos(a), cz + R * Math.sin(a)]);
  }
  // V[0]=east vertex, V[1]/V[2]=front flat, V[3]=west vertex, V[4]/V[5]=back flat

  const slabShape = (pts) => {
    const sh = new THREE.Shape();
    pts.forEach(([x, z], i) => i ? sh.lineTo(x, -z) : sh.moveTo(x, -z)); // shape-y = -world-z
    const geo = new THREE.ExtrudeGeometry(sh, { depth: 0.14, bevelEnabled: false });
    geo.rotateX(-Math.PI / 2); // lie flat: extrusion becomes +y
    return geo;
  };
  const frontMidTop = [cx, cz + R * Math.sin(Math.PI / 3)];
  const backMid = [cx, cz - R * Math.sin(Math.PI / 3)];
  const halves = {
    [H.rooms.ground_west]: [frontMidTop, V[2], V[3], V[4], backMid],
    [H.rooms.ground_east]: [frontMidTop, backMid, V[5], V[0], V[1]],
  };
  for (const [room, pts] of Object.entries(halves)) {
    const slab = new THREE.Mesh(slabShape(pts), matFloorBase());
    slab.userData.ground = true; slab.userData.level = 0;
    levelGroups[0].add(slab);
    const xs = pts.map(p => p[0]), zs = pts.map(p => p[1]);
    const c = new THREE.Vector3((Math.min(...xs) + Math.max(...xs)) / 2, 1.0, cz);
    S.roomsMeshes[room] = { slab, center: c, level: 0, room: L.rooms[room] };
    const lbl = makeLabel(room, 0.24);
    lbl.position.set(c.x, CH + 0.14, cz + R * 0.87 + 0.12);
    levelGroups[0].add(lbl);
  }
  const upSlab = new THREE.Mesh(slabShape(V), matFloorBase());
  upSlab.position.y = LH;
  upSlab.userData.ground = true; upSlab.userData.level = 1;
  levelGroups[1].add(upSlab);
  S.roomsMeshes[H.rooms.upper] = {
    slab: upSlab, center: new THREE.Vector3(cx, LH + 1, cz), level: 1, room: L.rooms[H.rooms.upper],
  };
  const upLbl = makeLabel(H.rooms.upper, 0.24);
  upLbl.position.set(cx, LH + CH + 0.14, cz + R * 0.87 + 0.12);
  levelGroups[1].add(upLbl);

  // walls: faces 0=[V0,V1] SE, 1=[V1,V2] front(OPEN), 2=[V2,V3] SW, 3=[V3,V4] NW,
  // 4=[V4,V5] back, 5=[V5,V0] NE. Trim 0.55 at the east/west vertex ends — those
  // corners are the doorways into the wings (the beams sit right on them).
  const faces = [
    { a: V[0], b: V[1], trimA: 0.55 }, // SE (door at east vertex)
    null,                              // front open
    { a: V[2], b: V[3], trimB: 0.55 }, // SW (door at west vertex)
    { a: V[3], b: V[4], trimA: 0.55 }, // NW (door at west vertex)
    { a: V[4], b: V[5] },              // back
    { a: V[5], b: V[0], trimB: 0.55 }, // NE (door at east vertex)
  ];
  for (const lv of [0, 1]) {
    for (const f of faces) {
      if (!f) continue;
      const dx = f.b[0] - f.a[0], dz = f.b[1] - f.a[1];
      const len = Math.hypot(dx, dz), ux = dx / len, uz = dz / len;
      const tA = f.trimA || 0, tB = f.trimB || 0;
      const l2 = len - tA - tB;
      if (l2 < 0.1) continue;
      const mx = f.a[0] + ux * (tA + l2 / 2), mz = f.a[1] + uz * (tA + l2 / 2);
      const wall = new THREE.Mesh(new THREE.BoxGeometry(l2, CH, 0.05), matWall);
      wall.position.set(mx, lv * LH + CH / 2, mz);
      wall.rotation.y = -Math.atan2(dz, dx);
      levelGroups[lv].add(wall);
    }
    // Exit | Entrance divider on the ground floor only
    if (lv === 0) {
      const div = new THREE.Mesh(new THREE.BoxGeometry(0.05, CH, R * 1.73 - 0.5), matWall);
      div.position.set(cx, CH / 2, cz);
      levelGroups[0].add(div);
    }
  }

  // hex roof
  const roof = new THREE.Mesh(slabShape(V), matRoof);
  roof.position.y = LH + CH + 0.02;
  roofGroup.add(roof);

  // six 5' walk-thru frames per level (twelve total), hose-clamped at the
  // corners — NO cross braces. Each face draws one frame; a vertex's leg
  // comes from its outgoing face so clamped joints don't double-render, and
  // the east/west vertices stay leg-free (they're the doorways to the wings).
  // The front face's walkthru arch IS the street entrance.
  for (let k = 0; k < 6; k++) {
    const a = V[k], b = V[(k + 1) % 6];
    for (const lv of [0, 1]) {
      const frame = buildFrameSeg(a[0], a[1], b[0], b[1], lv * LH,
        matFramePaint[(k + lv) % 2],
        { skipLegA: k === 0 || k === 3, skipLegB: true });
      grp(lv).add(frame);
    }
  }
  // hose-clamp sleeves at the frame joints
  V.forEach(([vx, vz], i) => {
    if (i === 0 || i === 3) return;
    for (const cy of [0.35, 1.05, 1.7, LH + 0.35, LH + 1.05, LH + 1.7]) {
      const clamp = new THREE.Mesh(new THREE.CylinderGeometry(0.033, 0.033, 0.06), matGalv);
      clamp.position.set(vx, cy, vz);
      grp(cy > LH ? 1 : 0).add(clamp);
    }
  });
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

      // flashlight icons in maze-diagram.drawio = the U'King DMX spotlights
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
      ? cfg.layout.hex_center.cz + hexR * Math.sin(Math.PI / 3) : 0),
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
