/* Guided demo scenarios: fill the form, run the analysis, narrate step by step. */
(function () {
  "use strict";
  const ETD = window.ETD;
  const $ = (id) => document.getElementById(id);

  let demos = [];
  let active = null;
  let step = 0;

  function setDemos(list) {
    demos = list;
    const sel = $("demo-select");
    list.forEach((d) => {
      const o = document.createElement("option");
      o.value = d.demo_id;
      o.textContent = d.title;
      sel.appendChild(o);
    });
  }

  function showStep() {
    if (!active) return;
    const steps = active.narration_steps;
    $("demo-step").textContent = `(${step + 1}/${steps.length}) ${steps[step]}`;
    $("demo-prev").disabled = step === 0;
    $("demo-next").textContent = step === steps.length - 1 ? "Finish ✓" : "Next ▶";
  }

  function withEndYear(req) {
    return req ? { ...req, end_year: req.end_year || ETD.wizard.lastCompleteYear() } : null;
  }

  async function start(demoId) {
    const demo = demos.find((d) => d.demo_id === demoId);
    if (!demo) return;
    active = demo;
    step = 0;
    $("demo-title").textContent = "Demo: " + demo.title;
    $("demo-story").textContent = demo.story;
    $("demo-banner").hidden = false;
    showStep();
    const req = withEndYear(demo.request);
    ETD.wizard.fill(req);
    await ETD.app.runAnalysis(req, withEndYear(demo.compare_request));
    if (demo.compare_request) ETD.map.setCompareBox(demo.compare_request.region);
  }

  function stop() {
    active = null;
    $("demo-banner").hidden = true;
    $("demo-select").value = "";
    ETD.map.setCompareBox(null);
  }

  function init() {
    $("demo-select").addEventListener("change", (e) => { if (e.target.value) start(e.target.value); });
    $("demo-prev").addEventListener("click", () => { if (step > 0) { step--; showStep(); } });
    $("demo-next").addEventListener("click", () => {
      if (!active) return;
      if (step < active.narration_steps.length - 1) { step++; showStep(); } else stop();
    });
    $("demo-close").addEventListener("click", stop);
  }

  ETD.demos = { init, setDemos, start, stop, isActive: () => !!active };
})();
