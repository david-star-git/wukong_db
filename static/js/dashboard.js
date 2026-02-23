let daysChart, bonusChart, siteChart;

function loadWorker(id) {
    fetch(`/api/worker/${id}/profile`)
        .then((r) => r.json())
        .then((data) => {
            document.getElementById("worker-name").textContent =
                data.worker.display_name;
            document.getElementById("worker-cedula").textContent =
                data.worker.cedula ?? "";
            document.getElementById("total-days").textContent =
                data.stats.total_days;
            document.getElementById("total-salary").textContent =
                data.stats.total_salary;
            document.getElementById("total-bonus").textContent =
                data.stats.total_bonus;
        });

    fetch(`/api/worker/${id}/charts`)
        .then((r) => r.json())
        .then(drawCharts);
}

function drawCharts(data) {
    if (daysChart) daysChart.destroy();
    if (bonusChart) bonusChart.destroy();
    if (siteChart) siteChart.destroy();

    daysChart = new Chart(document.getElementById("daysChart"), {
        type: "line",
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: "Days worked",
                    data: data.days,
                },
            ],
        },
    });

    bonusChart = new Chart(document.getElementById("bonusChart"), {
        type: "line",
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: "Bonus",
                    data: data.bonus,
                },
            ],
        },
    });

    siteChart = new Chart(document.getElementById("siteChart"), {
        type: "bar",
        data: {
            labels: data.sites.map((s) => s.code),
            datasets: [
                {
                    label: "Days per site",
                    data: data.sites.map((s) => s.days),
                },
            ],
        },
    });
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".worker").forEach((el) => {
        el.addEventListener("click", () => {
            document
                .querySelectorAll(".worker")
                .forEach((w) => w.classList.remove("selected"));

            el.classList.add("selected");

            const id = el.dataset.workerId;
            loadWorker(id);
        });
    });
});
