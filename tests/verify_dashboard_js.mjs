import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const GREEN = "[32m", RED = "[31m", DIM = "[2m", RESET = "[0m";

function makeElement(tag) {
  const node = {
    tagName: String(tag).toUpperCase(),
    children: [], attributes: {}, listeners: {},
    style: {}, dataset: {}, className: "", title: "", type: "",
    hidden: false, tabIndex: 0, colSpan: 1, innerHTML: "",
    appendChild(child) { node.children.push(child); return child; },
    setAttribute(name, value) { node.attributes[name] = String(value); },
    getAttribute(name) { return name in node.attributes ? node.attributes[name] : null; },
    removeAttribute(name) { delete node.attributes[name]; },
    addEventListener(type, handler) { (node.listeners[type] ||= []).push(handler); },
    removeEventListener() {},
    getBoundingClientRect() { return { left: 0, width: 1000, top: 0, height: 230 }; },
    click() { (node.listeners.click || []).forEach((h) => h({ preventDefault() {} })); },
    get textContent() {
      return node.children.map((c) => (c.nodeValue ?? c.textContent ?? "")).join("");
    },
    set textContent(value) {
      node.children = [];
      if (value !== "") node.children.push({ nodeValue: String(value) });
    }
  };
  return node;
}

function makeDocument() {
  const byId = new Map();
  return {
    getElementById(id) {
      if (!byId.has(id)) byId.set(id, makeElement("div"));
      return byId.get(id);
    },
    createElement: makeElement,
    createTextNode: (text) => ({ nodeValue: String(text) }),
    querySelectorAll: () => [],
    addEventListener() {}
  };
}

function boot() {
  const html = readFileSync(join(ROOT, "docs", "index.html"), "utf8");
  const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
  if (scripts.length !== 1) {
    throw new Error(`expected one inline <script> in docs/index.html, found ${scripts.length}`);
  }

  const sandbox = {
    document: makeDocument(), atob, Intl, console,
    location: { hostname: "example.github.io", pathname: "/hospital/" }
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);

  vm.runInContext(readFileSync(join(ROOT, "docs", "data.js"), "utf8"), sandbox);
  vm.runInContext(scripts[0][1], sandbox);

  if (!sandbox.window.__dashboard) {
    throw new Error("the dashboard script did not expose window.__dashboard");
  }
  return sandbox.window;
}

function readCsv(name) {
  const text = readFileSync(join(ROOT, "exports", `${name}.csv`), "utf8").replace(/^﻿/, "");
  const [head, ...body] = text.trim().split("\n");
  const keys = head.split(",");
  return body.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(keys.map((key, index) => [key, cells[index]]));
  });
}

const failures = [];
function check(label, actual, expected) {
  if (String(actual) !== String(expected)) {
    failures.push(`${label}: dashboard ${actual}, warehouse ${expected}`);
  }
}

function round2(value) {
  return (Math.round((value + Number.EPSILON) * 100) / 100).toFixed(2);
}

console.log(`${DIM}Booting docs/index.html in a DOM stub...${RESET}`);
const win = boot();
const dash = win.__dashboard;
const META = win.HOSPITAL_META;
const departments = META.departments.map((d) => d.name);

let a = dash.aggregate();
const kpi = readCsv("q01_operating_kpis")[0];
check("total visits", a.n, kpi.TotalVisits);
check("distinct patients", a.patients, kpi.DistinctPatients);
check("total revenue", a.bill.toFixed(2), Number(kpi.TotalBilledRevenueINR).toFixed(2));
check("average bill", round2(a.bill / a.n), Number(kpi.AverageBillINR).toFixed(2));
check("average wait", round2(a.wait / a.n), Number(kpi.AverageWaitMinutes).toFixed(2));
check("average satisfaction", round2(a.sat / a.n), Number(kpi.AverageSatisfaction).toFixed(2));

const repeat = readCsv("q11_repeat_patients")[0];
check("repeat patients", a.repeat, repeat.RepeatPatients);

for (const row of readCsv("q07_department_service_risk")) {
  const d = departments.indexOf(row.DepartmentName);
  if (d < 0) { failures.push(`unknown department in q07: ${row.DepartmentName}`); continue; }
  check(`${row.DepartmentName} visits`, a.deptN[d], row.TotalVisits);
  check(`${row.DepartmentName} avg wait`, round2(a.deptWait[d] / a.deptN[d]),
        Number(row.AverageWaitMinutes).toFixed(2));
  check(`${row.DepartmentName} avg satisfaction`, round2(a.deptSat[d] / a.deptN[d]),
        Number(row.AverageSatisfaction).toFixed(2));

  const within = dash.countUpTo(a.deptHist, d * dash.WAITMAX, 30);
  check(`${row.DepartmentName} within 30 min`,
        (100 * within / a.deptN[d]).toFixed(2),
        Number(row.VisitsWithin30MinutesPercent).toFixed(2));
}

for (let d = 0; d < departments.length; d++) {
  let total = 0;
  for (let v = 0; v < dash.WAITMAX; v++) total += a.deptHist[d * dash.WAITMAX + v];
  check(`${departments[d]} histogram total`, total, a.deptN[d]);
}

for (let d = 0; d < departments.length; d++) {
  const base = d * dash.WAITMAX, n = a.deptN[d];
  const p10 = dash.percentile(a.deptHist, base, n, 0.10);
  const p50 = dash.percentile(a.deptHist, base, n, 0.50);
  const p90 = dash.percentile(a.deptHist, base, n, 0.90);
  if (!(p10 <= p50 && p50 <= p90)) {
    failures.push(`${departments[d]}: percentiles out of order (${p10}/${p50}/${p90})`);
  }
}

