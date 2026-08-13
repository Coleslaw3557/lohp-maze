/* Audio pool console. No build step, no framework: fetch state, redraw, save on change. */
'use strict';

let STATE = null;
let MODE = 'unattended';          // which selection set the page EDITS (not the server's live mode)
let liveMode = null;              // the show server's live sound mode, for the header pill
let playing = null;               // the button of the file currently auditioning
const openRooms = new Set();       // initial state is collapsed; preserve user-opened rooms across redraws
const player = document.getElementById('player');
const $ = (id) => document.getElementById(id);
const basename = (path) => (path || '').split('/').pop();

function el(tag, props, ...kids) {
  const node = Object.assign(document.createElement(tag), props || {});
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    node.append(kid.nodeType ? kid : document.createTextNode(kid));
  }
  return node;
}

function toast(message, kind = 'info') {
  const box = $('toast');
  box.innerHTML = '';
  box.append(el('span', { className: kind }, message));
  box.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => box.classList.remove('show'), 6000);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let body = {};
  try { body = await response.json(); } catch (e) { /* empty body */ }
  if (!response.ok) throw new Error(body.message || `${response.status} ${path}`);
  return body;
}

const secs = (d) => (d ? `${Math.floor(d / 60)}:${String(Math.round(d % 60)).padStart(2, '0')}` : '–');

/* --- auditioning ------------------------------------------------------- */

function audition(relPath, button) {
  if (playing === button) { player.pause(); return; }
  if (playing) playing.classList.remove('on');
  player.src = '/audio/' + relPath.split('/').map(encodeURIComponent).join('/');
  player.play().catch((e) => toast(`cannot play ${basename(relPath)}: ${e.message}`, 'err'));
  button.classList.add('on');
  playing = button;
}
player.addEventListener('ended', () => { if (playing) playing.classList.remove('on'); playing = null; });
player.addEventListener('pause', () => { if (playing) playing.classList.remove('on'); playing = null; });

/* --- saving ------------------------------------------------------------ */

