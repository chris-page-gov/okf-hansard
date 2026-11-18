const byId = (id) => document.getElementById(id);
const dateLabel = new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" });
const formatDate = (day) => dateLabel.format(new Date(day + "T00:00:00Z"));
const facets = byId("facet");
const filters = ["house", "relation", "date"].map(byId);

function make(tag, text) {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

function link(text, url) {
  const a = make("a", text);
  a.href = url;
  return a;
}

function setOptions(select, choices, allLabel, selected = "") {
  const label = select.id === "date" ? formatDate : (value) => value;
  select.replaceChildren(new Option(allLabel, ""), ...choices.map((value) => new Option(label(value), value)));
  select.value = choices.includes(selected) ? selected : "";
}

function showFacets(example) {
  const groups = Object.entries(example.facets).filter(([group, entries]) =>
    entries.length && (!facets.value || group === facets.value)
  );
  byId("facets").replaceChildren(...groups.flatMap(([group, entries]) => {
    const values = make("dd", "");
    for (const [index, name] of entries.entries()) {
      if (index) values.append(", ");
      const biography = group === "People" ? example.biographies?.[name] : null;
      values.append(biography ? link(name, biography) : name);
    }
    return [make("dt", group), values];
  }));
}

function showTimeline(example) {
  const rows = example.rows.filter((row) =>
    filters.every((select) => !select.value || select.value === row[select.id])
  );
  byId("row-count").textContent = rows.length
    ? `${rows.length} of ${example.rows.length} timeline entries`
    : "No timeline entries match these filters.";
  byId("timeline").replaceChildren(...rows.map((row) => {
    const item = make("li", "");
    const time = make("time", formatDate(row.date));
    time.dateTime = row.date;
    const meta = make("p", "");
    meta.append(time, ` · ${row.house} · ${row.relation}`);
    item.append(meta, link(row.title, row.url));
    return item;
  }));
}

function updateLink(example) {
  const url = new URL(location.href);
  url.searchParams.set("example", example.id);
  for (const select of [...filters, facets]) {
    if (select.value) url.searchParams.set(select.id, select.value);
    else url.searchParams.delete(select.id);
  }
  history.replaceState(null, "", url);
}

function render(data) {
  const params = new URLSearchParams(location.search);
  const example = data.examples.find((item) => item.id === params.get("example")) ?? data.examples[0];
  byId("examples").replaceChildren(...data.examples.map((item) => {
    const option = link(item.title, `?example=${encodeURIComponent(item.id)}`);
    if (item.id === example.id) option.setAttribute("aria-current", "page");
    return option;
  }));
  const days = Object.keys(data.sittings).sort();
  const total = Object.values(data.sittings).reduce((sum, count) => sum + count, 0);
  byId("coverage").textContent =
    `Verified sittings from ${formatDate(days[0])} to ${formatDate(days.at(-1))} · ${total.toLocaleString("en-GB")} passages`;
  byId("example-title").textContent = example.title;
  byId("example-summary").textContent = example.summary;
  byId("example-sources").replaceChildren(...(example.links ?? []).map((source) => {
    const item = make("li", "");
    item.append(link(source.title, source.url));
    return item;
  }));
  setOptions(facets, Object.keys(example.facets).filter((group) => example.facets[group].length), "All facets", params.get("facet"));
  for (const select of filters) {
    const values = [...new Set(example.rows.map((row) => row[select.id]))];
    setOptions(select, values, { house: "Both Houses", relation: "All connections", date: "All dates" }[select.id], params.get(select.id));
    select.addEventListener("change", () => {
      showTimeline(example);
      updateLink(example);
    });
  }
  facets.addEventListener("change", () => {
    showFacets(example);
    updateLink(example);
  });
  showFacets(example);
  showTimeline(example);
  byId("companion").hidden = false;
}

try {
  const response = await fetch("demo.json");
  if (!response.ok) throw new Error("The demonstration data is unavailable.");
  render(await response.json());
} catch {
  byId("coverage").replaceChildren("The demonstration data could not load. ", link("Open the plain-text evidence", "demo-evidence.md"), ".");
}
