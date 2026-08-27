/* Shakha dashboard — vanilla JS, no build step.
   Everything here is a thin skin over the API; the server does the real git. */

const api = {
  async get(path) {
    const r = await fetch(path);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    return r.json();
  },
};

const state = {
  catalog: null,
  progress: {},
  current: null,      // full scenario object
  repo: null,         // last repo state
  stepDone: {},       // step index -> true
  history: [],        // terminal history
  historyAt: 0,
  level: '',          // catalog filter: level
  unsolvedOnly: false,
  view: 'path',       // 'path' (the curriculum) or 'category'
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/* ------------------------------------------------------------- panes */

/* On a phone the three panes take turns on one screen, driven by the tab bar.
   On a desktop they are all visible at once and these calls do nothing. */

const isNarrow = () => window.matchMedia('(max-width: 900px)').matches;

function setPane(name) {
  document.body.dataset.pane = name;
  document.querySelectorAll('.tabbtn')
    .forEach((b) => b.classList.toggle('active', b.dataset.pane === name));
  if (name === 'repo') flagRepo(false);
}

/* a dot on the Repo tab when the repository moved while you were looking elsewhere */
function flagRepo(on) {
  const btn = document.querySelector('.tabbtn[data-pane="repo"]');
  if (!btn) return;
  const dot = btn.querySelector('.flag');
  if (on && !dot) btn.appendChild(el('span', 'flag'));
  if (!on && dot) dot.remove();
}

document.querySelectorAll('.tabbtn').forEach((btn) => {
  btn.addEventListener('click', () => setPane(btn.dataset.pane));
});

/* ------------------------------------------------------------- catalog */

async function loadCatalog() {
  const data = await api.get('/api/catalog');
  state.catalog = data;
  state.progress = data.progress || {};
  $('#catalog-total').textContent = `(${data.total})`;
  renderCatalog();
  renderProgressCount();
}

function renderProgressCount() {
  const total = state.catalog ? state.catalog.total : 0;
  const solved = Object.values(state.progress).filter((p) => p.solved).length;
  $('#progress-count').textContent = `${solved}/${total}`;
  const bar = $('#progress-bar');
  if (bar) bar.style.width = total ? `${Math.round((solved / total) * 100)}%` : '0%';
}

function matchesFilters(s, query) {
  if (state.level && s.level !== state.level) return false;
  if (state.unsolvedOnly && (state.progress[s.id] || {}).solved) return false;
  if (!query) return true;
  return s.title.toLowerCase().includes(query)
    || s.id.toLowerCase().includes(query)
    || (s.summary || '').toLowerCase().includes(query);
}

function scenarioRow(item) {
  const prog = state.progress[item.id] || {};
  const row = el('div', 'cat-item');
  if (prog.solved) row.classList.add('solved');
  else if (prog.started) row.classList.add('started');
  if (state.current && state.current.id === item.id) row.classList.add('active');
  row.appendChild(el('span', 'tick', prog.solved ? '✔' : (prog.started ? '◐' : '○')));
  row.appendChild(el('span', 'title', item.title));
  row.onclick = () => openScenario(item.id);
  return row;
}

function renderGroup(list, label, items, openWhen) {
  const group = el('div', 'cat-group');
  if (openWhen) group.classList.add('open');
  const head = el('div', 'cat-head');
  head.appendChild(el('span', null, label));
  const solved = items.filter((i) => (state.progress[i.id] || {}).solved).length;
  head.appendChild(el('span', 'count', `${solved}/${items.length}`));
  head.onclick = () => group.classList.toggle('open');
  group.appendChild(head);

  const box = el('div', 'cat-items');
  items.forEach((item) => box.appendChild(scenarioRow(item)));
  group.appendChild(box);
  list.appendChild(group);
  return group;
}

function renderPath() {
  const query = $('#search').value.trim().toLowerCase();
  const list = $('#catalog-list');
  list.innerHTML = '';

  const curriculum = state.catalog.curriculum;
  if (!curriculum || !curriculum.stages.length) {
    list.appendChild(el('p', 'muted pad', 'No learning path is defined.'));
    return;
  }

  let firstUnfinished = true;
  curriculum.stages.forEach((stage) => {
    const items = stage.scenarios.filter((s) => matchesFilters(s, query));
    if (!items.length) return;

    const solved = stage.scenarios.filter((s) => (state.progress[s.id] || {}).solved).length;
    const complete = solved === stage.scenarios.length;
    /* open the first stage that still has work in it */
    const openWhen = !!query || (!complete && firstUnfinished)
      || (state.current && items.some((i) => i.id === state.current.id));
    if (!complete && firstUnfinished) firstUnfinished = false;

    const group = renderGroup(list, stage.title, items, openWhen);
    group.classList.add('stage');
    if (complete) group.classList.add('stage-done');

    const bar = el('div', 'stage-track');
    const fill = el('div', 'stage-fill');
    fill.style.width = `${Math.round((solved / stage.scenarios.length) * 100)}%`;
    bar.appendChild(fill);
    group.querySelector('.cat-head').after(bar);

    if (stage.summary) {
      const note = el('div', 'stage-summary', stage.summary);
      bar.after(note);
    }
  });

  if (!list.children.length) {
    list.appendChild(el('p', 'muted pad', 'Nothing matches that search and filter.'));
  }
}

function renderCatalog() {
  if (state.view === 'path') return renderPath();

  const query = $('#search').value.trim().toLowerCase();
  const list = $('#catalog-list');
  list.innerHTML = '';

  state.catalog.categories.forEach((cat) => {
    const items = cat.scenarios.filter((s) => matchesFilters(s, query));
    if (!items.length) return;

    const group = el('div', 'cat-group');
    if (query || (state.current && items.some((i) => i.id === state.current.id))) {
      group.classList.add('open');
    }

    const head = el('div', 'cat-head');
    head.appendChild(el('span', null, cat.label));
    const solved = items.filter((i) => (state.progress[i.id] || {}).solved).length;
    head.appendChild(el('span', 'count', `${solved}/${items.length}`));
    head.onclick = () => group.classList.toggle('open');
    group.appendChild(head);

    const box = el('div', 'cat-items');
    items.forEach((item) => {
      const prog = state.progress[item.id] || {};
      const row = el('div', 'cat-item');
      if (prog.solved) row.classList.add('solved');
      else if (prog.started) row.classList.add('started');
      if (state.current && state.current.id === item.id) row.classList.add('active');
      row.appendChild(el('span', 'tick', prog.solved ? '✔' : (prog.started ? '◐' : '○')));
      row.appendChild(el('span', 'title', item.title));
      row.onclick = () => openScenario(item.id);
      box.appendChild(row);
    });
    group.appendChild(box);
    list.appendChild(group);
  });

  if (!list.children.length) {
    const why = state.unsolvedOnly && !$('#search').value.trim() && !state.level
      ? 'Everything is solved. That is the whole catalogue.'
      : 'Nothing matches that search and filter.';
    list.appendChild(el('p', 'muted pad', why));
  }
}

/* ------------------------------------------------------------- navigation */

function allScenarios() {
  if (!state.catalog) return [];
  /* In path view, "next" should follow the curriculum's order, not the catalogue's. */
  if (state.view === 'path' && state.catalog.curriculum) {
    const ordered = state.catalog.curriculum.stages.flatMap((s) => s.scenarios);
    if (ordered.length) return ordered;
  }
  return state.catalog.categories.flatMap((c) => c.scenarios);
}

function openNextUnsolved() {
  const all = allScenarios();
  const start = state.current ? all.findIndex((s) => s.id === state.current.id) + 1 : 0;
  const ordered = all.slice(start).concat(all.slice(0, start));
  const next = ordered.find((s) => !(state.progress[s.id] || {}).solved);
  if (next) openScenario(next.id);
  else termLine('# every scenario is solved', 't-out');
}

/* ------------------------------------------------------------- cheatsheet */

async function showCheatsheet() {
  const solved = allScenarios().filter((s) => (state.progress[s.id] || {}).solved);

  const overlay = el('div', 'overlay');
  const box = el('div', 'editor cheatsheet');
  const head = el('div', 'editor-head');
  head.appendChild(el('span', null, `Cheatsheet — ${solved.length} solved scenario${solved.length === 1 ? '' : 's'}`));
  const close = el('button', 'ghost', 'Close');
  close.onclick = () => overlay.remove();
  head.appendChild(close);
  box.appendChild(head);

  const body = el('div', 'cheatsheet-body');
  if (!solved.length) {
    body.appendChild(el('p', 'muted',
      'Solve a scenario and its commands collect here — a reference built from what you have actually done.'));
  }

  /* Fetch each solved scenario so we have its cheatsheet rows. */
  for (const item of solved) {
    /* sequential: the catalogue is small and this keeps the API calls tidy */
    const full = await api.get(`/api/scenario/${item.id}`); // eslint-disable-line no-await-in-loop
    if (!(full.cheatsheet || []).length) continue;
    const section = el('div', 'cheat-section');
    section.appendChild(el('h3', null, full.title));
    const table = el('table', 'cheat');
    full.cheatsheet.forEach(([cmd, what]) => {
      const tr = el('tr');
      tr.appendChild(el('td', null, cmd));
      tr.appendChild(el('td', null, what));
      table.appendChild(tr);
    });
    section.appendChild(table);
    body.appendChild(section);
  }

  box.appendChild(body);

  const foot = el('div', 'editor-foot');
  foot.appendChild(el('span', 'muted', 'Built from the scenarios you have solved. Print or copy as you like.'));
  const copy = el('button', null, 'Copy as text');
  copy.onclick = async () => {
    const lines = [];
    body.querySelectorAll('.cheat-section').forEach((sec) => {
      lines.push(`## ${sec.querySelector('h3').textContent}`);
      sec.querySelectorAll('tr').forEach((tr) => {
        const tds = tr.querySelectorAll('td');
        lines.push(`  ${tds[0].textContent.padEnd(44)} ${tds[1].textContent}`);
      });
      lines.push('');
    });
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      copy.textContent = 'Copied';
    } catch (err) {
      copy.textContent = 'Copy blocked by the browser';
    }
  };
  foot.appendChild(copy);
  box.appendChild(foot);

  overlay.appendChild(box);
  overlay.onclick = (ev) => { if (ev.target === overlay) overlay.remove(); };
  document.body.appendChild(overlay);
}

