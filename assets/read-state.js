
(function () {
  var STORAGE_KEY = "hanou-career:readJobs:v1";
  var FILTER_KEY = "hanou-career:readFilter:v1";

  function loadRead() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return new Set(Array.isArray(arr) ? arr : []);
    } catch (e) {
      return new Set();
    }
  }

  function saveRead(set) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  }

  function loadFilter() {
    var v = localStorage.getItem(FILTER_KEY);
    return v === "all" || v === "read" || v === "unread" ? v : "unread";
  }

  function saveFilter(v) {
    localStorage.setItem(FILTER_KEY, v);
  }

  function setHidden(el, hidden) {
    if (!el) return;
    if (hidden) el.setAttribute("hidden", "");
    else el.removeAttribute("hidden");
  }

  function refreshCard(card, readSet) {
    var id = card.getAttribute("data-job-id");
    var isRead = readSet.has(id);
    card.classList.toggle("is-read", isRead);
    var pill = card.querySelector(".read-pill");
    setHidden(pill, !isRead);
    setHidden(card.querySelector(".js-mark-read"), isRead);
    setHidden(card.querySelector(".js-mark-unread"), !isRead);
  }

  function refreshNotesPage(readSet) {
    var id = document.body.getAttribute("data-job-id");
    if (!id) return;
    var isRead = readSet.has(id);
    document.body.classList.toggle("is-read", isRead);
    setHidden(document.querySelector(".read-pill"), !isRead);
    setHidden(document.querySelector(".js-mark-read"), isRead);
    setHidden(document.querySelector(".js-mark-unread"), !isRead);
  }

  function applyFilter(filter, readSet) {
    var cards = document.querySelectorAll(".job-card[data-job-id]");
    var visible = 0;
    cards.forEach(function (card) {
      var id = card.getAttribute("data-job-id");
      var isRead = readSet.has(id);
      var show =
        filter === "all" ||
        (filter === "unread" && !isRead) ||
        (filter === "read" && isRead);
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });
    var empty = document.getElementById("empty-filter");
    setHidden(empty, visible !== 0 || cards.length === 0);
    var count = document.getElementById("job-count");
    if (count) {
      var total = cards.length;
      var unread = 0;
      cards.forEach(function (c) {
        if (!readSet.has(c.getAttribute("data-job-id"))) unread += 1;
      });
      var base = count.getAttribute("data-base") || count.textContent;
      if (!count.getAttribute("data-base")) count.setAttribute("data-base", base);
      count.textContent =
        unread + " ungelesen · " + total + " gesamt · Filter: " +
        (filter === "unread" ? "Ungelesen" : filter === "read" ? "Gelesen" : "Alle");
    }
    document.querySelectorAll("[data-filter]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-filter") === filter);
    });
  }

  function paint() {
    var readSet = loadRead();
    document.querySelectorAll(".job-card[data-job-id]").forEach(function (card) {
      refreshCard(card, readSet);
    });
    refreshNotesPage(readSet);
    if (document.querySelector(".job-list")) {
      applyFilter(loadFilter(), readSet);
    }
  }

  function mark(id, asRead) {
    if (!id) return;
    var readSet = loadRead();
    if (asRead) readSet.add(id);
    else readSet.delete(id);
    saveRead(readSet);
    paint();
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!(t instanceof Element)) return;
    var readBtn = t.closest(".js-mark-read");
    if (readBtn) {
      ev.preventDefault();
      mark(readBtn.getAttribute("data-job-id"), true);
      return;
    }
    var unreadBtn = t.closest(".js-mark-unread");
    if (unreadBtn) {
      ev.preventDefault();
      mark(unreadBtn.getAttribute("data-job-id"), false);
      return;
    }
    var filterBtn = t.closest("[data-filter]");
    if (filterBtn) {
      ev.preventDefault();
      saveFilter(filterBtn.getAttribute("data-filter"));
      paint();
      return;
    }
    if (t.closest("#clear-read")) {
      ev.preventDefault();
      if (window.confirm("Alle Gelesen-Markierungen in diesem Browser löschen?")) {
        localStorage.removeItem(STORAGE_KEY);
        paint();
      }
    }
  });

  // Opening a job detail page counts as started review → mark read.
  var detailId = document.body.getAttribute("data-job-id");
  if (detailId) {
    var readSet = loadRead();
    if (!readSet.has(detailId)) {
      readSet.add(detailId);
      saveRead(readSet);
    }
  }

  paint();
})();
