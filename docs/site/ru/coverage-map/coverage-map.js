(() => {
  const MOBILE_QUERY = "(max-width: 767px), (hover: none) and (pointer: coarse)";
  const DEFAULT_CENTER = [20, 20];
  const DATASET_VERSION = "v6.1";

  const TEXT = {
    ru: {
      lat: "Широта",
      lon: "Долгота",
      copied: "Координаты скопированы",
      copyFailed: "Не удалось скопировать",
      switchToLight: "Switch to light theme",
      switchToDark: "Switch to dark theme",
    },
    en: {
      lat: "Lat",
      lon: "Lon",
      copied: "Coordinates copied",
      copyFailed: "Copy failed",
      switchToLight: "Switch to light theme",
      switchToDark: "Switch to dark theme",
    },
  };

  function normalizeLocale(value) {
    if (!value) {
      return null;
    }

    const normalized = String(value).toLowerCase();
    if (normalized.startsWith("ru")) {
      return "ru";
    }
    if (normalized.startsWith("en")) {
      return "en";
    }

    return null;
  }

  function getLocale() {
    const params = new URLSearchParams(window.location.search);
    return (
      normalizeLocale(params.get("lng")) ||
      normalizeLocale(params.get("lang")) ||
      normalizeLocale(document.documentElement.lang) ||
      normalizeLocale(navigator.language) ||
      "en"
    );
  }

  function isMobileLayout() {
    return window.matchMedia &&
      window.matchMedia(MOBILE_QUERY).matches;
  }


  function showInitError(message, details) {
    const mapEl = document.getElementById("map") || document.body;
    if (!mapEl) {
      return;
    }

    const errorEl = document.createElement("div");
    errorEl.className = "map-error";
    errorEl.innerHTML = `
      <strong>${message}</strong>
      ${details ? `<span>${details}</span>` : ""}
    `;

    mapEl.appendChild(errorEl);
  }


  function isThemeToggleEnabled() {
    const value = new URLSearchParams(window.location.search)
      .get("themeToggle");

    if (value === null) {
      return true;
    }

    return !["0", "false", "off", "no", "hidden"].includes(
      String(value).trim().toLowerCase()
    );
  }

  function getCurrentTheme() {
    return document.documentElement.dataset.theme ||
      window.__silamCoverageTheme ||
      "light";
  }

  function getCoveragePalette(theme) {
    // Светлая тема сохраняет яркие checkbox/label colors и отдельные мягкие badge colors.
    // Тёмная тема сохраняет более спокойные цвета, подобранные раньше отдельно.
    return theme === "dark"
      ? {
          europe: {
            stroke: "rgba(251,191,36,1)",
            fill: "rgba(251,191,36,0.24)",
            label: "rgba(220,174,57,1)",
            badge: "rgba(226,184,78,1)",
          },
          regional: {
            stroke: "rgba(52,211,153,1)",
            fill: "rgba(52,211,153,0.24)",
            label: "rgba(80,190,135,1)",
            badge: "rgba(92,196,146,1)",
          },
          hires: {
            stroke: "rgba(56,189,248,1)",
            fill: "rgba(56,189,248,0.24)",
            label: "rgba(80,165,215,1)",
            badge: "rgba(92,170,224,1)",
          },
          badgeBorder: "rgba(255,255,255,0.22)",
        }
      : {
          europe: {
            stroke: "rgba(255,200,0,1)",
            fill: "rgba(255,255,0,0.2)",
            label: "rgba(255,200,0,1)",
            badge: "rgba(255,228,141,1)",
          },
          regional: {
            stroke: "rgba(0,255,0,1)",
            fill: "rgba(0,255,0,0.2)",
            label: "rgba(0,255,0,1)",
            badge: "rgba(104,255,130,1)",
          },
          hires: {
            stroke: "rgba(0,120,255,1)",
            fill: "rgba(0,120,255,0.2)",
            label: "rgba(0,120,255,1)",
            badge: "rgba(165,209,255,1)",
          },
          badgeBorder: "rgba(0,0,0,0.15)",
        };
  }

  function makeBadgeBg(color) {
    if (!(typeof color === "string" && color.startsWith("rgba("))) {
      return color;
    }

    // Единая прозрачность цветной плашки для light/dark.
    return color.replace(
      /rgba\((\s*\d+\s*),(\s*\d+\s*),(\s*\d+\s*),\s*([0-9.]+)\s*\)/,
      "rgba($1,$2,$3,0.72)"
    );
  }


  function formatCoordinateDisplay(coordinate, text) {
    return `${text.lat}: ${coordinate[1].toFixed(3)}, ${text.lon}: ${coordinate[0].toFixed(3)}`;
  }

  function formatCoordinateClipboard(coordinate) {
    // Буфер обмена получает координаты в порядке lat, lon.
    return `${coordinate[1].toFixed(6)}, ${coordinate[0].toFixed(6)}`;
  }

  function copyTextToClipboard(value) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(value);
    }

    return new Promise((resolve, reject) => {
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      textarea.style.top = "0";

      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();

      try {
        const ok = document.execCommand("copy");
        document.body.removeChild(textarea);

        if (ok) {
          resolve();
        } else {
          reject(new Error("document.execCommand('copy') returned false"));
        }
      } catch (err) {
        document.body.removeChild(textarea);
        reject(err);
      }
    });
  }

  function showCopyToast(message, placement = {}) {
    let toastEl = document.querySelector(".copy-toast");
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.className = "copy-toast";
      toastEl.setAttribute("role", "status");
      toastEl.setAttribute("aria-live", "polite");
      document.body.appendChild(toastEl);
    }

    toastEl.classList.remove(
      "is-mobile-center",
      "is-below-element",
      "is-fallback"
    );

    toastEl.style.left = "";
    toastEl.style.top = "";
    toastEl.style.bottom = "";
    toastEl.style.transform = "";

    if (placement.type === "mobile-center") {
      toastEl.classList.add("is-mobile-center");
    } else if (placement.type === "below-element" && placement.element) {
      const rect = placement.element.getBoundingClientRect();
      toastEl.classList.add("is-below-element");
      toastEl.style.left = `${rect.left + rect.width / 2}px`;
      toastEl.style.top = `${rect.bottom + 8}px`;
    } else {
      toastEl.classList.add("is-fallback");
    }

    toastEl.textContent = message;
    toastEl.classList.add("is-visible");

    window.clearTimeout(showCopyToast.hideTimer);
    showCopyToast.hideTimer = window.setTimeout(() => {
      toastEl.classList.remove("is-visible");
    }, 1200);
  }

  function copyCoordinate(coordinate, text, placement) {
    return copyTextToClipboard(formatCoordinateClipboard(coordinate))
      .then(() => showCopyToast(text.copied, placement))
      .catch(() => showCopyToast(text.copyFailed, placement));
  }

  function buildCoverageStyle(entry) {
    return new ol.style.Style({
      stroke: new ol.style.Stroke({
        color: entry.stroke,
        width: 0.5,
      }),
      fill: new ol.style.Fill({
        color: entry.fill,
      }),
    });
  }

  function createCoverageLayer(coords, paletteEntry) {
    const polygonCoords = coords.map((coord) =>
      ol.proj.fromLonLat([coord[1], coord[0]])
    );

    const feature = new ol.Feature({
      geometry: new ol.geom.Polygon([polygonCoords]),
    });

    const source = new ol.source.Vector({
      features: [feature],
    });

    const layer = new ol.layer.Vector({
      source,
      style: buildCoverageStyle(paletteEntry),
    });

    return { layer, source };
  }


  function getThemeIconSvg(iconName) {
    if (iconName === "sun") {
      return `
        <svg class="theme-toggle-symbol theme-toggle-symbol-sun" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2" />
          <path
            d="M12 2.75v2.1M12 19.15v2.1M4.85 4.85l1.49 1.49M17.66 17.66l1.49 1.49M2.75 12h2.1M19.15 12h2.1M4.85 19.15l1.49-1.49M17.66 6.34l1.49-1.49"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
        </svg>
      `;
    }

    return `
      <svg class="theme-toggle-symbol theme-toggle-symbol-moon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path
          d="M20.2 14.55A7.5 7.5 0 0 1 9.45 3.8 8.5 8.5 0 1 0 20.2 14.55Z"
          fill="currentColor"
        />
      </svg>
    `;
  }

  function normalizeZoomButtons() {
    const zoomIn = document.querySelector(".ol-zoom .ol-zoom-in");
    const zoomOut = document.querySelector(".ol-zoom .ol-zoom-out");

    [
      [zoomIn, "plus"],
      [zoomOut, "minus"],
    ].forEach(([button, symbol]) => {
      if (!button || button.querySelector(".zoom-symbol")) {
        return;
      }

      button.textContent = "";

      const symbolEl = document.createElement("span");
      symbolEl.className = `zoom-symbol zoom-symbol-${symbol}`;
      symbolEl.setAttribute("aria-hidden", "true");

      button.appendChild(symbolEl);
    });
  }


  function normalizeRotateButton() {
    const compassEl = document.querySelector(".ol-rotate .ol-compass");
    if (!compassEl || compassEl.querySelector(".rotate-symbol")) {
      return;
    }

    compassEl.textContent = "";
    compassEl.insertAdjacentHTML(
      "beforeend",
      `
        <svg class="rotate-symbol rotate-symbol-arrow" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path
            d="M12 3.75 5.35 10.9H8.85V20.25H15.15V10.9H18.65L12 3.75Z"
            fill="none"
            stroke="currentColor"
            stroke-width="2.05"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
        </svg>
      `
    );
  }

  function stopMapDragOnControl(element) {
    if (!element || element.dataset.silamEventsBound) {
      return;
    }

    element.addEventListener("mousedown", (event) => event.stopPropagation());
    element.addEventListener("touchstart", (event) => event.stopPropagation(), {
      passive: true,
    });
    element.dataset.silamEventsBound = "true";
  }

  function addCoverageLegend(map, items, onChange) {
    const el = document.createElement("div");
    el.className = "ol-unselectable ol-control legend-control";

    el.innerHTML = items.map((item) => `
      <div class="row">
        <label class="row">
          <input
            type="checkbox"
            data-layer-id="${item.id}"
            checked
            style="accent-color:${item.palette.label};"
          />
          <span class="name">${item.name}</span>
        </label>
      </div>
    `).join("");

    stopMapDragOnControl(el);
    map.addControl(new ol.control.Control({ element: el }));

    el.querySelectorAll('input[type="checkbox"][data-layer-id]').forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        const id = checkbox.getAttribute("data-layer-id");
        const target = items.find((item) => item.id === id);

        if (target && target.layer) {
          target.layer.setVisible(checkbox.checked);
          onChange();
        }
      });
    });

    return el;
  }

  function updateLegendCheckboxColors(legendEl, items) {
    if (!legendEl) {
      return;
    }

    legendEl
      .querySelectorAll('input[type="checkbox"][data-layer-id]')
      .forEach((checkbox) => {
        const id = checkbox.getAttribute("data-layer-id");
        const item = items.find((candidate) => candidate.id === id);

        if (item) {
          checkbox.style.accentColor = item.palette.label;
        }
      });
  }

  function arrangePrimaryControls(legendEl) {
    const zoomEl = document.querySelector(".ol-zoom");
    if (!legendEl) {
      return null;
    }

    normalizeZoomButtons();

    let clusterEl = legendEl.closest(".coverage-control-cluster");
    if (!clusterEl) {
      const controlsContainer =
        legendEl.parentElement ||
        (zoomEl && zoomEl.parentElement);

      if (!controlsContainer) {
        return null;
      }

      clusterEl = document.createElement("div");
      clusterEl.className = "ol-unselectable ol-control coverage-control-cluster";
      controlsContainer.insertBefore(clusterEl, legendEl);
    }

    if (!clusterEl.contains(legendEl)) {
      clusterEl.appendChild(legendEl);
    }

    // Desktop: zoom слева рядом с легендой.
    // Mobile: zoom переносится в правую колонку.
    if (!isMobileLayout() && zoomEl && zoomEl.parentElement !== clusterEl) {
      clusterEl.insertBefore(zoomEl, legendEl);
    }

    stopMapDragOnControl(clusterEl);
    return clusterEl;
  }

  function arrangeAuxControls(themeToggleEl) {
    normalizeRotateButton();

    const rotateEl = document.querySelector(".ol-rotate");
    const zoomEl = document.querySelector(".ol-zoom");

    if (!themeToggleEl && !rotateEl && !zoomEl) {
      return null;
    }

    let clusterEl =
      (themeToggleEl && themeToggleEl.closest(".map-aux-control-cluster")) ||
      (rotateEl && rotateEl.closest(".map-aux-control-cluster")) ||
      (isMobileLayout() && zoomEl && zoomEl.closest(".map-aux-control-cluster"));

    if (!clusterEl) {
      const controlsContainer =
        (themeToggleEl && themeToggleEl.parentElement) ||
        (rotateEl && rotateEl.parentElement) ||
        (zoomEl && zoomEl.parentElement);

      if (!controlsContainer) {
        return null;
      }

      clusterEl = document.createElement("div");
      clusterEl.className = "ol-unselectable ol-control map-aux-control-cluster";
      controlsContainer.insertBefore(clusterEl, themeToggleEl || rotateEl || zoomEl);
    }

    // Порядок в правой колонке:
    // 1) theme toggle
    // 2) zoom на mobile
    // 3) rotate
    if (themeToggleEl && themeToggleEl.parentElement !== clusterEl) {
      clusterEl.appendChild(themeToggleEl);
    }

    if (isMobileLayout() && zoomEl && zoomEl.parentElement !== clusterEl) {
      clusterEl.appendChild(zoomEl);
    }

    if (rotateEl && rotateEl.parentElement !== clusterEl) {
      clusterEl.appendChild(rotateEl);
    }

    stopMapDragOnControl(clusterEl);
    return clusterEl;
  }

  function arrangeInfoWindowPlacement(mapEl, legendEl, infoWindow) {
    if (!mapEl || !legendEl || !infoWindow) {
      return;
    }

    if (isMobileLayout()) {
      if (infoWindow.parentElement !== legendEl) {
        legendEl.appendChild(infoWindow);
      }
      infoWindow.classList.add("legend-info");
      infoWindow.style.left = "";
      infoWindow.style.top = "";
      return;
    }

    if (infoWindow.parentElement !== mapEl) {
      mapEl.appendChild(infoWindow);
    }
    infoWindow.classList.remove("legend-info");
  }

  function addLocalThemeToggle(map, onThemeChange) {
    const el = document.createElement("div");
    el.className = "ol-unselectable ol-control theme-toggle-control";

    const button = document.createElement("button");
    button.type = "button";

    function updateButton() {
      const theme = getCurrentTheme() === "dark" ? "dark" : "light";
      const iconName = theme === "dark" ? "sun" : "moon";

      button.dataset.icon = iconName;
      button.innerHTML = getThemeIconSvg(iconName);
      button.title = theme === "dark"
        ? TEXT.en.switchToLight
        : TEXT.en.switchToDark;
      button.setAttribute("aria-label", button.title);
    }

    button.addEventListener("click", () => {
      const current = getCurrentTheme() === "dark" ? "dark" : "light";
      const next = current === "dark" ? "light" : "dark";

      document.documentElement.dataset.theme = next;
      window.__silamCoverageTheme = next;

      try {
        window.localStorage.setItem("docusaurus-theme", next);
      } catch (err) {
        // localStorage может быть недоступен в некоторых режимах браузера.
      }

      updateButton();
      onThemeChange(next);
    });

    updateButton();
    el.appendChild(button);
    stopMapDragOnControl(el);

    map.addControl(new ol.control.Control({ element: el }));
    return el;
  }

  function initCoverageMap() {
    if (typeof ol === "undefined") {
      showInitError(
        "Coverage map did not start",
        "OpenLayers was not loaded. Check internet access or the CDN script."
      );
      return;
    }

    if (typeof rotatedPolygon === "undefined" || typeof rotatedPolygonRegional === "undefined") {
      showInitError(
        "Coverage polygons were not loaded",
        "Make sure rotatedPolygon.js is in the same folder as index.html."
      );
      return;
    }

    const locale = getLocale();
    const text = TEXT[locale] || TEXT.en;
    document.documentElement.lang = locale;

    const mapEl = document.getElementById("map");
    const infoWindow = document.getElementById("info-window");
    if (!mapEl || !infoWindow) {
      return;
    }

    let currentTheme = getCurrentTheme();
    let coveragePalette = getCoveragePalette(currentTheme);

    const europeCoverage = createCoverageLayer(rotatedPolygon, coveragePalette.europe);
    const regionalCoverage = createCoverageLayer(rotatedPolygonRegional, coveragePalette.regional);

    let hiresCoverage = null;
    if (typeof rotatedPolygonHires !== "undefined") {
      hiresCoverage = createCoverageLayer(rotatedPolygonHires, coveragePalette.hires);
    }

    const rasterLayer = new ol.layer.Tile({
      source: new ol.source.OSM(),
    });

    const coverageItems = [
      {
        id: "regional",
        name: `SILAM Northern Europe (${DATASET_VERSION})`,
        paletteKey: "regional",
        palette: coveragePalette.regional,
        layer: regionalCoverage.layer,
      },
      {
        id: "europe",
        name: `SILAM Europe (${DATASET_VERSION})`,
        paletteKey: "europe",
        palette: coveragePalette.europe,
        layer: europeCoverage.layer,
      },
    ];

    if (hiresCoverage) {
      coverageItems.unshift({
        id: "hires",
        name: `SILAM Finland (${DATASET_VERSION})`,
        paletteKey: "hires",
        palette: coveragePalette.hires,
        layer: hiresCoverage.layer,
      });
    }

    const layers = [
      rasterLayer,
      europeCoverage.layer,
      regionalCoverage.layer,
    ];

    if (hiresCoverage) {
      layers.push(hiresCoverage.layer);
    }

    const map = new ol.Map({
      target: "map",
      layers,
      view: new ol.View({
        center: ol.proj.fromLonLat(DEFAULT_CENTER),
        zoom: isMobileLayout() ? 6 : 4,
      }),
    });

    let legendEl = null;
    let themeToggleEl = null;
    let mobileInfoFrame = null;

    function getActiveCoverageAtPixel(pixel) {
      let activeItem = null;

      map.forEachFeatureAtPixel(pixel, (feature, layer) => {
        activeItem = coverageItems.find((item) => item.layer === layer) || null;
        return Boolean(activeItem);
      });

      return activeItem;
    }

    function renderInfo(coordinate, pixel) {
      const activeItem = getActiveCoverageAtPixel(pixel);
      const coordText = formatCoordinateDisplay(coordinate, text);

      if (isMobileLayout()) {
        const badgeBg = activeItem ? makeBadgeBg(activeItem.palette.badge) : "";
        const activeClass = badgeBg ? " has-active-coverage" : " no-active-coverage";
        const activeStyle = badgeBg
          ? ` style="--coverage-active-bg:${badgeBg};border-color:${coveragePalette.badgeBorder};"`
          : "";

        const copyValue = formatCoordinateClipboard(coordinate);
        infoWindow.innerHTML = `<div class="mobile-coordinate-badge${activeClass}"${activeStyle} role="button" tabindex="0" title="${text.copied}" data-copy-value="${copyValue}">${coordText}</div>`;
        return;
      }

      if (activeItem) {
        const badgeBg = makeBadgeBg(activeItem.palette.badge);
        infoWindow.innerHTML = `
          <div class="coverage-hover-badge-wrap">
            <span
              class="coverage-hover-badge"
              style="--coverage-active-bg:${badgeBg};border-color:${coveragePalette.badgeBorder};"
            >
              ${activeItem.name}
            </span>
          </div>
          ${coordText}
        `;
        return;
      }

      infoWindow.textContent = coordText;
    }

    function updateMobileCenterInfo() {
      mobileInfoFrame = null;

      if (!isMobileLayout()) {
        return;
      }

      const view = map.getView();
      const centerCoordinate = view.getCenter();
      if (!centerCoordinate) {
        return;
      }

      renderInfo(
        ol.proj.toLonLat(centerCoordinate),
        map.getPixelFromCoordinate(centerCoordinate)
      );
    }

    function scheduleMobileCenterInfoUpdate() {
      if (mobileInfoFrame !== null) {
        return;
      }

      mobileInfoFrame = requestAnimationFrame(updateMobileCenterInfo);
    }

    function arrangeMapControls() {
      arrangePrimaryControls(legendEl);
      arrangeAuxControls(themeToggleEl);
      arrangeInfoWindowPlacement(mapEl, legendEl, infoWindow);

      if (isMobileLayout()) {
        scheduleMobileCenterInfoUpdate();
      }
    }

    function applyCoverageTheme(theme) {
      currentTheme = theme;
      coveragePalette = getCoveragePalette(theme);

      coverageItems.forEach((item) => {
        item.palette = coveragePalette[item.paletteKey];
        item.layer.setStyle(buildCoverageStyle(item.palette));
      });

      updateLegendCheckboxColors(legendEl, coverageItems);
      scheduleMobileCenterInfoUpdate();
    }

    if (isThemeToggleEnabled()) {
      themeToggleEl = addLocalThemeToggle(map, applyCoverageTheme);
    }

    legendEl = addCoverageLegend(map, coverageItems, () => {
      requestAnimationFrame(arrangeMapControls);
      scheduleMobileCenterInfoUpdate();
    });

    normalizeZoomButtons();
    arrangeMapControls();
    requestAnimationFrame(arrangeMapControls);
    setTimeout(arrangeMapControls, 0);

    map.getView().fit(europeCoverage.source.getExtent(), {
      padding: [10, 10, 10, 10],
    });


    infoWindow.addEventListener("click", (event) => {
      if (!isMobileLayout()) {
        return;
      }

      const badgeEl = event.target.closest(".mobile-coordinate-badge");
      if (!badgeEl || !infoWindow.contains(badgeEl)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const value = badgeEl.dataset.copyValue;
      if (!value) {
        return;
      }

      copyTextToClipboard(value)
        .then(() => showCopyToast(text.copied, {
          type: "below-element",
          element: legendEl || infoWindow,
        }))
        .catch(() => showCopyToast(text.copyFailed, {
          type: "below-element",
          element: legendEl || infoWindow,
        }));
    });

    infoWindow.addEventListener("keydown", (event) => {
      if (!isMobileLayout() || (event.key !== "Enter" && event.key !== " ")) {
        return;
      }

      const badgeEl = event.target.closest(".mobile-coordinate-badge");
      if (!badgeEl || !infoWindow.contains(badgeEl)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      const value = badgeEl.dataset.copyValue;
      if (!value) {
        return;
      }

      copyTextToClipboard(value)
        .then(() => showCopyToast(text.copied, {
          type: "below-element",
          element: legendEl || infoWindow,
        }))
        .catch(() => showCopyToast(text.copyFailed, {
          type: "below-element",
          element: legendEl || infoWindow,
        }));
    });

    window.addEventListener("resize", arrangeMapControls);

    const view = map.getView();
    view.on("change:center", scheduleMobileCenterInfoUpdate);
    view.on("change:resolution", scheduleMobileCenterInfoUpdate);
    map.on("pointerdrag", scheduleMobileCenterInfoUpdate);
    map.on("moveend", scheduleMobileCenterInfoUpdate);


    map.on("singleclick", (event) => {
      if (isMobileLayout()) {
        return;
      }

      const coordinate = ol.proj.toLonLat(event.coordinate);
      renderInfo(coordinate, event.pixel);
      infoWindow.style.left = `${event.pixel[0] + 15}px`;
      infoWindow.style.top = `${event.pixel[1] + 15}px`;

      copyCoordinate(coordinate, text, {
        type: "below-element",
        element: infoWindow,
      });
    });

    map.on("pointermove", (event) => {
      if (isMobileLayout()) {
        return;
      }

      renderInfo(ol.proj.toLonLat(event.coordinate), event.pixel);
      infoWindow.style.left = `${event.pixel[0] + 15}px`;
      infoWindow.style.top = `${event.pixel[1] + 15}px`;
    });

    scheduleMobileCenterInfoUpdate();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCoverageMap);
  } else {
    initCoverageMap();
  }
})();
