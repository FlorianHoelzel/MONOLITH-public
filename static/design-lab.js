(() => {
  "use strict";

  const canvas = document.querySelector("#sky-lens-canvas");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = window.matchMedia("(pointer: fine)");
  let animationFrame = 0;
  let tabAnimationFrame = 0;
  let stopped = false;
  const liquidTransition = { progress: 0, direction: 1 };
  // A new preset namespace applies this composition once; previous experiments
  // remain in v1 and subsequent adjustments to this preset are still saved.
  const effectsStorageKey = "monolith.design-lab.effects.night.v1";

  const defaultEffectSettings = {
    lens: {
      enabled: true,
      size: 0.14,
      distortion: 0.55,
      chromatic: 0.001,
      follow: 0.1,
      edgeGlow: 0.025,
      ambientMotion: 0,
    },
    liquid: {
      enabled: true,
      duration: 650,
      distortion: 0.025,
      turbulence: 0.04,
      shaderGlow: 0.03,
      overlayEnabled: true,
      overlayBlur: 4,
      overlayOpacity: 0.25,
      edgeOpacity: 0.12,
    },
    dither: {
      enabled: true,
      pattern: "bayer",
      palette: "duotone",
      pixelSize: 3,
      levels: 4,
      intensity: 0.4,
      inkColor: "#070e17",
      paperColor: "#526c82",
      contrast: 0.85,
      brightness: 0.12,
      revealRadius: 150,
      softness: 0.85,
      linger: 1.4,
      rimColor: "#8eafc4",
      rim: 0,
      reverse: false,
      wander: false,
      autoMotion: true,
      motionSpeed: 0.12,
      motionAmount: 0.4,
      clickBurst: false,
    },
    animatedList: {
      enabled: true,
      delay: 4200,
      visibleCount: 5,
      entranceScale: 0.97,
      spring: 0.35,
      pauseOnHover: true,
    },
    cardHover: {
      enabled: true,
      glideDuration: 280,
      opacity: 0.65,
      lift: 1.5,
      borderOpacity: 0.24,
    },
  };

  function cloneDefaults() {
    return JSON.parse(JSON.stringify(defaultEffectSettings));
  }

  function mergeSettings(defaults, saved) {
    const merged = saved && typeof saved === "object" ? JSON.parse(JSON.stringify(saved)) : {};
    Object.keys(defaults).forEach((group) => {
      merged[group] = { ...defaults[group], ...(saved?.[group] && typeof saved[group] === "object" ? saved[group] : {}) };
    });
    return merged;
  }

  function loadEffectSettings() {
    try {
      return mergeSettings(defaultEffectSettings, JSON.parse(localStorage.getItem(effectsStorageKey) || "null"));
    } catch (error) {
      return cloneDefaults();
    }
  }

  let effectSettings = loadEffectSettings();
  let effectsControlsContainer = null;
  let tabController = null;
  let feedController = null;

  const effectRegistry = [
    {
      id: "lens",
      title: "Square Lens",
      icon: "ti-focus-2",
      controls: [
        { type: "toggle", key: "enabled", label: "Effekt aktiv" },
        { type: "range", key: "size", label: "Größe", min: 0.08, max: 0.42, step: 0.01, digits: 2 },
        { type: "range", key: "distortion", label: "Brechung", min: 0, max: 1.6, step: 0.01, digits: 2 },
        { type: "range", key: "chromatic", label: "RGB-Shift", min: 0, max: 0.014, step: 0.0005, digits: 4 },
        { type: "range", key: "follow", label: "Folgetempo", min: 0.015, max: 0.25, step: 0.005, digits: 3 },
        { type: "range", key: "edgeGlow", label: "Randlicht", min: 0, max: 0.35, step: 0.01, digits: 2 },
        { type: "range", key: "ambientMotion", label: "Bewegung", min: 0, max: 2, step: 0.05, digits: 2 },
      ],
    },
    {
      id: "liquid",
      title: "Liquid Tab Morph",
      icon: "ti-droplet-half-2-filled",
      controls: [
        { type: "toggle", key: "enabled", label: "Effekt aktiv" },
        { type: "range", key: "duration", label: "Dauer", min: 250, max: 2600, step: 50, digits: 0, suffix: " ms" },
        { type: "range", key: "distortion", label: "Verzerrung", min: 0, max: 0.14, step: 0.005, digits: 3 },
        { type: "range", key: "turbulence", label: "Unruhe", min: 0, max: 0.24, step: 0.01, digits: 2 },
        { type: "range", key: "shaderGlow", label: "Shader Glow", min: 0, max: 0.35, step: 0.01, digits: 2 },
        { type: "toggle", key: "overlayEnabled", label: "Glas-Overlay" },
        { type: "range", key: "overlayBlur", label: "Overlay Blur", min: 0, max: 28, step: 1, digits: 0, suffix: " px" },
        { type: "range", key: "overlayOpacity", label: "Deckkraft", min: 0, max: 1, step: 0.05, digits: 2 },
        { type: "range", key: "edgeOpacity", label: "Glasrand", min: 0, max: 1, step: 0.01, digits: 2 },
        { type: "action", action: "previewTransition", label: "Übergang testen", icon: "ti-player-play" },
      ],
    },
    {
      id: "dither",
      title: "Dither Veil",
      icon: "ti-grain",
      controls: [
        { type: "toggle", key: "enabled", label: "Effekt aktiv" },
        { type: "select", key: "pattern", label: "Muster", options: [
          { value: "bayer", label: "Bayer" },
          { value: "noise", label: "Blue Noise" },
          { value: "lines", label: "Engraving" },
        ] },
        { type: "select", key: "palette", label: "Palette", options: [
          { value: "duotone", label: "Duotone" },
          { value: "rgb", label: "RGB" },
        ] },
        { type: "range", key: "pixelSize", label: "Pixelgröße", min: 1, max: 12, step: 1, digits: 0, suffix: " px" },
        { type: "range", key: "levels", label: "Farbstufen", min: 2, max: 8, step: 1, digits: 0 },
        { type: "range", key: "intensity", label: "Stärke", min: 0, max: 1, step: 0.05, digits: 2 },
        { type: "color", key: "inkColor", label: "Ink" },
        { type: "color", key: "paperColor", label: "Paper" },
        { type: "range", key: "contrast", label: "Kontrast", min: 0.5, max: 2, step: 0.05, digits: 2 },
        { type: "range", key: "brightness", label: "Helligkeit", min: -0.4, max: 0.4, step: 0.02, digits: 2 },
        { type: "range", key: "revealRadius", label: "Reveal Radius", min: 40, max: 420, step: 10, digits: 0, suffix: " px" },
        { type: "range", key: "softness", label: "Softness", min: 0.05, max: 1, step: 0.05, digits: 2 },
        { type: "range", key: "linger", label: "Linger", min: 0, max: 3, step: 0.1, digits: 1, suffix: " s" },
        { type: "color", key: "rimColor", label: "Rim-Farbe" },
        { type: "range", key: "rim", label: "Rim", min: 0, max: 0.5, step: 0.01, digits: 2 },
        { type: "toggle", key: "reverse", label: "Reverse" },
        { type: "toggle", key: "wander", label: "Auto-Reveal" },
        { type: "toggle", key: "autoMotion", label: "Eigenbewegung" },
        { type: "range", key: "motionSpeed", label: "Drift-Tempo", min: 0, max: 1.2, step: 0.02, digits: 2 },
        { type: "range", key: "motionAmount", label: "Drift-Stärke", min: 0, max: 1.5, step: 0.05, digits: 2 },
        { type: "toggle", key: "clickBurst", label: "Click Burst" },
      ],
    },
    {
      id: "animatedList",
      title: "Animated List",
      icon: "ti-list-details",
      controls: [
        { type: "toggle", key: "enabled", label: "Effekt aktiv" },
        { type: "range", key: "delay", label: "Intervall", min: 700, max: 6000, step: 100, digits: 0, suffix: " ms" },
        { type: "range", key: "visibleCount", label: "Einträge", min: 3, max: 7, step: 1, digits: 0 },
        { type: "range", key: "entranceScale", label: "Startgröße", min: 0.72, max: 1, step: 0.01, digits: 2 },
        { type: "range", key: "spring", label: "Federung", min: 0, max: 1, step: 0.05, digits: 2 },
        { type: "toggle", key: "pauseOnHover", label: "Pause bei Hover" },
        { type: "action", action: "addFeedItem", label: "Ereignis einfügen", icon: "ti-plus" },
      ],
    },
    {
      id: "cardHover",
      title: "Card Hover Effect",
      icon: "ti-cards",
      controls: [
        { type: "toggle", key: "enabled", label: "Effekt aktiv" },
        { type: "range", key: "glideDuration", label: "Gleitdauer", min: 80, max: 900, step: 20, digits: 0, suffix: " ms" },
        { type: "range", key: "opacity", label: "Fläche", min: 0, max: 1, step: 0.05, digits: 2 },
        { type: "range", key: "lift", label: "Anhebung", min: 0, max: 10, step: 0.5, digits: 1, suffix: " px" },
        { type: "range", key: "borderOpacity", label: "Randlicht", min: 0, max: 0.8, step: 0.02, digits: 2 },
      ],
    },
  ];

  const tabConfig = {
    rooms: { title: "Räume", panelTitle: "Geräte nach Räumen", number: "01" },
    all: { title: "Alle Geräte", panelTitle: "Alle Geräte", number: "02" },
    active: { title: "Aktiv", panelTitle: "Jetzt aktiv", number: "03" },
    overview: { title: "Status", panelTitle: "Systemstatus", number: "04" },
    feed: { title: "Feed", panelTitle: "Fake Feed", number: "05" },
  };

  function persistEffectSettings() {
    try {
      localStorage.setItem(effectsStorageKey, JSON.stringify(effectSettings));
    } catch (error) {
      // The controls still work when browser storage is unavailable.
    }
  }

  function applyEffectSettings() {
    const root = document.body.style;
    root.setProperty("--liquid-duration", `${effectSettings.liquid.duration}ms`);
    root.setProperty("--liquid-blur", `${effectSettings.liquid.overlayBlur}px`);
    root.setProperty("--liquid-overlay-opacity", effectSettings.liquid.overlayEnabled ? effectSettings.liquid.overlayOpacity : 0);
    root.setProperty("--liquid-edge-opacity", effectSettings.liquid.overlayEnabled ? effectSettings.liquid.edgeOpacity : 0);
    root.setProperty("--card-hover-duration", `${effectSettings.cardHover.glideDuration}ms`);
    root.setProperty("--card-hover-opacity", effectSettings.cardHover.opacity);
    root.setProperty("--card-hover-lift", `${effectSettings.cardHover.lift}px`);
    root.setProperty("--card-hover-border-opacity", effectSettings.cardHover.borderOpacity);
    document.body.classList.toggle("liquid-overlay-disabled", !effectSettings.liquid.overlayEnabled);
    document.body.classList.toggle("card-hover-disabled", !effectSettings.cardHover.enabled);
    document.body.classList.toggle("animated-list-disabled", !effectSettings.animatedList.enabled);
  }

  function formatControlValue(control, value) {
    return `${Number(value).toFixed(control.digits ?? 2)}${control.suffix || ""}`;
  }

  function notifyEffectChange(definition) {
    const settings = JSON.parse(JSON.stringify(effectSettings[definition.id] || {}));
    definition.onChange?.(settings);
    window.dispatchEvent(new CustomEvent("designlab:effect-change", {
      detail: { id: definition.id, settings },
    }));
  }

  function renderEffectControls() {
    if (!effectsControlsContainer) return;
    effectsControlsContainer.replaceChildren(...effectRegistry.map((definition) => {
      if (!effectSettings[definition.id]) effectSettings[definition.id] = {};
      const details = document.createElement("details");
      details.className = "effect-control-group";
      details.open = true;
      details.dataset.effect = definition.id;

      const summary = document.createElement("summary");
      const icon = document.createElement("i");
      icon.className = `ti ${definition.icon || "ti-sparkles"}`;
      icon.setAttribute("aria-hidden", "true");
      const title = document.createElement("span");
      title.textContent = definition.title;
      const state = document.createElement("span");
      state.className = `effect-enabled-state${effectSettings[definition.id].enabled !== false ? " is-on" : ""}`;
      state.title = effectSettings[definition.id].enabled !== false ? "Aktiv" : "Aus";
      summary.append(icon, title, state);

      const controls = document.createElement("div");
      controls.className = "effect-controls";
      definition.controls.forEach((control) => {
        if (control.type === "action") {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "effect-preview-button";
          button.innerHTML = `<i class="ti ${control.icon || "ti-player-play"}" aria-hidden="true"></i><span>${control.label}</span>`;
          button.addEventListener("click", () => {
            if (control.action === "previewTransition") tabController?.preview();
            if (control.action === "addFeedItem") feedController?.addNow();
          });
          controls.append(button);
          return;
        }

        const row = document.createElement("label");
        row.className = `effect-control-row${control.type === "toggle" ? " is-switch" : ""}`;
        const label = document.createElement("span");
        label.textContent = control.label;
        const value = effectSettings[definition.id][control.key];

        if (control.type === "toggle") {
          const switchControl = document.createElement("span");
          switchControl.className = "effect-switch";
          const input = document.createElement("input");
          input.type = "checkbox";
          input.checked = Boolean(value);
          input.setAttribute("aria-label", control.label);
          const track = document.createElement("span");
          input.addEventListener("change", () => {
            effectSettings[definition.id][control.key] = input.checked;
            state.classList.toggle("is-on", effectSettings[definition.id].enabled !== false);
            state.title = effectSettings[definition.id].enabled !== false ? "Aktiv" : "Aus";
            applyEffectSettings();
            persistEffectSettings();
            notifyEffectChange(definition);
          });
          switchControl.append(input, track);
          row.append(label, switchControl);
        } else if (control.type === "select") {
          row.classList.add("is-select");
          const select = document.createElement("select");
          select.setAttribute("aria-label", control.label);
          control.options.forEach((option) => {
            const item = document.createElement("option");
            item.value = option.value;
            item.textContent = option.label;
            select.append(item);
          });
          select.value = value;
          select.addEventListener("change", () => {
            effectSettings[definition.id][control.key] = select.value;
            persistEffectSettings();
            notifyEffectChange(definition);
          });
          row.append(label, select);
        } else if (control.type === "color") {
          row.classList.add("is-color");
          const input = document.createElement("input");
          input.type = "color";
          input.value = value;
          input.setAttribute("aria-label", control.label);
          const output = document.createElement("output");
          output.textContent = value.toUpperCase();
          input.addEventListener("input", () => {
            effectSettings[definition.id][control.key] = input.value;
            output.textContent = input.value.toUpperCase();
            persistEffectSettings();
            notifyEffectChange(definition);
          });
          row.append(label, input, output);
        } else {
          const input = document.createElement("input");
          input.type = "range";
          input.min = control.min;
          input.max = control.max;
          input.step = control.step;
          input.value = value;
          input.setAttribute("aria-label", control.label);
          const output = document.createElement("output");
          output.textContent = formatControlValue(control, value);
          input.addEventListener("input", () => {
            const nextValue = Number(input.value);
            effectSettings[definition.id][control.key] = nextValue;
            output.textContent = formatControlValue(control, nextValue);
            applyEffectSettings();
            persistEffectSettings();
            notifyEffectChange(definition);
          });
          row.append(label, input, output);
        }
        controls.append(row);
      });

      details.append(summary, controls);
      return details;
    }));
  }

  function initializeEffectControls() {
    const panel = document.querySelector("[data-effects-panel]");
    const toggle = document.querySelector("[data-effects-toggle]");
    const close = document.querySelector("[data-effects-close]");
    const reset = document.querySelector("[data-effects-reset]");
    effectsControlsContainer = document.querySelector("[data-effects-controls]");
    if (!panel || !toggle || !effectsControlsContainer) return;

    const setOpen = (open) => {
      panel.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      if (open) panel.querySelector("input, button")?.focus({ preventScroll: true });
      else toggle.focus({ preventScroll: true });
    };
    toggle.addEventListener("click", () => setOpen(panel.hidden));
    close?.addEventListener("click", () => setOpen(false));
    reset?.addEventListener("click", () => {
      effectSettings = cloneDefaults();
      effectRegistry.forEach((definition) => {
        if (!effectSettings[definition.id]) effectSettings[definition.id] = { ...(definition.defaultSettings || {}) };
      });
      applyEffectSettings();
      persistEffectSettings();
      renderEffectControls();
      effectRegistry.forEach(notifyEffectChange);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !panel.hidden) setOpen(false);
    });

    applyEffectSettings();
    renderEffectControls();
  }

  window.designLabEffects = {
    register(definition, initialSettings = {}) {
      if (!definition?.id || effectRegistry.some((item) => item.id === definition.id)) return false;
      effectRegistry.push({ ...definition, defaultSettings: { ...initialSettings } });
      effectSettings[definition.id] = { ...initialSettings, ...(effectSettings[definition.id] || {}) };
      persistEffectSettings();
      renderEffectControls();
      notifyEffectChange(effectRegistry.at(-1));
      return true;
    },
    getSettings() {
      return JSON.parse(JSON.stringify(effectSettings));
    },
  };

  function formatMinutes(seconds) {
    const minutes = Math.max(0, Math.ceil(Number(seconds || 0) / 60));
    return `${minutes} Min.`;
  }

  function hexToRgb(value) {
    const hex = String(value || "").replace("#", "");
    const normalized = hex.length === 3 ? hex.replace(/./g, (character) => character + character) : hex;
    const color = Number.parseInt(normalized.slice(0, 6), 16);
    if (!Number.isFinite(color)) return [0, 0, 0];
    return [((color >> 16) & 255) / 255, ((color >> 8) & 255) / 255, (color & 255) / 255];
  }

  // Velora Animated List behavior, adapted to the existing Flask page without
  // adding a React runtime: newest item first, spring entrance, looping feed.
  // https://velora.colorlib.com/components/animated-list
  const fakeFeedEvents = [
    { room: "Keller", title: "Waschgang beendet", detail: "Die Wäsche kann entnommen werden.", icon: "ti-wash-dry-1", type: "washer", state: "off" },
    { room: "Wohnzimmer", title: "Wiedergabe gestartet", detail: "Apple TV spielt Musik.", icon: "ti-device-tv", type: "media", state: "on" },
    { room: "Flur", title: "Bewegung erkannt", detail: "Kamera Haustür", icon: "ti-walk", type: "motion", state: "on" },
    { room: "Schlafzimmer", title: "Automatik aktiviert", detail: "Luftreiniger läuft im Auto-Modus.", icon: "ti-wind", type: "air", state: "on" },
    { room: "Wohnzimmer", title: "Reinigung beendet", detail: "Saugroboter ist zur Station zurückgekehrt.", icon: "ti-robot", type: "vacuum", state: "off" },
    { room: "Paket", title: "Sendung in Zustellung", detail: "Die Lieferung kommt voraussichtlich heute.", icon: "ti-package", type: "package", state: "active" },
    { room: "Küche", title: "Licht eingeschaltet", detail: "Arbeitsfläche", icon: "ti-bulb", type: "light", state: "on" },
    { room: "Netzwerk", title: "Gerät verbunden", detail: "Ein bekanntes Gerät ist wieder online.", icon: "ti-wifi", type: "network", state: "on" },
  ];

  function createFeedItem(event, sequence) {
    const item = document.createElement("article");
    item.className = `lab-feed-item feed-type-${event.type} feed-state-${event.state}`;
    item.dataset.feedSequence = String(sequence);

    const icon = document.createElement("span");
    icon.className = "lab-feed-icon";
    icon.setAttribute("aria-hidden", "true");
    const iconGlyph = document.createElement("i");
    iconGlyph.className = `ti ${event.icon}`;
    icon.append(iconGlyph);

    const content = document.createElement("span");
    content.className = "lab-feed-content";
    const main = document.createElement("span");
    main.className = "lab-feed-main";
    const room = document.createElement("span");
    room.className = "lab-feed-room";
    room.textContent = event.room;
    const title = document.createElement("strong");
    title.textContent = event.title;
    main.append(room, title);
    const detail = document.createElement("span");
    detail.className = "lab-feed-detail";
    detail.textContent = event.detail;
    content.append(main, detail);

    const time = document.createElement("time");
    time.dateTime = new Date().toISOString();
    time.textContent = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    item.append(icon, content, time);
    return item;
  }

  function initializeFakeFeed() {
    const feed = document.querySelector("[data-fake-feed]");
    if (!feed) return null;
    let eventIndex = 0;
    let sequence = 0;
    let timer = 0;
    let isActive = false;
    let isHovered = false;

    function clearTimer() {
      if (timer) window.clearTimeout(timer);
      timer = 0;
    }

    function shouldAnimate() {
      return effectSettings.animatedList.enabled && !reduceMotion.matches;
    }

    function addItem(force = false) {
      const event = fakeFeedEvents[eventIndex % fakeFeedEvents.length];
      eventIndex += 1;
      sequence += 1;
      const oldPositions = new Map(Array.from(feed.children).map((item) => [item, item.getBoundingClientRect().top]));
      const item = createFeedItem(event, sequence);
      feed.prepend(item);

      const limit = Math.round(effectSettings.animatedList.visibleCount);
      const overflow = Array.from(feed.children).slice(limit);
      overflow.forEach((oldItem) => {
        if (shouldAnimate() && !force) {
          const animation = oldItem.animate(
            [{ opacity: 1, transform: "scale(1)" }, { opacity: 0, transform: "scale(0.96)" }],
            { duration: 220, easing: "ease-out", fill: "forwards" },
          );
          animation.addEventListener("finish", () => oldItem.remove(), { once: true });
        } else {
          oldItem.remove();
        }
      });

      if (!shouldAnimate() || force) return;
      const spring = effectSettings.animatedList.spring;
      const overshoot = 1 + spring * 0.025;
      item.animate(
        [
          { opacity: 0, transform: `translateY(-12px) scale(${effectSettings.animatedList.entranceScale})` },
          { opacity: 1, transform: `translateY(2px) scale(${overshoot})`, offset: 0.72 },
          { opacity: 1, transform: "translateY(0) scale(1)" },
        ],
        { duration: 420 + spring * 260, easing: "cubic-bezier(.16,1,.3,1)" },
      );
      oldPositions.forEach((oldTop, oldItem) => {
        if (!oldItem.isConnected) return;
        const delta = oldTop - oldItem.getBoundingClientRect().top;
        oldItem.animate(
          [{ transform: `translateY(${delta}px)` }, { transform: "translateY(0)" }],
          { duration: 360, easing: "cubic-bezier(.16,1,.3,1)" },
        );
      });
    }

    function schedule() {
      clearTimer();
      if (!isActive || document.hidden || !effectSettings.animatedList.enabled) return;
      if (isHovered && effectSettings.animatedList.pauseOnHover) {
        timer = window.setTimeout(schedule, 250);
        return;
      }
      timer = window.setTimeout(() => {
        addItem();
        schedule();
      }, effectSettings.animatedList.delay);
    }

    function renderStatic() {
      clearTimer();
      feed.replaceChildren();
      const limit = Math.round(effectSettings.animatedList.visibleCount);
      for (let index = 0; index < limit; index += 1) addItem(true);
      if (isActive && effectSettings.animatedList.enabled) schedule();
    }

    feed.addEventListener("pointerenter", () => { isHovered = true; });
    feed.addEventListener("pointerleave", () => { isHovered = false; schedule(); });
    document.addEventListener("visibilitychange", schedule);
    reduceMotion.addEventListener("change", renderStatic);
    window.addEventListener("designlab:effect-change", (event) => {
      if (event.detail?.id === "animatedList") renderStatic();
    });
    renderStatic();

    return {
      addNow() { addItem(!shouldAnimate()); },
      setActive(active) { isActive = active; schedule(); },
      destroy() { clearTimer(); },
    };
  }

  // Velora Card Hover Effect behavior: one highlight glides between cards in
  // the same grid and also follows keyboard focus.
  // https://velora.colorlib.com/components/card-hover-effect
  function initializeCardHover() {
    let activeCard = null;

    function getHighlight(grid) {
      let highlight = grid.querySelector(":scope > .device-hover-highlight");
      if (!highlight) {
        highlight = document.createElement("span");
        highlight.className = "device-hover-highlight";
        highlight.setAttribute("aria-hidden", "true");
        grid.append(highlight);
      }
      return highlight;
    }

    function show(card) {
      if (!effectSettings.cardHover.enabled || !card) return;
      const grid = card.closest(".devices");
      if (!grid) return;
      const highlight = getHighlight(grid);
      const gridRect = grid.getBoundingClientRect();
      const cardRect = card.getBoundingClientRect();
      highlight.style.width = `${cardRect.width}px`;
      highlight.style.height = `${cardRect.height}px`;
      highlight.style.transform = `translate3d(${cardRect.left - gridRect.left + grid.scrollLeft}px, ${cardRect.top - gridRect.top + grid.scrollTop}px, 0)`;
      highlight.classList.add("is-visible");
      card.classList.add("is-hover-target");
      activeCard = card;
    }

    function hide(card) {
      if (card && card !== activeCard) return;
      activeCard?.classList.remove("is-hover-target");
      const grid = activeCard?.closest(".devices");
      grid?.querySelector(":scope > .device-hover-highlight")?.classList.remove("is-visible");
      activeCard = null;
    }

    document.addEventListener("pointerover", (event) => {
      if (!finePointer.matches) return;
      const card = event.target.closest?.(".lab-devices-panel .device-card");
      if (!card || card === activeCard) return;
      activeCard?.classList.remove("is-hover-target");
      show(card);
    });
    document.addEventListener("pointerout", (event) => {
      const card = event.target.closest?.(".lab-devices-panel .device-card");
      if (!card || card.contains(event.relatedTarget)) return;
      hide(card);
    });
    document.addEventListener("focusin", (event) => show(event.target.closest?.(".lab-devices-panel .device-card")));
    document.addEventListener("focusout", (event) => {
      const card = event.target.closest?.(".lab-devices-panel .device-card");
      if (card && !card.contains(event.relatedTarget)) hide(card);
    });
    window.addEventListener("designlab:effect-change", (event) => {
      if (event.detail?.id === "cardHover" && !event.detail.settings.enabled) hide();
    });
  }

  function getDeviceStatus(device) {
    if (device.type === "console") {
      if (device.network_connected === true) return { text: "An", stateClass: "on" };
      if (device.network_connected === false) return { text: "Aus", stateClass: "off" };
      return { text: "Unbekannt", stateClass: "unknown" };
    }
    if (device.type === "washer") {
      if (!device.value) return { text: "Aus", stateClass: "off" };
      return {
        text: Number(device.remaining) > 0 ? `An · ${formatMinutes(device.remaining)}` : "An",
        stateClass: "active",
      };
    }

    if (device.type === "dryer") {
      if (!device.configured) return { text: "Nicht eingerichtet", stateClass: "unknown" };
      if (!device.connected) return { text: "Nicht erreichbar", stateClass: "unknown" };
      if (device.active_dryer?.running) return { text: "Trockner läuft", stateClass: "active" };
      if (device.active_dryer?.status === "PICKUP") return { text: "Trockner fertig", stateClass: "off" };
      if (Number.isFinite(device.available_dryers)) {
        return {
          text: device.available_dryers === 1 ? "1 Trockner frei" : `${device.available_dryers} Trockner frei`,
          stateClass: "off",
        };
      }
      return { text: "Status unbekannt", stateClass: "unknown" };
    }

    if (device.type === "air_purifier") {
      return device.active
        ? { text: device.mode ? `An · ${device.mode}` : "An", stateClass: "on" }
        : { text: "Aus", stateClass: "off" };
    }

    if (device.type === "media") {
      const playing = device.playing === true || device.value === "Playing";
      if (device.status_source === "pyatv") {
        return {
          text: playing && device.title ? `Playing · ${device.title}` : playing ? "Playing" : "Paused",
          stateClass: playing ? "on" : "off",
        };
      }
    }

    if (device.type === "vacuum") {
      const vacuumStates = {
        docked: ["Gedockt", "off"],
        charging: ["Lädt", "charging"],
        cleaning: ["Reinigt", "active"],
        paused: ["Pausiert", "off"],
        returning_to_dock: ["Fährt zur Station", "active"],
      };
      const state = vacuumStates[String(device.value || "").toLowerCase()];
      return state
        ? { text: state[0], stateClass: state[1] }
        : { text: "Unbekannt", stateClass: "unknown" };
    }

    const isOn = [true, 1, "on", "On", "An"].includes(device.value);
    const isOff = [false, 0, "off", "Off", "Aus"].includes(device.value);
    if (isOn) {
      const detail = device.app_name || (Number.isFinite(Number(device.volume)) ? `Lautstärke ${device.volume}` : "");
      return { text: detail ? `An · ${detail}` : "An", stateClass: "on" };
    }
    if (isOff) return { text: "Aus", stateClass: "off" };
    return { text: device.value || "Unbekannt", stateClass: "unknown" };
  }

  function renderDevices(devices) {
    Object.entries(devices || {}).forEach(([deviceId, device]) => {
      const status = getDeviceStatus(device);
      document.querySelectorAll(`[data-device="${CSS.escape(deviceId)}"]`).forEach((card) => {
        card.classList.remove("is-on", "is-off", "is-active", "is-charging", "is-unknown");
        card.classList.add(`is-${status.stateClass}`);
        const state = card.querySelector(".device-state");
        state?.classList.remove("on", "off", "active", "charging", "unknown");
        state?.classList.add(status.stateClass);
        const text = card.querySelector(".device-state-text");
        if (text) text.textContent = status.text;
      });
    });
  }

  function populateDerivedViews(devices) {
    const sourceCards = Array.from(document.querySelectorAll('[data-lab-panel="rooms"] .device-card'));
    const allGrid = document.querySelector('[data-device-grid="all"]');
    const activeGrid = document.querySelector('[data-device-grid="active"]');
    const activeEmpty = document.querySelector("[data-active-empty]");
    const typeOverview = document.querySelector("[data-type-overview]");
    const activeStates = new Set(["on", "active", "charging"]);

    if (allGrid) allGrid.replaceChildren(...sourceCards.map((card) => card.cloneNode(true)));

    const activeIds = new Set(
      Object.entries(devices || {})
        .filter(([, device]) => activeStates.has(getDeviceStatus(device).stateClass))
        .map(([deviceId]) => deviceId),
    );
    const activeCards = sourceCards
      .filter((card) => activeIds.has(card.dataset.device))
      .map((card) => card.cloneNode(true));
    if (activeGrid) activeGrid.replaceChildren(...activeCards);
    if (activeEmpty) activeEmpty.hidden = activeCards.length > 0;

    const counts = { active: 0, idle: 0, unknown: 0 };
    const types = new Map();
    Object.values(devices || {}).forEach((device) => {
      const state = getDeviceStatus(device).stateClass;
      if (activeStates.has(state)) counts.active += 1;
      else if (state === "unknown") counts.unknown += 1;
      else counts.idle += 1;
      const type = String(device.type || "other");
      types.set(type, (types.get(type) || 0) + 1);
    });
    Object.entries(counts).forEach(([key, value]) => {
      const element = document.querySelector(`[data-status-count="${key}"]`);
      if (element) element.textContent = String(value).padStart(2, "0");
    });

    const typeLabels = {
      air_purifier: "Luftreiniger", dryer: "Trockner", light: "Lichter", media: "Medien",
      plug: "Steckdosen", switch: "Schalter", vacuum: "Saugroboter", washer: "Waschmaschinen",
    };
    if (typeOverview) {
      typeOverview.replaceChildren(...Array.from(types.entries()).sort().map(([type, count]) => {
        const item = document.createElement("div");
        item.className = "type-stat";
        const label = document.createElement("span");
        label.textContent = typeLabels[type] || type.replaceAll("_", " ");
        const value = document.createElement("strong");
        value.textContent = String(count).padStart(2, "0");
        item.append(label, value);
        return item;
      }));
    }
  }

  async function updateDevices() {
    try {
      const response = await fetch("/api/devices", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const devices = await response.json();
      renderDevices(devices);
      populateDerivedViews(devices);
    } catch (error) {
      document.querySelectorAll(".device-state-text").forEach((element) => {
        element.textContent = "Status nicht verfügbar";
      });
    }
  }

  function initializeTabs() {
    const tabs = Array.from(document.querySelectorAll("[data-lab-tab]"));
    const panels = new Map(Array.from(document.querySelectorAll("[data-lab-panel]")).map((panel) => [panel.dataset.labPanel, panel]));
    let activeKey = tabs.find((tab) => tab.classList.contains("is-active"))?.dataset.labTab || "rooms";
    let transitioning = false;

    function updateLabels(key) {
      const config = tabConfig[key];
      if (!config) return;
      const currentTitle = document.querySelector("[data-lab-current-title]");
      const panelTitle = document.querySelector("[data-panel-title]");
      const tabNumber = document.querySelector("[data-tab-number]");
      if (currentTitle) currentTitle.textContent = config.title;
      if (panelTitle) panelTitle.textContent = config.panelTitle;
      if (tabNumber) tabNumber.textContent = config.number;
    }

    function selectTab(nextKey) {
      if (transitioning || nextKey === activeKey || !panels.has(nextKey)) return;
      const oldIndex = tabs.findIndex((tab) => tab.dataset.labTab === activeKey);
      const newIndex = tabs.findIndex((tab) => tab.dataset.labTab === nextKey);
      const oldPanel = panels.get(activeKey);
      const newPanel = panels.get(nextKey);
      const liquidEnabled = effectSettings.liquid.enabled && !reduceMotion.matches;
      const duration = liquidEnabled ? effectSettings.liquid.duration : 1;
      const start = performance.now();
      let swapped = false;
      transitioning = true;
      liquidTransition.direction = newIndex >= oldIndex ? 1 : -1;
      if (liquidEnabled) {
        document.body.classList.add("is-tab-transitioning");
        oldPanel.classList.add("is-leaving");
      }

      tabs.forEach((tab) => {
        const selected = tab.dataset.labTab === nextKey;
        tab.classList.toggle("is-active", selected);
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
      });

      function swapPanels() {
        if (swapped) return;
        swapped = true;
        oldPanel.hidden = true;
        oldPanel.classList.remove("is-active", "is-leaving");
        newPanel.hidden = false;
        newPanel.classList.add("is-active");
        if (liquidEnabled) newPanel.classList.add("is-entering");
        updateLabels(nextKey);
        activeKey = nextKey;
        feedController?.setActive(nextKey === "feed");
      }

      function finishTransition() {
        swapPanels();
        newPanel.classList.remove("is-entering");
        document.body.classList.remove("is-tab-transitioning");
        liquidTransition.progress = 0;
        transitioning = false;
        if (tabAnimationFrame) cancelAnimationFrame(tabAnimationFrame);
        tabAnimationFrame = 0;
      }

      // Timers make the state change reliable even when requestAnimationFrame
      // is throttled in a background tab. The shader still uses RAF for motion.
      window.setTimeout(swapPanels, liquidEnabled ? duration * 0.39 : 0);
      window.setTimeout(finishTransition, duration + 34);

      function step(now) {
        const linear = Math.min(1, (now - start) / duration);
        liquidTransition.progress = linear < 0.5
          ? 2 * linear * linear
          : 1 - Math.pow(-2 * linear + 2, 2) / 2;

        if (transitioning && linear < 1) {
          tabAnimationFrame = requestAnimationFrame(step);
        }
      }
      tabAnimationFrame = requestAnimationFrame(step);
    }

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectTab(tab.dataset.labTab));
      tab.addEventListener("keydown", (event) => {
        let nextIndex = null;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
        if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") nextIndex = 0;
        if (event.key === "End") nextIndex = tabs.length - 1;
        if (nextIndex === null) return;
        event.preventDefault();
        tabs[nextIndex].focus();
        selectTab(tabs[nextIndex].dataset.labTab);
      });
    });

    return {
      preview() {
        if (transitioning) return;
        const currentIndex = tabs.findIndex((tab) => tab.dataset.labTab === activeKey);
        selectTab(tabs[(currentIndex + 1) % tabs.length].dataset.labTab);
      },
    };
  }

  function initializeLens() {
    if (!canvas) return;
    const gl = canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      depth: false,
      powerPreference: "high-performance",
    });

    if (!gl) {
      document.body.classList.add("webgl-unavailable");
      return;
    }

    // Visual model adapted from Tomoyuki Nakata's MIT-licensed square lens experiment:
    // https://github.com/tomoyukinakata/mouse-following-square-lens-effect
    // Reimplemented here in dependency-free WebGL for MONOLITH.
    const vertexSource = `
      attribute vec2 a_position;
      varying vec2 v_uv;

      void main() {
        v_uv = a_position * 0.5 + 0.5;
        gl_Position = vec4(a_position, 0.0, 1.0);
      }
    `;

    const fragmentSource = `
      precision highp float;

      uniform sampler2D u_texture;
      uniform vec2 u_resolution;
      uniform vec2 u_textureSize;
      uniform vec2 u_mouse;
      uniform float u_time;
      uniform float u_transition;
      uniform float u_transitionDirection;
      uniform float u_lensEnabled;
      uniform float u_lensSize;
      uniform float u_lensDistortion;
      uniform float u_lensChromatic;
      uniform float u_lensEdgeGlow;
      uniform float u_ambientMotion;
      uniform float u_liquidEnabled;
      uniform float u_liquidDistortion;
      uniform float u_liquidTurbulence;
      uniform float u_liquidGlow;
      uniform float u_ditherEnabled;
      uniform float u_ditherPixelSize;
      uniform float u_ditherLevels;
      uniform float u_ditherIntensity;
      uniform float u_ditherContrast;
      uniform float u_ditherBrightness;
      uniform float u_ditherRevealRadius;
      uniform float u_ditherSoftness;
      uniform float u_ditherRim;
      uniform float u_ditherReverse;
      uniform float u_ditherAutoMotion;
      uniform float u_ditherMotionSpeed;
      uniform float u_ditherMotionAmount;
      uniform int u_ditherPattern;
      uniform int u_ditherPalette;
      uniform vec3 u_ditherInk;
      uniform vec3 u_ditherPaper;
      uniform vec3 u_ditherRimColor;
      uniform vec4 u_ditherTrail[6];
      uniform vec4 u_ditherBurst;
      varying vec2 v_uv;

      vec2 coverUv(vec2 uv, vec2 meshSize, vec2 textureSize) {
        vec2 meshRatio = vec2(meshSize.x / meshSize.y, meshSize.y / meshSize.x);
        vec2 textureRatio = vec2(textureSize.x / textureSize.y, textureSize.y / textureSize.x);
        vec2 ratio = vec2(
          min(meshRatio.x / textureRatio.x, 1.0),
          min(meshRatio.y / textureRatio.y, 1.0)
        );
        return (uv - 0.5) * ratio + 0.5;
      }

      float randomValue(vec2 value) {
        return fract(sin(dot(value, vec2(12.9898, 78.233))) * 43758.5453);
      }

      float smoothNoise(vec2 value) {
        vec2 cell = floor(value);
        vec2 local = fract(value);
        local = local * local * (3.0 - 2.0 * local);
        return mix(
          mix(randomValue(cell), randomValue(cell + vec2(1.0, 0.0)), local.x),
          mix(randomValue(cell + vec2(0.0, 1.0)), randomValue(cell + vec2(1.0, 1.0)), local.x),
          local.y
        );
      }

      vec2 lensUv(vec2 uv, float distortion) {
        vec2 centered = uv - 0.5;
        float radiusSquared = dot(centered, centered);
        float scale = 1.0 + distortion * radiusSquared;
        return uv - ((centered * scale + 0.5) - uv);
      }

      // Dither model adapted from React Bits' Dither Veil component:
      // https://reactbits.dev/animations/dither-veil
      float bayer4(vec2 cell) {
        vec2 p = mod(floor(cell), 4.0);
        if (p.y < 1.0) {
          if (p.x < 1.0) return 0.03125;
          if (p.x < 2.0) return 0.53125;
          if (p.x < 3.0) return 0.15625;
          return 0.65625;
        }
        if (p.y < 2.0) {
          if (p.x < 1.0) return 0.78125;
          if (p.x < 2.0) return 0.28125;
          if (p.x < 3.0) return 0.90625;
          return 0.40625;
        }
        if (p.y < 3.0) {
          if (p.x < 1.0) return 0.21875;
          if (p.x < 2.0) return 0.71875;
          if (p.x < 3.0) return 0.09375;
          return 0.59375;
        }
        if (p.x < 1.0) return 0.96875;
        if (p.x < 2.0) return 0.46875;
        if (p.x < 3.0) return 0.84375;
        return 0.34375;
      }

      float ditherThreshold(vec2 cell) {
        if (u_ditherPattern == 1) return randomValue(cell * 1.731 + vec2(17.0, 43.0));
        if (u_ditherPattern == 2) {
          float line = fract((cell.x + cell.y) / 6.0);
          return clamp(abs(line * 2.0 - 1.0) + (bayer4(cell) - 0.5) * 0.32, 0.0, 1.0);
        }
        return bayer4(cell);
      }

      vec3 quantizeDither(vec3 value, float threshold) {
        float steps = max(u_ditherLevels - 1.0, 1.0);
        vec3 scaled = clamp(value, 0.0, 1.0) * steps;
        return min(floor(scaled) + step(vec3(threshold), fract(scaled)), vec3(steps)) / steps;
      }

      void main() {
        // A restrained version of Filip Zrnzevic's liquid morphology transition:
        // https://codepen.io/filipz/pen/JoGNQzm
        // The growing refractive boundary is applied to the sky while DOM panels cross at its midpoint.
        float shortestSide = min(u_resolution.x, u_resolution.y);
        vec2 liquidPoint = (v_uv - 0.5) * u_resolution / shortestSide;
        float liquidDistance = length(liquidPoint);
        float liquidRadius = mix(-0.15, 1.24, u_transition);
        float turbulence = (smoothNoise(v_uv * 8.0 + vec2(u_transition * 3.0, u_transitionDirection)) - 0.5) * u_liquidTurbulence;
        float liquidBoundary = (1.0 - smoothstep(0.02, 0.16, abs(liquidDistance - liquidRadius - turbulence))) * u_liquidEnabled;
        float liquidEnvelope = sin(u_transition * 3.14159265);
        vec2 liquidDirection = liquidDistance > 0.001 ? liquidPoint / liquidDistance : vec2(0.0);
        vec2 liquidFlow = liquidDirection * liquidBoundary * liquidEnvelope * u_liquidDistortion;
        liquidFlow += vec2(
          sin(liquidPoint.y * 13.0 + u_transition * 7.0),
          cos(liquidPoint.x * 11.0 - u_transition * 6.0)
        ) * liquidBoundary * 0.008 * u_transitionDirection;
        vec2 transitionUv = v_uv - liquidFlow;

        vec2 aspectScale = vec2(
          min(u_resolution.y / u_resolution.x, 1.0),
          min(u_resolution.x / u_resolution.y, 1.0)
        );
        vec2 squarePosition = (v_uv * 2.0 - 1.0) / aspectScale;
        squarePosition -= u_mouse / aspectScale;

        float squareSize = u_lensSize;
        float squareDistance = max(abs(squarePosition.x), abs(squarePosition.y));
        float squareMask = (1.0 - smoothstep(squareSize - 0.009, squareSize, squareDistance)) * u_lensEnabled;

        vec2 outsideUv = transitionUv;
        float wave = sin(outsideUv.y * 20.0 + u_time * 0.55) * 0.0015 * u_ambientMotion;
        float grain = (randomValue(outsideUv * 220.0 + u_time * 0.08) - 0.5) * 0.0014 * u_ambientMotion;
        outsideUv += vec2(grain, wave);
        vec3 rawOutside = texture2D(u_texture, coverUv(outsideUv, u_resolution, u_textureSize)).rgb;
        vec3 outside = rawOutside;
        float luminance = dot(outside, vec3(0.299, 0.587, 0.114));
        outside = mix(vec3(luminance), outside, 0.24);
        outside *= vec3(0.7, 0.87, 1.08);

        float ditherSize = max(u_ditherPixelSize, 1.0);
        float ditherMotion = u_ditherAutoMotion * u_ditherEnabled;
        vec2 flowField = vec2(
          smoothNoise(v_uv * 2.4 + vec2(u_time * 0.025 * u_ditherMotionSpeed, 2.7)),
          smoothNoise(v_uv * 2.9 + vec2(4.2, -u_time * 0.021 * u_ditherMotionSpeed))
        ) - 0.5;
        vec2 ditherDrift = (
          vec2(u_time * 7.0, -u_time * 3.2) * u_ditherMotionSpeed
          + flowField * ditherSize * 8.0 * u_ditherMotionAmount
        ) * ditherMotion;
        vec2 ditherCell = floor((gl_FragCoord.xy + ditherDrift) / ditherSize);
        float threshold = ditherThreshold(ditherCell);
        float movingVeil = smoothNoise(
          v_uv * 3.2
          + vec2(u_time * 0.018, -u_time * 0.013) * u_ditherMotionSpeed
        );
        threshold = clamp(
          threshold + (movingVeil - 0.5) * 0.16 * u_ditherMotionAmount * ditherMotion,
          0.0,
          1.0
        );
        vec3 graded = pow(clamp(
          (rawOutside - 0.5) * u_ditherContrast
          + 0.5
          + u_ditherBrightness
          + (movingVeil - 0.5) * 0.045 * u_ditherMotionAmount * ditherMotion,
          0.0,
          1.0
        ), vec3(1.6));
        vec3 ditherLevel;
        if (u_ditherPalette == 1) {
          ditherLevel = quantizeDither(graded, threshold);
        } else {
          float gray = dot(graded, vec3(0.2126, 0.7152, 0.0722));
          ditherLevel = vec3(quantizeDither(vec3(gray), threshold).r);
        }
        vec3 dithered = u_ditherPalette == 1
          ? ditherLevel
          : mix(u_ditherInk, u_ditherPaper, ditherLevel.r);

        vec2 screenPoint = v_uv * u_resolution;
        float reveal = 0.0;
        float rimMask = 0.0;
        for (int i = 0; i < 6; i++) {
          vec4 trail = u_ditherTrail[i];
          float distanceToTrail = distance(screenPoint, trail.xy * u_resolution);
          float radius = u_ditherRevealRadius * (0.72 + trail.z * 0.28);
          float innerRadius = radius * (1.0 - u_ditherSoftness * 0.82);
          float trailReveal = (1.0 - smoothstep(innerRadius, radius, distanceToTrail)) * trail.z;
          float trailRim = (1.0 - smoothstep(radius, radius + max(2.0, u_ditherRim * 70.0), distanceToTrail)) * trail.z;
          reveal = max(reveal, trailReveal);
          rimMask = max(rimMask, max(0.0, trailRim - trailReveal));
        }
        float burstDistance = distance(screenPoint, u_ditherBurst.xy * u_resolution);
        float burstWidth = max(14.0, u_ditherRevealRadius * 0.24);
        float burstRing = (1.0 - smoothstep(burstWidth * 0.35, burstWidth, abs(burstDistance - u_ditherBurst.z))) * u_ditherBurst.w;
        reveal = max(reveal, burstRing);
        rimMask = max(rimMask, burstRing * u_ditherRim);
        reveal = mix(reveal, 1.0 - reveal, u_ditherReverse);
        vec3 veiled = mix(dithered, rawOutside, reveal);
        veiled = mix(veiled, u_ditherRimColor, clamp(rimMask * u_ditherRim * 5.0, 0.0, 1.0));
        outside = mix(outside, veiled, u_ditherEnabled * u_ditherIntensity);

        vec2 squareUv = squarePosition / (squareSize * 2.0) + 0.5;
        vec2 distortedSquareUv = lensUv(squareUv, -u_lensDistortion);
        vec2 squareOffset = (distortedSquareUv - squareUv) * squareSize * aspectScale;
        vec2 imageUv = coverUv(transitionUv + squareOffset, u_resolution, u_textureSize);
        vec2 rgbDirection = (squareUv - 0.5) * 2.0 * aspectScale;
        float red = texture2D(u_texture, imageUv + rgbDirection * u_lensChromatic).r;
        float green = texture2D(u_texture, imageUv).g;
        float blue = texture2D(u_texture, imageUv - rgbDirection * u_lensChromatic).b;
        vec3 inside = vec3(red, green, blue) * vec3(1.03, 1.02, 1.04);

        vec3 color = mix(outside, inside, squareMask);
        color += vec3(0.13, 0.32, 0.5) * liquidBoundary * liquidEnvelope * u_liquidGlow * 1.84;
        float edge = 1.0 - smoothstep(0.0, 0.008, abs(squareDistance - squareSize + 0.004));
        color += vec3(0.9, 0.96, 1.0) * edge * u_lensEdgeGlow * u_lensEnabled;
        color += vec3(0.82, 0.94, 1.0) * liquidBoundary * liquidEnvelope * u_liquidGlow;
        gl_FragColor = vec4(color, 1.0);
      }
    `;

    function compileShader(type, source) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const message = gl.getShaderInfoLog(shader);
        gl.deleteShader(shader);
        throw new Error(message || "Shader konnte nicht kompiliert werden.");
      }
      return shader;
    }

    let program;
    try {
      program = gl.createProgram();
      gl.attachShader(program, compileShader(gl.VERTEX_SHADER, vertexSource));
      gl.attachShader(program, compileShader(gl.FRAGMENT_SHADER, fragmentSource));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(program) || "WebGL-Programm konnte nicht verknüpft werden.");
      }
    } catch (error) {
      document.body.classList.add("webgl-unavailable");
      return;
    }

    const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
    gl.useProgram(program);
    const positionLocation = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(positionLocation);
    gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

    const resolutionLocation = gl.getUniformLocation(program, "u_resolution");
    const textureSizeLocation = gl.getUniformLocation(program, "u_textureSize");
    const mouseLocation = gl.getUniformLocation(program, "u_mouse");
    const timeLocation = gl.getUniformLocation(program, "u_time");
    const transitionLocation = gl.getUniformLocation(program, "u_transition");
    const transitionDirectionLocation = gl.getUniformLocation(program, "u_transitionDirection");
    const lensEnabledLocation = gl.getUniformLocation(program, "u_lensEnabled");
    const lensSizeLocation = gl.getUniformLocation(program, "u_lensSize");
    const lensDistortionLocation = gl.getUniformLocation(program, "u_lensDistortion");
    const lensChromaticLocation = gl.getUniformLocation(program, "u_lensChromatic");
    const lensEdgeGlowLocation = gl.getUniformLocation(program, "u_lensEdgeGlow");
    const ambientMotionLocation = gl.getUniformLocation(program, "u_ambientMotion");
    const liquidEnabledLocation = gl.getUniformLocation(program, "u_liquidEnabled");
    const liquidDistortionLocation = gl.getUniformLocation(program, "u_liquidDistortion");
    const liquidTurbulenceLocation = gl.getUniformLocation(program, "u_liquidTurbulence");
    const liquidGlowLocation = gl.getUniformLocation(program, "u_liquidGlow");
    const ditherEnabledLocation = gl.getUniformLocation(program, "u_ditherEnabled");
    const ditherPixelSizeLocation = gl.getUniformLocation(program, "u_ditherPixelSize");
    const ditherLevelsLocation = gl.getUniformLocation(program, "u_ditherLevels");
    const ditherIntensityLocation = gl.getUniformLocation(program, "u_ditherIntensity");
    const ditherContrastLocation = gl.getUniformLocation(program, "u_ditherContrast");
    const ditherBrightnessLocation = gl.getUniformLocation(program, "u_ditherBrightness");
    const ditherRevealRadiusLocation = gl.getUniformLocation(program, "u_ditherRevealRadius");
    const ditherSoftnessLocation = gl.getUniformLocation(program, "u_ditherSoftness");
    const ditherRimLocation = gl.getUniformLocation(program, "u_ditherRim");
    const ditherReverseLocation = gl.getUniformLocation(program, "u_ditherReverse");
    const ditherAutoMotionLocation = gl.getUniformLocation(program, "u_ditherAutoMotion");
    const ditherMotionSpeedLocation = gl.getUniformLocation(program, "u_ditherMotionSpeed");
    const ditherMotionAmountLocation = gl.getUniformLocation(program, "u_ditherMotionAmount");
    const ditherPatternLocation = gl.getUniformLocation(program, "u_ditherPattern");
    const ditherPaletteLocation = gl.getUniformLocation(program, "u_ditherPalette");
    const ditherInkLocation = gl.getUniformLocation(program, "u_ditherInk");
    const ditherPaperLocation = gl.getUniformLocation(program, "u_ditherPaper");
    const ditherRimColorLocation = gl.getUniformLocation(program, "u_ditherRimColor");
    const ditherTrailLocation = gl.getUniformLocation(program, "u_ditherTrail[0]");
    const ditherBurstLocation = gl.getUniformLocation(program, "u_ditherBurst");
    const textureLocation = gl.getUniformLocation(program, "u_texture");
    const targetMouse = { x: 0.28, y: 0.08 };
    const easedMouse = { x: targetMouse.x, y: targetMouse.y };
    const ditherTrail = [];
    let pointerInside = false;
    let lastTrailAt = 0;
    let ditherBurst = null;
    const image = new Image();
    image.decoding = "async";

    function resize() {
      const ratio = Math.min(window.devicePixelRatio || 1, 1.35);
      const width = Math.max(1, Math.round(window.innerWidth * ratio));
      const height = Math.max(1, Math.round(window.innerHeight * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        canvas.style.width = `${window.innerWidth}px`;
        canvas.style.height = `${window.innerHeight}px`;
      }
      gl.viewport(0, 0, width, height);
      gl.uniform2f(resolutionLocation, width, height);
    }

    function draw(timestamp = 0) {
      if (stopped) return;
      resize();
      easedMouse.x += (targetMouse.x - easedMouse.x) * effectSettings.lens.follow;
      easedMouse.y += (targetMouse.y - easedMouse.y) * effectSettings.lens.follow;
      const ditherActive = effectSettings.dither.enabled && !reduceMotion.matches;
      const shouldReveal = pointerInside || (effectSettings.dither.wander && ditherActive);
      const seconds = timestamp * 0.001;
      const ditherMouse = pointerInside
        ? { x: easedMouse.x, y: easedMouse.y }
        : {
            x: Math.sin(seconds * 0.53) * 0.58 + Math.sin(seconds * 1.31 + 0.6) * 0.14,
            y: Math.sin(seconds * 0.71 + 1.1) * 0.48 + Math.cos(seconds * 1.57) * 0.1,
          };
      const ditherUv = { x: ditherMouse.x * 0.5 + 0.5, y: ditherMouse.y * 0.5 + 0.5 };
      if (shouldReveal && timestamp - lastTrailAt > 75) {
        ditherTrail.unshift({ x: ditherUv.x, y: ditherUv.y, born: timestamp });
        ditherTrail.length = Math.min(ditherTrail.length, 5);
        lastTrailAt = timestamp;
      }
      const trailUniform = new Float32Array(24);
      const trailPoints = shouldReveal
        ? [{ x: ditherUv.x, y: ditherUv.y, born: timestamp }, ...ditherTrail]
        : ditherTrail;
      trailPoints.slice(0, 6).forEach((point, index) => {
        const age = Math.max(0, timestamp - point.born);
        const strength = index === 0 && shouldReveal
          ? 1
          : effectSettings.dither.linger > 0
            ? Math.max(0, 1 - age / (effectSettings.dither.linger * 1000))
            : 0;
        trailUniform[index * 4] = point.x;
        trailUniform[index * 4 + 1] = point.y;
        trailUniform[index * 4 + 2] = strength;
      });
      ditherTrail.splice(0, ditherTrail.length, ...ditherTrail.filter((point) => (
        effectSettings.dither.linger > 0 && timestamp - point.born < effectSettings.dither.linger * 1000
      )));

      const burstUniform = new Float32Array(4);
      if (ditherBurst && effectSettings.dither.clickBurst) {
        const burstProgress = Math.min(1, (timestamp - ditherBurst.start) / 1200);
        burstUniform[0] = ditherBurst.x;
        burstUniform[1] = ditherBurst.y;
        burstUniform[2] = Math.hypot(canvas.width, canvas.height) * burstProgress;
        burstUniform[3] = 1 - burstProgress * burstProgress * burstProgress;
        if (burstProgress >= 1) ditherBurst = null;
      }
      gl.uniform2f(mouseLocation, easedMouse.x, easedMouse.y);
      gl.uniform1f(timeLocation, reduceMotion.matches ? 0 : timestamp * 0.001);
      gl.uniform1f(transitionLocation, reduceMotion.matches ? 0 : liquidTransition.progress);
      gl.uniform1f(transitionDirectionLocation, liquidTransition.direction);
      gl.uniform1f(lensEnabledLocation, effectSettings.lens.enabled ? 1 : 0);
      gl.uniform1f(lensSizeLocation, effectSettings.lens.size);
      gl.uniform1f(lensDistortionLocation, effectSettings.lens.distortion);
      gl.uniform1f(lensChromaticLocation, effectSettings.lens.chromatic);
      gl.uniform1f(lensEdgeGlowLocation, effectSettings.lens.edgeGlow);
      gl.uniform1f(ambientMotionLocation, effectSettings.lens.ambientMotion);
      gl.uniform1f(liquidEnabledLocation, effectSettings.liquid.enabled ? 1 : 0);
      gl.uniform1f(liquidDistortionLocation, effectSettings.liquid.distortion);
      gl.uniform1f(liquidTurbulenceLocation, effectSettings.liquid.turbulence);
      gl.uniform1f(liquidGlowLocation, effectSettings.liquid.shaderGlow);
      gl.uniform1f(ditherEnabledLocation, effectSettings.dither.enabled ? 1 : 0);
      gl.uniform1f(ditherPixelSizeLocation, effectSettings.dither.pixelSize * Math.min(window.devicePixelRatio || 1, 1.35));
      gl.uniform1f(ditherLevelsLocation, effectSettings.dither.levels);
      gl.uniform1f(ditherIntensityLocation, effectSettings.dither.intensity);
      gl.uniform1f(ditherContrastLocation, effectSettings.dither.contrast);
      gl.uniform1f(ditherBrightnessLocation, effectSettings.dither.brightness);
      gl.uniform1f(ditherRevealRadiusLocation, effectSettings.dither.revealRadius * Math.min(window.devicePixelRatio || 1, 1.35));
      gl.uniform1f(ditherSoftnessLocation, effectSettings.dither.softness);
      gl.uniform1f(ditherRimLocation, effectSettings.dither.rim);
      gl.uniform1f(ditherReverseLocation, effectSettings.dither.reverse ? 1 : 0);
      gl.uniform1f(ditherAutoMotionLocation, effectSettings.dither.autoMotion && !reduceMotion.matches ? 1 : 0);
      gl.uniform1f(ditherMotionSpeedLocation, effectSettings.dither.motionSpeed);
      gl.uniform1f(ditherMotionAmountLocation, effectSettings.dither.motionAmount);
      gl.uniform1i(ditherPatternLocation, { bayer: 0, noise: 1, lines: 2 }[effectSettings.dither.pattern] ?? 0);
      gl.uniform1i(ditherPaletteLocation, effectSettings.dither.palette === "rgb" ? 1 : 0);
      gl.uniform3fv(ditherInkLocation, hexToRgb(effectSettings.dither.inkColor));
      gl.uniform3fv(ditherPaperLocation, hexToRgb(effectSettings.dither.paperColor));
      gl.uniform3fv(ditherRimColorLocation, hexToRgb(effectSettings.dither.rimColor));
      gl.uniform4fv(ditherTrailLocation, trailUniform);
      gl.uniform4fv(ditherBurstLocation, burstUniform);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      if (!reduceMotion.matches) animationFrame = requestAnimationFrame(draw);
    }

    image.addEventListener("load", () => {
      const texture = gl.createTexture();
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.uniform1i(textureLocation, 0);
      gl.uniform2f(textureSizeLocation, image.naturalWidth, image.naturalHeight);
      draw(performance.now());
    }, { once: true });

    image.addEventListener("error", () => {
      document.body.classList.add("webgl-unavailable");
    }, { once: true });

    window.addEventListener("pointermove", (event) => {
      if (!finePointer.matches) return;
      pointerInside = true;
      targetMouse.x = (event.clientX / Math.max(1, window.innerWidth)) * 2 - 1;
      targetMouse.y = (1 - event.clientY / Math.max(1, window.innerHeight)) * 2 - 1;
      if (reduceMotion.matches) {
        easedMouse.x = targetMouse.x;
        easedMouse.y = targetMouse.y;
        draw(performance.now());
      }
    }, { passive: true });

    window.addEventListener("pointerout", (event) => {
      if (!event.relatedTarget) pointerInside = false;
    }, { passive: true });

    window.addEventListener("pointerdown", (event) => {
      if (!effectSettings.dither.enabled || !effectSettings.dither.clickBurst) return;
      if (event.pointerType === "mouse" && event.button !== 0) return;
      ditherBurst = {
        x: event.clientX / Math.max(1, window.innerWidth),
        y: 1 - event.clientY / Math.max(1, window.innerHeight),
        start: performance.now(),
      };
    }, { passive: true });

    reduceMotion.addEventListener("change", () => {
      if (animationFrame) cancelAnimationFrame(animationFrame);
      animationFrame = 0;
      draw(performance.now());
    });

    image.src = canvas.dataset.skySrc;
  }

  feedController = initializeFakeFeed();
  tabController = initializeTabs();
  initializeEffectControls();
  initializeCardHover();
  updateDevices();
  window.setInterval(updateDevices, 10000);
  initializeLens();
  window.addEventListener("pagehide", () => {
    stopped = true;
    if (animationFrame) cancelAnimationFrame(animationFrame);
    if (tabAnimationFrame) cancelAnimationFrame(tabAnimationFrame);
    feedController?.destroy();
  }, { once: true });
})();
