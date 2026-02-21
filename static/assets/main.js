   const sidebarToggleBtns = document.querySelectorAll(".sidebar-toggle");
const sidebar = document.querySelector(".sidebar");
const searchForm = document.querySelector(".search-form");
const themeToggleBtn = document.querySelector(".theme-toggle");
const themeIcon = themeToggleBtn ? themeToggleBtn.querySelector(".theme-icon") : null;
const themeText = themeToggleBtn ? themeToggleBtn.querySelector(".theme-text") : null;
const menuLinks = document.querySelectorAll(".menu-link");
// Updates the theme icon based on current theme and sidebar state
const updateThemeIcon = () => {
  if (!themeIcon) return;
  const isDark = document.body.classList.contains("dark-theme");
  themeIcon.textContent = isDark ? "light_mode" : "dark_mode";
  if (themeText) themeText.textContent = isDark ? "Light Mode" : "Dark Mode";
};
// Apply dark theme if saved or system prefers, then update icon
const savedTheme = localStorage.getItem("theme");
const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
const shouldUseDarkTheme = savedTheme === "dark" || (!savedTheme && systemPrefersDark);
document.body.classList.toggle("dark-theme", shouldUseDarkTheme);
document.documentElement.classList.toggle("dark", shouldUseDarkTheme);
updateThemeIcon();
// Toggle between themes on theme button click
if (themeToggleBtn) {
  themeToggleBtn.addEventListener("click", () => {
    const isDark = document.body.classList.toggle("dark-theme");
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("theme", isDark ? "dark" : "light");
    updateThemeIcon();
  });
}

const setActiveMenuLink = (activeLink) => {
  if (!activeLink) return;
  menuLinks.forEach((link) => link.classList.remove("active"));
  activeLink.classList.add("active");
};

menuLinks.forEach((link) => {
  link.addEventListener("click", () => setActiveMenuLink(link));
});

document.body.addEventListener("htmx:beforeRequest", (event) => {
  const trigger = event.detail && event.detail.elt;
  if (trigger && trigger.classList && trigger.classList.contains("menu-link")) {
    setActiveMenuLink(trigger);
  }
});
// Toggle sidebar collapsed state on buttons click
sidebarToggleBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
    updateThemeIcon();
  });
});
// Expand the sidebar when the search form is clicked
if (searchForm && sidebar) {
  searchForm.addEventListener("click", () => {
    if (sidebar.classList.contains("collapsed")) {
      sidebar.classList.remove("collapsed");
      const input = searchForm.querySelector("input");
      if (input) input.focus();
    }
  });
}
// Expand sidebar by default on large screens
if (window.innerWidth > 768 && sidebar) sidebar.classList.remove("collapsed");
