function enhanceAttendanceChart() {
  const donut = document.querySelector(".donut");
  if (!donut || donut.dataset.enhanced === "true") return;
  const value = Number.parseInt(donut.querySelector("strong")?.textContent || "0", 10);
  const rounded = Math.max(0, Math.min(100, Math.round(value / 5) * 5));
  donut.classList.add(`p-${rounded}`);
  donut.removeAttribute("style");
  donut.dataset.enhanced = "true";
}

function simulateDeviceAction(id, message, sync) {
  const device = state.devices.find((item) => item.id === Number(id));
  if (!device) return;
  toast(`${device.name}: operation started.`, "info");
  setTimeout(() => {
    device.status = "Online";
    if (sync) device.lastSync = "just now";
    addActivity("devices", message, device.name);
    saveState();
    render();
    toast(`${device.name}: ${message.toLowerCase()}.`);
  }, 650);
}

const chartObserver = new MutationObserver(enhanceAttendanceChart);
chartObserver.observe(document.getElementById("workspace"), { childList: true, subtree: true });
enhanceAttendanceChart();
