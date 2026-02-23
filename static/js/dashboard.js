// ─── Chart instances ──────────────────────────────────────────────────────────
let daysChart, bonusChart, siteChart;

// ─── Catppuccin Mocha palette (matches CSS vars) ─────────────────────────────
const C = {
    accent:    "#89b4fa",   // blue
    green:     "#a6e3a1",
    peach:     "#fab387",
    pink:      "#f5c2e7",
    mauve:     "#cba6f7",
    text:      "#cdd6f4",
    subtext:   "#a6adc8",
    surface0:  "#313244",
    surface1:  "#45475a",
    base:      "#1e1e2e",
};

Chart.defaults.color          = C.subtext;
Chart.defaults.borderColor    = C.surface0;
Chart.defaults.font.family    = "system-ui, sans-serif";
Chart.defaults.font.size      = 12;

function fmtNum(n) {
    if (n === null || n === undefined) return "—";
    return Number(n).toLocaleString();
}

// ─── Load a worker ────────────────────────────────────────────────────────────
function loadWorker(id) {
    if (!id) return;

    // highlight sidebar
    document.querySelectorAll(".worker").forEach(el => {
        el.classList.toggle("selected", el.dataset.workerId == id);
    });

    Promise.all([
        fetch(`/api/worker/${id}/profile`).then(r => r.json()),
        fetch(`/api/worker/${id}/charts`).then(r => r.json()),
    ]).then(([profile, charts]) => {
        renderProfile(profile);
        drawCharts(charts);
    }).catch(err => console.error("Failed to load worker:", err));
}

// ─── Render profile panel ─────────────────────────────────────────────────────
function renderProfile(data) {
    const w = data.worker;
    const s = data.stats;

    // Name
    document.getElementById("worker-name").textContent = w.display_name;

    // Cedula badge
    const cinBadge = document.getElementById("worker-cedula-badge");
    cinBadge.textContent = w.cedula ? `CIN ${w.cedula}` : "";
    cinBadge.style.display = w.cedula ? "" : "none";

    // Seniority badge
    const senBadge = document.getElementById("worker-seniority");
    if (s.first_week) {
        senBadge.textContent = `Since ${s.first_week}`;
        senBadge.style.display = "";
    } else {
        senBadge.style.display = "none";
    }

    // Stars
    const starEls = document.querySelectorAll(".star");
    starEls.forEach(el => {
        el.classList.toggle("on", Number(el.dataset.i) <= s.stars);
    });
    document.getElementById("stars-sub").textContent =
        `${s.stars}/5 — based on last ${Math.min(s.total_weeks, 4)} week(s)`;

    // Stat cards
    document.getElementById("stat-days").textContent    = fmtNum(s.total_days);
    document.getElementById("stat-weeks").textContent   = fmtNum(s.total_weeks);
    document.getElementById("stat-salary").textContent  = fmtNum(s.total_salary);
    document.getElementById("stat-bonus").textContent   = fmtNum(s.total_bonus);

    // Bonus likelihood
    const pct = s.bonus_likelihood ?? 0;
    document.getElementById("stat-likelihood").textContent = `${pct}%`;
    document.getElementById("likelihood-bar").style.width = `${pct}%`;

    // Bar color: green > 60, yellow > 30, red otherwise
    const bar = document.getElementById("likelihood-bar");
    bar.style.background = pct >= 60 ? C.green : pct >= 30 ? C.peach : "#f38ba8";
}

// ─── Draw / redraw charts ────────────────────────────────────────────────────
function drawCharts(data) {
    if (daysChart)  daysChart.destroy();
    if (bonusChart) bonusChart.destroy();
    if (siteChart)  siteChart.destroy();

    const sharedLineOpts = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { display: false },
            tooltip: { mode: "index", intersect: false },
        },
        scales: {
            x: {
                grid: { color: C.surface0 },
                ticks: { maxRotation: 45, minRotation: 30 },
            },
            y: {
                grid: { color: C.surface0 },
                beginAtZero: true,
            },
        },
        elements: {
            point: { radius: 4, hoverRadius: 6 },
            line:  { tension: 0.35, borderWidth: 2 },
        },
    };

    // ── Days Worked Line Chart ─────────────────────────────────────────────
    daysChart = new Chart(document.getElementById("daysChart"), {
        type: "line",
        data: {
            labels: data.labels,
            datasets: [{
                label: "Days worked",
                data:  data.days,
                borderColor:     C.accent,
                backgroundColor: C.accent + "33",
                fill: true,
            }],
        },
        options: {
            ...sharedLineOpts,
            scales: {
                ...sharedLineOpts.scales,
                y: { ...sharedLineOpts.scales.y, suggestedMax: 6 },
            },
        },
    });

    // ── Bonus Line Chart ───────────────────────────────────────────────────
    bonusChart = new Chart(document.getElementById("bonusChart"), {
        type: "line",
        data: {
            labels: data.bonus_labels,
            datasets: [{
                label: "Bonus",
                data:  data.bonus,
                borderColor:     C.green,
                backgroundColor: C.green + "33",
                fill: true,
            }],
        },
        options: sharedLineOpts,
    });

    // ── Sites Bar Chart ────────────────────────────────────────────────────
    const siteColors = [C.mauve, C.peach, C.accent, C.green, C.pink, C.subtext];

    siteChart = new Chart(document.getElementById("siteChart"), {
        type: "bar",
        data: {
            labels: data.sites.map(s => s.label),
            datasets: [{
                label: "Days worked",
                data:  data.sites.map(s => s.value),
                backgroundColor: data.sites.map((_, i) => siteColors[i % siteColors.length] + "cc"),
                borderColor:     data.sites.map((_, i) => siteColors[i % siteColors.length]),
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            const s = data.sites[items[0].dataIndex];
                            return s.label !== s.code ? `${s.code} – ${s.label}` : s.code;
                        },
                        label: (item) => ` ${item.raw} days`,
                    },
                },
            },
            scales: {
                x: {
                    grid: { color: C.surface0 },
                    ticks: { maxRotation: 35, minRotation: 0 },
                },
                y: {
                    grid: { color: C.surface0 },
                    beginAtZero: true,
                    ticks: {
                        // Show 0.5 increments for half-days
                        stepSize: 0.5,
                    },
                    title: { display: true, text: "Days", color: C.subtext },
                },
            },
        },
    });
}

// ─── Sidebar click listeners ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".worker").forEach(el => {
        el.addEventListener("click", () => loadWorker(el.dataset.workerId));
    });
});