for (const row of readCsv("q04_payment_mix")) {
  const p = META.payments.indexOf(row.PaymentMethod);
  check(`${row.PaymentMethod} visits`, a.payN[p], row.TotalVisits);
  check(`${row.PaymentMethod} revenue`, a.payBill[p].toFixed(2),
        Number(row.TotalRevenueINR).toFixed(2));
}
for (const row of readCsv("q05_age_band")) {
  const g = META.ageBands.indexOf(row.AgeGroup);
  check(`age ${row.AgeGroup} visits`, a.ageN[g], row.TotalVisits);
  check(`age ${row.AgeGroup} avg bill`, round2(a.ageBill[g] / a.ageN[g]),
        Number(row.AverageBillINR).toFixed(2));
}

const monthly = readCsv("q09_monthly_trend");
check("months on the trend line", monthly.length, META.months);
monthly.forEach((row, index) => {
  check(`${row.MonthStart} visits`, a.monN[index], row.TotalVisits);
});

{
  const rendered = win.document.getElementById("docBody").children
    .map((tr) => tr.children.map((td) => td.textContent.trim()));
  const expected = readCsv("q10_top_doctors");
  check("leaderboard row count", rendered.length, expected.length);
  expected.forEach((row, index) => {
    const got = rendered[index];
    if (!got) { failures.push(`leaderboard row ${index + 1} missing`); return; }
    check(`leaderboard ${index + 1} rank`, got[0], row.PerformanceRank);
    check(`leaderboard ${index + 1} name`, got[1], row.DoctorName);
    check(`leaderboard ${index + 1} visits`, got[2].replace(/,/g, ""), row.TotalVisits);
    check(`leaderboard ${index + 1} satisfaction`, got[3],
          Number(row.AverageSatisfaction).toFixed(2));
    check(`leaderboard ${index + 1} wait`, got[4],
          Number(row.AverageWaitMinutes).toFixed(2) + " min");
  });
}

const annual = readCsv("q02_annual_growth");
annual.forEach((row, yearIndex) => {
  dash.state.years.clear();
  dash.state.years.add(yearIndex);
  const slice = dash.aggregate();
  check(`filter to ${row.VisitYear}: visits`, slice.n, row.TotalVisits);
  check(`filter to ${row.VisitYear}: revenue`, slice.bill.toFixed(2),
        Number(row.TotalRevenueINR).toFixed(2));
});
dash.state.years.clear();

for (const row of readCsv("q08_weekday_weekend")) {
  dash.state.days.clear();
  dash.state.days.add(row.DayType === "Weekend" ? 1 : 0);
  const slice = dash.aggregate();
  check(`filter to ${row.DayType}: visits`, slice.n, row.TotalVisits);
  check(`filter to ${row.DayType}: revenue`, slice.bill.toFixed(2),
        Number(row.TotalRevenueINR).toFixed(2));
  check(`filter to ${row.DayType}: avg bill`, round2(slice.bill / slice.n),
        Number(row.AverageBillINR).toFixed(2));
}
dash.state.days.clear();

{
  const emergency = departments.indexOf("Emergency Medicine");
  dash.state.depts.clear();
  dash.state.depts.add(emergency);
  const slice = dash.aggregate();
  const row = readCsv("q07_department_service_risk")
    .find((r) => r.DepartmentName === "Emergency Medicine");
  check("filter to Emergency: visits", slice.n, row.TotalVisits);
  check("filter to Emergency: avg wait", round2(slice.wait / slice.n),
        Number(row.AverageWaitMinutes).toFixed(2));
  check("filter to Emergency: no other department survives",
        slice.deptN.filter((v) => v > 0).length, 1);
  dash.state.depts.clear();
}

{
  let sum = 0;
  for (let p = 0; p < META.payments.length; p++) {
    dash.state.pays.clear(); dash.state.pays.add(p);
    dash.state.ages.clear(); dash.state.ages.add(2);
    sum += dash.aggregate().n;
  }
  dash.state.pays.clear(); dash.state.ages.clear();
  const ageOnly = (() => {
    dash.state.ages.add(2);
    const n = dash.aggregate().n;
    dash.state.ages.clear();
    return n;
  })();
  check("payment slices partition the 36-55 age band", sum, ageOnly);
}

{
  dash.state.years.add(0);
  dash.state.depts.add(departments.indexOf("Emergency Medicine"));
  dash.state.days.add(1);
  dash.state.pays.add(0);
  dash.state.ages.add(0);
  const narrow = dash.aggregate();
  if (!(narrow.n >= 0 && narrow.n < a.n)) {
    failures.push(`narrow filter returned ${narrow.n}, expected fewer than ${a.n}`);
  }
  dash.render();
  dash.state.years.clear(); dash.state.depts.clear(); dash.state.days.clear();
  dash.state.pays.clear(); dash.state.ages.clear();
  dash.render();
}

if (failures.length) {
  console.log(`${RED}${failures.length} value(s) differ between the dashboard and exports/.${RESET}`);
  failures.slice(0, 20).forEach((line) => console.log(`  ${line}`));
  if (failures.length > 20) console.log(`  ... and ${failures.length - 20} more`);
  process.exit(1);
}

console.log(`${GREEN}Dashboard JavaScript agrees with exports/.${RESET}`);
console.log(`  KPIs, all ${departments.length} departments, wait histograms and percentiles,`);
console.log(`  payment mix, age bands and all ${META.months} months reconcile.`);
console.log("  The doctor leaderboard reproduces q10 row for row, ties included,");
console.log("  and the year, day-type and department filters reproduce the SQL slices.");
