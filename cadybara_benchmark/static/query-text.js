export const QUERY_TEXT_MAX_LINES = 3;
export const QUERY_TEXT_MAX_CHARS = 512;

export function formatCollapsibleQueryText(text, escapeHtml) {
  const raw = text || "";
  if (!raw) {
    return `<span class="text-body-secondary small">—</span>`;
  }
  const preview = raw.slice(0, QUERY_TEXT_MAX_CHARS);
  return `
    <div class="query-text-toggle is-collapsed" role="button" tabindex="0" aria-expanded="false">
      <span class="query-text-preview">${escapeHtml(preview)}</span>
      <span class="query-text-full"></span>
      <span class="query-text-more" aria-hidden="true">[...]</span>
    </div>
  `;
}

export function prepareQueryTextToggle(toggle, text) {
  if (!toggle) return;
  toggle.dataset.fullText = text || "";
  const full = toggle.querySelector(".query-text-full");
  if (full) full.textContent = "";
}

export function getQueryTextRaw(toggle) {
  if (!toggle) return "";
  if (toggle.dataset.fullText !== undefined) {
    return toggle.dataset.fullText;
  }
  const full = toggle.querySelector(".query-text-full");
  return full?.textContent || toggle.querySelector(".query-text-preview")?.textContent || "";
}

export function toggleQueryText(toggle) {
  const collapsed = toggle.classList.toggle("is-collapsed");
  toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  if (!collapsed) {
    const full = toggle.querySelector(".query-text-full");
    if (full && !full.textContent) {
      full.textContent = getQueryTextRaw(toggle);
    }
  }
}

export function finalizeCollapsibleQueryTexts(root = document) {
  root.querySelectorAll(".query-text-toggle:not([data-query-text-finalized])").forEach((toggle) => {
    toggle.dataset.queryTextFinalized = "true";
    const preview = toggle.querySelector(".query-text-preview");
    if (!preview) return;

    const raw = getQueryTextRaw(toggle);
    const needsChar = raw.length > QUERY_TEXT_MAX_CHARS;
    toggle.classList.add("is-collapsed");
    const needsLine = preview.scrollHeight > preview.clientHeight + 1;
    if (!needsChar && !needsLine) {
      toggle.replaceWith(document.createTextNode(raw));
      return;
    }
    toggle.classList.add("is-truncatable");
  });
}

export function bindCollapsibleQueryText(root = document) {
  if (root.dataset.queryTextBound === "true") return;
  root.dataset.queryTextBound = "true";

  root.addEventListener("click", (event) => {
    const toggle = event.target.closest(".query-text-toggle.is-truncatable");
    if (!toggle) return;
    event.stopPropagation();
    toggleQueryText(toggle);
  });

  root.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const toggle = event.target.closest(".query-text-toggle.is-truncatable");
    if (!toggle) return;
    event.preventDefault();
    event.stopPropagation();
    toggleQueryText(toggle);
  });
}
