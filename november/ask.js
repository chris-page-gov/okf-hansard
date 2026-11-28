const $ = (id) => document.getElementById(id);
const hitsPerPage = 25;
const root = new URL('./', location.href);
let catalogue;
let selected;
let matches = [];
let page = 0;
let request = 0;

async function json(path) {
  const response = await fetch(new URL(path, root));
  if (!response.ok) throw new Error('An evidence file could not be opened. Try again or open the coverage report.');
  if (!path.endsWith('.gz')) return response.json();
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes[0] !== 31 || bytes[1] !== 139) return JSON.parse(new TextDecoder().decode(bytes));
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).json();
}

function link(label, href) {
  const element = document.createElement('a');
  element.textContent = label;
  element.href = href;
  return element;
}

function timeline(key, anchor) {
  const url = new URL('history.html', root);
  url.searchParams.set('entity', key);
  if (anchor) {
    url.searchParams.set('day', anchor[0]);
    url.searchParams.set('anchor', anchor[6]);
  }
  return url.href;
}

async function openContext(row, button) {
  const [day, , , , section, order] = row;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) throw new Error('Invalid sitting date.');
  button.disabled = true;
  try {
    const lookup = await json('context/' + day + '/turns.json');
    if (lookup.snapshot !== selected.snapshot) throw new Error('The collection changed. Reload the finder and try again.');
    const entry = lookup.sections[section];
    const turn = (entry?.order.indexOf(order) ?? -1) + 1;
    if (!turn || !/^[a-f0-9]{20}$/.test(entry.stem) || !Number.isSafeInteger(lookup.page_turns)
        || lookup.page_turns < 1) {
      throw new Error('Context is unavailable for this snapshot. Open the Hansard link for this contribution.');
    }
    const page = Math.ceil(turn / lookup.page_turns);
    location.assign(new URL(`context/${day}/${entry.stem}-${page}.html#turn-${turn}`, root));
  } finally {
    button.disabled = false;
  }
}

function render() {
  const offset = page * hitsPerPage;
  const rows = matches.slice(offset, offset + hitsPerPage);
  const {key, record, snapshot} = selected;
  const view = timeline(key, matches.find((row) => row.length === 7));
  $('results').hidden = false;
  $('count').textContent = matches.length
    ? `${record.label}. Showing ${offset + 1} to ${offset + rows.length} of ${matches.length.toLocaleString('en-GB')} distinct Hansard links.`
    : `${record.label}. This bundle returned no retained matches.`;
  $('timeline').replaceChildren(link('Open the contribution timeline', view));
  $('links').replaceChildren(...rows.map((row) => {
    const [date, house, url, speaker] = row;
    const li = document.createElement('li');
    li.append(link([date, house, speaker].filter(Boolean).join(' · '), url));
    if (row.length === 7) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Show this contribution in context';
      button.addEventListener('click', () => openContext(row, button).catch(showError));
      li.append(' ', button);
    }
    return li;
  }));
  $('previous').disabled = page === 0;
  $('next').disabled = offset + rows.length >= matches.length;
  $('evidence').value = [
    `Hansard evidence for ${record.label} (${key})`,
    `Snapshot ${snapshot}`, `Coverage ${root}coverage.json`,
    $('coverage-summary').textContent,
    `This bundle has ${matches.length} distinct retained source links for this concept. These are configured alias matches.`,
    `Historical checks for this concept ${record.complete ? 'completed' : 'have limited coverage'}.`,
    `Timeline ${view}`, '', 'Selected dated source links',
    ...rows.slice(0, 8).map(([date, house, url, speaker]) => `- ${date} · ${house} · ${speaker || 'Speaker unlabelled'} · ${url}`),
    '', 'Answer the question using these records and state any additional sources you opened.'
  ].join('\n');
}

async function openConcept(key) {
  const opening = ++request;
  if (!/^[\w-]+$/.test(key) || !Object.hasOwn(catalogue.concepts, key)) return;
  $('status').textContent = 'Loading indexed matches…';
  $('results').hidden = true;
  const record = catalogue.concepts[key];
  const files = [`history/${key}.json`];
  if (record.archive_count) files.push(`history/${key}.archive.json.gz`);
  if (record.older_count) files.push(`history/${key}.older.json.gz`);
  const lists = await Promise.all(files.map(json));
  if (opening !== request) return;
  const links = new Map();
  for (const row of lists.flat().sort((a, b) => b[0].localeCompare(a[0]))) {
    const url = new URL(row[2]);
    if (url.origin !== 'https://hansard.parliament.uk') throw new Error('A source link has an unexpected address.');
    if (!links.has(row[2])) links.set(row[2], row);
  }
  matches = Array.from(links.values());
  selected = {key, record, snapshot: catalogue.snapshot};
  page = 0;
  render();
  $('status').textContent = '';
}

function normalise(value) {
  return value.toLocaleLowerCase('en-GB').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
}

$('lookup').addEventListener('submit', async (event) => {
  event.preventDefault();
  const lookup = ++request;
  const query = normalise($('concept').value);
  $('status').textContent = 'Finding concepts…';
  $('choices').replaceChildren();
  $('results').hidden = true;
  try {
    if (!query) throw new Error('Enter a concept name.');
    catalogue ??= await json('concepts.json');
    if (lookup !== request) return;
    const names = Object.entries(catalogue.concepts).map(([key, row]) =>
      [key, row, [key, row.label, ...row.aliases].map(normalise)]);
    const exact = names.filter(([, , labels]) => labels.includes(query));
    const options = exact.length ? exact : names.filter(([, , labels]) => labels.some((label) => label.includes(query)));
    if (options.length === 1) return await openConcept(options[0][0]);
    $('status').textContent = options.length ? 'Choose the concept you meant.' : 'No indexed concept matched. The contribution timeline remains available.';
    for (const [key, row] of options.slice(0, 15)) {
      const button = document.createElement('button');
      button.textContent = `${row.label} · ${row.group}`;
      button.addEventListener('click', () => openConcept(key).catch(showError));
      $('choices').append(button, ' ');
    }
  } catch (error) { showError(error); }
});

function showError(error) { $('status').textContent = error.message; }

$('previous').addEventListener('click', () => { page--; render(); });
$('next').addEventListener('click', () => { page++; render(); });
for (const button of document.querySelectorAll('[data-copy]')) {
  button.addEventListener('click', async () => {
    const field = $(button.dataset.copy);
    try {
      await navigator.clipboard.writeText(field.value);
      button.textContent = 'Copied';
    } catch {
      field.focus();
      field.select();
      button.textContent = 'Select and copy the text';
    }
  });
}
