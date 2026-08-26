/**
 * trend_chart.js — ClearScan Trend View
 *
 * /trends endpoint se data leke ek line chart (risk level over time) aur
 * ek bar chart (kaunse terms sabse zyada baar aaye) render karta hai.
 * Koi external chart library nahi — hand-rolled SVG, tumhare stack
 * (vanilla JS/HTML/CSS) ke saath consistent.
 *
 * Usage:
 *   <div id="trend-container"></div>
 *   <script src="/static/js/trend_chart.js"></script>
 *   <script>
 *     fetch('/trends').then(r => r.json()).then(data => {
 *       renderTrendChart({ container: document.getElementById('trend-container'), data });
 *     });
 *   </script>
 */

(function (global) {
  "use strict";

  const RISK_LABELS = { 0: "Unknown", 1: "Low", 2: "Medium", 3: "High" };
  const RISK_COLORS = { 0: "#5a5c70", 1: "#3ecf8e", 2: "#f5a623", 3: "#e5484d" };

  function _emptyState(container, message) {
    container.innerHTML =
      '<p style="opacity:0.6;font-size:13px;text-align:center;padding:20px 0;">' +
      message +
      "</p>";
  }

  function _lineChart(points, width, height) {
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.style.display = "block";

    const padding = { top: 20, right: 20, bottom: 36, left: 36 };
    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    // y-axis gridlines for risk levels 0-3
    [0, 1, 2, 3].forEach((level) => {
      const y = padding.top + plotH - (level / 3) * plotH;
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", padding.left);
      line.setAttribute("x2", width - padding.right);
      line.setAttribute("y1", y);
      line.setAttribute("y2", y);
      line.setAttribute("stroke", "#22232f");
      line.setAttribute("stroke-width", "1");
      svg.appendChild(line);

      const label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", padding.left - 8);
      label.setAttribute("y", y + 4);
      label.setAttribute("text-anchor", "end");
      label.setAttribute("font-size", "10");
      label.setAttribute("fill", "#7a7c90");
      label.textContent = RISK_LABELS[level];
      svg.appendChild(label);
    });

    if (points.length === 0) return svg;

    const stepX = points.length > 1 ? plotW / (points.length - 1) : 0;
    const coords = points.map((p, i) => ({
      x: padding.left + stepX * i,
      y: padding.top + plotH - (p.risk_score / 3) * plotH,
      p,
    }));

    if (coords.length > 1) {
      const pathD = coords
        .map((c, i) => (i === 0 ? `M ${c.x} ${c.y}` : `L ${c.x} ${c.y}`))
        .join(" ");
      const path = document.createElementNS(svgNS, "path");
      path.setAttribute("d", pathD);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "#8b8cf5");
      path.setAttribute("stroke-width", "2");
      svg.appendChild(path);
    }

    coords.forEach((c) => {
      const dot = document.createElementNS(svgNS, "circle");
      dot.setAttribute("cx", c.x);
      dot.setAttribute("cy", c.y);
      dot.setAttribute("r", "5");
      dot.setAttribute("fill", RISK_COLORS[c.p.risk_score] || "#8b8cf5");
      dot.setAttribute("stroke", "#0d0e14");
      dot.setAttribute("stroke-width", "1.5");

      const title = document.createElementNS(svgNS, "title");
      title.textContent = `${c.p.date} — ${RISK_LABELS[c.p.risk_score]}`;
      dot.appendChild(title);

      svg.appendChild(dot);

      const label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", c.x);
      label.setAttribute("y", height - 12);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "9");
      label.setAttribute("fill", "#7a7c90");
      label.textContent = c.p.date.split(",")[0]; // just the date part
      svg.appendChild(label);
    });

    return svg;
  }

  function _barChart(termFrequency, width) {
    const entries = Object.entries(termFrequency).sort((a, b) => b[1] - a[1]).slice(0, 8);
    if (entries.length === 0) return null;

    const maxCount = Math.max(...entries.map((e) => e[1]));
    const rowH = 26;
    const height = entries.length * rowH + 10;
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");

    const labelW = 130;
    const barMaxW = width - labelW - 40;

    entries.forEach(([term, count], i) => {
      const y = i * rowH + 8;
      const barW = (count / maxCount) * barMaxW;

      const label = document.createElementNS(svgNS, "text");
      label.setAttribute("x", labelW - 8);
      label.setAttribute("y", y + 12);
      label.setAttribute("text-anchor", "end");
      label.setAttribute("font-size", "11");
      label.setAttribute("fill", "#c8c9d6");
      label.textContent = term;
      svg.appendChild(label);

      const bar = document.createElementNS(svgNS, "rect");
      bar.setAttribute("x", labelW);
      bar.setAttribute("y", y);
      bar.setAttribute("width", Math.max(barW, 2));
      bar.setAttribute("height", 16);
      bar.setAttribute("rx", 3);
      bar.setAttribute("fill", "#8b8cf5");
      svg.appendChild(bar);

      const countLabel = document.createElementNS(svgNS, "text");
      countLabel.setAttribute("x", labelW + barW + 6);
      countLabel.setAttribute("y", y + 12);
      countLabel.setAttribute("font-size", "10");
      countLabel.setAttribute("fill", "#7a7c90");
      countLabel.textContent = count;
      svg.appendChild(countLabel);
    });

    return svg;
  }

  function renderTrendChart(opts) {
    const { container, data } = opts;
    if (!container) {
      console.error("renderTrendChart: container required");
      return;
    }

    const points = (data && data.points) || [];
    const termFrequency = (data && data.term_frequency) || {};

    container.innerHTML = "";

    if (points.length === 0) {
      _emptyState(container, "No report history yet — analyze a few reports to see trends here.");
      return;
    }

    const lineWrap = document.createElement("div");
    const lineHeading = document.createElement("p");
    lineHeading.style.cssText = "font-size:12px;opacity:0.6;margin:0 0 6px;";
    lineHeading.textContent = "Risk level over time";
    lineWrap.appendChild(lineHeading);
    lineWrap.appendChild(_lineChart(points, 380, 180));
    container.appendChild(lineWrap);

    const barSvg = _barChart(termFrequency, 380);
    if (barSvg) {
      const barWrap = document.createElement("div");
      barWrap.style.marginTop = "18px";
      const barHeading = document.createElement("p");
      barHeading.style.cssText = "font-size:12px;opacity:0.6;margin:0 0 6px;";
      barHeading.textContent = "Most frequent findings";
      barWrap.appendChild(barHeading);
      barWrap.appendChild(barSvg);
      container.appendChild(barWrap);
    }
  }

  global.renderTrendChart = renderTrendChart;
})(window);