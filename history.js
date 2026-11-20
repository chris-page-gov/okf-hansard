const $ = (id) => document.getElementById(id);
const localeDate = new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" });
const list = new Intl.NumberFormat("en-GB");
const limit = 50;
const proposed = new URLSearchParams(window.location.search);
let index;
let dayRecords = {};
let rows = [];
let offset = 0;
let requestId = 0;
let dayRequestId = 0;

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

function viewLink(url, label) {
  const a = document.createElement("a");
  a.href = url;
  a.textContent = label;
  return a;
}

function graphLink(route) {
  const local = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const url = new URL(local ? "/okf-explorer/explore/" : "https://chris-page-gov.github.io/okf-explorer/explore/",
    window.location.origin);
  url.searchParams.set("bundle", new URL("graph/okf-explorer.json", window.location));
  url.searchParams.set("view", "graph");
  url.searchParams.set("graph.center", `dataset/${route}`);
  url.hash = `dataset/${route}`;
  return viewLink(url, "Graph");
}

function timelineLink(day, route) {
  const url = new URL(window.location);
  url.search = new URLSearchParams({ day, anchor: route, entity: $("entity").value });
  return viewLink(url, "Timeline");
}

async function read(path, gzip = false) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("History evidence could not be loaded.");
  if (!gzip) return response.json();
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes[0] !== 0x1f || bytes[1] !== 0x8b) return JSON.parse(new TextDecoder().decode(bytes));
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"))).json();
}

function eligible() {
  const anchor = dayRecords[$("anchor").value];
  if (anchor) return anchor.entities;
  return [...new Set(Object.values(dayRecords).flatMap((record) => record.entities))];
}

function setEntities(wanted) {
  const entries = eligible()
    .map((key) => [key, index.entities[key]])
    .filter(([, row]) => !$("facet").value || row.group === $("facet").value)
    .sort(([, a], [, b]) => a.label.localeCompare(b.label, "en-GB"))
    .map(([key, row]) => [key, row.label]);
  const choices = index.focused_views && entries.length ? [["", "Choose an entity"], ...entries] : entries;
  options("entity", choices.length ? choices : [["", "No matched entities"]], wanted);
}

function selectAnchor(wantedEntity) {
  const route = $("anchor").value;
  const anchor = dayRecords[route];
  $("anchor-source").replaceChildren();
  if (anchor) {
    $("anchor-source").append(link(anchor.url, "Read the selected contribution in Hansard"));
    if (index.focused_views) $("anchor-source").append(" · ", graphLink(route));
  }
  const groups = [...new Set(eligible().map((key) => index.entities[key].group))].sort();
  options("facet", [["", "All facets"], ...groups.map((group) => [group, group])]);
  setEntities(wantedEntity);
}

async function selectDay(wantedAnchor, wantedEntity) {
  const id = ++dayRequestId;
  const day = $("day").value;
  const records = index.focused_views
    ? await read(`history/days/${encodeURIComponent(day)}.json`)
    : Object.fromEntries(Object.entries(index.contributions).filter(([, row]) => row.date === day));
  if (id !== dayRequestId) return false;
  dayRecords = records;
  options("anchor", [["", "All contributions that day"], ...Object.entries(records).map(([key, row]) =>
    [key, index.focused_views ? `${row.title} · ${row.order + 1}` : row.title])],
    wantedAnchor);
  selectAnchor(wantedEntity);
  return true;
}

function showPage() {
  const filtered = rows.filter(([day, house]) => (!$("year").value || day.startsWith($("year").value))
    && (!$("house").value || house === $("house").value));
  const end = Math.min(offset + limit, filtered.length);
  $("count").textContent = filtered.length
    ? `Showing ${list.format(offset + 1)} to ${list.format(end)} of ${list.format(filtered.length)} matches`
    : $("entity").value ? "No matches in this selection." : "Choose an entity to show its contributions.";
  $("links").start = offset + 1;
  $("links").replaceChildren(...filtered.slice(offset, end).map(([day, house, url, attribution, , , route]) => {
    const item = document.createElement("li");
    const label = [localeDate.format(new Date(day)), house, attribution].filter(Boolean).join(" · ");
    item.append(link(url, label));
    if (route) item.append(" · ", graphLink(route), " · ", timelineLink(day, route));
    return item;
  }));
  $("previous").disabled = offset === 0;
  $("next").disabled = end === filtered.length;
}

async function selectEntity() {
  const id = ++requestId;
  const key = $("entity").value;
  const row = index.entities[key];
  $("history-export").replaceChildren();
  $("history-export").hidden = !row?.yamlld;
  if (row?.yamlld) $("history-export").append(viewLink(row.yamlld, "Download this entity’s earlier matches as YAML-LD"));
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
  const anchor = dayRecords[$("anchor").value];
  const period = index.focused_views ? $("period").value : "earlier";
  const recentSuffix = index.month_entity_shards && period === "month" && !row?.captured_only
    ? ".month.json"
    : ".json";
  try {
    const [recent, archive, older] = row ? await Promise.all([
      read(`history/${encodeURIComponent(key)}${recentSuffix}`),
      period !== "month" && row.archive_count ? read(`history/${encodeURIComponent(key)}.archive.json.gz`, true) : [],
      period !== "month" && row.older_count ? read(`history/${encodeURIComponent(key)}.older.json.gz`, true) : [],
    ]) : [[], [], []];
    if (id !== requestId) return;
    const day = $("day").value;
    rows = [...recent, ...archive, ...older].filter(([date, , , , section, order, route]) => {
      if (period === "month") return Boolean(route);
      if (period === "all") return true;
      return date < day || (anchor && date === day && section === anchor.section && order < anchor.order);
    })
      .sort((left, right) => right[0].localeCompare(left[0]));
    offset = 0;
    const years = [...new Set(rows.map(([when]) => when.slice(0, 4)))];
    options("year", [["", "All years"], ...years.map((year) => [year, year])]);
    options("house", [["", "Both Houses"], ["Commons", "Commons"], ["Lords", "Lords"]]);
    $("year").disabled = false;
    $("house").disabled = false;
    $("status").textContent = "";
    $("scope").textContent = row?.captured_only
      ? "This timeline follows recorded links within the November capture."
      : row && period !== "month"
      ? `The search window starts on ${localeDate.format(new Date(index.from))}. ${row.complete
        ? "The planned archive and search checks completed."
        : "Some historical checks remain incomplete. Counts include the matches available so far."}${row.older_count
        ? " Includes available matches in the pre-2007 archive." : ""}`
      : "";
    showPage();
  } catch (error) {
    if (id === requestId) $("status").textContent = error.message;
  }
}

try {
  index = await read("history/index.json");
  const anchor = proposed.get("anchor") || "";
  const day = index.contributions?.[anchor]?.date || proposed.get("day") || anchor.match(/^[^/]+\/[a-z]+-(\d{4}-\d{2}-\d{2})-/)?.[1];
  options("day", [...index.days].reverse().map((value) => [value, localeDate.format(new Date(value))]), day);
  if (index.focused_views) {
    document.title = "Contribution timeline | November in Parliament";
    $("heading").textContent = "Contribution timeline";
    $("intro").textContent = "Choose a contribution and follow its people, places, organisations and subjects through Hansard.";
    $("period-control").hidden = false;
    $("period").addEventListener("change", selectEntity);
  }
  await selectDay(anchor, proposed.get("entity"));
  $("controls").hidden = false;
  $("day").addEventListener("change", async () => {
    ++requestId;
    try {
      if (await selectDay()) await selectEntity();
    } catch (error) {
      $("status").textContent = error.message;
    }
  });
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
