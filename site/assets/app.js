const body = document.body;
const sidebar = document.getElementById("sidebar");
const openButton = document.querySelector("[data-open-sidebar]");
const closeButtons = document.querySelectorAll("[data-close-sidebar]");
const nepalTime = document.getElementById("nepal-time");
const navItems = document.querySelectorAll(".nav-item[href^='#']");

function openSidebar() {
  body.classList.add("sidebar-open");
  openButton?.setAttribute("aria-expanded", "true");
  sidebar?.querySelector("a, button")?.focus();
}

function closeSidebar() {
  body.classList.remove("sidebar-open");
  openButton?.setAttribute("aria-expanded", "false");
}

function updateNepalTime() {
  if (!nepalTime) return;

  const formatter = new Intl.DateTimeFormat("en-NP", {
    timeZone: "Asia/Kathmandu",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });

  nepalTime.textContent = formatter.format(new Date());
}

openButton?.setAttribute("aria-controls", "sidebar");
openButton?.setAttribute("aria-expanded", "false");
openButton?.addEventListener("click", openSidebar);
closeButtons.forEach((button) => button.addEventListener("click", closeSidebar));

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    navItems.forEach((candidate) => {
      candidate.classList.remove("is-active");
      candidate.removeAttribute("aria-current");
    });
    item.classList.add("is-active");
    item.setAttribute("aria-current", "page");
    closeSidebar();
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && body.classList.contains("sidebar-open")) {
    closeSidebar();
    openButton?.focus();
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 900) closeSidebar();
});

updateNepalTime();
setInterval(updateNepalTime, 1000);
