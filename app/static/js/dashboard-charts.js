document.addEventListener("DOMContentLoaded", function () {
  const profitCanvas = document.getElementById("dailyProfitChart");
  const volumeCanvas = document.getElementById("volumeChart");
  const expenseCanvas = document.getElementById("expenseChart");

  if (!profitCanvas && !volumeCanvas && !expenseCanvas) return;

  fetch("/api/v1/reports/chart-data")
    .then((response) => response.json())
    .then((data) => {
      // 1. Daily Profit Trend Chart
      if (profitCanvas) {
        new Chart(profitCanvas, {
          type: "line",
          data: {
            labels: data.labels,
            datasets: [
              {
                label: "Net Profit (BDT)",
                data: data.daily_profit,
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.1)",
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointRadius: 4,
                pointBackgroundColor: "#10b981",
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    return `Net Profit: ৳${context.parsed.y.toLocaleString("en-BD", { minimumFractionDigits: 2 })}`;
                  },
                },
              },
            },
            scales: {
              y: {
                grid: { color: "#f1f5f9" },
                ticks: {
                  callback: function (val) {
                    return `৳${val.toLocaleString()}`;
                  },
                },
              },
              x: {
                grid: { display: false },
              },
            },
          },
        });
      }

      // 2. MYR Volume Chart (Purchase vs Sales)
      if (volumeCanvas) {
        new Chart(volumeCanvas, {
          type: "bar",
          data: {
            labels: data.labels,
            datasets: [
              {
                label: "MYR Purchased",
                data: data.myr_purchases,
                backgroundColor: "#0ea5e9",
                borderRadius: 4,
              },
              {
                label: "MYR Sold",
                data: data.myr_sales,
                backgroundColor: "#8b5cf6",
                borderRadius: 4,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: "top" },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} MYR`;
                  },
                },
              },
            },
            scales: {
              y: {
                grid: { color: "#f1f5f9" },
                ticks: {
                  callback: function (val) {
                    return `${val} MYR`;
                  },
                },
              },
              x: {
                grid: { display: false },
              },
            },
          },
        });
      }

      // 3. Operating Expense Breakdown
      if (expenseCanvas && data.expense_categories.labels.length > 0) {
        new Chart(expenseCanvas, {
          type: "doughnut",
          data: {
            labels: data.expense_categories.labels,
            datasets: [
              {
                data: data.expense_categories.data,
                backgroundColor: [
                  "#3b82f6",
                  "#10b981",
                  "#f59e0b",
                  "#ef4444",
                  "#8b5cf6",
                  "#ec4899",
                  "#14b8a6",
                  "#64748b",
                ],
                borderWidth: 1,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: "right" },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    return ` ${context.label}: ৳${context.parsed.toLocaleString("en-BD", { minimumFractionDigits: 2 })}`;
                  },
                },
              },
            },
          },
        });
      }
    })
    .catch((err) => console.error("Error loading dashboard charts:", err));
});
