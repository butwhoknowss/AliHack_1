/* Plotly time-series chart: data, 12-month running mean, trend line, confidence band. */
(function () {
  "use strict";
  const ETD = window.ETD;

  const dark = () => window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const COLORS = {
    data: "rgba(128,128,128,0.55)",
    get smooth() { return dark() ? "#e6edf3" : "#333333"; },
    trend: "#d55e00",
    band: "rgba(213,94,0,0.15)",
    cData: "rgba(0,114,178,0.35)",
    cSmooth: "#005a8c",
    cTrend: "#0072b2",
    cBand: "rgba(0,114,178,0.12)",
  };

  function runningMean(values, window = 12) {
    const out = new Array(values.length).fill(null);
    const half = Math.floor(window / 2);
    for (let i = 0; i < values.length; i++) {
      let sum = 0, n = 0;
      for (let j = i - half; j < i - half + window; j++) {
        if (j >= 0 && j < values.length && values[j] !== null && values[j] !== undefined) { sum += values[j]; n++; }
      }
      out[i] = n >= window * 0.75 ? sum / n : null;
    }
    return out;
  }

  const mean = (arr) => {
    const v = arr.filter((x) => x !== null && x !== undefined);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0;
  };

  /** Build traces for one analysis result. */
  function tracesFor(res, opts, palette, label) {
    const dates = res.series.map((p) => p.date);
    const useAnomaly = opts.showAnomaly && res.deseasonalize;
    const y = res.series.map((p) => (useAnomaly ? p.anomaly : p.value));
    // Trend line is fitted on anomalies when the seasons were removed; shift it to the data mean for raw view.
    const shift = res.deseasonalize && !useAnomaly ? mean(res.series.map((p) => p.value)) : 0;
    const trendY = res.trend_line.map((p) => (p.value === null ? null : p.value + shift));
    const prefix = label ? label + ": " : "";
    const traces = [];

    if (opts.showCI) {
      traces.push({
        x: res.ci_band.map((p) => p.date),
        y: res.ci_band.map((p) => p.high + shift),
        mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false, type: "scatter",
      });
      traces.push({
        x: res.ci_band.map((p) => p.date),
        y: res.ci_band.map((p) => p.low + shift),
        mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: palette.band,
        name: prefix + "95 % confidence band", hoverinfo: "skip", type: "scatter",
      });
    }
    traces.push({
      x: dates, y, type: "scatter", mode: "lines", connectgaps: false,
      line: { color: palette.data, width: 1 },
      name: prefix + (useAnomaly ? "Monthly anomaly" : "Monthly value"),
      hovertemplate: "%{x|%b %Y}: %{y:.3f} " + res.variable.units + "<extra></extra>",
    });
    traces.push({
      x: dates, y: runningMean(y), type: "scatter", mode: "lines",
      line: { color: palette.smooth, width: 2 }, name: prefix + "12-month running mean", hoverinfo: "skip",
    });
    traces.push({
      x: res.trend_line.map((p) => p.date), y: trendY, type: "scatter", mode: "lines",
      line: { color: palette.trend, width: 3 },
      name: `${prefix}Trend (${ETD.charts.fmt(res.trend.ols.slope_per_decade)} ${res.variable.units}/decade)`,
      hoverinfo: "skip",
    });
    return traces;
  }

  function render(res, opts, compare) {
    const el = document.getElementById("chart");
    el.innerHTML = "";
    const main = { data: COLORS.data, smooth: COLORS.smooth, trend: COLORS.trend, band: COLORS.band };
    const alt = { data: COLORS.cData, smooth: COLORS.cSmooth, trend: COLORS.cTrend, band: COLORS.cBand };
    let traces = tracesFor(res, opts, main, compare ? res.region.name || "Region A" : "");
    if (compare) traces = traces.concat(tracesFor(compare, opts, alt, compare.region.name || "Region B"));

    const useAnomaly = opts.showAnomaly && res.deseasonalize;
    // Follow the page theme (light/dark) so axis text stays readable.
    const css = getComputedStyle(document.documentElement);
    const ink = css.getPropertyValue("--ink").trim() || "#1d2733";
    const grid = css.getPropertyValue("--line").trim() || "#dde3ea";
    const layout = {
      height: 460,
      margin: { l: 60, r: 20, t: 10, b: 10 },
      hovermode: "x unified",
      // Legend above the plot so it never collides with the axis or the range slider.
      legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { size: 11 } },
      xaxis: {
        type: "date", gridcolor: grid, linecolor: grid,
        rangeslider: { visible: true, thickness: 0.06, bgcolor: "rgba(0,0,0,0)", bordercolor: grid },
      },
      yaxis: {
        title: { text: `${useAnomaly ? "Anomaly" : "Value"} (${res.variable.units})` },
        zeroline: useAnomaly, zerolinecolor: ink, gridcolor: grid, linecolor: grid,
      },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", size: 12, color: ink },
      hoverlabel: { font: { color: "#1d2733" }, bgcolor: "#ffffff" },
    };
    Plotly.newPlot(el, traces, layout, { responsive: true, displaylogo: false });
  }

  function fmt(x) {
    if (x === null || x === undefined || Number.isNaN(x)) return "–";
    const ax = Math.abs(x);
    const sign = x > 0 ? "+" : x < 0 ? "−" : "";
    let s;
    if (ax === 0) s = "0";
    else if (ax >= 100) s = ax.toFixed(0);
    else if (ax >= 10) s = ax.toFixed(1);
    else if (ax >= 0.1) s = ax.toFixed(2);
    else if (ax >= 0.001) s = ax.toFixed(3);
    else s = ax.toExponential(1);
    return sign + s;
  }

  function fmtP(p) {
    if (p === null || p === undefined) return "–";
    return p < 0.001 ? "p < 0.001" : "p = " + p.toFixed(3);
  }

  ETD.charts = { render, fmt, fmtP };
})();