/* ------------------------------------------------------------- lesson */

async function openScenario(id) {
  const scenario = await api.get(`/api/scenario/${id}`);
  state.current = scenario;
  state.stepDone = {};
  renderCatalog();
  renderLesson();
  if (isNarrow()) setPane('lesson');
  $('#term-in').disabled = false;
  clearTerminal();
  if (scenario.ready) {
    refreshState();
  } else {
    $('#repo-body').innerHTML = '<p class="muted pad">Press <b>Start scenario</b> to build the sandbox repository.</p>';
  }
}

function renderLesson() {
  const s = state.current;
  const pane = $('#lesson');
  pane.innerHTML = '';
  const box = el('div', 'lesson-inner');

  box.appendChild(el('h1', null, s.title));

  const chips = el('div', 'chips');
  chips.appendChild(el('span', `chip ${s.level}`, s.level));
  chips.appendChild(el('span', 'chip', `~${s.duration_min} min`));
  chips.appendChild(el('span', 'chip', `${(s.steps || []).length} steps`));
  (s.concepts || []).forEach((c) => chips.appendChild(el('span', 'chip', c)));
  box.appendChild(chips);

  if (s.summary) box.appendChild(el('p', 'summary', s.summary));

  if (s.mental_model) {
    const callout = el('div', 'callout');
    callout.appendChild(el('span', 'label', 'Mental model'));
    callout.appendChild(el('div', null, s.mental_model));
    box.appendChild(callout);
  }
  if (s.danger) {
    const callout = el('div', 'callout danger');
    callout.appendChild(el('span', 'label', 'Danger'));
    callout.appendChild(el('div', null, s.danger));
    box.appendChild(callout);
  }

  const bar = el('div', 'toolbar');
  const startBtn = el('button', 'primary', s.ready ? 'Rebuild sandbox' : 'Start scenario');
  startBtn.onclick = () => startScenario(s.ready ? 'reset' : 'start');
  const runAll = el('button', null, 'Run all steps');
  runAll.onclick = runAllSteps;
  const verifyBtn = el('button', null, 'Check my work');
  verifyBtn.onclick = verifyScenario;
  bar.append(startBtn, runAll, verifyBtn);
  box.appendChild(bar);

  if (s.explain) {
    const md = el('div', 'md');
    md.innerHTML = markdown(s.explain);
    box.appendChild(md);
  }

  box.appendChild(el('h2', null, 'Walk it through'));
  const steps = el('div', null);
  steps.id = 'steps';
  (s.steps || []).forEach((step, i) => steps.appendChild(renderStep(step, i)));
  box.appendChild(steps);

  box.appendChild(el('h2', null, 'Check my work'));
  const verify = el('div', 'verify-panel');
  verify.id = 'verify';
  verify.appendChild(el('p', 'muted',
    'These checks read the real repository. Solve it with the buttons above or by typing your own commands in the terminal — either way counts.'));
  box.appendChild(verify);

  if ((s.pitfalls || []).length) {
    box.appendChild(el('h2', null, 'Where people get burned'));
    const ul = el('ul', 'plain');
    s.pitfalls.forEach((p) => {
      const li = el('li');
      li.innerHTML = inlineMd(p);
      ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  if ((s.cheatsheet || []).length) {
    box.appendChild(el('h2', null, 'Cheatsheet'));
    const table = el('table', 'cheat');
    s.cheatsheet.forEach(([cmd, what]) => {
      const tr = el('tr');
      tr.appendChild(el('td', null, cmd));
      tr.appendChild(el('td', null, what));
      table.appendChild(tr);
    });
    box.appendChild(table);
  }

  pane.appendChild(box);
}

function renderStep(step, i) {
  const node = el('div', 'step');
  node.dataset.index = i;
  if (state.stepDone[i]) node.classList.add('done');
  if (i === 0) node.classList.add('open');

  const head = el('div', 'step-head');
  head.appendChild(el('span', 'step-num', state.stepDone[i] ? '✔' : String(i + 1)));
  head.appendChild(el('span', 'step-title', step.title));
  head.onclick = () => node.classList.toggle('open');
  node.appendChild(head);

  const body = el('div', 'step-body');
  if (step.why) {
    const why = el('p', 'step-why');
    why.innerHTML = inlineMd(step.why);
    body.appendChild(why);
  }

  const commands = step.commands || (step.run ? [step.run] : []);
  if (commands.length) {
    const row = el('div', 'cmd-row');
    commands.forEach((c) => row.appendChild(el('code', 'cmd', c)));
    const btn = el('button', 'primary', 'Run');
    btn.onclick = (ev) => { ev.stopPropagation(); runStep(i); };
    row.appendChild(btn);
    body.appendChild(row);
  }
  if (step.expect) body.appendChild(el('p', 'step-expect', `Expect: ${step.expect}`));

  node.appendChild(body);
  return node;
}

/* ------------------------------------------------------------- actions */

async function startScenario(action) {
  const s = state.current;
  termLine(`# ${action === 'reset' ? 'rebuilding' : 'building'} sandbox for ${s.id}`, 't-out');
  const res = await api.post(`/api/scenario/${s.id}/${action}`);
  if (res.error) return termLine(res.error, 't-err');
  state.stepDone = {};
  s.ready = true;
  applyState(res.state);
  renderLesson();
  markStarted(s.id);
  termLine('sandbox ready', 't-out');
}

async function runStep(index) {
  const s = state.current;
  const res = await api.post(`/api/scenario/${s.id}/run`, { step: index });
  if (res.error) return termLine(res.error, 't-err');
  (res.results || []).forEach(printResult);
  applyState(res.state);
  const graded = res.step_grade;
  if (!graded || graded.solved) {
    state.stepDone[index] = true;
    const node = document.querySelector(`.step[data-index="${index}"]`);
    if (node) {
      node.classList.add('done');
      node.querySelector('.step-num').textContent = '✔';
      const next = document.querySelector(`.step[data-index="${index + 1}"]`);
      if (next) { node.classList.remove('open'); next.classList.add('open'); }
    }
  } else if (graded) {
    graded.checks.filter((c) => !c.ok).forEach((c) => termLine(`! ${c.label}: ${c.reason}`, 't-err'));
  }
  markStarted(s.id);
}

async function runAllSteps() {
  const total = (state.current.steps || []).length;
  for (let i = 0; i < total; i += 1) {
    /* sequential on purpose: each command depends on the last one's repo state */
    await runStep(i); // eslint-disable-line no-await-in-loop
  }
  verifyScenario();
}

async function verifyScenario() {
  const s = state.current;
  const report = await api.post(`/api/scenario/${s.id}/verify`);
  if (report.error) return termLine(report.error, 't-err');
  const panel = $('#verify');
  panel.innerHTML = '';
  panel.classList.toggle('solved', !!report.solved);

  const title = el('p', null);
  title.innerHTML = report.solved
    ? `<b style="color:var(--green)">Solved.</b> ${report.passed}/${report.total} checks pass against the real repository.`
    : `<b style="color:var(--amber)">${report.passed}/${report.total} checks pass.</b> Keep going — the failing ones tell you what git is still missing.`;
  panel.appendChild(title);

  report.checks.forEach((c) => {
    const row = el('div', `check ${c.ok ? 'ok' : 'bad'}`);
    row.appendChild(el('span', 'mark', c.ok ? '✔' : '✘'));
    const body = el('div');
    body.appendChild(el('span', null, c.label));
    if (!c.ok && c.reason) body.appendChild(el('span', 'reason', c.reason));
    if (!c.ok && c.hint) body.appendChild(el('span', 'hint', `hint: ${c.hint}`));
    row.appendChild(body);
    panel.appendChild(row);
  });

  if (report.state) applyState(report.state);
  if (report.solved) {
    state.progress[s.id] = Object.assign({}, state.progress[s.id], { solved: true, started: true });
    renderCatalog();
    renderProgressCount();
  }
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function markStarted(id) {
  if (!state.progress[id] || !state.progress[id].started) {
    state.progress[id] = Object.assign({}, state.progress[id], { started: true });
    renderCatalog();
    renderProgressCount();
  }
}

async function refreshState() {
  const res = await api.get(`/api/scenario/${state.current.id}/state`);
  applyState(res.state);
}

/* ------------------------------------------------------------- terminal */

function clearTerminal() { $('#term-out').innerHTML = ''; }

function termLine(text, cls) {
  const out = $('#term-out');
  const line = el('div', cls || 't-out', text);
  out.appendChild(line);
  out.scrollTop = out.scrollHeight;
}

function printResult(r) {
  termLine(r.cmd, 't-cmd');
  if (r.stdout) termLine(r.stdout, 't-out');
  if (r.stderr) termLine(r.stderr, r.code === 0 ? 't-out' : 't-err');
}

async function submitCommand(command) {
  if (!state.current) return;
  state.history.push(command);
  state.historyAt = state.history.length;
  const res = await api.post(`/api/scenario/${state.current.id}/run`, {
    command, cwd: $('#term-cwd').value,
  });
  if (res.error) return termLine(res.error, 't-err');
  (res.results || []).forEach(printResult);
  applyState(res.state);
  markStarted(state.current.id);
}

/* ------------------------------------------------------------- repo view */

function applyState(repoState) {
  state.repo = repoState;
  if (isNarrow() && document.body.dataset.pane !== 'repo') flagRepo(true);
  const body = $('#repo-body');
  body.innerHTML = '';

  if (!repoState || !repoState.initialised) {
    body.appendChild(el('p', 'muted pad', 'No git repository here yet — that is the point of the first step.'));
    return;
  }

  body.appendChild(headSection(repoState));
  body.appendChild(areasSection(repoState.status));
  body.appendChild(filesSection(repoState));
  body.appendChild(graphSection(repoState));
  body.appendChild(branchSection(repoState));
  if (repoState.stashes && repoState.stashes.length) body.appendChild(stashSection(repoState.stashes));
  body.appendChild(reflogSection(repoState.reflog || []));
}

function section(title) {
  const node = el('div', 'repo-section');
  node.appendChild(el('h3', null, title));
  return node;
}

function headSection(s) {
  const node = section('HEAD');
  const line = el('div', 'headline');
  if (s.head.detached) {
    line.innerHTML = `detached at <span class="sha">${esc(s.head.sha)}</span>`;
    line.appendChild(el('span', 'badge', 'DETACHED HEAD'));
  } else if (s.head.branch) {
    line.innerHTML = `on <span class="b">${esc(s.head.branch)}</span>`
      + (s.head.sha ? ` at <span class="sha">${esc(s.head.sha)}</span>` : ' <i>(no commits yet)</i>');
  } else {
    line.textContent = 'unborn branch';
  }
  node.appendChild(line);
  if (s.operation) {
    const badge = el('span', 'badge warn', s.operation.toUpperCase() + ' IN PROGRESS');
    node.appendChild(badge);
  }
  return node;
}

function areasSection(status) {
  const node = section('Working tree · index · untracked');
  const grid = el('div', 'areas');
  const build = (cls, name, items) => {
    const area = el('div', `area ${cls}`);
    area.appendChild(el('div', 'name', name));
    if (!items.length) area.appendChild(el('div', 'none', 'empty'));
    items.slice(0, 8).forEach((f) => area.appendChild(el('div', 'f', typeof f === 'string' ? f : `${f.code} ${f.path}`)));
    return area;
  };
  grid.appendChild(build('staged', 'staged', status.staged));
  grid.appendChild(build('unstaged', 'modified', status.unstaged));
  grid.appendChild(build('untracked', 'untracked', status.untracked));
  node.appendChild(grid);
  if (status.conflicted.length) {
    const warn = el('div', 'badge', `${status.conflicted.length} conflicted: ${status.conflicted.join(', ')}`);
    node.appendChild(warn);
  }
  return node;
}

function filesSection(s) {
  const node = section('Working tree files — click to edit');
  const files = s.files || [];
  if (!files.length) {
    node.appendChild(el('p', 'muted', 'The folder is empty.'));
    return node;
  }
  const conflicted = new Set((s.status && s.status.conflicted) || []);
  const list = el('div', 'filelist');
  files.forEach((f) => {
    const row = el('button', `filechip${conflicted.has(f) ? ' conflict' : ''}`, f);
    row.onclick = () => openEditor(f);
    list.appendChild(row);
  });
  node.appendChild(list);
  return node;
}

/* ------------------------------------------------------------- editor */

async function openEditor(path) {
  const cwd = $('#term-cwd').value;
  const res = await api.get(`/api/scenario/${state.current.id}/file`
    + `?path=${encodeURIComponent(path)}&cwd=${encodeURIComponent(cwd)}`);
  if (res.error) return termLine(res.error, 't-err');

  const overlay = el('div', 'overlay');
  const box = el('div', 'editor');
  const head = el('div', 'editor-head');
  head.appendChild(el('span', null, `${cwd}/${path}`));
  const close = el('button', 'ghost', 'Close');
  close.onclick = () => overlay.remove();
  head.appendChild(close);
  box.appendChild(head);

  const area = el('textarea', 'editor-area');
  area.value = res.binary ? '(binary file)' : res.content;
  area.spellcheck = false;
  area.disabled = !!res.binary;
  box.appendChild(area);

  const foot = el('div', 'editor-foot');
  foot.appendChild(el('span', 'muted',
    'Saving writes the real file on disk — exactly like editing it in your editor.'));
  const save = el('button', 'primary', 'Save file');
  save.onclick = async () => {
    const out = await api.post(`/api/scenario/${state.current.id}/file`,
      { path, content: area.value, cwd });
    if (out.error) return termLine(out.error, 't-err');
    termLine(`# saved ${path}`, 't-out');
    applyState(out.state);
    overlay.remove();
  };
  foot.appendChild(save);
  box.appendChild(foot);

  overlay.appendChild(box);
  overlay.onclick = (ev) => { if (ev.target === overlay) overlay.remove(); };
  document.body.appendChild(overlay);
  area.focus();
}

/* Lane assignment: walk commits in git's --date-order and keep a list of
   "lanes", each waiting for a specific sha. Same idea as git log --graph. */
function layoutGraph(commits) {
  const lanes = [];
  const placed = new Map();
  commits.forEach((c, row) => {
    let lane = lanes.indexOf(c.sha);
    if (lane === -1) {
      lane = lanes.indexOf(null);
      if (lane === -1) { lanes.push(null); lane = lanes.length - 1; }
    }
    lanes[lane] = c.parents[0] || null;
    for (let p = 1; p < c.parents.length; p += 1) {
      if (lanes.indexOf(c.parents[p]) === -1) {
        const free = lanes.indexOf(null);
        if (free === -1) lanes.push(c.parents[p]);
        else lanes[free] = c.parents[p];
      }
    }
    placed.set(c.sha, { row, lane });
  });
  return placed;
}

function graphSection(s) {
  const node = section('Commit graph');
  const commits = s.commits || [];
  if (!commits.length) {
    node.appendChild(el('p', 'muted', 'No commits yet.'));
    return node;
  }

  const refsBySha = {};
  const add = (sha, text, cls) => {
    (refsBySha[sha] = refsBySha[sha] || []).push({ text, cls });
  };
  (s.branches || []).forEach((b) => {
    const full = commits.find((c) => c.short === b.sha || c.sha.startsWith(b.sha));
    if (full) add(full.sha, b.name, b.remote ? 'remote' : (b.current ? 'head' : ''));
  });
  (s.tags || []).forEach((t) => {
    const full = commits.find((c) => c.short === t.sha || c.sha.startsWith(t.sha));
    if (full) add(full.sha, t.name, 'tag');
  });

  const placed = layoutGraph(commits);
  const rowH = 26;
  const laneW = 14;
  const laneCount = Math.max(...[...placed.values()].map((p) => p.lane)) + 1;
  const colors = ['#58a6ff', '#4ac97e', '#e3b341', '#bc8cff', '#f26d6d', '#5ed3d3'];

  const wrap = el('div', 'graph-wrap');
  const svgNs = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNs, 'svg');
  svg.setAttribute('width', laneCount * laneW + 6);
  svg.setAttribute('height', commits.length * rowH);
  svg.style.flex = `0 0 ${laneCount * laneW + 6}px`;

  const cx = (lane) => lane * laneW + 8;
  const cy = (row) => row * rowH + rowH / 2;

  commits.forEach((c) => {
    const me = placed.get(c.sha);
    c.parents.forEach((parentSha) => {
      const parent = placed.get(parentSha);
      if (!parent) return;
      const path = document.createElementNS(svgNs, 'path');
      const x1 = cx(me.lane); const y1 = cy(me.row);
      const x2 = cx(parent.lane); const y2 = cy(parent.row);
      path.setAttribute('d', x1 === x2
        ? `M${x1},${y1} L${x2},${y2}`
        : `M${x1},${y1} C${x1},${y1 + rowH * 0.6} ${x2},${y2 - rowH * 0.6} ${x2},${y2}`);
      path.setAttribute('stroke', colors[parent.lane % colors.length]);
      path.setAttribute('stroke-width', '1.6');
      path.setAttribute('fill', 'none');
      svg.appendChild(path);
    });
  });

  commits.forEach((c) => {
    const me = placed.get(c.sha);
    const dot = document.createElementNS(svgNs, 'circle');
    dot.setAttribute('cx', cx(me.lane));
    dot.setAttribute('cy', cy(me.row));
    dot.setAttribute('r', '4');
    dot.setAttribute('fill', colors[me.lane % colors.length]);
    dot.setAttribute('stroke', '#161b22');
    dot.setAttribute('stroke-width', '2');
    svg.appendChild(dot);
  });

  wrap.appendChild(svg);

  const labels = el('div', 'graph-labels');
  commits.forEach((c) => {
    const line = el('div', 'commit-line');
    line.title = `${c.sha}\n${c.author}, ${c.when}`;
    (refsBySha[c.sha] || []).forEach((r) => line.appendChild(el('span', `ref ${r.cls}`, r.text)));
    line.appendChild(el('span', 'sha', c.short));
    line.appendChild(el('span', 'subj', c.subject));
    labels.appendChild(line);
  });
  wrap.appendChild(labels);
  node.appendChild(wrap);
  return node;
}

function branchSection(s) {
  const node = section('Refs');
  const list = el('div', 'reflist');
  (s.branches || []).forEach((b) => {
    const line = el('div');
    const marker = b.current ? '* ' : '  ';
    line.innerHTML = `<span style="color:${b.remote ? 'var(--purple)' : (b.current ? 'var(--green)' : 'var(--ink)')}">`
      + `${marker}${esc(b.name)}</span> <span class="up">${esc(b.sha)}</span>`
      + (b.upstream ? ` <span class="up">→ ${esc(b.upstream)}</span>` : '')
      + (b.track ? ` <span class="track">[${esc(b.track)}]</span>` : '');
    list.appendChild(line);
  });
  (s.tags || []).forEach((t) => {
    const line = el('div');
    line.innerHTML = `  <span style="color:var(--amber)">${esc(t.name)}</span>`
      + ` <span class="up">${esc(t.sha)}${t.annotated ? ' (annotated)' : ''}</span>`;
    list.appendChild(line);
  });
  (s.remotes || []).forEach((r) => {
    list.appendChild(el('div', 'up', `  remote ${r.name}`));
  });
  node.appendChild(list);
  return node;
}

function stashSection(stashes) {
  const node = section('Stash');
  const list = el('div', 'reflist');
  stashes.forEach((s) => list.appendChild(el('div', null, `${s.ref}  ${s.subject}`)));
  node.appendChild(list);
  return node;
}

function reflogSection(entries) {
  const node = section('Reflog — the undo history');
  const list = el('div', 'reflist');
  if (!entries.length) list.appendChild(el('div', 'up', 'empty'));
  entries.slice(0, 8).forEach((e) => {
    const line = el('div');
    line.innerHTML = `<span style="color:var(--amber)">${esc(e.sha)}</span> `
      + `<span class="up">${esc(e.ref)}</span> ${esc(e.what)}`;
    list.appendChild(line);
  });
  node.appendChild(list);
  return node;
}

/* ------------------------------------------------------------- markdown */

function inlineMd(text) {
  return esc(text)
    .replace(/`([^`]+)`/g, '<code class="inline">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\*([^*]+)\*/g, '<i>$1</i>');
}

function markdown(src) {
  const lines = src.split('\n');
  const out = [];
  let inCode = false;
  let inList = false;
  lines.forEach((raw) => {
    const line = raw.trimEnd();
    if (line.startsWith('```')) {
      if (inList) { out.push('</ul>'); inList = false; }
      out.push(inCode ? '</code></pre>' : '<pre><code>');
      inCode = !inCode;
      return;
    }
    if (inCode) { out.push(esc(raw)); return; }
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) { out.push('<ul class="plain">'); inList = true; }
      out.push(`<li>${inlineMd(line.replace(/^\s*[-*]\s+/, ''))}</li>`);
      return;
    }
    if (inList) { out.push('</ul>'); inList = false; }
    if (/^###\s+/.test(line)) return out.push(`<h3>${inlineMd(line.slice(4))}</h3>`);
    if (/^##\s+/.test(line)) return out.push(`<h2>${inlineMd(line.slice(3))}</h2>`);
    if (!line.trim()) return;
    out.push(`<p>${inlineMd(line)}</p>`);
  });
  if (inList) out.push('</ul>');
  if (inCode) out.push('</code></pre>');
  return out.join('\n');
}

