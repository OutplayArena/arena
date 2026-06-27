// logo-link.js — redirect the mkdocs Material header logo to the main app.
//
// By default the logo `<a class="md-logo">` in mkdocs Material links to
// `config.site_url` (https://arena.core-aix.org/docs/), which traps users
// inside the docs without a fast way back to the main app. Rewrite the
// href to https://arena.core-aix.org/ on every page load. Runs after DOM
// ready so the header is rendered, and uses a MutationObserver to re-apply
// the rewrite if Material swaps the header on navigation.
(function () {
  var TARGET = "https://arena.core-aix.org/";

  function rewriteLogo(root) {
    var logos = (root || document).querySelectorAll("a.md-logo");
    for (var i = 0; i < logos.length; i++) {
      var a = logos[i];
      if (a.getAttribute("href") !== TARGET) {
        a.setAttribute("href", TARGET);
        a.setAttribute("target", "_top");
        a.setAttribute("rel", "noopener");
      }
    }
  }

  function start() {
    rewriteLogo(document);
    var obs = new MutationObserver(function () {
      rewriteLogo(document);
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