async function savePool(pool, changes = {}) {
  const body = {
    files: pool.files.map((f) => ({ path: f.path, weight: f.weight })),
    volume: pool.volume,
    base: pool.loaded,  // what this page loaded — a stale tab's save gets a 409, not a silent clobber
    mode: MODE,         // attended edits land in the effects_attended override
    ...changes,
  };
  await api(`/api/pools/${encodeURIComponent(pool.name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

async function mutate(pool, changes, message) {
  try {
    await savePool(pool, changes);
    toast(message, 'ok');
    await load();
  } catch (e) {
    toast(e.message, 'err');
    // resync this tab to what's really on disk (a refused stale save, a file
    // retired elsewhere) instead of leaving the edit looking applied
    try { await load(); } catch (e2) { /* keep the original error toast */ }
  }
}

async function upload(fileList, pool, room) {
  const files = [...(fileList || [])];
  if (!files.length) return null;
  const form = new FormData();
  for (const file of files) form.append('file', file);
  if (pool) form.append('pool', pool);
  if (room) form.append('room', room);
  form.append('mode', MODE);
  toast(`uploading ${files.length} file${files.length > 1 ? 's' : ''}…`);
  try {
    const result = await api('/api/upload', { method: 'POST', body: form });
    let message = `uploaded ${result.saved.length} file(s)`
      + (pool ? ` into ${pool}${MODE === 'attended' ? ' (attended)' : ''}` : ' to the library');
    if (result.renamed.length) message += ` — renamed ${result.renamed.join(', ')} (basenames must be unique)`;
    if (result.skipped.length) message += ` — skipped ${result.skipped.join(', ')}`;
    toast(message, 'ok');
    await load();
    return result;
  } catch (e) {
    toast(e.message, 'err');
    return null;
  }
}

/* --- drag and drop ----------------------------------------------------- */

const isFileDrag = (e) => [...(e.dataTransfer ? e.dataTransfer.types : [])].includes('Files');

/* Dropped folders come through as entries, not files — someone handing over a
   prepared batch will drop the whole folder. Both lists have to be read out
   synchronously: the browser empties dataTransfer as soon as the handler yields. */
function filesFromDrop(dataTransfer) {
  const plain = [...dataTransfer.files];
  const entries = [...(dataTransfer.items || [])]
    .map((item) => (item.webkitGetAsEntry ? item.webkitGetAsEntry() : null))
    .filter(Boolean);
  if (!entries.some((entry) => entry.isDirectory)) return Promise.resolve(plain);

  const found = [];
  const walk = async (entry) => {
    if (entry.isFile) {
      found.push(await new Promise((resolve, reject) => entry.file(resolve, reject)));
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      for (;;) {
        const batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject));
        if (!batch.length) break;
        for (const child of batch) await walk(child);
      }
    }
  };
  return Promise.all(entries.map(walk)).then(() => found);
}

function dropZone(node, handle) {
  node.addEventListener('dragover', (e) => {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();        // the innermost zone wins: a pool, not the room card
    node.classList.add('drop');
  });
  node.addEventListener('dragleave', (e) => {
    if (!node.contains(e.relatedTarget)) node.classList.remove('drop');
  });
  node.addEventListener('drop', async (e) => {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    node.classList.remove('drop');
    document.body.classList.remove('dragging');
    handle(await filesFromDrop(e.dataTransfer));
  });
}

// Anything dropped outside a zone would otherwise make the browser navigate to
// the file. Catch it at the page level and treat it as a library drop.
document.addEventListener('dragover', (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault();
  document.body.classList.add('dragging');
});
document.addEventListener('dragleave', (e) => {
  if (!e.relatedTarget) document.body.classList.remove('dragging');
});
document.addEventListener('drop', async (e) => {
  if (!isFileDrag(e)) return;
  e.preventDefault();
  document.body.classList.remove('dragging');
  toLibrary(await filesFromDrop(e.dataTransfer));
});

/* --- the library inbox ------------------------------------------------- */

let recentUploads = [];       // paths from this session's library uploads

async function toLibrary(files) {
  const result = await upload(files, '', '');
  if (!result) return;
  recentUploads = [...result.saved, ...recentUploads.filter((p) => !result.saved.includes(p))];
  renderInbox();
}

dropZone($('dropzone'), toLibrary);
$('dropzone').onclick = () => $('inbox-input').click();
$('dropzone').onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') $('inbox-input').click(); };
$('inbox-input').onchange = (e) => { toLibrary(e.target.files); e.target.value = ''; };

function renderInbox() {
  const box = $('inbox-list');
  box.innerHTML = '';
  if (!recentUploads.length || !STATE) return;
  const known = new Map(STATE.library.map((f) => [f.path, f]));
  box.append(el('p', { className: 'fine' },
    `just uploaded — sitting in the library, assign them to a room action now or later:`));
  box.append(el('ul', null, recentUploads.map((path) => {
    const file = known.get(path);
    return file ? libraryRow(file) : null;
  }).filter(Boolean)));
}

/* --- rendering --------------------------------------------------------- */

function fileRow(pool, file) {
  const play = el('button', { className: 'play', title: 'audition' }, '▶');
  play.onclick = () => audition(file.path, play);

  const weight = el('input', {
    className: 'w', type: 'number', min: 1, max: 99, value: file.weight,
    title: 'relative chance of being picked',
  });
  weight.onchange = () => {
    file.weight = Math.max(1, Math.min(99, parseInt(weight.value, 10) || 1));
    mutate(pool, {}, `${file.name} weight ${file.weight}`);
  };

  const remove = el('button', { className: 'tiny danger', title: 'take out of this pool' }, '✕');
  remove.onclick = () => {
    pool.files = pool.files.filter((f) => f.path !== file.path);
    mutate(pool, {}, `${file.name} removed from ${pool.name}`);
  };

  return el('li', { className: file.exists ? '' : 'missing' },
    play,
    el('span', { className: 'name' }, file.name, file.exists ? null : ' — missing on disk'),
    el('span', { className: 'dur' }, secs(file.duration)),
    weight, remove);
}

function poolBlock(pool, action) {
  const block = el('details', {
    className: 'pool' + (pool.files.length ? ' has-sounds' : ' silent'),
    open: pool.files.length > 0,
  });

  const volume = el('input', {
    className: 'vol', type: 'number', min: 0, max: 1, step: 0.05, value: pool.volume,
    title: 'playback volume for this action',
  });
  volume.onclick = (e) => e.stopPropagation();
  volume.onkeydown = (e) => e.stopPropagation();
  volume.onchange = () => mutate(pool, { volume: parseFloat(volume.value) }, `${pool.name} volume ${volume.value}`);

  const head = el('summary', { className: 'head' },
    action ? el('span', { className: 'dot' }, action.kind) : el('span', { className: 'dot' }, 'no trigger'),
    action ? el('span', { className: 'trig' }, action.triggers.join(', ')) : null,
    action ? '→' : null,
    el('span', { className: 'eff' }, pool.name),
    action && action.shared
      ? el('span', { className: 'dot warn', title: 'the same pool answers other rooms too — edits hit all of them' },
          `shared ×${new Set(pool.used_by.map((u) => u.room)).size}`)
      : null,
    MODE === 'attended'
      ? (pool.attended_customized
          ? el('span', { className: 'dot attended-own',
              title: 'this pool has its own attended selection (effects_attended in audio_config.json)' },
              'attended override')
          : el('span', { className: 'dot',
              title: 'no attended override yet — plays the unattended files; the first edit here creates the override as a copy' },
              'tracking unattended'))
      : (pool.attended_customized
          ? el('span', { className: 'dot attended-own',
              title: 'this pool has a separate attended selection — switch Editing to Attended to change it' },
              'has attended variant')
          : null),
    action && action.route ? el('span', { className: 'fine' }, `(${action.route})`) : null,
    el('span', { className: 'spacer' }),
    el('span', { className: 'fine' }, `${pool.files.length} in pool · vol`),
    volume);

  if (action && action.room && action.testable !== false && STATE.server.online) {
    const test = el('button', { className: 'tiny secondary',
      title: "run the real effect in the real room (sounds follow the show server's LIVE mode — the header pill, not this Editing view)" }, 'Test in room');
    test.onclick = async (e) => {
      e.stopPropagation();
      try {
        await api('/api/play_in_room', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ effect: pool.name, room: action.room }),
        });
        toast(`fired ${pool.name} in ${action.room}`, 'ok');
      } catch (e) { toast(e.message, 'err'); }
    };
    head.append(test);
  }
  if (MODE === 'attended' && pool.attended_customized) {
    const revert = el('button', { className: 'tiny secondary',
      title: 'drop the attended override — this pool tracks the unattended selection again' }, 'Revert');
    revert.onclick = async (e) => {
      e.stopPropagation();
      try {
        await api(`/api/pools/${encodeURIComponent(pool.name)}/revert`, { method: 'POST' });
        toast(`${pool.name} tracks unattended again`, 'ok');
        await load();
      } catch (err) { toast(err.message, 'err'); }
    };
    head.append(revert);
  }
  block.append(head);

  if (pool.comment) block.append(el('p', { className: 'comment' }, pool.comment));

  if (pool.files.length) {
    block.append(el('ul', { className: 'files' }, pool.files.map((f) => fileRow(pool, f))));
  } else {
    block.append(el('div', { className: 'empty-note' }, 'no sounds — this action runs silent'));
  }

  /* add from the library */
  const picker = el('select', null, el('option', { value: '' }, 'Add from library…'));
  const inPool = new Set(pool.files.map((f) => f.path));
  for (const file of STATE.library) {
    if (inPool.has(file.path)) continue;
    picker.append(el('option', { value: file.path },
      `${file.name}${file.pools.length ? '  (in ' + file.pools.join(', ') + ')' : '  (unused)'}`));
  }
  picker.onchange = () => {
    if (!picker.value) return;
    pool.files.push({ path: picker.value, weight: 1 });
    mutate(pool, {}, `added ${picker.value.split('/').pop()} to ${pool.name}`);
  };

  const chooser = el('input', { type: 'file', multiple: true, accept: 'audio/*', hidden: true });
  chooser.onchange = () => upload(chooser.files, pool.name, action && action.room);
  const uploadBtn = el('button', { className: 'tiny' }, 'Upload…');
  uploadBtn.onclick = () => chooser.click();

  block.append(el('div', { className: 'foot' }, uploadBtn, picker, chooser,
    el('span', { className: 'fine' }, 'or drop files here')));

  dropZone(block, (files) => upload(files, pool.name, action && action.room));
  return block;
}

function askWhichAction(card, room, files) {
  card.querySelector('.ask')?.remove();
  const ask = el('div', { className: 'ask' },
    el('span', null, `${files.length} file${files.length > 1 ? 's' : ''} → which action in ${room.room}?`));
  for (const action of room.actions) {
    const pick = el('button', { className: 'tiny' }, `${action.kind} · ${action.pool.name}`);
    pick.onclick = () => { ask.remove(); upload(files, action.pool.name, room.room); };
    ask.append(pick);
  }
  const lib = el('button', { className: 'tiny secondary' }, 'library only');
  lib.onclick = () => { ask.remove(); toLibrary(files); };
  const cancel = el('button', { className: 'tiny secondary' }, 'cancel');
  cancel.onclick = () => ask.remove();
  ask.append(lib, cancel);
  card.insertBefore(ask, card.querySelector('.pool'));
}

function bikeAnswerEditor(room) {
  const bike = room.games && room.games.bike;
  if (!bike || !bike.questions || !bike.questions.length) return null;

  const panel = el('div', { className: 'game-key bike-key' },
    el('span', { className: 'game-title' }, 'Answer key'));

  for (const question of bike.questions) {
    const group = el('div', { className: 'answer-row' },
      el('span', { className: 'q' }, `Q${question.question}`));
    for (const option of question.options) {
      const button = el('button', {
        className: 'tiny' + (option.value === question.correct ? ' selected' : ''),
        title: option.trigger,
      }, option.label);
      button.onclick = async () => {
        try {
          await api('/api/games/bike', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers: { [question.question]: option.value } }),
          });
          toast(`Bike Q${question.question}: ${option.label} is right`, 'ok');
          await load();
        } catch (e) { toast(e.message, 'err'); }
      };
      group.append(button);
    }
    panel.append(group);
  }
  return panel;
}

function render() {
  const dot = $('server-dot');
  dot.className = 'dot ' + (STATE.server.online ? 'ok' : 'err');
  dot.textContent = STATE.server.online ? 'server online' : 'server offline';
  dot.title = STATE.server.url;
  refreshLiveMode();

  const global = $('global-actions');
  global.innerHTML = '';
  if (STATE.global_actions && STATE.global_actions.length) {
    const card = el('details', { className: 'room global' },
      el('summary', null, 'Maze-wide',
        el('span', { className: 'count' },
          `${STATE.global_actions.length} global action${STATE.global_actions.length > 1 ? 's' : ''}`)));
    for (const action of STATE.global_actions) card.append(poolBlock(action.pool, action));
    dropZone(card, (files) => {
      if (STATE.global_actions.length === 1) upload(files, STATE.global_actions[0].pool.name, '');
      else toLibrary(files);
    });
    global.append(card);
  }

  const rooms = $('rooms');
  rooms.innerHTML = '';
  for (const room of STATE.rooms) {
    const card = el('details', { className: 'room' + (room.actions.length ? '' : ' empty') },
      el('summary', null, room.room,
        el('span', { className: 'count' },
          room.actions.length ? `${room.actions.length} action${room.actions.length > 1 ? 's' : ''}`
                              : 'no sensor action yet')));
    card.open = openRooms.has(room.room);
    card.ontoggle = () => {
      if (card.open) openRooms.add(room.room);
      else openRooms.delete(room.room);
    };
    const editor = bikeAnswerEditor(room);
    if (editor) card.append(editor);
    for (const action of room.actions) card.append(poolBlock(action.pool, { ...action, room: room.room }));
    if (!room.actions.length) {
      card.append(el('div', { className: 'none' },
        'Nothing in triggers.json fires here yet — add the trigger first and it shows up with a pool to fill.'));
    }
    // Dropping on the card itself (not on one action) still works: straight in
    // if the room has one action, otherwise ask which.
    dropZone(card, (files) => {
      if (room.actions.length === 1) upload(files, room.actions[0].pool.name, room.room);
      else if (!room.actions.length) toLibrary(files);
      else askWhichAction(card, room, files);
    });
    rooms.append(card);
  }

  const orphans = $('orphans');
  orphans.innerHTML = '';
  $('orphans-title').textContent = `Pools with no trigger (${STATE.orphan_pools.length})`;
  for (const pool of STATE.orphan_pools) orphans.append(poolBlock(pool, null));

  renderLibrary();
  renderInbox();
}

function libraryRow(file) {
  const play = el('button', { className: 'play', title: 'audition' }, '▶');
  play.onclick = () => audition(file.path, play);

  const addToPool = async (poolName, fileName) => {
    if (!poolName) return;
    const pool = findPool(poolName);
    if (!pool) return;
    pool.files.push({ path: file.path, weight: 1 });
    await mutate(pool, {}, `added ${fileName} to ${pool.name}`);
  };

  const picker = el('select', null, el('option', { value: '' }, 'Add to…'));
  for (const name of STATE.pool_names) {
    if (!file.pools.includes(name)) picker.append(el('option', { value: name }, name));
  }
  picker.onchange = () => addToPool(picker.value, file.name);

  const bgPicker = el('select', { className: 'bg-add' },
    el('option', { value: '' }, 'Add to bed…'));
  for (const bg of STATE.background_pools || []) {
    if (!file.pools.includes(bg.name)) {
      bgPicker.append(el('option', { value: bg.name }, bg.label || `${bg.room} bed`));
    }
  }
  bgPicker.onchange = () => addToPool(bgPicker.value, file.name);

  const retire = el('button', { className: 'tiny danger', title: 'remove from every pool and move to audio_files/rejected/' }, 'Retire');
  retire.onclick = async () => {
    if (!confirm(`Retire ${file.name}?\n\nIt leaves every pool and moves to audio_files/rejected/ — not deleted.`)) return;
    try {
      const result = await api('/api/retire', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: file.path }),
      });
      toast(`retired ${file.name}${result.removed_from.length ? ' from ' + result.removed_from.join(', ') : ''}`, 'ok');
      recentUploads = recentUploads.filter((p) => p !== file.path);
      await load();
    } catch (e) { toast(e.message, 'err'); }
  };

  return el('li', null, play,
    el('span', { className: 'name' }, file.name),
    el('span', { className: 'dur' }, secs(file.duration)),
    el('span', { className: 'pools' + (file.pools.length ? '' : ' none') },
      file.pools.length ? file.pools.join(', ') : 'in no pool'),
    picker, bgPicker, retire);
}

function renderLibrary() {
  const box = $('library');
  const term = $('lib-search').value.trim().toLowerCase();
  const unusedOnly = $('lib-unused').checked;
  $('library-title').textContent =
    `Sound library (${STATE.library.length} files, ${STATE.unused_count} in no pool)`;

  const list = el('ul');
  for (const file of STATE.library) {
    if (term && !file.path.toLowerCase().includes(term)) continue;
    if (unusedOnly && file.pools.length) continue;
    list.append(libraryRow(file));
  }
  box.innerHTML = '';
  box.append(list);
}

function findPool(name) {
  for (const action of STATE.global_actions || []) {
    if (action.pool.name === name) return action.pool;
  }
  for (const room of STATE.rooms) {
    for (const action of room.actions) if (action.pool.name === name) return action.pool;
  }
  return STATE.orphan_pools.find((p) => p.name === name) || null;
}

/* --- attended / unattended ---------------------------------------------- */

function setEditMode(mode) {
  if (mode === MODE) return;
  MODE = mode;
  $('mode-unattended').classList.toggle('selected', mode === 'unattended');
  $('mode-attended').classList.toggle('selected', mode === 'attended');
  document.body.classList.toggle('attended', mode === 'attended');
  load().catch((e) => toast(`cannot load state: ${e.message}`, 'err'));
}
$('mode-unattended').onclick = () => setEditMode('unattended');
$('mode-attended').onclick = () => setEditMode('attended');

// The show server's LIVE mode — separate from the Editing selector above.
// Auditions through 'Test in room' play under this; the pill flips it.
async function refreshLiveMode() {
  const pill = $('live-mode');
  try {
    const state = await api('/api/server_sound_mode');
    liveMode = state.mode;
    pill.className = 'dot live ' + (liveMode === 'attended' ? 'warn' : 'ok');
    pill.textContent = `live: ${liveMode}`;
  } catch (e) {
    liveMode = null;
    pill.className = 'dot live';
    pill.textContent = 'live ?';
  }
}

$('live-mode').onclick = async () => {
  if (!liveMode) { refreshLiveMode(); return; }
  const want = liveMode === 'attended' ? 'unattended' : 'attended';
  try {
    await api('/api/server_sound_mode', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: want }),
    });
    toast(`the maze now plays ${want} sounds`, 'ok');
  } catch (e) { toast(e.message, 'err'); }
  refreshLiveMode();
};

/* --- header actions ---------------------------------------------------- */

$('apply-btn').onclick = async () => {
  const cues = $('apply-cues').checked;
  toast(cues ? 'reloading the server and rebuilding node cues…' : 'reloading the server…');
  try {
    const { result } = await api('/api/apply', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cues }),
    });
    const parts = [];
    let worst = 'ok';
    for (const [what, outcome] of Object.entries(result)) {
      if (!outcome) continue;
      const [status, message] = outcome;
      if (status !== 'ok') worst = 'err';
      parts.push(`${what}: ${status}${message ? ' — ' + message : ''}`);
    }
    toast(parts.join('  |  '), worst === 'ok' ? 'ok' : 'err');
    await load();
  } catch (e) { toast(e.message, 'err'); }
};

$('newpool-btn').onclick = async () => {
  const name = $('newpool-name').value.trim();
  if (!name) return;
  try {
    await api('/api/pools', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    $('newpool-name').value = '';
    toast(`created empty pool ${name} — it shows under a room once a trigger fires it`, 'ok');
    await load();
  } catch (e) { toast(e.message, 'err'); }
};

$('lib-upload-btn').onclick = () => $('lib-upload').click();
$('lib-upload').onchange = (e) => { toLibrary(e.target.files); e.target.value = ''; };
dropZone($('library-wrap'), toLibrary);
$('lib-search').oninput = renderLibrary;
$('lib-unused').onchange = renderLibrary;

function stampLoadedPools() {
  // Remember each pool's file list AS LOADED: savePool sends it as `base` so
  // the server can refuse a save built on a view another tab has outdated.
  const pools = [...(STATE.orphan_pools || [])];
  for (const action of STATE.global_actions || []) if (action.pool) pools.push(action.pool);
  for (const room of STATE.rooms || []) {
    for (const action of room.actions || []) if (action.pool) pools.push(action.pool);
  }
  for (const pool of pools) pool.loaded = pool.files.map((f) => f.path);
}

async function load() {
  STATE = await api(`/api/state?mode=${MODE}`);
  stampLoadedPools();
  render();
}

load().catch((e) => toast(`cannot load state: ${e.message}`, 'err'));