/* ------------------------------------------------------------- wiring */

$('#search').addEventListener('input', renderCatalog);
$('#next-unsolved').addEventListener('click', openNextUnsolved);
$('#show-cheatsheet').addEventListener('click', showCheatsheet);

document.querySelectorAll('.filter[data-level]').forEach((btn) => {
  btn.addEventListener('click', () => {
    state.level = btn.dataset.level;
    document.querySelectorAll('.filter[data-level]').forEach((b) => b.classList.toggle('active', b === btn));
    renderCatalog();
  });
});

document.querySelectorAll('.viewbtn').forEach((btn) => {
  btn.addEventListener('click', () => {
    state.view = btn.dataset.view;
    document.querySelectorAll('.viewbtn').forEach((b) => b.classList.toggle('active', b === btn));
    renderCatalog();
  });
});

$('#filter-unsolved').addEventListener('click', () => {
  state.unsolvedOnly = !state.unsolvedOnly;
  $('#filter-unsolved').classList.toggle('active', state.unsolvedOnly);
  renderCatalog();
});

document.addEventListener('keydown', (ev) => {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
  if (ev.key === 'Escape') {
    const overlay = document.querySelector('.overlay');
    if (overlay) overlay.remove();
    return;
  }
  if (typing) return;
  if (ev.key === '/') {
    ev.preventDefault();
    $('#search').focus();
  } else if (ev.key === 'n') {
    openNextUnsolved();
  } else if (ev.key === 'c') {
    showCheatsheet();
  }
});

$('#term-in').addEventListener('keydown', (ev) => {
  const input = ev.target;
  if (ev.key === 'Enter' && input.value.trim()) {
    const command = input.value.trim();
    input.value = '';
    submitCommand(command);
  } else if (ev.key === 'ArrowUp') {
    ev.preventDefault();
    if (state.historyAt > 0) { state.historyAt -= 1; input.value = state.history[state.historyAt]; }
  } else if (ev.key === 'ArrowDown') {
    ev.preventDefault();
    state.historyAt = Math.min(state.historyAt + 1, state.history.length);
    input.value = state.history[state.historyAt] || '';
  }
});

loadCatalog();
