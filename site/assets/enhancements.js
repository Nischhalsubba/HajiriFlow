const chartObserver = new MutationObserver(() => {
  const donut = document.querySelector(".donut");
  if (!donut || donut.dataset.enhanced === "true") return;
  const value = Number.parseInt(donut.querySelector("strong")?.textContent || "0", 10);
  const rounded = Math.max(0, Math.min(100, Math.round(value / 5) * 5));
  donut.classList.add(`p-${rounded}`);
  donut.removeAttribute("style");
  donut.dataset.enhanced = "true";
});

chartObserver.observe(document.getElementById("workspace"), { childList: true, subtree: true });
