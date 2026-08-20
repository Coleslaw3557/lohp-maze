// Camp ground plan — Jen's LotHP-26-v3.svg placement drawing rendered around
// the maze at true scale (address 4:30 & B, plaza frontage).
//
// SELF-CONTAINED module: all camp-lot rendering lives here, behind the Camp
// button. app.js only calls window.CAMP_LAYOUT.build(THREE) once and toggles
// the returned group's visibility — nothing else in the sim depends on this
// file, and this file depends on nothing but camp_layout_data.js (baked world
// coordinates; regenerate with sim/tools/camp_from_svg.py after an SVG rev).
//
// What it draws (drawing legend -> Tim's ground truth):
//   lot + frontage labels        the 175' B / 50' plaza / 150' / 100' edges
//   Black Rock shade zones       EMT-conduit shade structures (aluminet roof)
//   Trailer + BRS                cargo trailer under a Black Rock shade
//   Camp Communal Space          4 Costco carports pinwheeled around an open
//                                square, Black Rock shade in the center
//   Water                        250-gallon water tank
//   Small Generator              Predator 5000 inverter
//   plus: 6 cars, OSS container, shower & evap, 2 bike racks, shared fuel
//   depot circles (Blazing Death Ship), maze tie-down margin, and the
//   extension cord routes from the generator (wiring-guides/camp-power-cords.md).
window.CAMP_LAYOUT = (() => {
  const FT = 0.3048;

  function build(THREE) {
    const D = window.CAMP_DATA;
    const g = new THREE.Group();
    g.name = 'camp-layout';
    if (!D) return g;

    // ---- shared materials (MeshStandard so day/night lighting applies; a
    // touch of emissive keeps things findable on the moonlit night setting)
    const mat = (color, opts = {}) => new THREE.MeshStandardMaterial(
      Object.assign({ color, roughness: 0.92, metalness: 0.05,
                      emissive: color, emissiveIntensity: 0.06 }, opts));
    const matEMT = mat(0x9aa2a8, { metalness: 0.55, roughness: 0.45 });
    const matAluminet = mat(0xb8bfc6, { transparent: true, opacity: 0.42,
                                        side: THREE.DoubleSide, depthWrite: false });
    const matCarport = mat(0xe8e4da, { transparent: true, opacity: 0.9, side: THREE.DoubleSide });
    const matWall = mat(0xe8e4da, { transparent: true, opacity: 0.82 });
    const CP_EAVE_FT = 6.5, CP_RIDGE_FT = 8.5; // Costco carport eave / ridge
    const matDark = mat(0x453e40);
    const matGuy = new THREE.LineBasicMaterial({ color: 0xcf7f33, transparent: true, opacity: 0.7 });

    // ---- tiny builders -----------------------------------------------------
    const box = (parent, w, h, d, m, x, y, z, rotY = 0) => {
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
      b.position.set(x, y, z); b.rotation.y = rotY;
      parent.add(b); return b;
    };
    const post = (parent, x, z, h, r = 0.014) => {
      const c = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 6), matEMT);
      c.position.set(x, h / 2, z);
      parent.add(c); return c;
    };
    // flat filled polygon on the ground (slightly lifted; drawn under lines)
    const flatPoly = (pts, color, opacity, y) => {
      const shape = new THREE.Shape(pts.map(([x, z]) => new THREE.Vector2(x, -z)));
      const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity,
          side: THREE.DoubleSide, depthWrite: false,
          polygonOffset: true, polygonOffsetFactor: -1 }));
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = y;
      g.add(mesh);
    };
    const outline = (pts, color, y, { dashed = false, opacity = 0.9 } = {}) => {
      const v = pts.map(([x, z]) => new THREE.Vector3(x, y, z));
      v.push(v[0].clone());
      const geo = new THREE.BufferGeometry().setFromPoints(v);
      const m = dashed
        ? new THREE.LineDashedMaterial({ color, dashSize: 0.5, gapSize: 0.35, transparent: true, opacity })
        : new THREE.LineBasicMaterial({ color, transparent: true, opacity });
      const line = new THREE.Line(geo, m);
      if (dashed) line.computeLineDistances();
      g.add(line);
    };
    const polyline = (pts, color, y, { dashed = false, opacity = 0.9 } = {}) => {
      const v = pts.map(([x, z]) => new THREE.Vector3(x, y, z));
      const geo = new THREE.BufferGeometry().setFromPoints(v);
      const m = dashed
        ? new THREE.LineDashedMaterial({ color, dashSize: 0.5, gapSize: 0.35, transparent: true, opacity })
        : new THREE.LineBasicMaterial({ color, transparent: true, opacity });
      const line = new THREE.Line(geo, m);
      if (dashed) line.computeLineDistances();
      g.add(line);
    };
    const circlePts = (cx, cz, r, n = 48) => Array.from({ length: n },
      (_, i) => [cx + r * Math.cos(i / n * 2 * Math.PI), cz + r * Math.sin(i / n * 2 * Math.PI)]);
    // an OBB's local frame: +x spans w, +z spans d, origin at the center
    const frame = (o, y = 0) => {
      const f = new THREE.Group();
      f.position.set(o.cx, y, o.cz); f.rotation.y = o.rot || 0;
      g.add(f); return f;
    };
    const obbCorners = (o) => {
      const c = Math.cos(o.rot || 0), s = Math.sin(o.rot || 0);
      return [[-o.w / 2, -o.d / 2], [o.w / 2, -o.d / 2], [o.w / 2, o.d / 2], [-o.w / 2, o.d / 2]]
        .map(([x, z]) => [o.cx + x * c + z * s, o.cz - x * s + z * c]);
    };
    const localFt = (o, xFt, zFt) => {
      const c = Math.cos(o.rot || 0), s = Math.sin(o.rot || 0);
      const x = xFt * FT, z = zFt * FT;
      return [o.cx + x * c + z * s, o.cz - x * s + z * c];
    };
    const label = (text, x, y, z, h = 0.62, color = '#ffe9c9') => {
      const pad = 8, font = '600 34px system-ui, sans-serif';
      const cv = document.createElement('canvas');
      cv.height = 46;
      const meas = cv.getContext('2d');
      meas.font = font;
      cv.width = Math.ceil(meas.measureText(text).width) + pad * 2;
      const c2 = cv.getContext('2d'); // width change reset the context state
      c2.font = font; c2.textBaseline = 'middle';
      c2.lineWidth = 6; c2.strokeStyle = 'rgba(10,8,6,0.85)';
      c2.strokeText(text, pad, 24); c2.fillStyle = color; c2.fillText(text, pad, 24);
      const tex = new THREE.CanvasTexture(cv);
      tex.anisotropy = 4;
      const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
        opacity: 0.92, depthWrite: false }));
      sp.scale.set(h * cv.width / cv.height, h, 1);
      sp.position.set(x, y, z);
      g.add(sp);
    };

    // a Black Rock shade: EMT legs on a perimeter grid under a flat aluminet
    // roof, corner guy lines out to playa stakes, and (Tim 2026-08-06) shade
    // panels coming down at an angle off every roof edge — sloping ~6 ft out
    // toward the tie-down line, which is why the drawn zones are 6 ft bigger
    // than the structure on every side
    const brShade = (o, wFt, dFt, hFt, { legsEvery = 12, skirts = true } = {}) => {
      const f = frame(o);
      const w = wFt * FT, d = dFt * FT, h = hFt * FT;
      const roof = new THREE.Mesh(new THREE.PlaneGeometry(w, d), matAluminet);
      roof.rotation.x = -Math.PI / 2; roof.position.y = h;
      f.add(roof);
      const nx = Math.max(2, Math.round(wFt / legsEvery) + 1), nz = Math.max(2, Math.round(dFt / legsEvery) + 1);
      for (let i = 0; i < nx; i++)
        for (let j = 0; j < nz; j++) {
          if (i > 0 && i < nx - 1 && j > 0 && j < nz - 1) continue; // perimeter only
          post(f, -w / 2 + i * w / (nx - 1), -d / 2 + j * d / (nz - 1), h);
        }
      if (skirts) {
        // panels run from the roof edge all the way to the GROUND at the
        // tie-down line ~6 ft out (Tim 2026-08-06)
        const out = 6 * FT, hBot = 0.02;
        const slant = Math.hypot(out, h - hBot);
        const tilt = Math.atan2(h - hBot, out);
        for (let s = 0; s < 4; s++) { // +z, +x, -z, -x sides
          const wrap = new THREE.Group();
          wrap.rotation.y = s * Math.PI / 2;
          f.add(wrap);
          const across = (s % 2 === 0 ? w : d) - 0.3, half = (s % 2 === 0 ? d : w) / 2;
          const p = new THREE.Mesh(new THREE.PlaneGeometry(across, slant), matAluminet);
          p.rotation.x = -Math.PI / 2 + tilt;
          p.position.set(0, (h + hBot) / 2, half + out / 2);
          wrap.add(p);
        }
      }
      for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
        const top = new THREE.Vector3(sx * w / 2, h, sz * d / 2);
        const stake = new THREE.Vector3(sx * (w / 2 + 5 * FT), 0.05, sz * (d / 2 + 5 * FT));
        f.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([top, stake]), matGuy));
      }
      return f;
    };

    // a Costco carport: 10x20 peaked white canopy on six legs, ridge along
    // the long side. Built ridge-along-x, then yawed for the tall orientation.
    const carport = (parent, cxFt, czFt, wFt, dFt) => {
      const yaw = dFt > wFt ? Math.PI / 2 : 0;
      if (dFt > wFt) [wFt, dFt] = [dFt, wFt];
      const w = wFt * FT, d = dFt * FT, hEave = CP_EAVE_FT * FT, hRidge = CP_RIDGE_FT * FT;
      const c = new THREE.Group();
      c.position.set(cxFt * FT, 0, czFt * FT); c.rotation.y = yaw;
      parent.add(c);
      for (const px of [-1, 0, 1]) for (const pz of [-1, 1])
        post(c, px * (w / 2 - 0.06), pz * (d / 2 - 0.06), hEave, 0.017);
      const tilt = Math.atan2(hRidge - hEave, d / 2);
      const slope = Math.hypot(d / 2, hRidge - hEave);
      for (const s of [-1, 1]) { // two half-roofs meeting at the ridge
        const p = new THREE.Mesh(new THREE.PlaneGeometry(w, slope), matCarport);
        p.rotation.x = -Math.PI / 2 + s * tilt;
        p.position.set(0, (hEave + hRidge) / 2, s * d / 4);
        c.add(p);
      }
    };

    // ---- the lot ----------------------------------------------------------
    flatPoly(D.lot, 0xfbb040, 0.10, 0.012);
    outline(D.lot, 0xfbb040, 0.05);
    for (const e of Object.values(D.edges || {}))
      label(e.label, e.pos[0], 0.7, e.pos[1], 0.42, '#ffd489');

    // ---- the plaza intersection + the Man (Tim 2026-08-06: 4:30 & B plaza,
    // camp at the plaza's own 2:15; bearings derived from that in the bake
    // tool). Rim circle, the 4:30 radial + B-ring road bands meeting at it,
    // a center marker, and a Man direction line with a distant beacon.
    if (D.plaza) {
      const P = D.plaza, pcx = P.c[0], pcz = P.c[1], R = P.r;
      const mx = P.man[0], mz = P.man[1], rx = P.ring[0], rz = P.ring[1];
      outline(circlePts(pcx, pcz, R), 0xffd489, 0.045, { opacity: 0.55 });
      const RW = 20 * FT, LEN = 60; // 40 ft wide streets, drawn 60 m out
      const band = (dx, dz) => {
        const px = -dz, pz = dx;
        flatPoly([
          [pcx + dx * R - px * RW, pcz + dz * R - pz * RW],
          [pcx + dx * (R + LEN) - px * RW, pcz + dz * (R + LEN) - pz * RW],
          [pcx + dx * (R + LEN) + px * RW, pcz + dz * (R + LEN) + pz * RW],
          [pcx + dx * R + px * RW, pcz + dz * R + pz * RW],
        ], 0xffffff, 0.05, 0.008);
      };
      band(mx, mz); band(-mx, -mz); // the 4:30 radial through the plaza
      band(rx, rz); band(-rx, -rz); // the B ring through the plaza
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 3, 8), matEMT);
      pole.position.set(pcx, 1.5, pcz); g.add(pole);
      outline(circlePts(pcx, pcz, 1.2), 0xffd489, 0.05, { opacity: 0.8 });
      label('4:30 & B Plaza — center', pcx, 3.4, pcz, 0.55, '#ffd489');
      // the Man: exact direction, beacon clamped onto the ground plane
      const MD = 130;
      outline([[pcx + mx * 1.2, pcz + mz * 1.2], [pcx + mx * MD, pcz + mz * MD]],
        0xffa040, 0.06, { dashed: true, opacity: 0.8 });
      const man = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.25, 16, 8),
        mat(0xff8c2a, { emissiveIntensity: 0.65 }));
      man.position.set(pcx + mx * MD, 8, pcz + mz * MD); g.add(man);
      label(`The Man — ≈${P.man_dist_m} m this way`, pcx + mx * MD, 17.2, pcz + mz * MD, 1.1, '#ffb060');
      label('The Man ⇢', pcx + mx * (R + 14), 1.6, pcz + mz * (R + 14), 0.55, '#ffb060');
    }

    // ---- zones ------------------------------------------------------------
    for (const z of D.zones) {
      const corners = obbCorners(z);
      if (z.key === 'bds_strip') {
        flatPoly(corners, 0xec008c, 0.13, 0.024);
        outline(corners, 0xec6fae, 0.055, { opacity: 0.6 });
      } else if (z.key === 'tiedown') {
        // the maze lives here — outline only, clear of the effects floor
        outline(corners, 0xd6cec8, 0.045, { dashed: true, opacity: 0.55 });
      } else if (z.key === 'brs_tents') {
        flatPoly(corners, 0xffffff, 0.05, 0.03);
        // Tim 2026-08-06: the structure is 30x40, 8 ft tall; the drawn 45x55
        // zone is that plus ~6 ft of tie-downs on every side. The 12 tent
        // spots (4x3, 10x10 each) subdivide the STRUCTURE; the middle 2 are
        // excluded — only the 10 edge spots get campers.
        const GW = 40 * FT, GD = 30 * FT;
        brShade(z, 40, 30, 8, { legsEvery: 10 });
        const l2w = (lx, lz) => {
          const c = Math.cos(z.rot || 0), s = Math.sin(z.rot || 0);
          return [z.cx + lx * c + lz * s, z.cz - lx * s + lz * c];
        };
        const NX = 4, NZ = 3;
        for (let i = 0; i <= NX; i++) {
          const x = -GW / 2 + i * GW / NX;
          outline([l2w(x, -GD / 2), l2w(x, GD / 2)], 0xd6cec8, 0.04, { opacity: 0.4 });
        }
        for (let j = 0; j <= NZ; j++) {
          const zz = -GD / 2 + j * GD / NZ;
          outline([l2w(-GW / 2, zz), l2w(GW / 2, zz)], 0xd6cec8, 0.04, { opacity: 0.4 });
        }
        for (let i = 0; i < NX; i++)
          for (let j = 0; j < NZ; j++) {
            const x0 = -GW / 2 + i * GW / NX, z0 = -GD / 2 + j * GD / NZ;
            const x1 = x0 + GW / NX, z1 = z0 + GD / NZ;
            if (i > 0 && i < NX - 1 && j > 0 && j < NZ - 1) { // excluded middle
              outline([l2w(x0 + 0.4, z0 + 0.4), l2w(x1 - 0.4, z1 - 0.4)], 0xcf7f33, 0.042, { opacity: 0.5 });
              outline([l2w(x0 + 0.4, z1 - 0.4), l2w(x1 - 0.4, z0 + 0.4)], 0xcf7f33, 0.042, { opacity: 0.5 });
            } else {
              flatPoly([l2w(x0 + 0.15, z0 + 0.15), l2w(x1 - 0.15, z0 + 0.15),
                        l2w(x1 - 0.15, z1 - 0.15), l2w(x0 + 0.15, z1 - 0.15)],
                0xffffff, 0.06, 0.034);
            }
          }
        label(z.label, z.cx, 3.35, z.cz, 0.6);
      } else if (z.key === 'communal') {
        // Tim 2026-08-06: one 10x20 Costco carport centered on each side of
        // the 40x40 — corners touch at (±10,±10), 20x20 square stays open —
        // with a Black Rock shade over the whole square, LEVEL with the
        // canopy (eave height, so coverage is continuous). Sidewalls on every
        // outward face; inward faces open; door gaps front (maze side) and
        // rear (facing the water tank).
        flatPoly(corners, 0xffffff, 0.05, 0.03);
        const f = frame(z);
        carport(f, 0, 15, 20, 10);   // front (local +z = maze/plaza side)
        carport(f, 15, 0, 10, 20);
        carport(f, 0, -15, 20, 10);  // rear (faces the water)
        carport(f, -15, 0, 10, 20);
        // floors under the carports (Tim 2026-08-06)
        const matFloor = mat(0xc4a06b, { roughness: 0.85 });
        box(f, 20 * FT, 0.06, 10 * FT, matFloor, 0, 0.05, 15 * FT);
        box(f, 20 * FT, 0.06, 10 * FT, matFloor, 0, 0.05, -15 * FT);
        box(f, 10 * FT, 0.06, 20 * FT, matFloor, 15 * FT, 0.05, 0);
        box(f, 10 * FT, 0.06, 20 * FT, matFloor, -15 * FT, 0.05, 0);
        brShade({ cx: z.cx, cz: z.cz, rot: z.rot }, 20, 20, CP_EAVE_FT,
          { legsEvery: 20, skirts: false }); // enclosed by the carports
        // sidewalls, zone-local feet: [x0, z0, x1, z1] at eave height
        const DOOR = 8, J = (20 - DOOR) / 2; // 6 ft jamb panels beside doors
        for (const [x0, z0, x1, z1] of [
          [-10, 20, -10 + J, 20], [10 - J, 20, 10, 20],    // front wall + door
          [-10, -20, -10 + J, -20], [10 - J, -20, 10, -20], // rear wall + door
          [20, -10, 20, 10], [-20, -10, -20, 10],           // side outer walls
          [-10, 10, -10, 20], [10, 10, 10, 20],             // front carport ends
          [-10, -20, -10, -10], [10, -20, 10, -10],         // rear carport ends
          [10, 10, 20, 10], [10, -10, 20, -10],             // east carport ends
          [-20, 10, -10, 10], [-20, -10, -10, -10],         // west carport ends
        ]) {
          const len = Math.hypot(x1 - x0, z1 - z0) * FT;
          box(f, x0 === x1 ? 0.06 : len, CP_EAVE_FT * FT, z0 === z1 ? 0.06 : len,
            matWall, (x0 + x1) / 2 * FT, CP_EAVE_FT * FT / 2, (z0 + z1) / 2 * FT);
        }
        label(z.label, z.cx, 3.6, z.cz, 0.6);
      }
    }

    // ---- items ------------------------------------------------------------
    for (const it of D.items) {
      const f = 'w' in it ? frame(it) : null;
      switch (it.kind) {
        case 'car': {
          box(f, it.w, 1.35, it.d * 0.96, matDark, 0, 0.7, 0);
          box(f, it.w * 0.55, 0.5, it.d * 0.8, mat(0x2e2a2c), 0, 1.55, 0);
          break;
        }
        case 'container': { // OSS 20' container, parked on the B-street side
          box(f, it.w, 2.6, it.d, mat(0x8a4a32), 0, 1.3, 0);
          label(it.label, it.cx, 3.15, it.cz, 0.5);
          break;
        }
        case 'trailer_brs': { // cargo trailer under its own Black Rock shade
          // Tim 2026-08-06: structure is 10x20, 10 ft tall; the drawn 22x32
          // zone is that plus ~6 ft of tie-downs on every side
          brShade(it, 10, 20, 10, { legsEvery: 10 });
          box(f, 8.5 * FT, 2.1, 20 * FT, mat(0xd9d5cf), 0, 1.5, 0);
          const tongue = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 4 * FT, 6), matEMT);
          tongue.rotation.x = Math.PI / 2 - 0.12;
          tongue.position.set(0, 0.32, 12 * FT);
          f.add(tongue);
          label(it.label, it.cx, 3.55, it.cz, 0.55);
          break;
        }
        case 'bike_rack': {
          box(f, it.w, 0.08, it.d, matDark, 0, 0.05, 0);
          for (let i = 0; i < 7; i++)
            box(f, 0.03, 0.8, it.d, matDark, -it.w / 2 + (i + 0.5) * it.w / 7, 0.48, 0);
          break;
        }
        case 'shower_box': {
          box(f, it.w, 7 * FT, it.d, mat(0x7d8894, { transparent: true, opacity: 0.85 }), 0, 3.5 * FT, 0);
          break;
        }
        case 'evap': { // black evap tray beside the shower stall
          box(f, it.w, 0.25, it.d, mat(0x23262b), 0, 0.13, 0);
          label(it.label, it.cx, 2.5, it.cz, 0.5);
          break;
        }
        case 'generator': { // Predator 5000 inverter on its 5x5 pad
          outline(obbCorners(it), 0xd3d1e9, 0.04, { opacity: 0.5 });
          box(f, 0.62, 0.48, 0.45, mat(0xb02a25), 0, 0.26, 0);
          label(it.label, it.cx, 1.9, it.cz, 0.48);
          break;
        }
        case 'water': { // 250-gallon tank on its pad circle
          outline(circlePts(it.cx, it.cz, it.r), 0xd3d1e9, 0.04, { opacity: 0.5 });
          const tank = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 1.5, 20),
            mat(0xdfe5e8, { roughness: 0.5 }));
          tank.position.set(it.cx, 0.75, it.cz); g.add(tank);
          label(it.label, it.cx, 2.35, it.cz, 0.5);
          break;
        }
        case 'fuel_pad': { // shared with Blazing Death Ship, mostly off-lot
          flatPoly(circlePts(it.cx, it.cz, it.r), 0xd3d1e9, 0.14, 0.028);
          outline(circlePts(it.cx, it.cz, it.r), 0xd3d1e9, 0.04, { dashed: true, opacity: 0.7 });
          box(g, 0.34, 0.45, 0.17, mat(0xb02a25), it.cx - 0.5, 0.23, it.cz, 0.4);
          box(g, 0.34, 0.45, 0.17, mat(0xb02a25), it.cx + 0.3, 0.23, it.cz + 0.4, -0.3);
          label(it.label, it.cx, 1.8, it.cz, 0.5);
          break;
        }
        case 'fuel_ring': { // 25' clearance ring
          outline(circlePts(it.cx, it.cz, it.r), 0xd3d1e9, 0.04, { dashed: true, opacity: 0.55 });
          break;
        }
      }
    }

    // ---- extension cord runs (wiring-guides/camp-power-cords.md) ----------
    // Four home runs off the Predator 5000 plus one daisy-chain branch: the
    // gen->water cord splits at the tank into a short stinger to the kitchen
    // (the communal's REAR carport — the one facing the water, where the
    // coffee maker lives). Colors match the plan artifact. Camp-side ends
    // track the baked drawing so an SVG rev moves the cords with the items;
    // the maze drop is the audio_power battery bus behind the hex
    // (maze_layout.json), a constant so this file still depends on
    // camp_layout_data.js only.
    {
      const MAZE_BUS = [10.044, -0.72];
      const zoneC = (k) => { const z = D.zones.find((x) => x.key === k); return z && [z.cx, z.cz]; };
      const itemC = (k) => { const i = D.items.find((x) => x.kind === k); return i && [i.cx, i.cz]; };
      const zone = (k) => D.zones.find((x) => x.key === k);
      const item = (k) => D.items.find((x) => x.kind === k);
      const genAt = itemC('generator');
      const waterAt = itemC('water');
      const tents = zone('brs_tents');
      const communal = zone('communal');
      const trailer = item('trailer_brs');
      const tentSideDrop = tents && localFt(tents, 28, 0);
      const kitchenAt = (() => { // rear carport center, zone-local (0, -15 ft)
        const z = D.zones.find((x) => x.key === 'communal');
        if (!z) return null;
        const lz = -15 * FT;
        return [z.cx + lz * Math.sin(z.rot || 0), z.cz + lz * Math.cos(z.rot || 0)];
      })();
      const aroundTentSide = tents ? [localFt(tents, 28, -24), localFt(tents, 28, 24)] : [];
      const aroundCommunalFront = communal ? [localFt(communal, -21, 21), localFt(communal, 21, 21)] : [];
      const aroundCommunalWest = communal ? [localFt(communal, -21, 21), localFt(communal, -21, -21)] : [];
      const cords = [
        { from: genAt, via: aroundTentSide, to: MAZE_BUS, gauge: '10/3', color: 0xe06a50 },  // maze battery bus
        { from: genAt, via: aroundCommunalFront, to: trailer && [trailer.cx, trailer.cz], gauge: '10/3', color: 0x7fb086 },
        { from: genAt, via: tents ? [localFt(tents, 28, -24)] : [], to: tentSideDrop || zoneC('brs_tents'), gauge: '12/3', color: 0xa68ac9 },
        { from: genAt, via: aroundCommunalWest, to: waterAt, gauge: '12/3', color: 0xcfa53d },
        { from: waterAt, to: kitchenAt, gauge: '12/3', color: 0x62a7c0 }, // kitchen stinger off the tank
      ];
      for (const c of cords) {
        if (!c.from || !c.to) continue; // a bake rev renamed an endpoint — skip, don't crash
        const pts = [c.from, ...(c.via || []).filter(Boolean), c.to];
        let len = 0;
        const segments = [];
        const m = mat(c.color, { emissiveIntensity: 0.5, roughness: 0.6 });
        for (let i = 0; i < pts.length - 1; i++) {
          const a = pts[i], b = pts[i + 1];
          const dx = b[0] - a[0], dz = b[1] - a[1], segLen = Math.hypot(dx, dz);
          if (segLen < 0.05) continue;
          len += segLen;
          segments.push({ a, dx, dz, len: segLen });
          const bar = new THREE.Mesh(new THREE.BoxGeometry(segLen, 0.035, 0.14), m);
          bar.position.set(a[0] + dx / 2, 0.05, a[1] + dz / 2);
          bar.rotation.y = Math.atan2(-dz, dx);
          g.add(bar);
        }
        // 1px overlay line so the run stays visible at overview zoom
        polyline(pts, c.color, 0.065, { opacity: 0.95 });
        const dot = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.12, 12), m);
        dot.position.set(c.to[0], 0.06, c.to[1]);
        g.add(dot);
        let walk = len * 0.55;
        let labelAt = pts[pts.length - 1];
        for (const s of segments) {
          if (walk <= s.len) {
            const t = walk / s.len;
            labelAt = [s.a[0] + s.dx * t, s.a[1] + s.dz * t];
            break;
          }
          walk -= s.len;
        }
        label(`${Math.round(len / FT)}′ · ${c.gauge}`,
          labelAt[0], 0.55, labelAt[1],
          0.42, '#' + c.color.toString(16).padStart(6, '0'));
      }
    }
    return g;
  }

  return { build };
})();
