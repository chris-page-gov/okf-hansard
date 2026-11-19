const $ = (id) => document.getElementById(id);
const localeDate = new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" });
const list = new Intl.NumberFormat("en-GB");
const limit = 50;
const proposed = new URLSearchParams(window.location.search);
let index;
let rows = [];
let offset = 0;
let requestId = 0;

function options(id, entries, selected = $(id).value) {
  const select = $(id);
  select.replaceChildren(...entries.map(([value, label]) => new Option(label, value)));
  if (entries.some(([value]) => value === selected)) select.value = selected;
}

function link(url, label) {
  const target = new URL(url);
  if (target.origin !== "https://hansard.parliament.uk") throw new Error("Unexpected source link.");
  const a = document.createElement("a");
  a.href = target.href;
  a.textContent = label;
  return a;
}

async function read(path, gzip = false) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("History evidence could not be loaded.");
  return gzip
    ? new Response(response.body.pipeThrough(new DecompressionStream("gzip"))).json()
    : response.json();
}

function eligible() {
  const anchor = index.contributions[$("anchor").value];
  if (anchor) return anchor.entities;
  return [...new Set(Object.values(index.contributions)
    .filter((record) => record.date === $("day").value)
    .flatMap((record) => record.entities))];
}

function setEntities(wanted) {
  const entries = eligible()
    .map((key) => [key, index.entities[key]])
    .filter(([, row]) => !$("facet").value || row.group === $("facet").value)
    .sort(([, a], [, b]) => a.label.localeCompare(b.label, "en-GB"))
    .map(([key, row]) => [key, row.label]);
  options("entity", entries.length ? entries : [["", "No matched entities"]], wanted);
}

function selectAnchor(wantedEntity) {
  const anchor = index.contributions[$("anchor").value];
  $("anchor-source").replaceChildren();
  if (anchor) $("anchor-source").append(link(anchor.url, "Read the selected contribution in Hansard"));
  const groups = [...new Set(eligible().map((key) => index.entities[key].group))].sort();
  options("facet", [["", "All facets"], ...groups.map((group) => [group, group])]);
  setEntities(wantedEntity);
}

function selectDay(wantedAnchor, wantedEntity) {
  const sameDay = Object.entries(index.contributions).filter(([, row]) => row.date === $("day").value);
  options("anchor", [["", "All contributions that day"], ...sameDay.map(([key, row]) => [key, row.title])],
    wantedAnchor);
  selectAnchor(wantedEntity);
}

function showPage() {
  const filtered = rows.filter(([day, house]) => (!$("year").value || day.startsWith($("year").value))
    && (!$("house").value || house === $("house").value));
  const end = Math.min(offset + limit, filtered.length);
  $("count").textContent = filtered.length
    ? `Showing ${list.format(offset + 1)} to ${list.format(end)} of ${list.format(filtered.length)} matches`
    : "No earlier matches in this selection.";
  $("links").start = offset + 1;
  $("links").replaceChildren(...filtered.slice(offset, end).map(([day, house, url, attribution]) => {
    const item = document.createElement("li");
    const label = [localeDate.format(new Date(day)), house, attribution].filter(Boolean).join(" · ");
    item.append(link(url, label));
    return item;
  }));
  $("previous").disabled = offset === 0;
  $("next").disabled = end === filtered.length;
}

async function selectEntity() {
  const id = ++requestId;
  const key = $("entity").value;
  const row = index.entities[key];
  $("status").textContent = row ? `Loading mentions of ${row.label}…` : "";
  $("scope").textContent = "";
  $("links").replaceChildren();
  $("count").textContent = "";
  $("year").disabled = true;
  $("house").disabled = true;
  $("previous").disabled = true;
  $("next").disabled = true;
  const location = new URL(window.location);
  for (const name of ["day", "anchor", "entity"]) {
    if ($(name).value) location.searchParams.set(name, $(name).value);
    else location.searchParams.delete(name);
  }
  window.history.replaceState(null, "", location);
  const anchor = index.contributions[$("anchor").value];
  try {
    const [recent, archive] = row ? await Promise.all([
      read(`history/${encodeURIComponent(key)}.json`),
      row.archive_count ? read(`history/${encodeURIComponent(key)}.archive.json.gz`, true) : [],
    ]) : [[], []];
    if (id !== requestId) return;
    const day = $("day").value;
    rows = [...recent, ...archive].filter(([date, , , , section, order]) =>
      date < day || (anchor && date === day && section === anchor.section && order < anchor.order))
      .sort((left, right) => right[0].localeCompare(left[0]));
    offset = 0;
    const years = [...new Set(rows.map(([when]) => when.slice(0, 4)))];
    options("year", [["", "All years"], ...years.map((year) => [year, year])]);
    options("house", [["", "Both Houses"], ["Commons", "Commons"], ["Lords", "Lords"]]);
    $("year").disabled = false;
    $("house").disabled = false;
    $("status").textContent = "";
    $("scope").textContent = row
      ? `History checked from ${localeDate.format(new Date(index.from))}. ${row.complete
        ? "The planned archive and search checks completed."
        : "Some historical checks remain incomplete. Counts include the matches available so far."}`
      : "";
    showPage();
  } catch (error) {
    if (id === requestId) $("status").textContent = error.message;
  }
}

try {
  index = await read("history/index.json");
  const day = index.contributions[proposed.get("anchor")]?.date || proposed.get("day");
  options("day", [...index.days].reverse().map((value) => [value, localeDate.format(new Date(value))]), day);
  selectDay(proposed.get("anchor") || "", proposed.get("entity"));
  $("controls").hidden = false;
  $("day").addEventListener("change", () => { selectDay(); selectEntity(); });
  $("anchor").addEventListener("change", () => { selectAnchor(); selectEntity(); });
  $("facet").addEventListener("change", () => { setEntities(); selectEntity(); });
  $("entity").addEventListener("change", selectEntity);
  for (const id of ["year", "house"]) $(id).addEventListener("change", () => { offset = 0; showPage(); });
  $("previous").addEventListener("click", () => { offset -= limit; showPage(); });
  $("next").addEventListener("click", () => { offset += limit; showPage(); });
  await selectEntity();
} catch (error) {
  $("status").textContent = error.message;
}
