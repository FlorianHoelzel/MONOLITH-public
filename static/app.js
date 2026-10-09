// Canvas text needs the same font as the rest of the dashboard.
if (typeof Chart !== "undefined") {
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 11;
  Chart.defaults.font.weight = 450;
  document.fonts.load('400 12px "Manrope"').then(() => {
    Object.values(Chart.instances).forEach(chart => chart.update("none"));
  });
}

let temperatureChart = null;
let humidityChart = null;
let pm25Chart = null;
let iaiChart = null;

let selectedHistoryRoom = "livingroom";
let selectedHistoryHours = 24;
let picnicHasLoaded = false;
let picnicIsLoading = false;
let plannerHasLoaded = false;
let plannerIsLoading = false;
let plannerVisibleMonth = new Date(
  new Date().getFullYear(),
  new Date().getMonth(),
  1
);
let plannerEvents = [];
let plannerUpcomingEvents = [];
let mealPlanHasLoaded = false;
let mealPlanIsLoading = false;
let randomRecipeHasLoaded = false;
let randomRecipeIsLoading = false;
let currentMealPlanRecipe = null;
let mealPlanBookmarks = [];
let draggedMealPlanItem = null;
let packagesHasLoaded = false;
let packagesIsLoading = false;
let packages = [];
let packagesFilter = "active";
let packagesTrackingConfigured = false;
let financeHasLoaded = false;
let financeIsLoading = false;
let servicesHasLoaded = false;
let servicesIsLoading = false;
let serviceLogsCursor = null;
let serviceLogsLoading = false;
let serviceLogsInitialized = false;
let serverHasLoaded = false;
let serverIsLoading = false;
let networkHasLoaded = false;
let networkIsLoading = false;
let networkData = null;
let networkFilter = "all";
let networkSearch = "";
let selectedNetworkDeviceMac = null;
let financeVisibleMonth = new Date(
  new Date().getFullYear(),
  new Date().getMonth(),
  1
);
let petHasLoaded = false;
let petIsLoading = false;
let petWeightChart = null;
let weatherHasLoaded = false;
let weatherIsLoading = false;
let weatherData = null;
let weatherTemperatureChart = null;
let weatherPrecipitationChart = null;
let weatherChartRange = "48";
let weatherSearchTimer = null;
let weatherSearchLocations = [];
const FINANCE_TRANSFER_HIDDEN_KEY = "monolith.finance.transfer.hidden";

const FEED_PAGE_SIZE = 30;
let feedEvents = [];
let feedHasMore = true;
let feedIsInitialized = false;
let feedIsRefreshing = false;
let feedIsLoadingMore = false;
let feedHasLoadedOlder = false;
const CAMERA_TIMELINE_DAYS = 7;
let cameraEvents = [];
let cameraHasLoaded = false;
let cameraIsLoading = false;
let cameraSelectedDayKey = "";
let cameraName = "Wohnzimmer";
let cameraLiveAvailable = false;
let cameraLiveReason = "not_configured";
let cameraLiveAttempt = 0;
let cameraLiveReadyTimer = null;
let cameraLiveRetryTimer = null;
let latestDevices = {};
let mediaRenderSignature = "";
let mediaActivitySignature = "";
let mediaPowerPending = null;
let mediaActionError = "";

const WEWASH_DRYER_DURATION_MINUTES = 162;


// ============================================================
// HELPERS
// ============================================================

function qs(selector) {
  return document.querySelector(selector);
}


function qsa(selector) {
  return document.querySelectorAll(selector);
}


function formatNumber(
  value,
  digits = 1
) {
  if (
    value === null
    || value === undefined
    || value === ""
  ) {
    return "-";
  }


  const number =
    Number(
      value
    );


  if (
    Number.isNaN(
      number
    )
  ) {
    return "-";
  }


  return number.toFixed(
    digits
  );
}


function formatDuration(seconds) {
  const totalSeconds =
    Math.max(
      0,
      Number(seconds) || 0
    );


  const minutes =
    Math.floor(
      totalSeconds / 60
    );


  const hours =
    Math.floor(
      minutes / 60
    );


  if (hours > 0) {
    const remainingMinutes =
      minutes % 60;


    if (
      remainingMinutes > 0
    ) {
      return (
        `${hours} Std. `
        + `${remainingMinutes} Min.`
      );
    }


    return `${hours} Std.`;
  }


  if (minutes > 0) {
    return `${minutes} Min.`;
  }


  return (
    `${Math.floor(totalSeconds)} Sek.`
  );
}


function escapeHtml(value) {
  return String(
    value ?? ""
  )
    .replaceAll(
      "&",
      "&amp;"
    )
    .replaceAll(
      "<",
      "&lt;"
    )
    .replaceAll(
      ">",
      "&gt;"
    )
    .replaceAll(
      '"',
      "&quot;"
    )
    .replaceAll(
      "'",
      "&#039;"
    );
}


function includesAny(
  text,
  values
) {
  return values.some(
    value =>
      text.includes(
        value
      )
  );
}


// ============================================================
// DATE / TIME
// ============================================================

function parseDateValue(value) {
  if (
    value === null
    || value === undefined
    || value === ""
  ) {
    return null;
  }


  if (
    typeof value
    === "number"
  ) {
    let timestamp =
      value;


    if (
      timestamp
      < 100000000000
    ) {
      timestamp *= 1000;
    }


    const date =
      new Date(
        timestamp
      );


    if (
      Number.isNaN(
        date.getTime()
      )
    ) {
      return null;
    }


    return date;
  }


  const text =
    String(
      value
    ).trim();


  if (!text) {
    return null;
  }


  if (
    /^\d+(?:\.\d+)?$/.test(
      text
    )
  ) {
    let timestamp =
      Number(
        text
      );


    if (
      timestamp
      < 100000000000
    ) {
      timestamp *= 1000;
    }


    const date =
      new Date(
        timestamp
      );


    if (
      Number.isNaN(
        date.getTime()
      )
    ) {
      return null;
    }


    return date;
  }


  const normalized =
    text.replace(
      " ",
      "T"
    );


  const date =
    new Date(
      normalized
    );


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return null;
  }


  return date;
}


function getEventTimestamp(event) {
  return (
    event.created_at
    ?? event.recorded_at
    ?? event.timestamp
    ?? event.time
    ?? event.datetime
    ?? event.date
    ?? null
  );
}


function formatEventTime(event) {
  const raw =
    getEventTimestamp(
      event
    );


  const date =
    parseDateValue(
      raw
    );


  if (!date) {
    return "";
  }


  return date.toLocaleTimeString(
    "de-DE",
    {
      hour:
        "2-digit",

      minute:
        "2-digit",
    }
  );
}


// ============================================================
// DEVICES
// ============================================================

function getAirPurifierMode(device) {
  const state = String(
    device.state ?? ""
  )
    .trim()
    .toLowerCase();


  const namedModes = {
    auto: "Auto",
    automatic: "Auto",
    sleep: "Sleep",
    silent: "Sleep",
    medium: "Medium",
    turbo: "Turbo",
  };


  if (namedModes[state]) {
    return namedModes[state];
  }


  const speed = Number(
    device.speed
  );


  if (!Number.isFinite(speed)) {
    return null;
  }


  // Der Pi liefert je nach Quelle entweder die Stufe 1-3
  // oder HomeKit-RotationSpeed als Prozentwert.
  if (speed === 1) {
    return "Sleep";
  }


  if (speed === 2) {
    return "Medium";
  }


  if (speed === 3) {
    return "Turbo";
  }


  if (speed <= 0) {
    return "Auto";
  }


  if (speed <= 25) {
    return "Sleep";
  }


  if (speed <= 60) {
    return "Medium";
  }


  return "Turbo";
}


function formatCurrency(cents) {
  return new Intl.NumberFormat(
    "de-DE",
    {
      style: "currency",
      currency: "EUR"
    }
  ).format(
    (Number(cents) || 0) / 100
  );
}


function getEventDateKey(event) {
  const date = parseDateValue(
    getEventTimestamp(event)
  );


  if (!date) {
    return "";
  }


  return [
    date.getFullYear(),
    String(
      date.getMonth() + 1
    ).padStart(2, "0"),
    String(
      date.getDate()
    ).padStart(2, "0"),
  ].join("-");
}


function formatEventDate(event) {
  const date = parseDateValue(
    getEventTimestamp(event)
  );


  if (!date) {
    return "";
  }


  return date.toLocaleDateString(
    "de-DE",
    {
      weekday: "long",
      day: "2-digit",
      month: "long",
      year: "numeric",
    }
  );
}


function formatCurrency(cents) {
  const value = Number(cents);


  if (!Number.isFinite(value)) {
    return "-";
  }


  return new Intl.NumberFormat(
    "de-DE",
    {
      style: "currency",
      currency: "EUR"
    }
  ).format(
    value / 100
  );
}


function getDeviceStatus(device) {
  if (device.type === "console") {
    if (device.network_connected === true) return { text: "An", stateClass: "on" };
    if (device.network_connected === false) return { text: "Aus", stateClass: "off" };
    return { text: "Unbekannt", stateClass: "unknown" };
  }

  // ----------------------------------------------------------
  // WASCHMASCHINE / TROCKNER
  // ----------------------------------------------------------

  if (
    device.type
    === "washer"
  ) {
    if (
      device.value
    ) {
      if (
        device.remaining
        > 0
      ) {
        return {
          text:
            `An · ${formatDuration(device.remaining)}`,

          stateClass:
            "active",
        };
      }


      return {
        text:
          "An",

        stateClass:
          "active",
      };
    }


    return {
      text:
        "Aus",

      stateClass:
        "off",
    };
  }


  // ----------------------------------------------------------
  // WEWASH TROCKNER
  // ----------------------------------------------------------

  if (
    device.type
    === "dryer"
  ) {
    if (!device.configured) {
      return {
        text:
          "Nicht eingerichtet",

        stateClass:
          "unknown",
      };
    }


    if (!device.connected) {
      return {
        text:
          "Nicht erreichbar",

        stateClass:
          "unknown",
      };
    }


    const activeDryer =
      device.active_dryer;

    if (activeDryer) {
      const dryerName =
        "Trockner";

      if (
        activeDryer.status
        === "PICKUP"
      ) {
        return {
          text:
            `${dryerName} fertig`,

          stateClass:
            "off",
        };
      }


      if (activeDryer.running) {
        const remainingSeconds =
          getDryerRemainingSeconds(
            activeDryer.status_changed_at
          );

        return {
          text:
            remainingSeconds === null
              ? "An"
              : (
                remainingSeconds === 0
                  ? "An · 0 Min."
                  : `An · ${formatDuration(remainingSeconds)}`
              ),

          stateClass:
            "active",
        };
      }


      return {
        text:
          `${dryerName} reserviert`,

        stateClass:
          "off",
      };
    }


    const available =
      device.available_dryers;

    if (!Number.isFinite(available)) {
      return {
        text:
          "Status unbekannt",

        stateClass:
          "unknown",
      };
    }


    return {
      text:
        available === 1
          ? "1 Trockner frei"
          : `${available} Trockner frei`,

      stateClass:
        "off",
    };
  }


  // ----------------------------------------------------------
  // AIR PURIFIER
  // ----------------------------------------------------------

  if (
    device.type
    === "air_purifier"
  ) {
    if (
    device.active
    ) {
      const mode =
        getAirPurifierMode(
          device
        );


      return {
        text:
          mode
            ? `An · ${mode}`
            : "An",

        stateClass:
          "on",
      };
    }


    return {
      text:
        "Aus",

      stateClass:
        "off",
    };
  }


  // ----------------------------------------------------------
  // MEDIA
  // ----------------------------------------------------------

  if (
    device.type
    === "media"
  ) {
    if (
      device.status_source === "pyatv"
    ) {
      const isPlaying =
        device.playing === true
        || device.value === "Playing";


      return {
        text:
          isPlaying
            ? (
                device.title
                  ? `Playing · ${device.title}`
                  : "Playing"
              )
            : "Paused",

        stateClass:
          isPlaying
            ? "on"
            : "off",
      };
    }


    if (
      device.value === true
      || device.value === "On"
      || device.value === "on"
      || device.value === "An"
      || device.value === 1
    ) {
      const detail =
        device.app_name
        || (
          Number.isFinite(
            Number(device.volume)
          )
            ? `Lautstärke ${device.volume}`
            : null
        );


      return {
        text:
          detail
            ? `An · ${detail}`
            : "An",

        stateClass:
          "on",
      };
    }


    if (
      device.value === false
      || device.value === "Off"
      || device.value === "off"
      || device.value === "Aus"
      || device.value === 0
    ) {
      return {
        text:
          "Aus",

        stateClass:
          "off",
      };
    }


    return {
      text:
        device.value
        || "Unbekannt",

      stateClass:
        "unknown",
    };
  }


  // ----------------------------------------------------------
  // VACUUM
  // ----------------------------------------------------------

  if (
    device.type
    === "vacuum"
  ) {
    const vacuumStates = {
      docked: {
        text:
          "Gedockt",

        stateClass:
          "off",
      },

      charging: {
        text:
          "Lädt",

        stateClass:
          "charging",
      },

      cleaning: {
        text:
          "Reinigt",

        stateClass:
          "active",
      },

      paused: {
        text:
          "Pausiert",

        stateClass:
          "off",
      },

      returning_to_dock: {
        text:
          "Fährt zur Station",

        stateClass:
          "active",
      },
    };


    const vacuumStatus =
      vacuumStates[
        String(
          device.value
        ).toLowerCase()
      ];


    if (vacuumStatus) {
      return vacuumStatus;
    }


    if (
      !device.value
      || device.value
      === "Unbekannt"
    ) {
      return {
        text:
          "Unbekannt",

        stateClass:
          "unknown",
      };
    }


    return {
      text:
        "Unbekannt",

      stateClass:
        "unknown",
    };
  }


  // ----------------------------------------------------------
  // LIGHT / SWITCH
  // ----------------------------------------------------------

  const isOn =
    device.value === true
    || device.value === "on"
    || device.value === "On"
    || device.value === "An"
    || device.value === 1;


  return {
    text:
      isOn
        ? "An"
        : "Aus",

    stateClass:
      isOn
        ? "on"
        : "off",
  };
}


function renderDevices(devices) {
  Object.entries(
    devices
  ).forEach(
    ([
      deviceId,
      device
    ]) => {

      const card =
        qs(
          `[data-device="${deviceId}"]`
        );


      if (!card) {
        return;
      }


      const stateElement =
        card.querySelector(
          ".device-state"
        );


      const textElement =
        card.querySelector(
          ".device-state-text"
        );


      const status =
        getDeviceStatus(
          device
        );


      stateElement.classList.remove(
        "on",
        "off",
        "active",
        "charging",
        "unknown"
      );


      stateElement.classList.add(
        status.stateClass
      );


      textElement.textContent =
        status.text;


      card.classList.remove(
        "is-on",
        "is-off",
        "is-active",
        "is-charging",
        "is-unknown"
      );


      if (
        status.stateClass
        === "on"
      ) {
        card.classList.add(
          "is-on"
        );
      }


      if (
        status.stateClass
        === "off"
      ) {
        card.classList.add(
          "is-off"
        );
      }


      if (
        status.stateClass
        === "active"
      ) {
        card.classList.add(
          "is-active"
        );
      }


      if (
        status.stateClass
        === "charging"
      ) {
        card.classList.add(
          "is-charging"
        );
      }


      if (
        status.stateClass
        === "unknown"
      ) {
        card.classList.add(
          "is-unknown"
        );
      }
    }
  );
}


async function updateDevices() {
  try {
    const response =
      await fetch(
        "/api/devices"
      );


    if (!response.ok) {
      return;
    }


    const devices =
      await response.json();


    latestDevices = devices;


    renderDevices(
      devices
    );

  } catch (error) {
    console.error(
      "Fehler beim Laden der Geräte:",
      error
    );


  }
}


// ============================================================
// MEDIA
// ============================================================

function isMediaDeviceOn(device) {
  return (
    device.value === true
    || device.value === "On"
    || device.value === "on"
    || device.value === "An"
    || device.value === 1
  );
}


function isMediaPlaybackActive(device) {
  if (device.connected === false) {
    return false;
  }


  if (
    device.status_source
    !== "webos"
  ) {
    return (
      device.playing === true
      || device.value === "Playing"
      || String(
        device.playback_state || ""
      ).toLowerCase() === "playing"
    );
  }


  return isMediaDeviceOn(
    device
  );
}


function getMediaDeviceState(device) {
  if (
    device.status_source
    === "pc_agent"
  ) {
    if (!device.connected) {
      return {
        key: "offline",
        label: "Nicht erreichbar",
      };
    }


    if (isMediaPlaybackActive(device)) {
      return {
        key: "playing",
        label: "Wiedergabe aktiv",
      };
    }


    return {
      key: "idle",
      label: device.media_visible
        ? "Pausiert"
        : "Bereit",
    };
  }


  if (
    device.status_source
    === "pyatv"
  ) {
    if (!device.connected) {
      return {
        key: "offline",
        label: "Nicht erreichbar",
      };
    }


    if (isMediaPlaybackActive(device)) {
      return {
        key: "playing",
        label: "Wiedergabe aktiv",
      };
    }


    if (
      String(
        device.power_state || ""
      ).toLowerCase() === "off"
    ) {
      return {
        key: "off",
        label: "Ausgeschaltet",
      };
    }


    return {
      key: "idle",
      label: "Bereit",
    };
  }


  if (isMediaDeviceOn(device)) {
    return {
      key: "on",
      label: "Eingeschaltet",
    };
  }


  if (
    device.value === false
    || device.value === "Off"
    || device.value === "off"
    || device.value === "Aus"
    || device.value === 0
  ) {
    return {
      key: "off",
      label: "Standby",
    };
  }


  return {
    key: device.connected
      ? "idle"
      : "offline",
    label: device.connected
      ? "Bereit"
      : "Nicht erreichbar",
  };
}


function formatMediaPlaybackState(value) {
  const labels = {
    changing: "Wechselt",
    closed: "Geschlossen",
    idle: "Bereit",
    loading: "Wird geladen",
    opened: "Geöffnet",
    paused: "Pausiert",
    playing: "Spielt",
    seeking: "Spult",
    stopped: "Gestoppt",
  };


  const normalized = String(
    value || ""
  ).toLowerCase();


  return labels[normalized]
    || (
      normalized
        ? value
        : "Unbekannt"
    );
}


function formatMediaLastSeen(value) {
  const date = parseDateValue(
    value
  );


  if (!date) {
    return "Noch nicht gesehen";
  }


  return date.toLocaleString(
    "de-DE",
    {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


function mediaDeviceDetails(device) {
  if (
    device.status_source
    === "webos"
  ) {
    const volume = Number(
      device.volume
    );


    return [
      [
        "Aktive App",
        device.app_name || "Keine App aktiv",
      ],
      [
        "Lautstärke",
        Number.isFinite(volume)
          ? `${Math.round(volume)} %`
          : "Nicht verfügbar",
      ],
      [
        "Ton",
        device.muted === true
          ? "Stumm"
          : (
              device.muted === false
                ? "Aktiv"
                : "Nicht verfügbar"
            ),
      ],
    ];
  }


  if (
    device.status_source
    === "pc_agent"
  ) {
    return [
      [
        "Anwendung",
        device.app_name || "Unbekannte Anwendung",
      ],
      [
        "Inhalt",
        device.title || "Kein Titel gemeldet",
      ],
      [
        "Künstler",
        device.artist || device.album || "Nicht gemeldet",
      ],
    ];
  }


  return [
    [
      "Wiedergabe",
      formatMediaPlaybackState(
        device.playback_state
      ),
    ],
    [
      "Inhalt",
      device.title || "Kein Titel gemeldet",
    ],
    [
      "Zuletzt gesehen",
      formatMediaLastSeen(
        device.last_seen
      ),
    ],
  ];
}


function mediaDeviceCardMarkup(
  deviceId,
  device
) {
  const state = getMediaDeviceState(
    device
  );


  const details = mediaDeviceDetails(
    device
  )
    .map(
      ([label, value]) => `
        <div class="media-device-detail">
          <dt>${escapeHtml(label)}</dt>
          <dd>${escapeHtml(value)}</dd>
        </div>
      `
    )
    .join("");


  const canControlPower = (
    deviceId === "device_display_01"
    && device.read_only !== true
  );


  const powerIsOn = isMediaDeviceOn(
    device
  );


  const isPending =
    mediaPowerPending === deviceId;


  const footer = canControlPower
    ? `
      <button
        class="media-power-button ${powerIsOn ? "is-on" : ""}"
        type="button"
        data-media-power
        data-media-device="${escapeHtml(deviceId)}"
        data-media-power-value="${powerIsOn ? "false" : "true"}"
        aria-label="${escapeHtml(device.name)} ${powerIsOn ? "ausschalten" : "einschalten"}"
        aria-pressed="${powerIsOn ? "true" : "false"}"
        ${isPending ? "disabled aria-busy=\"true\"" : ""}
      >
        <i class="ti ${isPending ? "ti-loader-2" : "ti-power"}" aria-hidden="true"></i>
        <span>${isPending ? "Wird geschaltet" : (powerIsOn ? "Ausschalten" : "Einschalten")}</span>
      </button>
    `
    : `
      <span class="media-status-source">
        <i class="ti ti-broadcast" aria-hidden="true"></i>
        Live-Status
      </span>
    `;


  return `
    <article
      class="media-device-card is-${state.key}"
      data-media-card="${escapeHtml(deviceId)}"
    >
      <div class="media-device-card-header">
        <div class="media-device-identity">
          <span class="media-device-icon" aria-hidden="true">
            <i class="${escapeHtml(device.icon || "ti ti-device-speaker")}"></i>
          </span>
          <div>
            <h4>${escapeHtml(device.name)}</h4>
            <span>${escapeHtml(device.room)}</span>
          </div>
        </div>

        <span class="media-connection-state is-${state.key}">
          <span aria-hidden="true"></span>
          ${escapeHtml(state.label)}
        </span>
      </div>

      <dl class="media-device-details">
        ${details}
      </dl>

      <div class="media-device-card-footer">
        ${footer}
      </div>
    </article>
  `;
}


function renderMediaNowPlaying(
  mediaDevices
) {
  const container = qs(
    "[data-media-now-playing]"
  );


  if (!container) {
    return;
  }


  const title = container.querySelector(
    "h3"
  );
  const detail = container.querySelector(
    "[data-media-now-playing-detail]"
  );
  const label = container.querySelector(
    ".media-now-playing-label"
  );
  const visual = container.querySelector(
    ".media-now-playing-visual"
  );
  const artwork = container.querySelector(
    "[data-media-now-playing-artwork]"
  );
  const icon = container.querySelector(
    ".media-now-playing-visual > i"
  );
  const meta = container.querySelector(
    "[data-media-now-playing-meta]"
  );


  const rankedDevices = mediaDevices
    .map(
      ([deviceId, device]) => ({
        deviceId,
        device,
      })
    )
    .sort(
      (left, right) => {
        const leftPlaying = left.device.status_source !== "webos"
          && isMediaPlaybackActive(left.device);
        const rightPlaying = right.device.status_source !== "webos"
          && isMediaPlaybackActive(right.device);


        return Number(rightPlaying)
          - Number(leftPlaying);
      }
    );
  const activeDevice = rankedDevices.find(
      item => isMediaPlaybackActive(
        item.device
      )
    );
  const featuredDevice = activeDevice
    || rankedDevices.find(
      item => (
        item.device.status_source === "pc_agent"
        && item.device.media_visible === true
        && Boolean(
          item.device.title
          || item.device.app_name
        )
      )
    );


  container.classList.remove(
    "is-loading",
    "is-idle",
    "is-offline",
    "is-active",
    "is-playing"
  );


  if (featuredDevice) {
    const device = featuredDevice.device;
    const isPlayback =
      device.status_source !== "webos";
    const playbackActive =
      isMediaPlaybackActive(device);
    const headline = (
      device.title
      || device.app_name
      || device.name
    );
    const detailText = (
      device.artist
      || (
        isPlayback
          ? (
              playbackActive
                ? `${device.name} spielt gerade`
                : `${device.name} ist pausiert`
            )
          : `${device.name} ist eingeschaltet`
      )
    );
    const metaValues = [
      device.name,
      device.room,
    ];


    if (
      device.status_source === "pc_agent"
      && device.app_name
    ) {
      metaValues.push(
        device.app_name
      );
    }


    if (
      Number.isFinite(
        Number(device.volume)
      )
    ) {
      metaValues.push(
        `Lautstärke ${Math.round(Number(device.volume))} %`
      );
    }


    container.classList.add(
      "is-active"
    );


    if (playbackActive) {
      container.classList.add(
        "is-playing"
      );
    }


    label.textContent = playbackActive
      ? (
          isPlayback
            ? "Läuft gerade"
            : "Aktives Gerät"
        )
      : "Pausiert";
    title.textContent = headline;
    detail.textContent = detailText;
    icon.className = device.icon
      || "ti ti-player-play";
    const artworkUrl = String(
      device.artwork_url || ""
    ).trim();


    visual?.classList.toggle(
      "has-artwork",
      Boolean(artworkUrl)
    );


    if (artwork) {
      artwork.hidden = !artworkUrl;

      if (artworkUrl) {
        if (
          artwork.getAttribute("src")
          !== artworkUrl
        ) {
          artwork.src = artworkUrl;
        }
      } else {
        artwork.removeAttribute("src");
      }
    }
    meta.innerHTML = metaValues
      .map(
        value => `<span>${escapeHtml(value)}</span>`
      )
      .join("");


    return;
  }


  const connectedCount = mediaDevices
    .filter(
      ([, device]) => device.connected === true
    )
    .length;


  const hasAvailableDevice = mediaDevices
    .some(
      ([, device]) => {
        const state = getMediaDeviceState(
          device
        );


        return state.key !== "offline";
      }
    );


  container.classList.add(
    hasAvailableDevice
      ? "is-idle"
      : "is-offline"
  );
  label.textContent = "Wiedergabe";
  title.textContent = hasAvailableDevice
    ? "Gerade läuft nichts"
    : "Keine Mediengeräte erreichbar";
  detail.textContent = hasAvailableDevice
    ? "Die verbundenen Geräte sind bereit."
    : "MONOLITH wartet auf den nächsten Gerätestatus.";
  icon.className = hasAvailableDevice
    ? "ti ti-player-pause"
    : "ti ti-devices-off";
  visual?.classList.remove(
    "has-artwork"
  );


  if (artwork) {
    artwork.hidden = true;
    artwork.removeAttribute("src");
  }
  meta.innerHTML = connectedCount > 0
    ? `<span>${escapeHtml(connectedCount)} ${connectedCount === 1 ? "Gerät verbunden" : "Geräte verbunden"}</span>`
    : "";
}


function renderMediaDashboard(devices) {
  const mediaDevices = Object.entries(
    devices || {}
  ).filter(
    ([, device]) => (
      device.type === "media"
      && device.media_visible !== false
    )
  );


  const signature = JSON.stringify({
    mediaDevices,
    mediaPowerPending,
    mediaActionError,
  });


  if (
    signature === mediaRenderSignature
  ) {
    return;
  }


  mediaRenderSignature = signature;


  const grid = qs(
    "[data-media-devices]"
  );
  const headerStatus = qs(
    "[data-media-header-status]"
  );
  const actionError = qs(
    "[data-media-action-error]"
  );


  if (
    !grid
    || !headerStatus
    || !actionError
  ) {
    return;
  }


  const activeCount = mediaDevices
    .filter(
      ([, device]) => isMediaPlaybackActive(
        device
      )
    )
    .length;
  const connectedCount = mediaDevices
    .filter(
      ([, device]) => device.connected === true
    )
    .length;


  headerStatus.textContent = mediaDevices.length
    ? `${activeCount} aktiv, ${connectedCount} verbunden`
    : "Keine Mediengeräte eingerichtet";


  actionError.hidden = !mediaActionError;
  actionError.textContent = mediaActionError;


  if (!mediaDevices.length) {
    grid.innerHTML = `
      <div class="media-empty-state">
        <i class="ti ti-device-tv-off" aria-hidden="true"></i>
        <strong>Keine Mediengeräte eingerichtet</strong>
        <span>Eingerichtete Mediengeräte erscheinen automatisch hier.</span>
      </div>
    `;
  } else {
    grid.innerHTML = mediaDevices
      .map(
        ([deviceId, device]) => mediaDeviceCardMarkup(
          deviceId,
          device
        )
      )
      .join("");
  }


  renderMediaNowPlaying(
    mediaDevices
  );
}


function renderMediaUnavailable() {
  const headerStatus = qs(
    "[data-media-header-status]"
  );
  const grid = qs(
    "[data-media-devices]"
  );


  if (headerStatus) {
    headerStatus.textContent =
      "Status nicht verfügbar";
  }


  if (grid) {
    grid.innerHTML = `
      <div class="media-empty-state is-error">
        <i class="ti ti-plug-off" aria-hidden="true"></i>
        <strong>Gerätestatus nicht verfügbar</strong>
        <span>MONOLITH versucht es automatisch erneut.</span>
      </div>
    `;
  }
}


function renderMediaActivity(
  events,
  failed = false
) {
  const container = qs(
    "[data-media-activity]"
  );


  if (!container) {
    return;
  }


  const mediaEvents = failed
    ? []
    : compactFeedEvents(
        events || []
      )
        .filter(
          event => getFeedMeta(event).type === "media"
        )
        .slice(0, 8);


  const signature = JSON.stringify({
    failed,
    events: mediaEvents.map(
      event => [
        event.id,
        event.title,
        event.detail,
        getEventTimestamp(event),
      ]
    ),
  });


  if (
    signature === mediaActivitySignature
  ) {
    return;
  }


  mediaActivitySignature = signature;


  if (failed) {
    container.innerHTML = `
      <div class="media-empty-state is-error">
        <i class="ti ti-history-off" aria-hidden="true"></i>
        <strong>Aktivitäten nicht verfügbar</strong>
        <span>Der Feed wird automatisch erneut geladen.</span>
      </div>
    `;


    return;
  }


  if (!mediaEvents.length) {
    container.innerHTML = `
      <div class="media-empty-state">
        <i class="ti ti-history" aria-hidden="true"></i>
        <strong>Noch keine Medienaktivitäten</strong>
        <span>Neue Wiedergabe- und Gerätestatus erscheinen hier.</span>
      </div>
    `;


    return;
  }


  container.innerHTML = mediaEvents
    .map(
      event => {
        const meta = getFeedMeta(
          event
        );
        const room = (
          meta.label
          || event.room
          || "Medien"
        );
        const detail = event.detail
          ? `<p>${escapeHtml(event.detail)}</p>`
          : "";
        const timestamp = getEventTimestamp(
          event
        );


        return `
          <article class="media-activity-item is-${escapeHtml(meta.state)}">
            <span class="media-activity-icon" aria-hidden="true">
              <i class="${escapeHtml(meta.icon)}"></i>
            </span>
            <div>
              <span class="media-activity-room">${escapeHtml(room)}</span>
              <strong>${escapeHtml(getFeedTitle(event))}</strong>
              ${detail}
            </div>
            <time datetime="${escapeHtml(timestamp)}">${escapeHtml(formatEventTime(event))}</time>
          </article>
        `;
      }
    )
    .join("");
}


async function setMediaPower(button) {
  const deviceId = button.dataset.mediaDevice;
  const requestedValue =
    button.dataset.mediaPowerValue === "true";


  if (
    !deviceId
    || mediaPowerPending
  ) {
    return;
  }


  mediaPowerPending = deviceId;
  mediaActionError = "";
  mediaRenderSignature = "";
  renderMediaDashboard(
    latestDevices
  );


  try {
    const response = await fetch(
      "/api/state",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          device: deviceId,
          value: requestedValue,
        }),
      }
    );
    const data = await response.json();


    if (!response.ok) {
      throw new Error(
        data.error
        || "Der Fernseher konnte nicht geschaltet werden."
      );
    }


    await updateDevices();

  } catch (error) {
    mediaActionError = error.message
      || "Der Fernseher konnte nicht geschaltet werden.";

  } finally {
    mediaPowerPending = null;
    mediaRenderSignature = "";
    renderMediaDashboard(
      latestDevices
    );
  }
}


function setupMedia() {
  const artwork = qs(
    "[data-media-now-playing-artwork]"
  );


  artwork?.addEventListener(
    "error",
    () => {
      artwork.hidden = true;
      artwork.closest(
        ".media-now-playing-visual"
      )?.classList.remove(
        "has-artwork"
      );
    }
  );


  qs("#dashboard-media")?.addEventListener(
    "click",
    event => {
      const button = event.target.closest(
        "[data-media-power]"
      );


      if (button) {
        setMediaPower(
          button
        );
      }
    }
  );
}


// ============================================================
// CLIMATE - CURRENT
// ============================================================

function renderSensors(sensors) {
  Object.entries(
    sensors
  ).forEach(
    ([
      roomId,
      sensor
    ]) => {

      const card =
        qs(
          `[data-sensor-room="${roomId}"]`
        );


      if (!card) {
        return;
      }


      const temperatureElement =
        card.querySelector(
          ".temperature-value"
        );


      const humidityElement =
        card.querySelector(
          ".humidity-value"
        );


      temperatureElement.textContent =
        formatNumber(
          sensor.temperature,
          1
        );


      humidityElement.textContent =
        formatNumber(
          sensor.humidity,
          1
        );
    }
  );
}


async function updateSensors() {
  try {
    const response =
      await fetch(
        "/api/sensors"
      );


    if (!response.ok) {
      return;
    }


    const sensors =
      await response.json();


    renderSensors(
      sensors
    );

  } catch (error) {
    console.error(
      "Fehler beim Laden der Sensoren:",
      error
    );
  }
}


// ============================================================
// DASHBOARD TABS
// ============================================================

let dashboardNavigationTimer = null;


function applyDashboardGroup(
  target,
  animate = false
) {
  const targetButton = qs(
    `.dashboard-tab-button[data-dashboard-tab="${target}"]`
  );
  const nextGroup = targetButton?.closest(
    ".dashboard-tab-group"
  );

  if (!nextGroup) {
    return;
  }

  const groups = Array.from(
    qsa(
      ".dashboard-tab-group"
    )
  );
  const previousPositions = animate
    ? new Map(
        groups.map(group => [
          group.dataset.dashboardGroup,
          group.getBoundingClientRect().left
        ])
      )
    : null;

  groups.forEach(group => {
    const active = group === nextGroup;
    const groupButton = group.querySelector(
      "[data-dashboard-group-button]"
    );
    const children = group.querySelector(
      ".dashboard-tab-children"
    );

    group.classList.toggle(
      "active",
      active
    );
    group.classList.remove(
      "is-leaving"
    );
    groupButton?.setAttribute(
      "aria-expanded",
      active ? "true" : "false"
    );
    children?.setAttribute(
      "aria-hidden",
      active ? "false" : "true"
    );
  });

  if (!previousPositions) {
    return;
  }

  groups.forEach(group => {
    const previousLeft = previousPositions.get(
      group.dataset.dashboardGroup
    );
    const currentLeft = group.getBoundingClientRect().left;
    const offset = previousLeft - currentLeft;

    if (Math.abs(offset) < 0.5) {
      return;
    }

    group.animate(
      [
        { transform: `translateX(${offset}px)` },
        { transform: "translateX(0)" }
      ],
      {
        duration: 260,
        easing: "cubic-bezier(0.16, 1, 0.3, 1)"
      }
    );
  });

  nextGroup.querySelector(
    ".dashboard-tab-children"
  )?.animate(
    [
      {
        opacity: 0,
        transform: "translateX(-4px)"
      },
      {
        opacity: 1,
        transform: "translateX(0)"
      }
    ],
    {
      duration: 180,
      delay: 70,
      easing: "cubic-bezier(0.16, 1, 0.3, 1)",
      fill: "backwards"
    }
  );
}


function activateDashboardTab(
  target,
  animateNavigation = true
) {
  const targetButton = qs(
    `.dashboard-tab-button[data-dashboard-tab="${target}"]`
  );

  if (!targetButton) {
    return;
  }

  if (dashboardNavigationTimer) {
    clearTimeout(
      dashboardNavigationTimer
    );
    dashboardNavigationTimer = null;
  }

  const currentGroup = qs(
    ".dashboard-tab-group.active"
  );
  const nextGroup = targetButton.closest(
    ".dashboard-tab-group"
  );
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;
  const switchesGroup = currentGroup
    && nextGroup
    && currentGroup !== nextGroup;

  const commit = () => {
    applyDashboardGroup(
      target,
      switchesGroup
        && animateNavigation
        && !reduceMotion
    );
    commitDashboardTab(
      target
    );
    dashboardNavigationTimer = null;
  };

  if (
    !switchesGroup
    || !animateNavigation
    || reduceMotion
  ) {
    commit();
    return;
  }

  currentGroup.classList.add(
    "is-leaving"
  );
  dashboardNavigationTimer = setTimeout(
    commit,
    90
  );
}


function commitDashboardTab(
  target
) {
  if (target !== "cameras") {
    stopCameraLive();
  }

  qsa(
    ".dashboard-tab-button"
  ).forEach(
    button => {

      const active =
        button.dataset.dashboardTab
        === target;


      button.classList.toggle(
        "active",
        active
      );


      button.setAttribute(
        "aria-selected",
        active
          ? "true"
          : "false"
      );


      button.tabIndex =
        active
          ? 0
          : -1;
    }
  );


  qsa(
    "[data-dashboard-panel]"
  ).forEach(
    panel => {

      panel.hidden =
        panel.dataset.dashboardPanel
        !== target;
    }
  );


  const layout =
    qs(
      ".main-layout"
    );


  if (layout) {
    layout.dataset.activeDashboardTab =
      target;
  }


  if (
    target === "climate"
    && isHistoryTabActive()
  ) {
    requestAnimationFrame(
      () => {

        ensureHistoryCharts();

        temperatureChart?.resize();

        humidityChart?.resize();

        pm25Chart?.resize();

        iaiChart?.resize();

        loadHistory();
      }
    );
  }


  if (target === "weather") {
    loadWeather(weatherHasLoaded);
  }


  if (
    target === "shopping"
    && !picnicHasLoaded
  ) {
    loadPicnic();
  }


  if (
    target === "planner"
    && !plannerHasLoaded
  ) {
    loadPlanner();
  }


  if (target === "meal-plan") {
    loadMealPlan();
    loadRandomRecipe();
  }


  if (target === "packages") {
    loadPackages(packagesHasLoaded);
  }


  if (
    target === "finance"
    && !financeHasLoaded
  ) {
    loadFinances();
  }


  if (target === "services") {
    loadServices(
      servicesHasLoaded
    );
    loadServiceLogs(
      !serviceLogsInitialized
    );
  }


  if (target === "server") {
    loadServerStatus(true);
  }


  if (target === "network") {
    loadNetworkStatus(networkHasLoaded);
  }


  if (target === "cameras") {
    loadCameraEvents();
    startCameraLive();
  }


  if (
    target === "pet"
  ) {
    loadPet(true);
  }
}


// ============================================================
// RASPBERRY PI
// ============================================================

function formatServerBytes(bytes) {
  if (
    bytes === null
    || bytes === undefined
    || bytes === ""
  ) {
    return "-";
  }

  const value = Number(bytes);

  if (!Number.isFinite(value) || value < 0) {
    return "-";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  let displayValue = value;
  let unitIndex = 0;

  while (
    displayValue >= 1024
    && unitIndex < units.length - 1
  ) {
    displayValue /= 1024;
    unitIndex += 1;
  }

  const digits = unitIndex >= 3 ? 1 : 0;
  return `${displayValue.toFixed(digits)} ${units[unitIndex]}`;
}


function formatServerPercent(value) {
  if (
    value === null
    || value === undefined
    || value === ""
  ) {
    return "-";
  }

  const number = Number(value);
  return Number.isFinite(number)
    ? `${number.toLocaleString("de-DE", { maximumFractionDigits: 1 })} %`
    : "-";
}


function formatServerDuration(seconds) {
  if (
    seconds === null
    || seconds === undefined
    || seconds === ""
  ) {
    return "-";
  }

  const value = Number(seconds);

  if (!Number.isFinite(value) || value < 0) {
    return "-";
  }

  const totalMinutes = Math.floor(value / 60);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return `${days} Tage, ${hours} Std.`;
  }

  if (hours > 0) {
    return `${hours} Std., ${minutes} Min.`;
  }

  return `${minutes} Min.`;
}


function serverUsageState(value, warning = 85, critical = 95) {
  if (
    value === null
    || value === undefined
    || value === ""
  ) {
    return "unknown";
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "unknown";
  }

  if (number >= critical) {
    return "critical";
  }

  return number >= warning ? "warning" : "healthy";
}


function setServerMetric(name, value, detail, percent, state) {
  const metric = qs(`[data-server-metric="${name}"]`);

  if (!metric) {
    return;
  }

  const safePercent = Math.max(
    0,
    Math.min(100, Number(percent) || 0)
  );
  metric.className = `server-metric is-${state || "unknown"}`;
  metric.querySelector("[data-server-metric-value]").textContent = value;
  metric.querySelector("[data-server-metric-detail]").textContent = detail;
  const fill = metric.querySelector("[data-server-meter-fill]");

  if (fill) {
    fill.style.width = `${safePercent}%`;
  }
}


function renderServerStatus(data) {
  const cpu = data.metrics?.cpu || {};
  const temperature = data.metrics?.temperature || {};
  const memory = data.metrics?.memory;
  const swap = data.metrics?.swap;
  const storage = data.metrics?.storage;
  const network = data.metrics?.network || {};
  const identity = data.identity || {};

  setServerMetric(
    "cpu",
    formatServerPercent(cpu.usage_percent),
    [
      cpu.logical_cores ? `${cpu.logical_cores} Kerne` : null,
      cpu.frequency_mhz ? `${cpu.frequency_mhz} MHz` : null
    ].filter(Boolean).join(" · ") || "Keine Messdaten",
    cpu.usage_percent,
    serverUsageState(cpu.usage_percent)
  );
  setServerMetric(
    "temperature",
    temperature.celsius !== null
      && temperature.celsius !== undefined
      && Number.isFinite(Number(temperature.celsius))
      ? `${Number(temperature.celsius).toLocaleString("de-DE", { maximumFractionDigits: 1 })} °C`
      : "-",
    temperature.celsius === null || temperature.celsius === undefined
      ? "Sensor nicht verfügbar"
      : "SoC-Temperatur",
    temperature.celsius,
    temperature.state || "unknown"
  );
  setServerMetric(
    "memory",
    formatServerPercent(memory?.usage_percent),
    memory
      ? `${formatServerBytes(memory.used_bytes)} von ${formatServerBytes(memory.total_bytes)}`
      : "Nicht verfügbar",
    memory?.usage_percent,
    serverUsageState(memory?.usage_percent)
  );
  setServerMetric(
    "storage",
    formatServerPercent(storage?.usage_percent),
    storage
      ? `${formatServerBytes(storage.free_bytes)} frei`
      : "Nicht verfügbar",
    storage?.usage_percent,
    serverUsageState(storage?.usage_percent)
  );

  const performance = qs("[data-server-performance]");

  if (performance) {
    const stats = [
      ["Load 1 Min.", cpu.load_1 ?? "-"],
      ["Load 5 Min.", cpu.load_5 ?? "-"],
      ["Load 15 Min.", cpu.load_15 ?? "-"],
      ["CPU-Takt", cpu.frequency_mhz ? `${cpu.frequency_mhz} MHz` : "-"],
      ["Swap", swap ? formatServerPercent(swap.usage_percent) : "-"],
      ["Systemlaufzeit", formatServerDuration(data.metrics?.uptime_seconds)]
    ];
    performance.innerHTML = stats.map(([label, value]) => `
      <div class="server-stat">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join("");
  }

  const identityList = qs("[data-server-identity]");

  if (identityList) {
    const bootedAt = data.metrics?.booted_at
      ? new Date(data.metrics.booted_at)
      : null;
    const identityRows = [
      ["Modell", identity.model || "-"],
      ["Betriebssystem", identity.operating_system || "-"],
      ["Kernel", identity.kernel || "-"],
      ["Architektur", identity.architecture || "-"],
      ["Hostname", identity.hostname || "-"],
      ["Gestartet", bootedAt && !Number.isNaN(bootedAt.getTime())
        ? bootedAt.toLocaleString("de-DE", { dateStyle: "medium", timeStyle: "short" })
        : "-"]
    ];
    identityList.innerHTML = identityRows.map(([label, value]) => `
      <div>
        <dt>${escapeHtml(label)}</dt>
        <dd title="${escapeHtml(value)}">${escapeHtml(value)}</dd>
      </div>
    `).join("");
  }

  const networkBody = qs("[data-server-network]");

  if (networkBody) {
    networkBody.innerHTML = `
      <div class="server-network-address">
        <span>IPv4-Adresse</span>
        <strong>${escapeHtml(network.ipv4 || "Nicht verfügbar")}</strong>
        <small>${escapeHtml(network.interface || "Keine Schnittstelle erkannt")}</small>
      </div>
      <div class="server-network-traffic">
        <div>
          <span><i class="ti ti-arrow-down" aria-hidden="true"></i> Empfangen</span>
          <strong>${escapeHtml(formatServerBytes(network.rx_bytes))}</strong>
        </div>
        <div>
          <span><i class="ti ti-arrow-up" aria-hidden="true"></i> Gesendet</span>
          <strong>${escapeHtml(formatServerBytes(network.tx_bytes))}</strong>
        </div>
      </div>
    `;
  }

  const checks = qs("[data-server-checks]");

  if (checks) {
    const rows = Array.isArray(data.checks) ? data.checks : [];
    checks.innerHTML = rows.length
      ? rows.map(check => `
          <article class="server-check is-${escapeHtml(check.state || "unknown")}">
            <span class="server-check-icon" aria-hidden="true"><i class="ti ${escapeHtml(check.icon || "ti-info-circle")}"></i></span>
            <div>
              <span>${escapeHtml(check.label)}</span>
              <small>${escapeHtml(check.detail)}</small>
            </div>
            <strong>${escapeHtml(check.value)}</strong>
          </article>
        `).join("")
      : '<p class="server-empty">Keine Prüfdaten verfügbar.</p>';
  }

  const health = qs("[data-server-health]");
  const healthState = ["healthy", "warning", "critical", "unknown"]
    .includes(data.health?.state)
    ? data.health.state
    : "unknown";

  if (health) {
    health.className = `server-overall-status is-${healthState}`;
    health.textContent = data.health?.label || "Status unbekannt";
  }

  const subtitle = qs("[data-server-subtitle]");

  if (subtitle) {
    subtitle.textContent = data.source === "raspberry-pi"
      ? `${identity.model || "Raspberry Pi"} · ${identity.hostname || "Host"}`
      : "Lokale Entwicklungsvorschau · Pi-Sensoren sind hier nicht verfügbar";
  }

  const updated = qs("[data-server-updated]");

  if (updated) {
    const checkedAt = new Date(data.checked_at || Date.now());
    updated.textContent = `Zuletzt geprüft: ${checkedAt.toLocaleTimeString("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    })}`;
  }
}


function renderServerError() {
  const health = qs("[data-server-health]");

  if (health) {
    health.className = "server-overall-status is-critical";
    health.textContent = "Abfrage fehlgeschlagen";
  }

  qsa("[data-server-metric]").forEach(metric => {
    metric.className = "server-metric is-unknown";
    metric.querySelector("[data-server-metric-value]").textContent = "-";
    metric.querySelector("[data-server-metric-detail]").textContent = "Nicht erreichbar";
  });

  const checks = qs("[data-server-checks]");

  if (checks) {
    checks.innerHTML = '<p class="server-empty">Die Systemdaten konnten nicht geladen werden. Bitte erneut versuchen.</p>';
  }
}


async function loadServerStatus(force = false) {
  if (
    serverIsLoading
    || (serverHasLoaded && !force)
  ) {
    return;
  }

  const refreshButton = qs("[data-server-refresh]");
  serverIsLoading = true;
  refreshButton?.classList.add("is-loading");
  refreshButton?.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(
      "/api/system/raspberry-pi",
      { cache: "no-store" }
    );
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error("Raspberry-Pi-Status nicht verfügbar");
    }

    renderServerStatus(data);
    serverHasLoaded = true;
  } catch (error) {
    console.error("Fehler beim Laden des Raspberry-Pi-Status:", error);
    renderServerError();
  } finally {
    serverIsLoading = false;
    refreshButton?.classList.remove("is-loading");
    refreshButton?.removeAttribute("aria-busy");
  }
}


function setupServerStatus() {
  qs("[data-server-refresh]")?.addEventListener(
    "click",
    () => loadServerStatus(true)
  );
}


// ============================================================
// NETWORK
// ============================================================

function formatNetworkRate(bytesPerSecond) {
  const value = Number(bytesPerSecond);

  if (!Number.isFinite(value) || value < 0) {
    return "-";
  }

  const bits = value * 8;
  const units = ["Bit/s", "KBit/s", "MBit/s", "GBit/s"];
  let displayValue = bits;
  let unitIndex = 0;

  while (displayValue >= 1000 && unitIndex < units.length - 1) {
    displayValue /= 1000;
    unitIndex += 1;
  }

  const digits = displayValue >= 100 || unitIndex === 0 ? 0 : 1;
  return `${displayValue.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })} ${units[unitIndex]}`;
}


function formatNetworkBitRate(bitsPerSecond) {
  const bits = Number(bitsPerSecond);
  return Number.isFinite(bits) && bits >= 0
    ? formatNetworkRate(bits / 8)
    : "-";
}


function formatNetworkSeen(value) {
  const date = parseDateValue(value);

  if (!date) {
    return "Nie bestätigt";
  }

  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));

  if (seconds < 60) {
    return "Gerade eben";
  }

  if (seconds < 3600) {
    return `Vor ${Math.floor(seconds / 60)} Min.`;
  }

  if (seconds < 86400) {
    return `Vor ${Math.floor(seconds / 3600)} Std.`;
  }

  return date.toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric"
  });
}


function setNetworkSummary(name, value, detail, state = "healthy") {
  const card = qs(`[data-network-summary="${name}"]`);

  if (!card) {
    return;
  }

  card.className = `network-summary-card is-${state}`;
  card.querySelector("[data-network-summary-value]").textContent = value;
  card.querySelector("[data-network-summary-detail]").textContent = detail;
}


function renderNetworkChart(history) {
  const chart = qs("[data-network-chart]");

  if (!chart) {
    return;
  }

  const points = Array.isArray(history)
    ? history.filter(item => Number.isFinite(Number(item.recorded_at)))
    : [];

  if (points.length < 2) {
    chart.innerHTML = '<div class="network-chart-empty">Der Verlauf baut sich nach den ersten Messungen automatisch auf.</div>';
    return;
  }

  const width = 1000;
  const height = 130;
  const values = points.flatMap(item => [
    Number(item.download_bytes_per_second) || 0,
    Number(item.upload_bytes_per_second) || 0
  ]);
  const maxValue = Math.max(...values, 1);

  const pathFor = key => points.map((item, index) => {
    const x = points.length === 1 ? width : index * width / (points.length - 1);
    const y = height - (Number(item[key]) || 0) / maxValue * (height - 8) - 4;
    return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  const downloadPath = pathFor("download_bytes_per_second");
  const uploadPath = pathFor("upload_bytes_per_second");
  const fillPath = `${downloadPath} L${width},${height} L0,${height} Z`;

  chart.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Traffic-Verlauf, Spitzenwert ${escapeHtml(formatNetworkRate(maxValue))}">
      <defs>
        <linearGradient id="network-download-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#42d674"></stop>
          <stop offset="1" stop-color="#42d674" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <line class="network-chart-grid" x1="0" x2="${width}" y1="${height / 3}" y2="${height / 3}"></line>
      <line class="network-chart-grid" x1="0" x2="${width}" y1="${height * 2 / 3}" y2="${height * 2 / 3}"></line>
      <path class="network-chart-fill" d="${fillPath}"></path>
      <path class="network-chart-download" d="${downloadPath}"></path>
      <path class="network-chart-upload" d="${uploadPath}"></path>
    </svg>
  `;
}


function networkDeviceIcon(device) {
  const type = String(device.device_type || "").toLowerCase();

  if (type.includes("computer")) return "ti-device-desktop";
  if (type.includes("television") || type.includes("media")) return "ti-device-tv";
  if (type.includes("speaker")) return "ti-device-speaker";
  if (type.includes("iphone") || type.includes("phone")) return "ti-device-mobile";
  if (type.includes("watch")) return "ti-device-watch";
  if (device.connection_type === "wlan") return "ti-wifi";
  return "ti-device-desktop-analytics";
}


function networkDeviceMatches(device) {
  const matchesFilter = {
    all: true,
    online: device.active,
    offline: !device.active,
    wlan: device.connection_type === "wlan",
    lan: device.connection_type === "lan",
    unknown: !device.known,
    new: device.new
  }[networkFilter];

  if (!matchesFilter) {
    return false;
  }

  if (!networkSearch) {
    return true;
  }

  return [device.name, device.ip, device.mac, device.monolith_name, device.room]
    .filter(Boolean)
    .join(" ")
    .toLocaleLowerCase("de-DE")
    .includes(networkSearch);
}


function renderNetworkDevices() {
  const container = qs("[data-network-devices]");

  if (!container || !networkData) {
    return;
  }

  const devices = Array.isArray(networkData.devices) ? networkData.devices : [];
  const visible = devices.filter(networkDeviceMatches);
  const count = qs("[data-network-device-count]");

  if (count) {
    count.textContent = `${visible.length} von ${devices.length} Geräten`;
  }

  const counts = {
    all: devices.length,
    online: devices.filter(item => item.active).length,
    offline: devices.filter(item => !item.active).length,
    wlan: devices.filter(item => item.connection_type === "wlan").length,
    lan: devices.filter(item => item.connection_type === "lan").length,
    unknown: devices.filter(item => !item.known).length,
    new: devices.filter(item => item.new).length
  };

  Object.entries(counts).forEach(([key, value]) => {
    const target = qs(`[data-network-filter-count="${key}"]`);
    if (target) target.textContent = String(value);
  });

  if (!visible.length) {
    container.innerHTML = '<div class="network-list-empty">Für diesen Filter wurden keine Geräte gefunden.</div>';
    return;
  }

  container.innerHTML = visible.map(device => {
    const badges = [
      device.monolith ? '<span class="network-device-badge is-monolith">MONOLITH</span>' : "",
      device.new ? '<span class="network-device-badge is-new">Neu</span>' : "",
      !device.known ? '<span class="network-device-badge">Unbekannt</span>' : ""
    ].join("");
    const connectionDetail = [device.band, device.signal_dbm !== null && device.signal_dbm !== undefined ? `${device.signal_dbm} dBm` : null]
      .filter(Boolean)
      .join(" · ");

    return `
      <button class="network-device-row ${device.active ? "is-online" : "is-offline"}" type="button" data-network-device-mac="${escapeHtml(device.mac)}">
        <span class="network-device-icon" aria-hidden="true"><i class="ti ${networkDeviceIcon(device)}"></i></span>
        <span class="network-device-identity">
          <strong>${escapeHtml(device.name)}</strong>
          <span class="network-device-badges">${badges}</span>
        </span>
        <span class="network-device-state">${device.active ? "Online" : "Offline"}</span>
        <span class="network-device-connection">${escapeHtml(device.connection_type === "wlan" ? "WLAN" : "LAN")}</span>
        <span class="network-device-address">
          <span>${escapeHtml(device.ip || "Keine IP")}</span>
          <small>${escapeHtml(device.mac)}</small>
        </span>
        <span class="network-device-last-seen">
          <span>${escapeHtml(formatNetworkSeen(device.last_seen))}</span>
          <small>${escapeHtml(connectionDetail || device.interface || "Verbindung unbekannt")}</small>
        </span>
        <i class="ti ti-chevron-right" aria-hidden="true"></i>
      </button>
    `;
  }).join("");
}


function renderMeshNode(node) {
  const children = Array.isArray(node.children) ? node.children : [];
  const type = String(node.connection?.type || "").toUpperCase();
  const detail = [node.model, type].filter(Boolean).join(" · ");
  const icon = node.repeater ? "ti-router" : type.includes("WLAN") ? "ti-wifi" : "ti-device-desktop-analytics";

  return `
    <li>
      <div class="network-mesh-node">
        <i class="ti ${icon}" aria-hidden="true"></i>
        <div>
          <strong>${escapeHtml(node.name || "Netzwerkgerät")}</strong>
          <small>${escapeHtml(detail || node.mac || "Direkte Verbindung")}</small>
        </div>
        ${node.mesh ? '<span>Mesh</span>' : ""}
      </div>
      ${children.length ? `<ul>${children.map(renderMeshNode).join("")}</ul>` : ""}
    </li>
  `;
}


function renderNetworkMesh(mesh) {
  const container = qs("[data-network-mesh]");
  const count = qs("[data-network-mesh-count]");
  const roots = Array.isArray(mesh?.roots) ? mesh.roots : [];

  if (count) {
    count.textContent = Number.isFinite(Number(mesh?.node_count))
      ? `${mesh.node_count} Knoten`
      : "--";
  }

  if (!container) {
    return;
  }

  container.innerHTML = roots.length
    ? `<ul>${roots.map(renderMeshNode).join("")}</ul>`
    : '<div class="network-list-empty">Diese FRITZ!Box stellt keine Mesh-Topologie bereit.</div>';
}


function renderNetworkWlan(networks) {
  const container = qs("[data-network-wlan]");

  if (!container) {
    return;
  }

  const items = Array.isArray(networks) ? networks : [];
  container.innerHTML = items.length
    ? items.map(network => `
        <article class="network-wlan-item ${network.enabled ? "is-active" : "is-inactive"}">
          <i class="ti ti-wifi" aria-hidden="true"></i>
          <div>
            <strong>${escapeHtml(network.band)}${network.guest ? " · Gast" : ""}</strong>
            <small>${escapeHtml(network.ssid || "Ohne SSID")} · ${network.enabled ? "Aktiv" : "Inaktiv"}</small>
          </div>
          <div class="network-wlan-meta">
            <strong>${network.channel ? `Kanal ${escapeHtml(network.channel)}` : "Kanal -"}</strong>
            <span>${escapeHtml(network.client_count || 0)} Geräte${network.utilization_percent !== null && network.utilization_percent !== undefined ? ` · ${escapeHtml(network.utilization_percent)} %` : ""}</span>
          </div>
        </article>
      `).join("")
    : '<div class="network-list-empty">Keine WLAN-Daten verfügbar.</div>';
}


function networkEventIcon(eventType) {
  const icons = {
    internet_lost: "ti-world-off",
    internet_restored: "ti-world-check",
    new_device: "ti-device-mobile-plus",
    important_device_offline: "ti-alert-triangle",
    external_ip_changed: "ti-switch-horizontal",
    mesh_node_offline: "ti-router-off",
    fritzos_update: "ti-download"
  };
  return icons[eventType] || "ti-info-circle";
}


function renderNetworkEvents(events) {
  const container = qs("[data-network-events]");

  if (!container) {
    return;
  }

  const items = Array.isArray(events) ? events.slice(0, 20) : [];
  container.innerHTML = items.length
    ? items.map(event => `
        <article class="network-event is-${escapeHtml(event.severity || "info")}">
          <span class="network-event-icon" aria-hidden="true"><i class="ti ${networkEventIcon(event.event_type)}"></i></span>
          <div>
            <strong>${escapeHtml(event.title)}</strong>
            <small>${escapeHtml(event.detail || "")}</small>
          </div>
          <time datetime="${escapeHtml(event.created_at)}">${escapeHtml(formatNetworkSeen(event.created_at))}</time>
        </article>
      `).join("")
    : '<div class="network-list-empty">Noch keine Netzwerkereignisse aufgezeichnet.</div>';
}


function renderNetworkStatus(data) {
  networkData = data;
  const internet = data.internet || {};
  const connection = data.connection || {};
  const router = data.router || {};
  const home = data.home_network || {};
  const online = Boolean(internet.connected);
  const internetAvailable = internet.available !== false && data.success !== false;

  setNetworkSummary(
    "internet",
    internetAvailable ? (online ? "Online" : "Offline") : "Unbekannt",
    [internet.ipv4, internet.ipv6].filter(Boolean).join(" · ") || "Keine externe Adresse",
    internetAvailable ? (online ? "healthy" : "critical") : "unknown"
  );
  setNetworkSummary(
    "connection",
    `↓ ${formatNetworkRate(connection.download_bytes_per_second)}`,
    `↑ ${formatNetworkRate(connection.upload_bytes_per_second)} · Max. ↓ ${formatNetworkBitRate(connection.max_download_bits_per_second)}`,
    online ? "healthy" : "unknown"
  );
  setNetworkSummary(
    "router",
    router.model || "FRITZ!Box",
    [router.software_version ? `FRITZ!OS ${router.software_version}` : null, router.uptime_seconds !== null && router.uptime_seconds !== undefined ? formatServerDuration(router.uptime_seconds) : null]
      .filter(Boolean).join(" · ") || "Modelldaten nicht verfügbar",
    data.success ? "healthy" : "unknown"
  );
  setNetworkSummary(
    "home",
    `${home.active_devices ?? 0} aktiv`,
    `${home.wlan_devices ?? 0} WLAN · ${home.lan_devices ?? 0} LAN · ${home.unknown_devices ?? 0} unbekannt`,
    Number(home.unknown_devices || 0) > 0 ? "warning" : "healthy"
  );

  const health = qs("[data-network-health]");
  if (health) {
    health.className = `network-overall-status is-${internetAvailable ? (online ? "healthy" : "critical") : "unknown"}`;
    health.textContent = internetAvailable
      ? (online ? "Internet verbunden" : "Internet offline")
      : "Status nicht verfügbar";
  }

  const subtitle = qs("[data-network-subtitle]");
  if (subtitle) {
    subtitle.textContent = router.model
      ? `${router.model} · ${home.active_devices ?? 0} Geräte aktiv`
      : "FRITZ!Box und Heimnetz";
  }

  const error = qs("[data-network-error]");
  if (error) {
    const messages = [data.error, ...(Array.isArray(data.errors) ? data.errors : [])].filter(Boolean);
    error.hidden = messages.length === 0;
    error.textContent = messages.join(" ");
  }

  renderNetworkChart(data.traffic_history);
  renderNetworkDevices();
  renderNetworkMesh(data.mesh);
  renderNetworkWlan(data.wlan);
  renderNetworkEvents(data.events);

  const updated = qs("[data-network-updated]");
  const date = parseDateValue(data.collected_at);
  if (updated && date) {
    updated.textContent = `Zuletzt geprüft: ${date.toLocaleTimeString("de-DE", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    })}`;
  }
}


function renderNetworkFailure(message) {
  const health = qs("[data-network-health]");
  const error = qs("[data-network-error]");

  if (health) {
    health.className = "network-overall-status is-critical";
    health.textContent = "Abfrage fehlgeschlagen";
  }

  if (error) {
    error.hidden = false;
    error.textContent = message || "Die Netzwerkdaten konnten nicht geladen werden.";
  }
}


function openNetworkDevice(mac) {
  const device = networkData?.devices?.find(item => item.mac === mac);
  const dialog = qs("[data-network-device-dialog]");

  if (!device || !dialog) {
    return;
  }

  selectedNetworkDeviceMac = mac;
  qs("[data-network-detail-name]").textContent = device.name;
  qs("[data-network-detail-status]").textContent = device.active
    ? "Online im Heimnetz"
    : `Offline · ${formatNetworkSeen(device.last_seen)}`;

  const details = [
    ["IP-Adresse", device.ip || "-"],
    ["MAC-Adresse", device.mac],
    ["Verbindung", device.connection_type === "wlan" ? "WLAN" : "LAN"],
    ["WLAN-Band", device.band || "-"],
    ["Signal", device.signal_dbm !== null && device.signal_dbm !== undefined ? `${device.signal_dbm} dBm` : "-"],
    ["Datenrate", device.speed_mbit ? `${device.speed_mbit} MBit/s` : "-"],
    ["Schnittstelle", device.interface || "-"],
    ["Mesh-Zugang", device.access_point || "-"],
    ["Zuletzt gesehen", formatNetworkSeen(device.last_seen)],
    ["MONOLITH", device.monolith ? [device.monolith_name, device.room].filter(Boolean).join(" · ") : "Nicht zugeordnet"]
  ];
  qs("[data-network-detail-list]").innerHTML = details.map(([label, value]) => `
    <div><dt>${escapeHtml(label)}</dt><dd title="${escapeHtml(value)}">${escapeHtml(value)}</dd></div>
  `).join("");

  const knownButton = qs("[data-network-detail-known]");
  const importantButton = qs("[data-network-detail-important]");
  knownButton.classList.toggle("is-active", device.known);
  knownButton.textContent = device.known ? "Als bekannt gespeichert" : "Als bekannt markieren";
  importantButton.classList.toggle("is-active", device.important);
  importantButton.textContent = device.important ? "Wichtiges Gerät" : "Als wichtig markieren";
  if (!dialog.open) {
    dialog.showModal();
  }
}


async function updateNetworkDeviceFlag(flag) {
  const device = networkData?.devices?.find(item => item.mac === selectedNetworkDeviceMac);

  if (!device) {
    return;
  }

  const nextValue = !device[flag];
  const response = await fetch(
    `/api/system/network/devices/${encodeURIComponent(device.mac)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [flag]: nextValue })
    }
  );
  const result = await response.json();

  if (!response.ok || !result.success) {
    throw new Error(result.error || "Geräteeinstellung konnte nicht gespeichert werden.");
  }

  device.known = result.device.known;
  device.important = result.device.important;
  if (device.known) device.new = false;
  renderNetworkDevices();
  openNetworkDevice(device.mac);
}


async function loadNetworkStatus(force = false) {
  if (networkIsLoading || (networkHasLoaded && !force)) {
    return;
  }

  const refreshButton = qs("[data-network-refresh]");
  networkIsLoading = true;
  refreshButton?.classList.add("is-loading");
  refreshButton?.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(
      `/api/system/network${force ? "?refresh=1" : ""}`,
      { cache: "no-store" }
    );
    const data = await response.json();
    renderNetworkStatus(data);
    networkHasLoaded = true;
  } catch (error) {
    console.error("Fehler beim Laden des Netzwerkstatus:", error);
    renderNetworkFailure(error.message);
  } finally {
    networkIsLoading = false;
    refreshButton?.classList.remove("is-loading");
    refreshButton?.removeAttribute("aria-busy");
  }
}


function setupNetworkStatus() {
  qs("[data-network-refresh]")?.addEventListener("click", () => loadNetworkStatus(true));

  qs("[data-network-search]")?.addEventListener("input", event => {
    networkSearch = event.target.value.trim().toLocaleLowerCase("de-DE");
    renderNetworkDevices();
  });

  qs("[data-network-filters]")?.addEventListener("click", event => {
    const button = event.target.closest("[data-network-filter]");
    if (!button) return;
    networkFilter = button.dataset.networkFilter;
    qsa("[data-network-filter]").forEach(item => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", active ? "true" : "false");
    });
    renderNetworkDevices();
  });

  qs("[data-network-devices]")?.addEventListener("click", event => {
    const row = event.target.closest("[data-network-device-mac]");
    if (row) openNetworkDevice(row.dataset.networkDeviceMac);
  });

  const dialog = qs("[data-network-device-dialog]");
  qs("[data-network-detail-close]")?.addEventListener("click", () => dialog?.close());
  dialog?.addEventListener("click", event => {
    if (event.target === dialog) dialog.close();
  });
  qs("[data-network-detail-known]")?.addEventListener("click", async () => {
    try {
      await updateNetworkDeviceFlag("known");
    } catch (error) {
      renderNetworkFailure(error.message);
    }
  });
  qs("[data-network-detail-important]")?.addEventListener("click", async () => {
    try {
      await updateNetworkDeviceFlag("important");
    } catch (error) {
      renderNetworkFailure(error.message);
    }
  });
}


// ============================================================
// SYSTEM SERVICES
// ============================================================

function formatServiceUptime(seconds) {
  if (
    seconds === null
    || seconds === undefined
  ) {
    return "-";
  }

  const totalMinutes = Math.max(
    0,
    Math.floor(Number(seconds) / 60)
  );
  const days = Math.floor(
    totalMinutes / 1440
  );
  const hours = Math.floor(
    (totalMinutes % 1440) / 60
  );
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return `${days} T ${hours} Std.`;
  }

  if (hours > 0) {
    return `${hours} Std. ${minutes} Min.`;
  }

  if (minutes > 0) {
    return `${minutes} Min.`;
  }

  return "< 1 Min.";
}


function formatServiceMemory(bytes) {
  if (
    bytes === null
    || bytes === undefined
    || bytes === ""
  ) {
    return "-";
  }

  const value = Number(bytes);

  if (
    !Number.isFinite(value)
    || value < 0
  ) {
    return "-";
  }

  if (value < 1024 * 1024) {
    return `${Math.round(value / 1024)} KB`;
  }

  return (
    `${(value / (1024 * 1024)).toFixed(1)} MB`
  );
}


function renderServices(data) {
  const list = qs(
    "[data-services-list]"
  );
  const summary = qs(
    "[data-services-summary]"
  );
  const host = qs(
    "[data-services-host]"
  );
  const updated = qs(
    "[data-services-updated]"
  );

  if (
    !list
    || !summary
  ) {
    return;
  }

  const services = Array.isArray(
    data.services
  )
    ? data.services
    : [];
  const active = Number(
    data.summary?.active
  ) || 0;
  const total = Number(
    data.summary?.total
  ) || services.length;
  const health = [
    "healthy",
    "degraded",
    "unavailable"
  ].includes(data.summary?.health)
    ? data.summary.health
    : "unavailable";

  list.classList.remove(
    "is-loading"
  );
  list.innerHTML = services.length
    ? services.map(service => {
        const state = [
          "active",
          "inactive",
          "failed",
          "activating",
          "deactivating",
          "reloading",
          "unknown"
        ].includes(service.state)
          ? service.state
          : "unknown";

        return `
          <article class="service-row" data-state="${state}">
            <span class="service-icon" aria-hidden="true">
              <i class="ti ${escapeHtml(service.icon)}"></i>
            </span>
            <div class="service-copy">
              <strong>${escapeHtml(service.name)}</strong>
              <span>${escapeHtml(service.description)}</span>
            </div>
            <div class="service-metrics">
              <div class="service-metric">
                <span>Laufzeit</span>
                <strong>${escapeHtml(formatServiceUptime(service.uptime_seconds))}</strong>
              </div>
              <div class="service-metric">
                <span>Speicher</span>
                <strong>${escapeHtml(formatServiceMemory(service.memory_bytes))}</strong>
              </div>
              <div class="service-metric">
                <span>PID</span>
                <strong>${escapeHtml(service.pid || "-")}</strong>
              </div>
            </div>
            <span class="service-state">
              ${escapeHtml(service.status_label || "Unbekannt")}
            </span>
          </article>
        `;
      }).join("")
    : `
        <div class="services-empty">
          Keine Dienstinformationen verfügbar.
        </div>
      `;

  summary.className = (
    "services-overall-status "
    + (
      health === "healthy"
        ? "is-healthy"
        : "is-degraded"
    )
  );
  summary.textContent = (
    `${active} von ${total} aktiv`
  );

  const checkedAt = data.checked_at
    ? new Date(data.checked_at)
    : new Date();
  const checkedTime = Number.isNaN(
    checkedAt.getTime()
  )
    ? "gerade eben"
    : checkedAt.toLocaleTimeString(
        "de-DE",
        {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit"
        }
      );

  if (updated) {
    updated.textContent = (
      `Geprüft um ${checkedTime}`
    );
  }

  if (host) {
    host.textContent = [
      data.host,
      data.platform,
      data.source === "systemd"
        ? "systemd"
        : "lokale Vorschau"
    ]
      .filter(Boolean)
      .join(" · ");
  }

}


function renderServicesError() {
  const list = qs(
    "[data-services-list]"
  );
  const summary = qs(
    "[data-services-summary]"
  );
  const updated = qs(
    "[data-services-updated]"
  );

  if (list) {
    list.classList.remove(
      "is-loading"
    );
    list.innerHTML = `
      <div class="services-empty">
        Der Dienststatus konnte nicht geladen werden.<br />
        Bitte versuche es erneut.
      </div>
    `;
  }

  if (summary) {
    summary.className = (
      "services-overall-status is-error"
    );
    summary.textContent = "Abfrage fehlgeschlagen";
  }

  if (updated) {
    updated.textContent = "Keine aktuellen Daten";
  }

}


function formatServiceLogTime(value) {
  const timestamp = new Date(value);

  if (Number.isNaN(timestamp.getTime())) {
    return "--:--:--";
  }

  return timestamp.toLocaleTimeString(
    "de-DE",
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }
  );
}


function serviceLogTone(priority) {
  const value = Number(priority);

  if (value <= 3) {
    return "error";
  }

  if (value === 4) {
    return "warning";
  }

  if (value === 5) {
    return "notice";
  }

  return "default";
}


function setServiceLogsLive(active) {
  const indicator = qs(
    ".services-terminal-live"
  );

  if (!indicator) {
    return;
  }

  indicator.classList.toggle(
    "is-paused",
    !active
  );
  indicator.textContent = active
    ? "Live"
    : "Pausiert";
}


function renderServiceLogs(
  data,
  reset = false
) {
  const terminal = qs(
    "[data-services-terminal]"
  );

  if (!terminal) {
    return;
  }

  if (!data.supported) {
    terminal.innerHTML = `
      <p class="terminal-command"><span>$</span> journalctl --follow</p>
      <p class="terminal-muted">Das Live-Journal ist nur auf dem Raspberry Pi verfügbar.</p>
    `;
    setServiceLogsLive(false);
    return;
  }

  const entries = Array.isArray(data.entries)
    ? data.entries
    : [];
  const shouldFollow = reset || (
    terminal.scrollHeight
    - terminal.scrollTop
    - terminal.clientHeight
    < 48
  );

  if (reset) {
    terminal.innerHTML = `
      <p class="terminal-command"><span>$</span> journalctl -fu monolith -u monolith-homekit -u robovac-matterbridge</p>
      <p class="terminal-muted" data-service-log-waiting>Live-Verbindung hergestellt. Warte auf Protokollzeilen...</p>
    `;
  }

  if (entries.length) {
    terminal.querySelector(
      "[data-service-log-waiting]"
    )?.remove();
  }

  entries.forEach(entry => {
    const tone = serviceLogTone(
      entry.priority
    );

    terminal.insertAdjacentHTML(
      "beforeend",
      `
        <p class="terminal-log-line is-${tone}">
          <time class="terminal-log-time">${escapeHtml(formatServiceLogTime(entry.timestamp))}</time>
          <span class="terminal-log-service" title="${escapeHtml(entry.unit)}">${escapeHtml(entry.service)}</span>
          <span class="terminal-log-message">${escapeHtml(entry.message)}</span>
        </p>
      `
    );
  });

  while (terminal.childElementCount > 320) {
    terminal.firstElementChild?.remove();
  }

  if (data.cursor) {
    serviceLogsCursor = data.cursor;
  }

  if (shouldFollow) {
    terminal.scrollTop = terminal.scrollHeight;
  }

  setServiceLogsLive(true);
}


function renderServiceLogsError(message) {
  const terminal = qs(
    "[data-services-terminal]"
  );

  if (!terminal) {
    return;
  }

  terminal.innerHTML = `
    <p class="terminal-command"><span>$</span> journalctl --follow</p>
    <p class="terminal-error">[ERR] ${escapeHtml(message)}</p>
    <p class="terminal-muted">Mit Aktualisieren erneut versuchen.</p>
  `;
  setServiceLogsLive(false);
}


async function loadServiceLogs(reset = false) {
  if (serviceLogsLoading) {
    return;
  }

  if (reset) {
    serviceLogsCursor = null;
    serviceLogsInitialized = false;
  }

  serviceLogsLoading = true;

  try {
    const query = serviceLogsCursor
      ? `?cursor=${encodeURIComponent(serviceLogsCursor)}`
      : "";
    const response = await fetch(
      `/api/system/services/logs${query}`,
      {
        cache: "no-store"
      }
    );
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(
        data.error
        || "Live-Journal nicht verfügbar"
      );
    }

    renderServiceLogs(
      data,
      reset || !serviceLogsInitialized
    );
    serviceLogsInitialized = true;
  } catch (error) {
    setServiceLogsLive(false);

    if (!serviceLogsInitialized || reset) {
      renderServiceLogsError(
        error.message
        || "Live-Journal nicht verfügbar"
      );
    }
  } finally {
    serviceLogsLoading = false;
  }
}


async function loadServices(force = false) {
  if (
    servicesIsLoading
    || (servicesHasLoaded && !force)
  ) {
    return;
  }

  const refreshButton = qs(
    "[data-services-refresh]"
  );
  servicesIsLoading = true;
  refreshButton?.classList.add(
    "is-loading"
  );
  refreshButton?.setAttribute(
    "aria-busy",
    "true"
  );

  try {
    const response = await fetch(
      "/api/system/services",
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        "Dienststatus nicht verfügbar"
      );
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(
        "Ungültige Statusantwort"
      );
    }

    renderServices(data);
    servicesHasLoaded = true;
  } catch (error) {
    console.error(
      "Fehler beim Laden der Dienste:",
      error
    );
    renderServicesError();
  } finally {
    servicesIsLoading = false;
    refreshButton?.classList.remove(
      "is-loading"
    );
    refreshButton?.removeAttribute(
      "aria-busy"
    );
  }
}


function setupServices() {
  qs(
    "[data-services-refresh]"
  )?.addEventListener(
    "click",
    () => {
      loadServices(true);
      loadServiceLogs(true);
    }
  );
}


// ============================================================
// PACKAGES
// ============================================================

function packageDateKey(date = new Date()) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0")
  ].join("-");
}


function packageDeliveryDate(item) {
  if (item.status === "out_for_delivery") {
    return packageDateKey();
  }

  return item.expected_delivery;
}


function formatPackageDate(value) {
  if (!value) {
    return "Noch offen";
  }

  const parsed = new Date(`${value}T12:00:00`);

  if (Number.isNaN(parsed.getTime())) {
    return "Noch offen";
  }

  const today = packageDateKey();
  const tomorrow = packageDateKey(
    new Date(
      new Date().getFullYear(),
      new Date().getMonth(),
      new Date().getDate() + 1
    )
  );

  if (value === today) {
    return "Heute";
  }

  if (value === tomorrow) {
    return "Morgen";
  }

  return parsed.toLocaleDateString(
    "de-DE",
    {
      weekday: "short",
      day: "2-digit",
      month: "2-digit"
    }
  );
}


function formatPackageTimestamp(value) {
  const parsed = new Date(Number(value) * 1000);

  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return parsed.toLocaleString(
    "de-DE",
    {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }
  );
}


function formatPackageSyncTime(value) {
  if (!value) {
    return "Noch nicht synchronisiert";
  }

  const seconds = Math.max(
    0,
    Math.floor(Date.now() / 1000 - Number(value))
  );

  if (seconds < 60) {
    return "Gerade geprüft";
  }

  if (seconds < 3600) {
    return `Vor ${Math.floor(seconds / 60)} Min. geprüft`;
  }

  return `Vor ${Math.floor(seconds / 3600)} Std. geprüft`;
}


function renderPackagesSummary() {
  const active = packages.filter(
    item => item.status !== "delivered"
  );
  const today = active.filter(
    item => packageDeliveryDate(item) === packageDateKey()
  );

  const activeCount = qs("[data-packages-active-count]");
  const todayCount = qs("[data-packages-today-count]");

  if (activeCount) {
    activeCount.textContent = String(active.length);
  }

  if (todayCount) {
    todayCount.textContent = String(today.length);
  }
}


function packageHistoryMarkup(history) {
  if (!history?.length) {
    return "";
  }

  return `
    <details class="package-history">
      <summary>
        Verlauf
        <span>${history.length}</span>
      </summary>
      <div class="package-history-list">
        ${history.map(item => `
          <div class="package-history-item">
            <i class="ti ti-circle-check"></i>
            <div>
              <strong>${escapeHtml(item.status_label)}</strong>
              <span>${escapeHtml(item.detail || "Status aktualisiert")}</span>
              ${item.location
                ? `<span>${escapeHtml(item.location)}</span>`
                : ""
              }
              <time>${escapeHtml(formatPackageTimestamp(
                item.occurred_at || item.created_at
              ))}</time>
            </div>
          </div>
        `).join("")}
      </div>
    </details>
  `;
}


function renderPackageCard(item) {
  const carrier = item.carrier_details || {};
  const trackingLink = carrier.tracking_url
    ? `
      <a
        class="package-action-link"
        href="${escapeHtml(carrier.tracking_url)}"
        target="_blank"
        rel="noreferrer"
      >
        <i class="ti ti-external-link"></i>
        Beim Dienstleister
      </a>
    `
    : "";
  const syncMessage = item.tracking_state === "error"
    ? item.last_sync_error
    : formatPackageSyncTime(item.last_synced_at);

  return `
    <article
      class="package-card"
      data-package-id="${item.id}"
      data-package-status="${escapeHtml(item.status)}"
      style="--package-carrier-color: ${escapeHtml(carrier.color || "#a0a0a7")};"
    >
      <span class="package-card-accent" aria-hidden="true"></span>

      <div class="package-card-main">
        <div class="package-card-heading">
          <div class="package-card-title">
            <h4>${escapeHtml(item.name)}</h4>
            <span class="package-carrier">
              ${escapeHtml(carrier.name || "Anderer Dienstleister")}
            </span>
          </div>
          <span class="package-status">
            ${escapeHtml(item.status_label)}
          </span>
        </div>

        <div class="package-card-details">
          <div class="package-detail">
            <span>Sendungsnummer</span>
            <code title="${escapeHtml(item.tracking_number)}">
              ${escapeHtml(item.tracking_number)}
            </code>
          </div>
          <div class="package-detail">
            <span>Lieferung</span>
            <strong>${escapeHtml(formatPackageDate(packageDeliveryDate(item)))}</strong>
          </div>
        </div>

        ${item.note
          ? `<p class="package-card-note">${escapeHtml(item.note)}</p>`
          : ""
        }

        <div class="package-sync-state ${
          item.tracking_state === "error" ? "error" : ""
        }">
          <i class="ti ${
            item.tracking_state === "error"
              ? "ti-alert-circle"
              : "ti-cloud-check"
          }"></i>
          ${escapeHtml(syncMessage)}
        </div>

        ${packageHistoryMarkup(item.history)}
      </div>

      <div class="package-card-actions">
        ${trackingLink}

        <button
          class="package-delete-button"
          type="button"
          data-package-delete
          aria-label="${escapeHtml(item.name)} löschen"
        >
          <i class="ti ti-trash"></i>
          <span>Löschen</span>
        </button>
      </div>
    </article>
  `;
}


function renderPackages() {
  const container = qs("[data-packages-list]");

  if (!container) {
    return;
  }

  const visiblePackages = packagesFilter === "active"
    ? packages.filter(item => item.status !== "delivered")
    : packages;

  container.setAttribute("aria-busy", "false");
  renderPackagesSummary();

  const subtitle = qs("[data-packages-list-subtitle]");

  if (subtitle) {
    subtitle.textContent = visiblePackages.length === 1
      ? "1 Sendung"
      : `${visiblePackages.length} Sendungen`;
  }

  if (!visiblePackages.length) {
    const message = packagesFilter === "active"
      ? "Keine aktiven Pakete. Neue Sendungen erscheinen hier."
      : "Noch keine Pakete gespeichert.";

    container.innerHTML = `
      <div class="packages-empty">
        <div>
          <i class="ti ti-package"></i>
          ${escapeHtml(message)}
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = visiblePackages
    .map(renderPackageCard)
    .join("");
}


async function loadPackages(force = false) {
  if (packagesIsLoading || (packagesHasLoaded && !force)) {
    return;
  }

  packagesIsLoading = true;
  const container = qs("[data-packages-list]");
  container?.setAttribute("aria-busy", "true");

  try {
    const response = await fetch("/api/packages");
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Pakete konnten nicht geladen werden");
    }

    packages = data.packages || [];
    packagesTrackingConfigured = Boolean(data.tracking_configured);
    packagesHasLoaded = true;

    const setupNotice = qs("[data-packages-setup]");
    const form = qs("[data-packages-add-form]");

    if (setupNotice) {
      setupNotice.hidden = packagesTrackingConfigured;
    }

    form?.querySelectorAll("input, select, textarea, button")
      .forEach(control => {
        control.disabled = !packagesTrackingConfigured;
      });

    const refreshButton = qs("[data-packages-refresh]");

    if (refreshButton) {
      refreshButton.disabled = !packagesTrackingConfigured;
    }

    renderPackages();
  } catch (error) {
    console.error("Fehler beim Laden der Pakete:", error);

    if (container) {
      container.setAttribute("aria-busy", "false");
      container.innerHTML = `
        <div class="packages-error">
          <div>
            <i class="ti ti-alert-circle"></i>
            Pakete konnten nicht geladen werden.
          </div>
        </div>
      `;
    }
  } finally {
    packagesIsLoading = false;
  }
}


function setPackagesFormStatus(message, type = "error") {
  const status = qs("[data-packages-form-status]");

  if (!status) {
    return;
  }

  status.textContent = message || "";
  status.classList.toggle("success", type === "success");
  status.hidden = !message;
}


async function removePackage(packageId) {
  const item = packages.find(
    entry => entry.id === packageId
  );

  if (!item || !window.confirm(`„${item.name}“ wirklich löschen?`)) {
    return;
  }

  const response = await fetch(
    `/api/packages/${packageId}`,
    { method: "DELETE" }
  );
  const data = await response.json();

  if (!response.ok || !data.success) {
    setPackagesFormStatus(
      data.error || "Paket konnte nicht gelöscht werden"
    );
    return;
  }

  packagesHasLoaded = false;
  await loadPackages();
}


async function refreshPackagesNow() {
  const button = qs("[data-packages-refresh]");
  button.disabled = true;
  button.classList.add("is-loading");
  setPackagesFormStatus("");

  try {
    const response = await fetch(
      "/api/packages/refresh",
      { method: "POST" }
    );
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Aktualisierung fehlgeschlagen");
    }

    if (data.busy) {
      setPackagesFormStatus(
        "Eine Aktualisierung läuft bereits. Die Ansicht wird gleich nachgeladen.",
        "success"
      );
    }

    packagesHasLoaded = false;
    await loadPackages();

    if (data.live_fallbacks) {
      setPackagesFormStatus(
        "Ship24-Liveabfrage erfolgreich verwendet.",
        "success"
      );
    } else if (data.errors?.length) {
      setPackagesFormStatus(
        `${data.errors.length} Sendung konnte nicht aktualisiert werden`
      );
    }
  } catch (error) {
    setPackagesFormStatus(error.message);
  } finally {
    button.disabled = false;
    button.classList.remove("is-loading");
  }
}


function setupPackages() {
  const form = qs("[data-packages-add-form]");
  const list = qs("[data-packages-list]");

  qsa("[data-packages-filter]").forEach(button => {
    button.addEventListener("click", () => {
      packagesFilter = button.dataset.packagesFilter;

      qsa("[data-packages-filter]").forEach(filterButton => {
        const active = filterButton === button;
        filterButton.classList.toggle("active", active);
        filterButton.setAttribute(
          "aria-pressed",
          active ? "true" : "false"
        );
      });

      renderPackages();
    });
  });

  form?.addEventListener("submit", async event => {
    event.preventDefault();
    setPackagesFormStatus("");

    const submitButton = form.querySelector("button[type='submit']");
    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    submitButton.disabled = true;

    try {
      const response = await fetch(
        "/api/packages",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        }
      );
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Paket konnte nicht gespeichert werden");
      }

      form.reset();
      setPackagesFormStatus("Tracking wurde gestartet", "success");
      packagesFilter = "active";
      packagesHasLoaded = false;
      await loadPackages();
    } catch (error) {
      setPackagesFormStatus(error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  list?.addEventListener("click", event => {
    const button = event.target.closest("[data-package-delete]");

    if (!button) {
      return;
    }

    const card = button.closest("[data-package-id]");
    removePackage(Number(card?.dataset.packageId));
  });

  qs("[data-packages-refresh]")?.addEventListener(
    "click",
    refreshPackagesNow
  );
}


// ============================================================
// FINANCES
// ============================================================

function financeMonthKey(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0")
  ].join("-");
}


function formatFinanceInputDate(date) {
  return [
    String(date.getDate()).padStart(2, "0"),
    String(date.getMonth() + 1).padStart(2, "0"),
    date.getFullYear()
  ].join("/");
}


function parseFinanceInputDate(value) {
  const match = String(value || "").match(
    /^(\d{2})\/(\d{2})\/(\d{4})$/
  );

  if (!match) {
    return null;
  }

  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const parsed = new Date(year, month - 1, day);

  if (
    parsed.getFullYear() !== year
    || parsed.getMonth() !== month - 1
    || parsed.getDate() !== day
  ) {
    return null;
  }

  return [
    year,
    String(month).padStart(2, "0"),
    String(day).padStart(2, "0")
  ].join("-");
}


function normalizeFinanceDateInput(value) {
  const digits = String(value).replace(/\D/g, "").slice(0, 8);

  if (digits.length <= 2) {
    return digits;
  }

  if (digits.length <= 4) {
    return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  }

  return [
    digits.slice(0, 2),
    digits.slice(2, 4),
    digits.slice(4)
  ].join("/");
}


function normalizeFinanceAmountInput(value) {
  const cleaned = String(value)
    .replaceAll(".", ",")
    .replace(/[^\d,]/g, "");
  const [whole = "", ...decimalParts] = cleaned.split(",");

  if (!decimalParts.length) {
    return whole;
  }

  return `${whole},${decimalParts.join("").slice(0, 2)}`;
}


function formatFinanceAmountInput(amountCents) {
  return (Number(amountCents) / 100)
    .toFixed(2)
    .replace(".", ",");
}


function setFinanceTransferVisibility(isHidden, persist = false) {
  const form = qs("[data-finance-transfer-form]");
  const toggle = qs("[data-finance-transfer-toggle]");
  const label = isHidden
    ? "Startübertrag anzeigen"
    : "Startübertrag ausblenden";

  document.documentElement.classList.toggle(
    "finance-transfer-hidden",
    isHidden
  );

  if (form) {
    form.hidden = isHidden;
  }

  if (toggle) {
    toggle.setAttribute("aria-expanded", String(!isHidden));
    toggle.setAttribute("aria-label", label);
    toggle.title = label;

    const icon = toggle.querySelector("i");

    if (icon) {
      icon.className = isHidden
        ? "ti ti-eye"
        : "ti ti-eye-off";
    }
  }

  if (persist) {
    try {
      localStorage.setItem(
        FINANCE_TRANSFER_HIDDEN_KEY,
        String(isHidden)
      );
    } catch (error) {
      // Die Einstellung ist optional.
    }
  }
}


function setFinanceStatus(message, type = "error") {
  const status = qs("[data-finance-status]");

  if (!status) {
    return;
  }

  status.textContent = message || "";
  status.dataset.status = type;
  status.hidden = !message;
}


function updateFinanceMonthControls() {
  const label = qs("[data-finance-month-label]");
  const dateInput = qs(
    "[data-finance-expense-form] input[name='spent_on']"
  );

  if (label) {
    label.textContent = financeVisibleMonth.toLocaleDateString(
      "de-DE",
      {
        month: "long",
        year: "numeric"
      }
    );
  }

  if (!dateInput) {
    return;
  }

  const today = new Date();
  const isCurrentMonth =
    today.getFullYear() === financeVisibleMonth.getFullYear()
    && today.getMonth() === financeVisibleMonth.getMonth();

  const defaultDate = isCurrentMonth
    ? today
    : new Date(
        financeVisibleMonth.getFullYear(),
        financeVisibleMonth.getMonth(),
        1
      );

  dateInput.value = formatFinanceInputDate(defaultDate);
}


function financeDeleteButton(kind, id, name) {
  const actionLabel = kind === "recurring"
    ? `${name} ab diesem Monat entfernen`
    : `${name} löschen`;
  const actionTitle = kind === "recurring"
    ? "Ab diesem Monat entfernen"
    : "Eintrag löschen";

  return `
    <button
      class="finance-delete-button"
      type="button"
      data-finance-delete="${kind}"
      data-finance-entry-id="${id}"
      aria-label="${escapeHtml(actionLabel)}"
      title="${actionTitle}"
    >
      <i class="ti ti-trash"></i>
    </button>
  `;
}


function renderFinanceRecurring(entries) {
  const container = qs("[data-finance-recurring-list]");

  if (!container) {
    return;
  }

  const groups = [
    {
      type: "income",
      title: "Einnahmen"
    },
    {
      type: "fixed_expense",
      title: "Fixkosten"
    }
  ];

  container.innerHTML = groups.map(group => {
    const items = entries.filter(
      entry => entry.entry_type === group.type
    );

    const rows = items.length
      ? items.map(entry => `
          <div class="finance-list-row">
            <span>${escapeHtml(entry.name)}</span>
            <strong>${formatCurrency(entry.amount_cents)}</strong>
            ${financeDeleteButton("recurring", entry.id, entry.name)}
          </div>
        `).join("")
      : `
          <div class="finance-list-empty">
            Noch keine ${group.title.toLowerCase()} eingetragen
          </div>
        `;

    return `
      <div class="finance-list-group">
        <h4>${group.title}</h4>
        ${rows}
      </div>
    `;
  }).join("");
}


function renderFinanceExpenses(entries) {
  const container = qs("[data-finance-expense-list]");

  if (!container) {
    return;
  }

  if (!entries.length) {
    container.innerHTML = `
      <div class="finance-list-empty finance-expense-empty">
        In diesem Monat sind noch keine weiteren Ausgaben eingetragen.
      </div>
    `;
    return;
  }

  container.innerHTML = entries.map(entry => {
    const spentOn = new Date(`${entry.spent_on}T12:00:00`)
      .toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit"
      });

    return `
      <div class="finance-list-row finance-expense-row">
        <span>
          ${escapeHtml(entry.name)}
          <small>${spentOn}</small>
        </span>
        <strong>${formatCurrency(entry.amount_cents)}</strong>
        ${financeDeleteButton("expense", entry.id, entry.name)}
      </div>
    `;
  }).join("");
}


function renderFinances(data) {
  const summary = data.summary || {};
  const available = qs("[data-finance-available]");
  const transferInput = qs(
    "[data-finance-transfer-form] input[name='amount']"
  );

  if (available) {
    const availableCents = Number(summary.available_cents) || 0;
    available.textContent = formatCurrency(availableCents);
    available.classList.toggle(
      "is-negative",
      availableCents < 0
    );
  }

  const values = {
    "[data-finance-carried]": summary.carried_over_cents,
    "[data-finance-income]": summary.income_cents,
    "[data-finance-fixed]": summary.fixed_expense_cents,
    "[data-finance-variable]": summary.variable_expense_cents
  };

  Object.entries(values).forEach(([selector, value]) => {
    const element = qs(selector);

    if (element) {
      element.textContent = formatCurrency(value);
    }
  });

  if (transferInput) {
    const manualTransferCents = Number(
      summary.manual_transfer_cents
    ) || 0;
    transferInput.value = manualTransferCents
      ? formatFinanceAmountInput(manualTransferCents)
      : "";
  }

  renderFinanceRecurring(data.recurring || []);
  renderFinanceExpenses(data.expenses || []);
}


async function loadFinances() {
  if (financeIsLoading) {
    return;
  }

  financeIsLoading = true;
  updateFinanceMonthControls();
  setFinanceStatus("");

  try {
    const response = await fetch(
      `/api/finances?month=${financeMonthKey(financeVisibleMonth)}`
    );
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Finanzen konnten nicht geladen werden");
    }

    renderFinances(data);
    financeHasLoaded = true;
    setFinanceStatus("");
  } catch (error) {
    setFinanceStatus(
      error.message || "Finanzen konnten nicht geladen werden"
    );
  } finally {
    financeIsLoading = false;
  }
}


async function submitFinanceTransfer(form) {
  const submitButton = form.querySelector("button[type='submit']");
  const formData = new FormData(form);

  submitButton.disabled = true;
  setFinanceStatus("");

  try {
    const response = await fetch("/api/finances/transfer", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        month: financeMonthKey(financeVisibleMonth),
        amount: formData.get("amount")
      })
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Übertrag konnte nicht gespeichert werden");
    }

    financeHasLoaded = false;
    await loadFinances();
  } catch (error) {
    setFinanceStatus(
      error.message || "Übertrag konnte nicht gespeichert werden"
    );
  } finally {
    submitButton.disabled = false;
  }
}


async function submitFinanceForm(form, endpoint) {
  const submitButton = form.querySelector("button[type='submit']");
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  if (endpoint.endsWith("/recurring")) {
    payload.start_month = financeMonthKey(financeVisibleMonth);
  }

  if (endpoint.endsWith("/expenses")) {
    const spentOn = parseFinanceInputDate(payload.spent_on);

    if (!spentOn) {
      setFinanceStatus("Bitte ein gültiges Datum im Format TT/MM/JJJJ eingeben");
      return;
    }

    if (!spentOn.startsWith(financeMonthKey(financeVisibleMonth))) {
      setFinanceStatus("Das Datum muss im ausgewählten Monat liegen");
      return;
    }

    payload.spent_on = spentOn;
  }

  submitButton.disabled = true;
  setFinanceStatus("");

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Eintrag konnte nicht gespeichert werden");
    }

    form.reset();
    financeHasLoaded = false;
    updateFinanceMonthControls();
    await loadFinances();
  } catch (error) {
    setFinanceStatus(
      error.message || "Eintrag konnte nicht gespeichert werden"
    );
  } finally {
    submitButton.disabled = false;
  }
}


async function deleteFinanceEntry(kind, entryId, button) {
  const endpoint = kind === "recurring"
    ? `/api/finances/recurring/${entryId}?month=${financeMonthKey(financeVisibleMonth)}`
    : `/api/finances/expenses/${entryId}`;

  button.disabled = true;
  setFinanceStatus("");

  try {
    const response = await fetch(endpoint, {
      method: "DELETE"
    });
    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Eintrag konnte nicht gelöscht werden");
    }

    financeHasLoaded = false;
    await loadFinances();
  } catch (error) {
    button.disabled = false;
    setFinanceStatus(
      error.message || "Eintrag konnte nicht gelöscht werden"
    );
  }
}


function setupFinances() {
  const recurringForm = qs("[data-finance-recurring-form]");
  const expenseForm = qs("[data-finance-expense-form]");
  const transferForm = qs("[data-finance-transfer-form]");
  const panel = qs("[data-dashboard-panel='finance']");

  let transferIsHidden = document.documentElement.classList.contains(
    "finance-transfer-hidden"
  );

  try {
    transferIsHidden = localStorage.getItem(
      FINANCE_TRANSFER_HIDDEN_KEY
    ) === "true";
  } catch (error) {
    // Die Einstellung ist optional.
  }

  updateFinanceMonthControls();
  setFinanceTransferVisibility(transferIsHidden);

  qsa(".finance-amount-input input").forEach(input => {
    input.addEventListener("input", () => {
      input.value = normalizeFinanceAmountInput(input.value);
    });
  });

  const dateInput = expenseForm?.querySelector(
    "input[name='spent_on']"
  );

  dateInput?.addEventListener("input", () => {
    dateInput.value = normalizeFinanceDateInput(dateInput.value);
  });

  recurringForm?.addEventListener("submit", event => {
    event.preventDefault();
    submitFinanceForm(
      recurringForm,
      "/api/finances/recurring"
    );
  });

  expenseForm?.addEventListener("submit", event => {
    event.preventDefault();
    submitFinanceForm(
      expenseForm,
      "/api/finances/expenses"
    );
  });

  transferForm?.addEventListener("submit", event => {
    event.preventDefault();
    submitFinanceTransfer(transferForm);
  });

  qs("[data-finance-transfer-toggle]")?.addEventListener(
    "click",
    () => {
      setFinanceTransferVisibility(
        !transferForm?.hidden,
        true
      );
    }
  );

  qs("[data-finance-previous-month]")?.addEventListener(
    "click",
    () => {
      financeVisibleMonth.setMonth(
        financeVisibleMonth.getMonth() - 1
      );
      financeHasLoaded = false;
      loadFinances();
    }
  );

  qs("[data-finance-next-month]")?.addEventListener(
    "click",
    () => {
      financeVisibleMonth.setMonth(
        financeVisibleMonth.getMonth() + 1
      );
      financeHasLoaded = false;
      loadFinances();
    }
  );

  panel?.addEventListener("click", event => {
    const button = event.target.closest("[data-finance-delete]");

    if (!button) {
      return;
    }

    deleteFinanceEntry(
      button.dataset.financeDelete,
      button.dataset.financeEntryId,
      button
    );
  });
}


// ============================================================
// PLANNER
// ============================================================

function plannerDateKey(date) {
  return [
    date.getFullYear(),
    String(
      date.getMonth() + 1
    ).padStart(2, "0"),
    String(
      date.getDate()
    ).padStart(2, "0"),
  ].join("-");
}


function parsePlannerDate(value) {
  if (
    typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}$/.test(value)
  ) {
    const [year, month, day] =
      value.split("-").map(Number);

    return new Date(
      year,
      month - 1,
      day
    );
  }

  return parseDateValue(value);
}


function getPlannerGridRange() {
  const firstDay = new Date(
    plannerVisibleMonth.getFullYear(),
    plannerVisibleMonth.getMonth(),
    1
  );
  const mondayOffset =
    (firstDay.getDay() + 6) % 7;
  const start = new Date(firstDay);
  start.setDate(
    start.getDate() - mondayOffset
  );
  const end = new Date(start);
  end.setDate(
    end.getDate() + 42
  );

  return {
    start,
    end,
  };
}


function plannerEventTime(event) {
  if (event.all_day) {
    return "Ganztägig";
  }

  const startsAt = parsePlannerDate(
    event.start
  );

  if (!startsAt) {
    return "";
  }

  return startsAt.toLocaleTimeString(
    "de-DE",
    {
      hour: "2-digit",
      minute: "2-digit",
    }
  );
}


function renderPlannerCalendar() {
  const grid = qs(
    "[data-planner-calendar-grid]"
  );
  const label = qs(
    "[data-planner-month-label]"
  );

  if (!grid || !label) {
    return;
  }

  label.textContent =
    plannerVisibleMonth.toLocaleDateString(
      "de-DE",
      {
        month: "long",
        year: "numeric",
      }
    );

  const range = getPlannerGridRange();
  const todayKey = plannerDateKey(
    new Date()
  );
  const visibleMonth =
    plannerVisibleMonth.getMonth();
  const days = [];

  for (let index = 0; index < 42; index += 1) {
    const day = new Date(range.start);
    day.setDate(
      day.getDate() + index
    );
    const dayKey = plannerDateKey(day);
    const dayEvents = plannerEvents.filter(
      event => {
        const startsAt = parsePlannerDate(
          event.start
        );

        return (
          startsAt
          && plannerDateKey(startsAt) === dayKey
        );
      }
    );
    const visibleEvents = dayEvents.slice(0, 3);
    const remaining =
      dayEvents.length - visibleEvents.length;
    const classes = ["planner-day"];

    if (day.getMonth() !== visibleMonth) {
      classes.push("outside-month");
    }

    if (dayKey === todayKey) {
      classes.push("today");
    }

    const eventMarkup = visibleEvents.map(
      event => {
        const time = plannerEventTime(event);
        const title = escapeHtml(event.title);
        const calendar = escapeHtml(
          event.calendar || "Kalender"
        );

        return `
          <div
            class="planner-calendar-event"
            title="${title} | ${calendar}"
          >
            ${
              event.all_day
                ? ""
                : `<time>${escapeHtml(time)}</time>`
            }
            ${title}
          </div>
        `;
      }
    ).join("");

    days.push(`
      <div
        class="${classes.join(" ")}"
        role="gridcell"
        aria-label="${escapeHtml(
          day.toLocaleDateString(
            "de-DE",
            {
              weekday: "long",
              day: "numeric",
              month: "long",
            }
          )
        )}"
      >
        <div class="planner-day-header">
          <span class="planner-day-number">
            ${day.getDate()}
          </span>
        </div>
        <div class="planner-day-events">
          ${eventMarkup}
          ${
            remaining > 0
              ? `<span class="planner-day-more">+${remaining} weitere</span>`
              : ""
          }
        </div>
      </div>
    `);
  }

  grid.innerHTML = days.join("");
  grid.setAttribute(
    "aria-busy",
    plannerIsLoading ? "true" : "false"
  );
}


function plannerUpcomingMeta(event) {
  const parts = [
    plannerEventTime(event),
  ];

  if (event.location) {
    parts.push(event.location);
  } else if (event.calendar) {
    parts.push(event.calendar);
  }

  return parts.filter(Boolean).join(" | ");
}


function renderPlannerUpcoming(
  calendarState
) {
  const container = qs(
    "[data-planner-upcoming]"
  );

  if (!container) {
    return;
  }

  if (
    calendarState.status !== "ready"
  ) {
    const isError =
      calendarState.status === "error";
    container.innerHTML = `
      <div class="planner-empty-state ${
        isError ? "error" : ""
      }">
        ${escapeHtml(
          calendarState.message
          || "Kalender ist noch nicht eingerichtet"
        )}
      </div>
    `;
    return;
  }

  const now = new Date();
  const startToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate()
  );
  const end = new Date(startToday);
  end.setDate(
    end.getDate() + 7
  );
  const events = plannerUpcomingEvents
    .filter(
      event => {
        const startsAt = parsePlannerDate(
          event.start
        );
        const endsAt = parsePlannerDate(
          event.end
        ) || startsAt;

        return (
          startsAt
          && endsAt >= startToday
          && startsAt < end
        );
      }
    )
    .slice(0, 12);

  if (!events.length) {
    container.innerHTML = `
      <div class="planner-empty-state">
        In den nächsten 7 Tagen steht nichts an
      </div>
    `;
    return;
  }

  container.innerHTML = events.map(
    event => {
      const startsAt = parsePlannerDate(
        event.start
      );
      const weekday = startsAt.toLocaleDateString(
        "de-DE",
        {
          weekday: "short",
        }
      ).replace(".", "");

      return `
        <article class="planner-upcoming-item">
          <time
            class="planner-upcoming-date"
            datetime="${escapeHtml(event.start)}"
          >
            ${escapeHtml(weekday)}
            <strong>${startsAt.getDate()}</strong>
          </time>
          <div class="planner-item-copy">
            <strong>${escapeHtml(event.title)}</strong>
            <span>${escapeHtml(
              plannerUpcomingMeta(event)
            )}</span>
          </div>
        </article>
      `;
    }
  ).join("");
}


function setPlannerLoading(isLoading) {
  plannerIsLoading = isLoading;

  qsa(
    "[data-planner-refresh], "
    + "[data-planner-previous], "
    + "[data-planner-next], "
    + "[data-planner-today]"
  ).forEach(
    button => {
      button.disabled = isLoading;
    }
  );

  const refreshButton = qs(
    "[data-planner-refresh]"
  );

  refreshButton?.classList.toggle(
      "is-loading",
      isLoading
  );

  renderPlannerCalendar();
}


function updatePlannerSyncStatus(data) {
  const status = qs(
    "[data-planner-sync-status]"
  );
  const subtitle = qs(
    "[data-planner-calendar-subtitle]"
  );

  if (status) {
    const syncedAt = parsePlannerDate(
      data.synced_at
    );

    status.textContent = syncedAt
      ? `Synchronisiert um ${syncedAt.toLocaleTimeString(
          "de-DE",
          {
            hour: "2-digit",
            minute: "2-digit",
          }
        )}`
      : "iCloud nicht verbunden";
  }

  if (subtitle) {
    const names =
      data.calendar?.calendars || [];
    subtitle.textContent = names.length
      ? names.join(", ")
      : "Monatsübersicht";
  }
}


async function loadPlanner(
  forceRefresh = false
) {
  if (plannerIsLoading) {
    return;
  }

  setPlannerLoading(true);
  const range = getPlannerGridRange();

  try {
    const parameters = new URLSearchParams({
      start: plannerDateKey(range.start),
      end: plannerDateKey(range.end),
    });

    if (forceRefresh) {
      parameters.set("refresh", "1");
    }

    const response = await fetch(
      `/api/planner?${parameters}`
    );
    const data = await response.json();

    plannerEvents =
      data.calendar?.events || [];

    const today = new Date();
    if (
      today >= range.start
      && today < range.end
    ) {
      plannerUpcomingEvents = [
        ...plannerEvents,
      ];
    }

    plannerHasLoaded = true;
    updatePlannerSyncStatus(data);
    renderPlannerUpcoming(
      data.calendar || {
        status: "error",
        message: "Kalender konnte nicht geladen werden",
      }
    );
  } catch (error) {
    console.error(
      "Fehler beim Laden des Planers:",
      error
    );
    renderPlannerUpcoming({
      status: "error",
      message: "Planer konnte nicht geladen werden",
    });
  } finally {
    setPlannerLoading(false);
  }
}


function setupPlanner() {
  const previous = qs(
    "[data-planner-previous]"
  );
  const next = qs(
    "[data-planner-next]"
  );
  const today = qs(
    "[data-planner-today]"
  );
  const refresh = qs(
    "[data-planner-refresh]"
  );

  renderPlannerCalendar();

  previous?.addEventListener(
    "click",
    () => {
      plannerVisibleMonth = new Date(
        plannerVisibleMonth.getFullYear(),
        plannerVisibleMonth.getMonth() - 1,
        1
      );
      loadPlanner();
    }
  );

  next?.addEventListener(
    "click",
    () => {
      plannerVisibleMonth = new Date(
        plannerVisibleMonth.getFullYear(),
        plannerVisibleMonth.getMonth() + 1,
        1
      );
      loadPlanner();
    }
  );

  today?.addEventListener(
    "click",
    () => {
      const now = new Date();
      plannerVisibleMonth = new Date(
        now.getFullYear(),
        now.getMonth(),
        1
      );
      loadPlanner();
    }
  );

  refresh?.addEventListener(
    "click",
    () => loadPlanner(true)
  );
}


// ============================================================
// WEWASH
// ============================================================

function getDryerRemainingSeconds(isoTimestamp) {
  if (!isoTimestamp) {
    return null;
  }

  const startedAt =
    new Date(isoTimestamp).getTime();

  if (!Number.isFinite(startedAt)) {
    return null;
  }

  const finishedAt =
    startedAt
    + (
      WEWASH_DRYER_DURATION_MINUTES
      * 60000
    );

  const remainingMinutes =
    Math.max(
      0,
      Math.ceil(
        (
          finishedAt
          - Date.now()
        )
        / 60000
      )
    );

  return remainingMinutes * 60;
}


function setupDashboardTabs() {
  const buttons =
    qsa(
      ".dashboard-tab-button"
    );

  const groupButtons =
    qsa(
      "[data-dashboard-group-button]"
    );


  buttons.forEach(
    button => {

      button.addEventListener(
        "click",
        () => {

          activateDashboardTab(
            button.dataset.dashboardTab
          );
        }
      );


      button.addEventListener(
        "keydown",
        event => {

          const siblingButtons = Array.from(
            button.closest(
              ".dashboard-tab-children"
            )?.querySelectorAll(
              ".dashboard-tab-button"
            ) || []
          );
          const index = siblingButtons.indexOf(
            button
          );

          let nextIndex = null;


          if (
            event.key === "ArrowRight"
          ) {
            nextIndex =
              (index + 1)
              % siblingButtons.length;
          }


          if (
            event.key === "ArrowLeft"
          ) {
            nextIndex =
              (index - 1 + siblingButtons.length)
              % siblingButtons.length;
          }


          if (
            event.key === "Home"
          ) {
            nextIndex = 0;
          }


          if (
            event.key === "End"
          ) {
            nextIndex =
              siblingButtons.length - 1;
          }


          if (
            nextIndex === null
          ) {
            return;
          }


          event.preventDefault();

          siblingButtons[
            nextIndex
          ].focus();

          activateDashboardTab(
            siblingButtons[
              nextIndex
            ].dataset.dashboardTab
          );
        }
      );
    }
  );


  groupButtons.forEach(
    (button, index) => {
      button.addEventListener(
        "click",
        () => {
          const firstTab = button.closest(
            ".dashboard-tab-group"
          )?.querySelector(
            ".dashboard-tab-button"
          );

          if (firstTab) {
            activateDashboardTab(
              firstTab.dataset.dashboardTab
            );
          }
        }
      );

      button.addEventListener(
        "keydown",
        event => {
          if (
            event.key !== "ArrowLeft"
            && event.key !== "ArrowRight"
            && event.key !== "Home"
            && event.key !== "End"
          ) {
            return;
          }

          let nextIndex = index;

          if (event.key === "ArrowRight") {
            nextIndex = (index + 1) % groupButtons.length;
          }

          if (event.key === "ArrowLeft") {
            nextIndex = (index - 1 + groupButtons.length) % groupButtons.length;
          }

          if (event.key === "Home") {
            nextIndex = 0;
          }

          if (event.key === "End") {
            nextIndex = groupButtons.length - 1;
          }

          event.preventDefault();
          groupButtons[nextIndex].focus();
        }
      );
    }
  );


  const requestedTab = new URLSearchParams(
    window.location.search
  ).get("tab");
  const requestedButton = Array.from(buttons).find(
    button => button.dataset.dashboardTab === requestedTab
  );

  if (requestedButton) {
    activateDashboardTab(
      requestedTab,
      false
    );
  } else {
    activateDashboardTab(
      "overview",
      false
    );
  }
}


function setupHeaderClock() {
  const clock =
    qs(
      "#header-clock"
    );


  if (!clock) {
    return;
  }


  const hoursElement =
    clock.querySelector(
      "[data-clock-hours]"
    );


  const minutesElement =
    clock.querySelector(
      "[data-clock-minutes]"
    );


  const dateElement = qs("#header-date");


  if (
    !hoursElement
    || !minutesElement
  ) {
    return;
  }


  const renderClock = () => {
    const now =
      new Date();


    const options = { timeZone: "Europe/Berlin" };
    const time = new Intl.DateTimeFormat("de-DE", {
      ...options, hour: "2-digit", minute: "2-digit"
    }).format(now);
    const [hours, minutes] = time.split(":");


    hoursElement.textContent =
      hours;

    minutesElement.textContent =
      minutes;


    if (dateElement) {
      const weekday = new Intl.DateTimeFormat("de-DE", { ...options, weekday: "short" }).format(now).replace(/\.$/, "");
      const date = new Intl.DateTimeFormat("de-DE", { ...options, day: "numeric", month: "short" }).format(now);
      dateElement.querySelector("[data-header-date-long]").textContent = `${weekday}., ${date}`;
      dateElement.querySelector("[data-header-date-short]").textContent = new Intl.DateTimeFormat("de-DE", { ...options, day: "2-digit", month: "2-digit" }).format(now);
      dateElement.dateTime = now.toISOString();
    }

    clock.dateTime =
      now.toISOString();

    clock.setAttribute(
      "aria-label",
      `Uhrzeit ${time}`
    );
  };


  renderClock();

  setInterval(
    renderClock,
    1000
  );
}


// ============================================================
// CLIMATE WORKSPACE
// ============================================================

function isHistoryTabActive() {
  const climatePanel =
    qs(
      "#dashboard-climate"
    );


  return Boolean(
    climatePanel
    && !climatePanel.hidden
  );
}


function ensureHistoryCharts() {
  if (
    !temperatureChart
  ) {
    temperatureChart =
      createChart(
        "temperature-chart",
        "Temperatur",
        "°C"
      );
  }


  if (
    !humidityChart
  ) {
    humidityChart =
      createChart(
        "humidity-chart",
        "Luftfeuchtigkeit",
        "%"
      );
  }


  if (
    !pm25Chart
  ) {
    pm25Chart =
      createChart(
        "pm25-chart",
        "PM2.5",
        "µg/m³",
        {
          min: 0,
        }
      );
  }


  if (
    !iaiChart
  ) {
    iaiChart =
      createChart(
        "iai-chart",
        "IAI",
        "",
        {
          min: 1,
          max: 12,
          stepSize: 1,
        }
      );
  }
}


function syncClimateRoomSelection(
  roomId
) {
  let roomName = "";


  qsa(
    ".climate-card"
  ).forEach(
    card => {

      const selected =
        card.dataset.sensorRoom
        === roomId;


      card.classList.toggle(
        "selected",
        selected
      );


      card.setAttribute(
        "aria-selected",
        selected
          ? "true"
          : "false"
      );


      card.tabIndex =
        selected
          ? 0
          : -1;


      if (selected) {
        roomName =
          card.querySelector(
            "h3"
          )?.textContent.trim()
          || "";
      }
    }
  );


  const historyHeading =
    qs(
      "#climate-history-heading"
    );


  if (
    historyHeading
    && roomName
  ) {
    historyHeading.textContent =
      roomName;
  }


  qsa(
    "[data-hallway-air-quality-chart]"
  ).forEach(
    chart => {
      chart.hidden =
        roomId !== "hallway";
    }
  );


  if (roomId === "hallway") {
    requestAnimationFrame(
      () => {
        pm25Chart?.resize();
        iaiChart?.resize();
      }
    );
  }
}


function selectClimateRoom(
  roomId,
  { focus = false } = {}
) {
  if (!roomId) {
    return;
  }


  selectedHistoryRoom =
    roomId;


  syncClimateRoomSelection(
    roomId
  );


  if (focus) {
    const selectedCard =
      Array.from(
        qsa(
          ".climate-card"
        )
      ).find(
        card =>
          card.dataset.sensorRoom
          === roomId
      );


    selectedCard?.focus();
  }


  if (
    isHistoryTabActive()
  ) {
    loadHistory();
  }
}


function setupClimateRoomSelection() {
  const cards =
    Array.from(
      qsa(
        ".climate-card"
      )
    );


  if (!cards.length) {
    return;
  }


  const initiallySelected =
    cards.find(
      card =>
        card.getAttribute(
          "aria-selected"
        ) === "true"
    )
    || cards[0];


  selectedHistoryRoom =
    initiallySelected.dataset.sensorRoom;


  syncClimateRoomSelection(
    selectedHistoryRoom
  );


  cards.forEach(
    (card, index) => {

      card.addEventListener(
        "click",
        () => {

          selectClimateRoom(
            card.dataset.sensorRoom
          );
        }
      );


      card.addEventListener(
        "keydown",
        event => {

          if (
            event.key === "Enter"
            || event.key === " "
          ) {
            event.preventDefault();

            selectClimateRoom(
              card.dataset.sensorRoom
            );

            return;
          }


          let nextIndex = null;


          if (
            event.key === "ArrowDown"
            || event.key === "ArrowRight"
          ) {
            nextIndex =
              (index + 1)
              % cards.length;
          }


          if (
            event.key === "ArrowUp"
            || event.key === "ArrowLeft"
          ) {
            nextIndex =
              (index - 1 + cards.length)
              % cards.length;
          }


          if (event.key === "Home") {
            nextIndex = 0;
          }


          if (event.key === "End") {
            nextIndex =
              cards.length - 1;
          }


          if (nextIndex === null) {
            return;
          }


          event.preventDefault();

          selectClimateRoom(
            cards[nextIndex]
              .dataset
              .sensorRoom,
            { focus: true }
          );
        }
      );
    }
  );
}


// ============================================================
// CLIMATE - HISTORY
// ============================================================

function createChart(
  canvasId,
  label,
  unit,
  scaleOptions = {}
) {
  const canvas =
    qs(
      `#${canvasId}`
    );


  if (!canvas) {
    return null;
  }


  const ctx =
    canvas.getContext(
      "2d"
    );


  return new Chart(
    ctx,
    {
      type:
        "line",

      data: {
        labels:
          [],

        datasets: [
          {
            label:
              label,

            data:
              [],

            tension:
              0.25,

            borderWidth:
              2,

            pointRadius:
              0,

            pointHoverRadius:
              4,

            borderColor:
              "#d9d9df",

            backgroundColor:
              "rgba(217, 217, 223, 0.10)",

            spanGaps:
              true,

            fill:
              true,
          },
        ],
      },

      options: {
        responsive:
          true,

        maintainAspectRatio:
          false,

        interaction: {
          intersect:
            false,

          mode:
            "index",
        },

        plugins: {
          legend: {
            display:
              false,
          },

          tooltip: {
            displayColors:
              false,

            backgroundColor:
              "#171719",

            borderColor:
              "#2f2f35",

            borderWidth:
              1,

            titleColor:
              "#f5f5f5",

            bodyColor:
              "#c9c9cf",

            callbacks: {
              label(context) {
                return (
                  `${context.parsed.y} ${unit}`
                );
              },
            },
          },
        },

        scales: {
          x: {
            ticks: {
              color:
                getComputedStyle(document.body).getPropertyValue("--text-muted").trim(),

              maxTicksLimit:
                6,

              maxRotation:
                0,

              minRotation:
                0,
            },

            grid: {
              color:
                "rgba(255, 255, 255, 0.05)",
            },
          },

          y: {
            min:
              scaleOptions.min,

            max:
              scaleOptions.max,

            ticks: {
              color:
                getComputedStyle(document.body).getPropertyValue("--text-muted").trim(),

              stepSize:
                scaleOptions.stepSize,
            },

            grid: {
              color:
                "rgba(255, 255, 255, 0.05)",
            },
          },
        },
      },
    }
  );
}


function getHistoryTimestamp(entry) {
  return (
    entry.recorded_at
    ?? entry.created_at
    ?? entry.timestamp
    ?? entry.time
    ?? null
  );
}


function buildHistoryLabels(
  history,
  hours
) {
  return history.map(
    entry => {

      const raw =
        getHistoryTimestamp(
          entry
        );


      const date =
        parseDateValue(
          raw
        );


      if (!date) {
        return "";
      }


      if (
        hours === 168
      ) {
        return date.toLocaleString(
          "de-DE",
          {
            day:
              "2-digit",

            month:
              "2-digit",

            hour:
              "2-digit",

            minute:
              "2-digit",
          }
        );
      }


      return date.toLocaleTimeString(
        "de-DE",
        {
          hour:
            "2-digit",

          minute:
            "2-digit",
        }
      );
    }
  );
}


function getLatestHistoryValue(
  history,
  key
) {
  for (
    let index = history.length - 1;
    index >= 0;
    index -= 1
  ) {
    const value =
      history[index][key];

    if (
      value !== null
      && value !== undefined
    ) {
      return value;
    }
  }


  return null;
}


function updateHistoryCards(
  history
) {


  const tempCurrent =
    qs(
      "#history-temperature-current"
    );


  const humidityCurrent =
    qs(
      "#history-humidity-current"
    );


  const pm25Current =
    qs(
      "#history-pm25-current"
    );


  const iaiCurrent =
    qs(
      "#history-iai-current"
    );


  if (
    !tempCurrent
    || !humidityCurrent
  ) {
    return;
  }


  if (!history.length) {
    tempCurrent.textContent =
      "-";

    humidityCurrent.textContent =
      "-";

    if (pm25Current) {
      pm25Current.textContent =
        "-";
    }

    if (iaiCurrent) {
      iaiCurrent.textContent =
        "-";
    }

    return;
  }


  const temperature =
    getLatestHistoryValue(
      history,
      "temperature"
    );


  const humidity =
    getLatestHistoryValue(
      history,
      "humidity"
    );


  const pm25 =
    getLatestHistoryValue(
      history,
      "pm25"
    );


  const iai =
    getLatestHistoryValue(
      history,
      "iai"
    );


  tempCurrent.textContent =
    `${formatNumber(temperature, 1)} °C`;


  humidityCurrent.textContent =
    `${formatNumber(humidity, 1)} %`;


  if (pm25Current) {
    pm25Current.textContent =
      `${formatNumber(pm25, 1)} µg/m³`;
  }


  if (iaiCurrent) {
    iaiCurrent.textContent =
      formatNumber(iai, 0);
  }
}


function renderHistory(
  history,
  hours
) {
  ensureHistoryCharts();


  const labels =
    buildHistoryLabels(
      history,
      hours
    );


  const temperatures =
    history.map(
      item =>
        item.temperature
    );


  const humidities =
    history.map(
      item =>
        item.humidity
    );


  const pm25Values =
    history.map(
      item =>
        item.pm25
    );


  const iaiValues =
    history.map(
      item =>
        item.iai
    );


  if (
    temperatureChart
  ) {
    temperatureChart
      .data
      .labels =
        labels;


    temperatureChart
      .data
      .datasets[
        0
      ]
      .data =
        temperatures;


    temperatureChart.update();
  }


  if (
    humidityChart
  ) {
    humidityChart
      .data
      .labels =
        labels;


    humidityChart
      .data
      .datasets[
        0
      ]
      .data =
        humidities;


    humidityChart.update();
  }


  if (
    pm25Chart
  ) {
    pm25Chart.data.labels =
      labels;

    pm25Chart.data.datasets[0].data =
      pm25Values;

    pm25Chart.update();
  }


  if (
    iaiChart
  ) {
    iaiChart.data.labels =
      labels;

    iaiChart.data.datasets[0].data =
      iaiValues;

    iaiChart.update();
  }


  updateHistoryCards(
    history
  );
}


async function loadHistory() {
  try {
    ensureHistoryCharts();


    const response =
      await fetch(
        `/api/history?room=${selectedHistoryRoom}&hours=${selectedHistoryHours}`
      );


    if (!response.ok) {
      return;
    }


    const data =
      await response.json();


    if (!data.success) {
      return;
    }


    renderHistory(
      data.history || [],
      selectedHistoryHours
    );

  } catch (error) {
    console.error(
      "Fehler beim Laden der Historie:",
      error
    );
  }
}


function setupHistoryControls() {
  const rangeButtons =
    qsa(
      ".range-button"
    );


  rangeButtons.forEach(
    button => {

      button.addEventListener(
        "click",
        () => {

          rangeButtons.forEach(
            btn =>
              btn.classList.remove(
                "active"
              )
          );


          button.classList.add(
            "active"
          );


          selectedHistoryHours =
            Number(
              button.dataset.hours
            );


          if (
            isHistoryTabActive()
          ) {
            loadHistory();
          }
        }
      );
    }
  );
}


// ============================================================
// CAMERAS
// ============================================================

function isCameraTabActive() {
  return qs(
    ".main-layout"
  )?.dataset.activeDashboardTab === "cameras";
}


function clearCameraLiveTimers() {
  if (cameraLiveReadyTimer) {
    clearTimeout(cameraLiveReadyTimer);
    cameraLiveReadyTimer = null;
  }

  if (cameraLiveRetryTimer) {
    clearTimeout(cameraLiveRetryTimer);
    cameraLiveRetryTimer = null;
  }
}


function setCameraLiveState(
  state,
  reason = cameraLiveReason
) {
  const placeholder = qs(
    "[data-camera-live-placeholder]"
  );
  const title = qs(
    "[data-camera-live-title]"
  );
  const message = qs(
    "[data-camera-live-message]"
  );
  const retry = qs(
    "[data-camera-live-retry]"
  );
  const status = qs(
    "[data-camera-live-state]"
  );
  const statusIcon = qs(
    "[data-camera-live-state-icon]"
  );
  const statusLabel = qs(
    "[data-camera-live-state-label]"
  );
  const copy = {
    idle: {
      title: "Livebild bereit",
      message: (
        "Der Stream startet, sobald der Kamera-Tab geöffnet ist."
      ),
      label: "Bereit",
      icon: "ti ti-video",
    },
    connecting: {
      title: "Livebild wird verbunden",
      message: (
        "Die Verbindung bleibt vollständig im lokalen Netzwerk."
      ),
      label: "Verbindet",
      icon: "ti ti-loader-2",
    },
    live: {
      title: "Livebild",
      message: "Lokale Kameravorschau ist aktiv.",
      label: "Live",
      icon: "ti ti-video",
    },
    error: {
      title: "Livebild nicht erreichbar",
      message: (
        "Kamera oder RTSP-Stream antwortet gerade nicht."
      ),
      label: "Verbindung fehlgeschlagen",
      icon: "ti ti-alert-circle",
    },
    unavailable: {
      title: "Livebild nicht konfiguriert",
      message: reason === "ffmpeg_missing"
        ? "FFmpeg fehlt auf dem MONOLITH-Server."
        : "Die RTSP-Zugangsdaten fehlen auf dem MONOLITH-Server.",
      label: "Nicht konfiguriert",
      icon: "ti ti-plug-off",
    },
  }[state];

  if (!copy) {
    return;
  }

  title && (title.textContent = copy.title);
  message && (message.textContent = copy.message);
  statusLabel && (
    statusLabel.textContent = copy.label
  );

  if (statusIcon) {
    statusIcon.className = copy.icon;
  }

  placeholder?.classList.toggle(
    "is-hidden",
    state === "live"
  );

  if (retry) {
    retry.hidden = state !== "error";
  }

  if (status) {
    status.classList.toggle(
      "is-connecting",
      state === "connecting"
    );
    status.classList.toggle(
      "is-live",
      state === "live"
    );
    status.classList.toggle(
      "is-error",
      state === "error"
    );
  }
}


function markCameraLiveConnected(attempt) {
  if (
    attempt !== cameraLiveAttempt
    || !isCameraTabActive()
  ) {
    return;
  }

  if (cameraLiveReadyTimer) {
    clearTimeout(cameraLiveReadyTimer);
  }

  cameraLiveReadyTimer = null;
  setCameraLiveState("live");
}


function handleCameraLiveFailure(attempt) {
  if (
    attempt !== cameraLiveAttempt
    || !isCameraTabActive()
  ) {
    return;
  }

  clearCameraLiveTimers();
  cameraLiveAttempt += 1;

  const feed = qs(
    "[data-camera-live-feed]"
  );

  if (feed) {
    feed.removeAttribute("src");
    feed.classList.remove("is-visible");
  }

  setCameraLiveState("error");
  scheduleCameraLiveRetry();
}


function waitForCameraLiveFrame(
  attempt,
  startedAt
) {
  if (
    attempt !== cameraLiveAttempt
    || !isCameraTabActive()
  ) {
    return;
  }

  const feed = qs(
    "[data-camera-live-feed]"
  );

  if (feed?.naturalWidth > 0) {
    markCameraLiveConnected(attempt);
    return;
  }

  if (Date.now() - startedAt >= 8000) {
    handleCameraLiveFailure(attempt);
    return;
  }

  cameraLiveReadyTimer = setTimeout(
    () => waitForCameraLiveFrame(
      attempt,
      startedAt
    ),
    250
  );
}


function stopCameraLive() {
  clearCameraLiveTimers();
  cameraLiveAttempt += 1;

  const feed = qs(
    "[data-camera-live-feed]"
  );

  if (feed) {
    feed.removeAttribute("src");
    feed.classList.remove("is-visible");
  }

  if (cameraLiveAvailable) {
    setCameraLiveState("idle");
  }
}


function scheduleCameraLiveRetry() {
  if (
    cameraLiveRetryTimer
    || !cameraLiveAvailable
  ) {
    return;
  }

  cameraLiveRetryTimer = setTimeout(
    () => {
      cameraLiveRetryTimer = null;
      startCameraLive(true);
    },
    10000
  );
}


function startCameraLive(force = false) {
  const feed = qs(
    "[data-camera-live-feed]"
  );

  if (
    !feed
    || !cameraLiveAvailable
    || !isCameraTabActive()
    || document.visibilityState !== "visible"
  ) {
    return;
  }

  if (
    feed.hasAttribute("src")
    && !force
  ) {
    return;
  }

  clearCameraLiveTimers();
  cameraLiveAttempt += 1;
  const attempt = cameraLiveAttempt;

  feed.classList.add("is-visible");
  setCameraLiveState("connecting");
  feed.src = (
    `/api/camera/live?attempt=${attempt}`
  );
  cameraLiveReadyTimer = setTimeout(
    () => waitForCameraLiveFrame(
      attempt,
      Date.now()
    ),
    250
  );
}


function configureCameraLive(camera) {
  cameraLiveAvailable = Boolean(
    camera?.live_available
  );
  cameraLiveReason = camera?.live_reason
    || "not_configured";

  const feed = qs(
    "[data-camera-live-feed]"
  );

  if (feed) {
    feed.alt = `Livebild der Kamera ${cameraName}`;
  }

  if (!cameraLiveAvailable) {
    stopCameraLive();
    setCameraLiveState(
      "unavailable",
      cameraLiveReason
    );
    return;
  }

  startCameraLive();
}


function getCameraDateKey(date) {
  return [
    date.getFullYear(),
    String(
      date.getMonth() + 1
    ).padStart(2, "0"),
    String(
      date.getDate()
    ).padStart(2, "0"),
  ].join("-");
}


function getCameraTimelineDays() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  return Array.from(
    {
      length: CAMERA_TIMELINE_DAYS,
    },
    (unused, index) => {
      const date = new Date(today);
      date.setDate(
        today.getDate()
        - (
          CAMERA_TIMELINE_DAYS
          - index
          - 1
        )
      );

      return {
        date,
        key: getCameraDateKey(date),
      };
    }
  );
}


function formatCameraDayName(
  date,
  index
) {
  if (
    index
    === CAMERA_TIMELINE_DAYS - 1
  ) {
    return "Heute";
  }

  if (
    index
    === CAMERA_TIMELINE_DAYS - 2
  ) {
    return "Gestern";
  }

  return date.toLocaleDateString(
    "de-DE",
    {
      weekday: "short",
    }
  ).replace(".", "");
}


function getCameraEventsForDay(dayKey) {
  return cameraEvents.filter(
    event =>
      getEventDateKey(event)
      === dayKey
  );
}


function renderCameraSelectionSummary(
  days,
  events
) {
  const selectedIndex = days.findIndex(
    day => day.key === cameraSelectedDayKey
  );
  const selectedDay = days[selectedIndex];
  const dayLabel = qs(
    "[data-camera-selected-day]"
  );
  const countLabel = qs(
    "[data-camera-selected-count]"
  );

  if (dayLabel && selectedDay) {
    const name = formatCameraDayName(
      selectedDay.date,
      selectedIndex
    );
    const date = selectedDay.date.toLocaleDateString(
      "de-DE",
      {
        day: "2-digit",
        month: "2-digit",
      }
    );

    dayLabel.textContent = `${name}, ${date}`;
  }

  if (countLabel) {
    countLabel.textContent = events.length === 1
      ? "1 Ereignis"
      : `${events.length} Ereignisse`;
  }
}


function getCameraEventPosition(event) {
  const date = parseDateValue(
    getEventTimestamp(event)
  );

  if (!date) {
    return 0;
  }

  const seconds = (
    date.getHours() * 3600
    + date.getMinutes() * 60
    + date.getSeconds()
  );

  return Math.max(
    0.15,
    Math.min(
      99.85,
      seconds / 86400 * 100
    )
  );
}


function renderCameraDaySelector(days) {
  const selector = qs(
    "[data-camera-day-selector]"
  );

  if (!selector) {
    return;
  }

  selector.innerHTML = days.map(
    (day, index) => {
      const count = getCameraEventsForDay(
        day.key
      ).length;
      const label = formatCameraDayName(
        day.date,
        index
      );
      const date = day.date.toLocaleDateString(
        "de-DE",
        {
          day: "2-digit",
          month: "2-digit",
        }
      );

      return `
        <button
          class="camera-day-button ${
            day.key === cameraSelectedDayKey
              ? "active"
              : ""
          }"
          type="button"
          data-camera-day="${day.key}"
          aria-pressed="${
            day.key === cameraSelectedDayKey
              ? "true"
              : "false"
          }"
        >
          <span class="camera-day-copy">
            <strong>${escapeHtml(label)}</strong>
            <span>${escapeHtml(date)}</span>
          </span>
          <span class="camera-day-count">${count}</span>
        </button>
      `;
    }
  ).join("");

  selector.querySelectorAll(
    "[data-camera-day]"
  ).forEach(
    button => button.addEventListener(
      "click",
      () => {
        cameraSelectedDayKey =
          button.dataset.cameraDay;

        selector.querySelectorAll(
          "[data-camera-day]"
        ).forEach(
          dayButton => {
            const active = (
              dayButton.dataset.cameraDay
              === cameraSelectedDayKey
            );
            dayButton.classList.toggle(
              "active",
              active
            );
            dayButton.setAttribute(
              "aria-pressed",
              active ? "true" : "false"
            );
          }
        );

        const selectedEvents =
          getCameraEventsForDay(
            cameraSelectedDayKey
          );
        renderCameraTimeline(
          selectedEvents
        );
        renderCameraEventList(
          selectedEvents
        );
        renderCameraSelectionSummary(
          days,
          selectedEvents
        );
      }
    )
  );
}


function renderCameraTimeline(events) {
  const timeline = qs(
    "[data-camera-timeline]"
  );

  if (!timeline) {
    return;
  }

  if (!events.length) {
    timeline.innerHTML = `
      <div class="camera-timeline-empty">
        Keine Bewegung an diesem Tag
      </div>
    `;
    return;
  }

  const chronological = [...events].sort(
    (left, right) =>
      Number(left.timestamp)
      - Number(right.timestamp)
  );

  timeline.innerHTML = chronological.map(
    event => {
      const time = formatEventTime(event);
      const title = [
        time,
        event.room || cameraName,
        getFeedTitle(event),
      ].filter(Boolean).join(", ");

      return `
        <button
          class="camera-timeline-marker"
          type="button"
          style="left: ${getCameraEventPosition(event)}%"
          data-camera-event-id="${Number(event.id)}"
          aria-label="${escapeHtml(title)}"
          title="${escapeHtml(title)}"
        ></button>
      `;
    }
  ).join("");

  timeline.querySelectorAll(
    "[data-camera-event-id]"
  ).forEach(
    marker => marker.addEventListener(
      "click",
      () => highlightCameraEvent(
        marker.dataset.cameraEventId
      )
    )
  );
}


function renderCameraEventList(events) {
  const list = qs(
    "[data-camera-event-list]"
  );

  if (!list) {
    return;
  }

  if (!events.length) {
    list.innerHTML = `
      <div class="camera-events-empty">
        Für diesen Tag wurden keine Bewegungen erkannt.
      </div>
    `;
    return;
  }

  const newestFirst = [...events].sort(
    (left, right) =>
      Number(right.timestamp)
      - Number(left.timestamp)
  );

  list.innerHTML = newestFirst.map(
    event => `
      <article
        id="camera-event-${Number(event.id)}"
        class="camera-event-item"
        data-camera-event-item="${Number(event.id)}"
      >
        <time class="camera-event-time">
          ${escapeHtml(formatEventTime(event))}
        </time>
        <span class="camera-event-icon" aria-hidden="true">
          <i class="ti ti-walk"></i>
        </span>
        <span class="camera-event-copy">
          <strong>${escapeHtml(getFeedTitle(event))}</strong>
          <span>${escapeHtml(event.room || cameraName)}</span>
        </span>
      </article>
    `
  ).join("");
}


function renderCameraEvents() {
  const days = getCameraTimelineDays();

  if (
    !cameraSelectedDayKey
    || !days.some(
      day => day.key === cameraSelectedDayKey
    )
  ) {
    cameraSelectedDayKey = days[
      days.length - 1
    ].key;
  }

  const selectedEvents = getCameraEventsForDay(
    cameraSelectedDayKey
  );
  const status = qs(
    "[data-camera-header-status]"
  );
  const name = qs(
    "[data-camera-name]"
  );

  if (status) {
    status.textContent = cameraEvents.length === 1
      ? "1 Bewegung in 7 Tagen"
      : `${cameraEvents.length} Bewegungen in 7 Tagen`;
  }

  if (name) {
    name.textContent = cameraName;
  }

  renderCameraDaySelector(days);
  renderCameraTimeline(selectedEvents);
  renderCameraEventList(selectedEvents);
  renderCameraSelectionSummary(
    days,
    selectedEvents
  );
}


function renderCameraError() {
  const status = qs(
    "[data-camera-header-status]"
  );
  const timeline = qs(
    "[data-camera-timeline]"
  );
  const list = qs(
    "[data-camera-event-list]"
  );

  if (status) {
    status.textContent = (
      "Ereignisse nicht erreichbar"
    );
  }

  if (timeline) {
    timeline.innerHTML = `
      <div class="camera-timeline-empty">
        Timeline nicht verfügbar
      </div>
    `;
  }

  if (list) {
    list.innerHTML = `
      <div class="camera-events-error" role="status">
        Bewegungsereignisse konnten nicht geladen werden.
      </div>
    `;
  }
}


async function loadCameraEvents() {
  if (cameraIsLoading) {
    return;
  }

  cameraIsLoading = true;

  const refresh = qs(
    "[data-camera-refresh]"
  );
  refresh?.classList.add(
    "is-loading"
  );

  if (refresh) {
    refresh.disabled = true;
  }

  try {
    const response = await fetch(
      `/api/camera/events?days=${CAMERA_TIMELINE_DAYS}`
    );

    if (!response.ok) {
      throw new Error(
        "Kameraereignisse nicht erreichbar"
      );
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(
        data.error
        || "Kameraereignisse nicht verfügbar"
      );
    }

    cameraEvents = Array.isArray(
      data.events
    )
      ? data.events
      : [];
    cameraName = data.camera?.name
      || cameraName;
    cameraHasLoaded = true;
    renderCameraEvents();
    configureCameraLive(data.camera);

  } catch (error) {
    console.error(
      "Fehler beim Laden der Kameraereignisse:",
      error
    );

    if (!cameraHasLoaded) {
      renderCameraError();
    }

  } finally {
    cameraIsLoading = false;
    refresh?.classList.remove(
      "is-loading"
    );

    if (refresh) {
      refresh.disabled = false;
    }
  }
}


function highlightCameraEvent(eventId) {
  qsa(
    "[data-camera-event-item]"
  ).forEach(
    item => item.classList.toggle(
      "is-highlighted",
      item.dataset.cameraEventItem
      === eventId
    )
  );

  qsa(
    ".camera-timeline-marker"
  ).forEach(
    marker => marker.classList.toggle(
      "active",
      marker.dataset.cameraEventId
      === eventId
    )
  );

  const item = qs(
    `[data-camera-event-item="${eventId}"]`
  );

  item?.scrollIntoView({
    behavior: window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches
      ? "auto"
      : "smooth",
    block: "nearest",
  });
}


function setupCamera() {
  const feed = qs(
    "[data-camera-live-feed]"
  );

  feed?.addEventListener(
    "load",
    () => markCameraLiveConnected(
      cameraLiveAttempt
    )
  );

  feed?.addEventListener(
    "error",
    () => {
      if (
        !isCameraTabActive()
        || !feed.hasAttribute("src")
      ) {
        return;
      }

      handleCameraLiveFailure(
        cameraLiveAttempt
      );
    }
  );

  qs(
    "[data-camera-live-retry]"
  )?.addEventListener(
    "click",
    () => startCameraLive(true)
  );

  qs(
    "[data-camera-refresh]"
  )?.addEventListener(
    "click",
    () => loadCameraEvents()
  );
}


// ============================================================
// FEED
// ============================================================

function getFeedMeta(event) {
  const sourceId =
    String(
      event.source_id
      || ""
    ).toLowerCase();


  const title =
    String(
      event.title
      || ""
    ).toLowerCase();


  const eventType =
    String(
      event.event_type
      || event.type
      || ""
    ).toLowerCase();


  // ----------------------------------------------------------
  // PACKAGES
  // ----------------------------------------------------------

  if (
    eventType === "package"
    || sourceId.startsWith("package:")
  ) {
    let packageState = "announced";

    if (
      includesAny(
        title,
        [
          "zustellversuch",
          "problem",
          "fehlgeschlagen",
          "nicht zugestellt",
        ]
      )
    ) {
      packageState = "alert";
    } else if (
      includesAny(
        title,
        [
          "zugestellt",
          "abgeholt",
        ]
      )
    ) {
      packageState = "delivered";
    } else if (
      includesAny(
        title,
        [
          "in zustellung",
          "abholbereit",
        ]
      )
    ) {
      packageState = "active";
    } else if (
      includesAny(
        title,
        [
          "unterwegs",
          "transport",
        ]
      )
    ) {
      packageState = "transit";
    }

    return {
      icon:
        "ti ti-package",

      label:
        "Paket",

      type:
        "package",

      state:
        packageState,
    };
  }


  // ----------------------------------------------------------
  // PICNIC / EINKAUF
  // ----------------------------------------------------------

  if (
    eventType === "picnic"
    || sourceId.startsWith(
      "picnic_"
    )
  ) {
    return {
      icon:
        "ti ti-shopping-cart",

      type:
        "shopping",

      state:
        "on",
    };
  }


  // ----------------------------------------------------------
  // PRESENCE
  // ----------------------------------------------------------

  if (
    eventType === "presence"
    || sourceId.startsWith(
      "presence_"
    )
  ) {

    // Nach Hause gekommen
    if (
      includesAny(
        title,
        [
          "nach hause gekommen",
          "angekommen",
          "zuhause",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-door-enter",

        type:
          "presence",

        state:
          "on",
      };
    }


    // Haus verlassen
    if (
      includesAny(
        title,
        [
          "haus verlassen",
          "weg",
          "abwesend",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-door-exit",

        type:
          "presence",

        state:
          "off",
      };
    }


    return {
      icon:
        "ti ti-user",

      type:
        "presence",

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // WASCHMASCHINE
  // ----------------------------------------------------------

  if (
    sourceId.includes(
      "washer"
    )
    || sourceId.includes(
      "dryer"
    )
    || eventType
      === "washer"
    || eventType
      === "dryer"
  ) {
    const laundryType = (
      sourceId.includes("dryer")
      || eventType === "dryer"
    )
      ? "dryer"
      : "washer";

    if (
      includesAny(
        title,
        [
          "gestartet",
          "läuft",
          "start",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-wash-dry-1",

        type:
          laundryType,

        state:
          "on",
      };
    }


    if (
      includesAny(
        title,
        [
          "beendet",
          "fertig",
          "ausgeschaltet",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-wash-dry-1",

        type:
          laundryType,

        state:
          "off",
      };
    }


    return {
      icon:
        "ti ti-wash-dry-1",

      type:
        laundryType,

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // AIR PURIFIER
  // ----------------------------------------------------------

  if (
    sourceId.includes(
      "air_purifier"
    )
    || eventType
      === "air_purifier"
  ) {
    if (
      includesAny(
        title,
        [
          "ausgeschaltet",
          "ausgeschalten",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-wind",

        type:
          "air",

        state:
          "off",
      };
    }


    if (
      includesAny(
        title,
        [
          "eingeschaltet",
          "auf ",
          "auto",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-wind",

        type:
          "air",

        state:
          "on",
      };
    }


    return {
      icon:
        "ti ti-wind",

      type:
        "air",

      state:
        "neutral",
    };
  }


  if (sourceId === "device_console_01") {
    return {
      icon: "ti ti-device-gamepad-2",
      type: "console",
      state: title.includes("ausgeschaltet") ? "off" : "on",
    };
  }

  // ----------------------------------------------------------
  // TV / MEDIA
  // ----------------------------------------------------------

  if (
    sourceId.includes(
      "lg_tv"
    )
    || sourceId.includes(
      "homepod"
    )
    || sourceId.includes(
      "apple_tv"
    )
    || eventType
      === "media"
  ) {
    const mediaIcon =
      sourceId.includes("pc")
        ? "ti ti-device-desktop"
        : (
            sourceId.includes("homepod")
              ? "ti ti-device-speaker"
              : "ti ti-device-tv"
          );
    const mediaType =
      sourceId.includes("pc")
        ? "computer"
        : "media";


    if (
      includesAny(
        title,
        [
          "ausgeschaltet",
          "ausgeschalten",
          "standby",
          "pausiert",
          "paused",
        ]
      )
    ) {
      return {
        icon:
          mediaIcon,

        type:
          mediaType,

        state:
          "off",
      };
    }


    if (
      includesAny(
        title,
        [
          "eingeschaltet",
          "gestartet",
          "aktiv",
          "spielt",
          "playing",
        ]
      )
    ) {
      return {
        icon:
          mediaIcon,

        type:
          mediaType,

        state:
          "on",
      };
    }


    return {
      icon:
        mediaIcon,

      type:
        mediaType,

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // PC
  // ----------------------------------------------------------

  if (
    sourceId.includes(
      "pc"
    )
    || title.includes(
      "pc"
    )
  ) {
    if (
      includesAny(
        title,
        [
          "ausgeschaltet",
          "heruntergefahren",
          "offline",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-device-desktop",

        type:
          "computer",

        state:
          "off",
      };
    }


    if (
      includesAny(
        title,
        [
          "eingeschaltet",
          "gestartet",
          "online",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-device-desktop",

        type:
          "computer",

        state:
          "on",
      };
    }


    return {
      icon:
        "ti ti-device-desktop",

      type:
        "computer",

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // ROBOVAC
  // ----------------------------------------------------------

  if (
    sourceId.includes(
      "robovac"
    )
    || title.includes(
      "robovac"
    )
    || title.includes(
      "staubsauger"
    )
  ) {
    if (
      includesAny(
        title,
        [
          "reinigt",
          "gestartet",
          "reinigung gestartet",
          "fährt zur station",
          "lädt",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-robot",

        type:
          "vacuum",

        state:
          "on",
      };
    }


    if (
      includesAny(
        title,
        [
          "beendet",
          "station",
          "dock",
          "zurückgekehrt",
          "gestoppt",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-robot",

        type:
          "vacuum",

        state:
          "off",
      };
    }


    return {
      icon:
        "ti ti-robot",

      type:
        "vacuum",

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // NETWORK
  // ----------------------------------------------------------

  if (
    title.includes(
      "netzwerk"
    )
    || title.includes(
      "wlan"
    )
    || title.includes(
      "internet"
    )
    || eventType
      === "network"
  ) {
    if (
      includesAny(
        title,
        [
          "offline",
          "getrennt",
          "ausfall",
          "nicht erreichbar",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-wifi",

        type:
          "network",

        state:
          "error",
      };
    }


    if (
      includesAny(
        title,
        [
          "online",
          "verbunden",
          "wiederhergestellt",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-wifi",

        type:
          "network",

        state:
          "on",
      };
    }


    return {
      icon:
        "ti ti-wifi",

      type:
        "network",

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // MOTION
  // ----------------------------------------------------------

  if (
    title.includes(
      "bewegung"
    )
    || title.includes(
      "motion"
    )
    || eventType
      === "motion"
  ) {
    return {
      icon:
        "ti ti-walk",

      type:
        "motion",

      state:
        "on",
    };
  }


  // ----------------------------------------------------------
  // CAMERA
  // ----------------------------------------------------------

  if (
    title.includes(
      "kamera"
    )
    || title.includes(
      "camera"
    )
  ) {
    return {
      icon:
        "ti ti-camera",

      type:
        "camera",

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // LIGHT
  // ----------------------------------------------------------

  if (
    sourceId.includes(
      "lamp"
    )
    || sourceId.includes(
      "light"
    )
    || sourceId.includes(
      "led"
    )
    || sourceId.includes(
      "sideboard"
    )
    || sourceId.includes(
      "desk"
    )
    || sourceId.includes(
      "cabinet"
    )
    || title.includes(
      "licht"
    )
    || title.includes(
      "lampe"
    )
    || eventType
      === "device"
  ) {
    if (
      includesAny(
        title,
        [
          "ausgeschaltet",
          "ausgeschalten",
        ]
      )
    ) {
      return {
        icon:
          "ti ti-bulb",

        type:
          "light",

        state:
          "off",
      };
    }


    if (
      title.includes(
        "eingeschaltet"
      )
    ) {
      return {
        icon:
          "ti ti-bulb",

        type:
          "light",

        state:
          "on",
      };
    }


    return {
      icon:
        "ti ti-bulb",

      type:
        "light",

      state:
        "neutral",
    };
  }


  // ----------------------------------------------------------
  // DEFAULT
  // ----------------------------------------------------------

  return {
    icon:
      "ti ti-activity",

    type:
      "system",

    state:
      "neutral",
  };
}


function getFeedTitle(event) {
  const sourceId = String(
    event.source_id
    || ""
  ).toLowerCase();


  const eventType = String(
    event.event_type
    || event.type
    || ""
  ).toLowerCase();


  const title = String(
    event.title
    || ""
  );


  if (
    !sourceId.includes("air_purifier")
    && eventType !== "air_purifier"
  ) {
    return title;
  }


  return title.replace(
    /(\d+(?:[.,]\d+)?)\s*%/,
    (match, value) => {
      const mode = getAirPurifierMode({
        state: "manual",
        speed: Number(
          value.replace(",", ".")
        ),
      });

      return mode || match;
    }
  );
}


function compactFeedEvents(events) {
  const compacted = [];
  let previousAppleTvTimestamp = null;
  const previousPcPlaybackTimestamps = new Map();

  events.forEach(event => {
    const sourceId = String(
      event.source_id
      || ""
    ).toLowerCase();

    const title = String(
      event.title
      || ""
    ).toLowerCase();

    const detail = String(
      event.detail
      || ""
    ).toLowerCase();

    const timestamp = Number(
      event.timestamp
      || event.created_at
    );

    const isPcPlayback =
      sourceId.includes("pc_media")
      && (
        title.includes("wiedergabe gestartet")
        || title.includes("pausiert")
      );

    if (isPcPlayback && Number.isFinite(timestamp)) {
      const signature = `${sourceId}|${title}|${detail}`;
      const previousTimestamp =
        previousPcPlaybackTimestamps.get(signature);

      if (
        Number.isFinite(previousTimestamp)
        && previousTimestamp - timestamp <= 600
      ) {
        return;
      }

      previousPcPlaybackTimestamps.set(
        signature,
        timestamp
      );
    }

    const isAppleTvPlayback =
      sourceId.includes("apple_tv")
      && (
        title.includes("wiedergabe gestartet")
        || title.includes("pausiert")
      );

    if (!isAppleTvPlayback) {
      compacted.push(event);
      previousAppleTvTimestamp = null;
      return;
    }

    if (
      previousAppleTvTimestamp !== null
      && Number.isFinite(timestamp)
      && previousAppleTvTimestamp - timestamp <= 120
    ) {
      previousAppleTvTimestamp = timestamp;
      return;
    }

    compacted.push(event);

    if (Number.isFinite(timestamp)) {
      previousAppleTvTimestamp = timestamp;
    }
  });

  return compacted;
}


function renderFeed(
  events,
  preserveScrollPosition = false
) {
  const visibleEvents =
    compactFeedEvents(
      Array.isArray(events)
        ? events
        : []
    );


  const feed =
    qs(
      "#activity-feed"
    );


  if (!feed) {
    return;
  }


  const previousScrollHeight =
    feed.scrollHeight;

  const previousScrollTop =
    feed.scrollTop;

  // Capture visual positions before replacing the snapshot, including any
  // in-flight translation, so inserting at the top does not jump existing rows.
  const previousPositions = new Map(
    Array.from(feed.querySelectorAll("[data-feed-key]"), item => [
      item.dataset.feedKey,
      item.getBoundingClientRect().top,
    ])
  );
  const previousIds = new Set(
    Array.from(feed.querySelectorAll("[data-feed-event-id]"), item => item.dataset.feedEventId)
  );
  const hadSnapshot = feed.dataset.feedRendered === "true";
  feed.dataset.feedRendered = "true";
  const firstKnownIndex = visibleEvents.findIndex(event => previousIds.has(String(event.id)));
  const newestPreviousId = Math.max(0, ...Array.from(previousIds, Number));
  const arrivalIds = new Set(
    hadSnapshot && !preserveScrollPosition
      ? visibleEvents.filter((event, index) =>
          !previousIds.has(String(event.id))
          && (firstKnownIndex >= 0 ? index < firstKnownIndex : Number(event.id) > newestPreviousId)
        ).map(event => String(event.id))
      : []
  );

  if (
    visibleEvents.length === 0
  ) {
    feed.innerHTML = `
      <div class="feed-empty">
        Noch keine Aktivitäten
      </div>
    `;

    return;
  }


  const paginationStatus =
    feedIsLoadingMore
      ? `
        <div
          class="feed-pagination-status"
          role="status"
        >
          Weitere Aktivitäten werden geladen …
        </div>
      `
      : (
          feedIsInitialized
          && !feedHasMore
          ? `
            <div class="feed-pagination-status">
              Keine älteren Aktivitäten
            </div>
          `
          : ""
        );

  feed.innerHTML =
    visibleEvents
      .map(
        (event, index) => {

          const meta =
            getFeedMeta(
              event
            );


          const room =
            escapeHtml(
              meta.label
              || event.room
              || "System"
            );


          const title =
            escapeHtml(
              getFeedTitle(
                event
              )
            );


          const detail =
            event.detail
            && meta.type !== "package"
              ? `
                <div class="feed-detail">
                  ${escapeHtml(event.detail)}
                </div>
              `
              : "";


          const time =
            formatEventTime(
              event
            );


          const previousEvent =
            visibleEvents[index - 1];

          const dateSeparator =
            previousEvent
            && getEventDateKey(previousEvent)
              !== getEventDateKey(event)
              ? `
                <div class="feed-date-separator" data-feed-key="date-${escapeHtml(getEventDateKey(event))}">
                  <span>
                    ${escapeHtml(formatEventDate(event))}
                  </span>
                </div>
              `
              : "";

          const nextEvent =
            visibleEvents[index + 1];

          const precedesDateSeparator =
            nextEvent
            && getEventDateKey(event)
              !== getEventDateKey(nextEvent);


          return `
            ${dateSeparator}

            <div
              data-feed-event-id="${escapeHtml(String(event.id))}"
              data-feed-key="event-${escapeHtml(String(event.id))}"
              class="
                feed-item
                feed-type-${meta.type}
                feed-state-${meta.state}
                ${
                  precedesDateSeparator
                    ? "feed-item-before-date-separator"
                    : ""
                }
              "
            >

              <div class="feed-icon" aria-hidden="true">
                <i class="${meta.icon}"></i>
              </div>

              <div class="feed-content">

                <div class="feed-main">

                  <span class="feed-room">
                    ${room}
                  </span>

                  <span class="feed-title">
                    ${title}
                  </span>

                </div>

                ${detail}

              </div>

              <div class="feed-time">
                ${escapeHtml(time)}
              </div>

            </div>
          `;
        }
      )
      .join("")
    + paginationStatus;


  if (preserveScrollPosition) {
    feed.scrollTop =
      previousScrollTop
      + feed.scrollHeight
      - previousScrollHeight;
  }

  if (
    arrivalIds.size === 0
    || document.hidden
    || window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return;
  }

  const timing = {
    duration: 620,
    easing: "cubic-bezier(0.22, 1, 0.36, 1)",
  };
  // Read every final position before animating; effects automatically release
  // transform and opacity at completion, restoring the exact original card.
  const items = Array.from(feed.querySelectorAll("[data-feed-key]"), item => ({
    item,
    top: item.getBoundingClientRect().top,
  }));
  items.forEach(({ item, top }) => {
    if (arrivalIds.has(item.dataset.feedEventId)) {
      item.animate([
        { transform: "translateY(-20px) scale(0.9)", opacity: 0 },
        { transform: "translateY(0) scale(1)", opacity: 1 },
      ], timing);
    } else if (previousPositions.has(item.dataset.feedKey)) {
      const offset = previousPositions.get(item.dataset.feedKey) - top;
      if (Math.abs(offset) > 0.5) {
        item.animate([
          { transform: `translateY(${offset}px)` },
          { transform: "translateY(0)" },
        ], timing);
      }
    }
  });
}


async function updateFeed() {
  if (feedIsRefreshing) {
    return;
  }


  feedIsRefreshing = true;

  try {
    const response =
      await fetch(
        `/api/events?limit=${FEED_PAGE_SIZE}`
      );


    if (!response.ok) {
      return;
    }


    const data =
      await response.json();


    if (!data.success) {
      return;
    }


    const latestEvents =
      data.events || [];


    if (feedHasLoadedOlder) {
      const knownEvents =
        new Map(
          feedEvents.map(
            event => [event.id, event]
          )
        );


      latestEvents.forEach(
        event => knownEvents.set(
          event.id,
          event
        )
      );


      feedEvents = Array.from(
        knownEvents.values()
      ).sort(
        (left, right) =>
          right.timestamp - left.timestamp
          || right.id - left.id
      );

    } else {
      feedEvents = latestEvents;
      feedHasMore = Boolean(
        data.has_more
      );
    }


    feedIsInitialized = true;

    const feed = qs(
      "#activity-feed"
    );

    renderFeed(
      feedEvents,
      feedHasLoadedOlder
      && Boolean(feed?.scrollTop)
    );

  } catch (error) {
    console.error(
      "Fehler beim Laden des Feeds:",
      error
    );


  } finally {
    feedIsRefreshing = false;
  }
}


async function loadMoreFeedEvents() {
  if (
    !feedIsInitialized
    || feedIsLoadingMore
    || !feedHasMore
    || feedEvents.length === 0
  ) {
    return;
  }


  const oldestEvent =
    feedEvents[
      feedEvents.length - 1
    ];

  const parameters =
    new URLSearchParams({
      limit: String(
        FEED_PAGE_SIZE
      ),
      before_timestamp: String(
        oldestEvent.timestamp
      ),
      before_id: String(
        oldestEvent.id
      ),
    });


  feedIsLoadingMore = true;
  feedHasLoadedOlder = true;
  renderFeed(feedEvents);


  try {
    const response = await fetch(
      `/api/events?${parameters}`
    );


    if (!response.ok) {
      return;
    }


    const data = await response.json();


    if (!data.success) {
      return;
    }


    const knownIds = new Set(
      feedEvents.map(
        event => event.id
      )
    );

    const olderEvents = (
      data.events || []
    ).filter(
      event => !knownIds.has(event.id)
    );


    feedEvents.push(...olderEvents);
    feedHasMore = Boolean(
      data.has_more
    );

  } catch (error) {
    console.error(
      "Fehler beim Nachladen des Feeds:",
      error
    );

  } finally {
    feedIsLoadingMore = false;
    renderFeed(feedEvents);
  }
}


function setupFeedInfiniteScroll() {
  const feed = qs(
    "#activity-feed"
  );


  if (!feed) {
    return;
  }


  feed.addEventListener(
    "scroll",
    () => {
      const remainingDistance =
        feed.scrollHeight
        - feed.scrollTop
        - feed.clientHeight;


      if (remainingDistance <= 120) {
        loadMoreFeedEvents();
      }
    },
    {
      passive: true,
    }
  );
}


// ============================================================
// PICNIC
// ============================================================

function setPicnicStatus(
  message,
  state = "loading"
) {
  const status = qs(
    "[data-picnic-status]"
  );

  const text = qs(
    "[data-picnic-status-text]"
  );


  if (!status || !text) {
    return;
  }


  status.dataset.state = state;
  text.textContent = message;
}


function formatPicnicDateRange(
  startValue,
  endValue
) {
  const start = parseDateValue(
    startValue
  );
  const end = parseDateValue(
    endValue
  );


  if (!start) {
    return "Termin noch offen";
  }


  const day = new Intl.DateTimeFormat(
    "de-DE",
    {
      weekday: "long",
      day: "2-digit",
      month: "2-digit"
    }
  ).format(start);

  const timeFormatter =
    new Intl.DateTimeFormat(
      "de-DE",
      {
        hour: "2-digit",
        minute: "2-digit"
      }
    );

  const startTime =
    timeFormatter.format(start);

  const endTime = end
    ? timeFormatter.format(end)
    : null;


  return endTime
    ? `${day}, ${startTime}-${endTime} Uhr`
    : `${day}, ${startTime} Uhr`;
}


function picnicStatusLabel(status) {
  const normalized = String(
    status || ""
  ).toUpperCase();

  const labels = {
    CURRENT: "Geplant",
    ORDERED: "Bestellt",
    CONFIRMED: "Bestätigt",
    PENDING: "Wird bestätigt",
    COMPLETED: "Geliefert",
    CANCELLED: "Storniert",
    CANCELED: "Storniert",
    PREPARING: "Wird zusammengestellt",
    PACKING: "Wird zusammengestellt",
    READY: "Bereit zur Auslieferung",
    DELIVERY: "Unterwegs",
    DELIVERING: "Unterwegs",
    DELIVERED: "Geliefert"
  };


  return labels[normalized]
    || status
    || "Bestätigt";
}


function picnicDeliveryVisual(status) {
  const normalized = String(
    status || ""
  ).toUpperCase();


  if (
    normalized === "COMPLETED"
    || normalized === "DELIVERED"
  ) {
    return {
      tone: "delivered",
      marker: "ti-check"
    };
  }


  if (
    normalized === "CANCELLED"
    || normalized === "CANCELED"
  ) {
    return {
      tone: "cancelled",
      marker: "ti-x"
    };
  }


  return {
    tone: "scheduled",
    marker: "ti-clock"
  };
}


function picnicItemsMarkup(items) {
  return items
    .map(
      item => `
        <article class="shopping-item">
          <div class="shopping-item-product">
            ${item.image_url
              ? `
                <img
                  src="${escapeHtml(item.image_url)}"
                  alt=""
                  loading="lazy"
                  referrerpolicy="no-referrer"
                  onerror="this.hidden=true; this.nextElementSibling.hidden=false"
                />
                <i class="ti ti-shopping-bag" hidden></i>
              `
              : `<i class="ti ti-shopping-bag"></i>`
            }

            <span class="shopping-item-quantity">
              ${escapeHtml(item.quantity || 1)}×
            </span>
          </div>

          <div class="shopping-item-copy">
            <strong>${escapeHtml(item.name)}</strong>
            <span>${escapeHtml(item.unit_quantity || "Picnic")}</span>
          </div>

          <div class="shopping-item-price">
            ${escapeHtml(formatCurrency(item.line_price))}
          </div>
        </article>
      `
    )
    .join("");
}


function renderPicnicCart(purchase) {
  const list = qs(
    "[data-picnic-cart]"
  );
  const title = qs(
    "[data-picnic-active-title]"
  );
  const total = qs(
    "[data-picnic-total]"
  );
  const count = qs(
    "[data-picnic-count]"
  );


  if (!list || !title || !total || !count) {
    return;
  }


  const items = purchase?.items || [];
  const totalCount = Number(
    purchase?.total_count || 0
  );

  title.textContent =
    purchase?.title || "Warenkorb";
  total.textContent = formatCurrency(
    purchase?.total_price || 0
  );
  count.textContent = totalCount === 1
    ? "1 Artikel"
    : `${totalCount} Artikel`;


  if (!items.length) {
    const emptyMessage =
      purchase?.kind === "order"
        ? "Für diese Bestellung sind keine Artikel verfügbar."
        : "Dein Warenkorb ist leer.";

    list.innerHTML = `
      <div class="shopping-empty">
        ${escapeHtml(emptyMessage)}
      </div>
    `;
    return;
  }


  list.innerHTML = picnicItemsMarkup(
    items
  );
}


function renderPicnicDeliveries(deliveries) {
  const container = qs(
    "[data-picnic-deliveries]"
  );


  if (!container) {
    return;
  }


  if (!deliveries?.length) {
    container.innerHTML = `
      <div class="shopping-empty compact">
        Noch keine früheren Lieferungen.
      </div>
    `;
    return;
  }


  container.innerHTML = deliveries
    .map(
      delivery => {
        const visual =
          picnicDeliveryVisual(
            delivery.status
          );

        const hasEta =
          delivery.eta_start;

        const start = hasEta
          ? delivery.eta_start
          : delivery.window_start;

        const end = hasEta
          ? delivery.eta_end
          : delivery.window_end;

        return `
          <button
            class="shopping-delivery"
            type="button"
            data-picnic-delivery-id="${escapeHtml(delivery.id)}"
            aria-label="Bestellung vom ${escapeHtml(formatPicnicDateRange(start, end))} öffnen"
          >
            <div class="shopping-delivery-icon ${visual.tone}">
              <i class="ti ti-truck-delivery"></i>
              <i class="shopping-delivery-icon-marker ti ${visual.marker}"></i>
            </div>

            <div class="shopping-delivery-copy">
              <strong>${escapeHtml(picnicStatusLabel(delivery.status))}</strong>
              <span>${escapeHtml(formatPicnicDateRange(start, end))}</span>
            </div>

            <div class="shopping-delivery-action">
              <span class="shopping-delivery-price">
                ${escapeHtml(formatCurrency(delivery.total_price))}
              </span>
              <i class="ti ti-chevron-right"></i>
            </div>
          </button>
        `;
      }
    )
    .join("");
}


async function openPicnicDelivery(
  deliveryId
) {
  const dialog = qs(
    "[data-picnic-delivery-dialog]"
  );
  const title = qs(
    "#picnic-delivery-dialog-title"
  );
  const meta = qs(
    "[data-picnic-delivery-dialog-meta]"
  );
  const count = qs(
    "[data-picnic-delivery-dialog-count]"
  );
  const total = qs(
    "[data-picnic-delivery-dialog-total]"
  );
  const items = qs(
    "[data-picnic-delivery-dialog-items]"
  );


  if (
    !dialog
    || !title
    || !meta
    || !count
    || !total
    || !items
  ) {
    return;
  }


  title.textContent = "Bestellung";
  meta.textContent = "Wird geladen...";
  count.textContent = "-";
  total.textContent = "-";
  items.innerHTML = `
    <div class="shopping-empty">
      Bestellung wird geladen...
    </div>
  `;


  if (!dialog.open) {
    dialog.showModal();
  }


  try {
    const response = await fetch(
      `/api/picnic/deliveries/${encodeURIComponent(deliveryId)}`
    );
    const data = await response.json();


    if (!response.ok || !data.success) {
      throw new Error(
        data.error
        || "Bestellung konnte nicht geladen werden"
      );
    }


    const delivery = data.delivery;
    const itemCount = Number(
      delivery.total_count || 0
    );

    title.textContent =
      "Vergangene Bestellung";
    meta.textContent = formatPicnicDateRange(
      delivery.eta_start
      || delivery.window_start,
      delivery.eta_end
      || delivery.window_end
    );
    count.textContent = itemCount === 1
      ? "1 Artikel"
      : `${itemCount} Artikel`;
    total.textContent = formatCurrency(
      delivery.total_price
    );

    items.innerHTML = delivery.items?.length
      ? picnicItemsMarkup(delivery.items)
      : `
        <div class="shopping-empty">
          Für diese Bestellung sind keine Artikel verfügbar.
        </div>
      `;

  } catch (error) {
    meta.textContent =
      "Laden fehlgeschlagen";
    items.innerHTML = `
      <div class="shopping-empty">
        ${escapeHtml(error.message)}
      </div>
    `;
  }
}


function renderPicnicOrderStatus(order) {
  const container = qs(
    "[data-picnic-order-status]"
  );


  if (!container) {
    return;
  }


  if (!order) {
    container.innerHTML = `
      <div class="shopping-order-status empty">
        <div class="shopping-order-status-icon">
          <i class="ti ti-clock-pause"></i>
        </div>

        <div>
          <strong>Keine aktive Bestellung</strong>
          <span>Der aktuelle Warenkorb steht links.</span>
        </div>
      </div>
    `;
    return;
  }


  const hasEta = order.eta_start;
  const visual = picnicDeliveryVisual(
    order.status
  );
  const start = hasEta
    ? order.eta_start
    : order.window_start;
  const end = hasEta
    ? order.eta_end
    : order.window_end;

  container.innerHTML = `
    <div class="shopping-order-status active">
      <div class="shopping-order-status-icon ${visual.tone}">
        <i class="ti ti-truck-delivery"></i>
        <i class="shopping-delivery-icon-marker ti ${visual.marker}"></i>
      </div>

      <div>
        <strong>${escapeHtml(picnicStatusLabel(order.status))}</strong>
        <span>${escapeHtml(formatPicnicDateRange(start, end))}</span>
      </div>
    </div>
  `;
}


function showPicnicConnectState(data) {
  const card = qs(
    "[data-picnic-connect]"
  );
  const title = qs(
    "[data-picnic-connect-title]"
  );
  const copy = qs(
    "[data-picnic-connect-copy]"
  );
  const requestButton = qs(
    "[data-picnic-request-code]"
  );
  const loginForm = qs(
    "[data-picnic-login-form]"
  );
  const codeForm = qs(
    "[data-picnic-code-form]"
  );


  if (
    !card
    || !title
    || !copy
    || !requestButton
    || !loginForm
    || !codeForm
  ) {
    return;
  }


  const needsSetup =
    !data.configured;
  const needsCode =
    data.two_factor_required;

  card.hidden = !(
    needsSetup
    || needsCode
    || !data.success
  );

  requestButton.hidden = !needsCode;
  loginForm.hidden = !needsSetup;
  codeForm.hidden = true;


  if (needsSetup) {
    title.textContent =
      "Picnic verbinden";
    copy.textContent =
      "Melde dich direkt hier mit deinem Picnic-Konto an.";
    return;
  }


  if (needsCode) {
    title.textContent =
      "Anmeldung bestätigen";
    copy.textContent =
      "Picnic verlangt einmalig eine Bestätigung per SMS.";
    return;
  }


  title.textContent =
    "Picnic nicht erreichbar";
  copy.textContent =
    data.error
    || "Die Daten konnten nicht geladen werden.";
}


async function loadPicnic(forceRefresh = false) {
  if (picnicIsLoading) {
    return;
  }


  picnicIsLoading = true;
  setPicnicStatus(
    "Picnic wird aktualisiert...",
    "loading"
  );

  const refreshButton = qs(
    "[data-picnic-refresh]"
  );

  refreshButton?.classList.add(
    "loading"
  );


  try {
    const response = await fetch(
      forceRefresh
        ? "/api/picnic?refresh=1"
        : "/api/picnic"
    );
    const data = await response.json();

    picnicHasLoaded = true;
    showPicnicConnectState(data);


    if (!data.configured) {
      setPicnicStatus(
        "Noch nicht eingerichtet",
        "idle"
      );
      renderPicnicCart(null);
      renderPicnicDeliveries([]);
      renderPicnicOrderStatus(null);
      return;
    }


    if (data.two_factor_required) {
      setPicnicStatus(
        "Bestätigung erforderlich",
        "warning"
      );
      renderPicnicCart(null);
      renderPicnicDeliveries([]);
      renderPicnicOrderStatus(null);
      return;
    }


    if (!response.ok || !data.success) {
      setPicnicStatus(
        data.error || "Verbindung fehlgeschlagen",
        "error"
      );
      return;
    }


    setPicnicStatus(
      "Verbunden",
      "connected"
    );
    renderPicnicCart(
      data.active_purchase
    );
    renderPicnicDeliveries(
      data.recent_deliveries || []
    );
    renderPicnicOrderStatus(
      data.current_order
    );

  } catch (error) {
    setPicnicStatus(
      "Picnic ist gerade nicht erreichbar",
      "error"
    );
    showPicnicConnectState({
      configured: true,
      success: false,
      error: "Die Verbindung zu MONOLITH ist fehlgeschlagen."
    });
    console.error(
      "Fehler beim Laden von Picnic:",
      error
    );

  } finally {
    picnicIsLoading = false;
    refreshButton?.classList.remove(
      "loading"
    );
  }
}


function setupPicnic() {
  const refreshButton = qs(
    "[data-picnic-refresh]"
  );
  const requestButton = qs(
    "[data-picnic-request-code]"
  );
  const loginForm = qs(
    "[data-picnic-login-form]"
  );
  const codeForm = qs(
    "[data-picnic-code-form]"
  );
  const deliveries = qs(
    "[data-picnic-deliveries]"
  );
  const deliveryDialog = qs(
    "[data-picnic-delivery-dialog]"
  );
  const closeDeliveryDialog = qs(
    "[data-picnic-delivery-dialog-close]"
  );


  refreshButton?.addEventListener(
    "click",
    () => loadPicnic(true)
  );


  deliveries?.addEventListener(
    "click",
    event => {
      const entry = event.target.closest(
        "[data-picnic-delivery-id]"
      );


      if (!entry) {
        return;
      }


      openPicnicDelivery(
        entry.dataset.picnicDeliveryId
      );
    }
  );


  closeDeliveryDialog?.addEventListener(
    "click",
    () => deliveryDialog?.close()
  );


  deliveryDialog?.addEventListener(
    "click",
    event => {
      if (event.target === deliveryDialog) {
        deliveryDialog.close();
      }
    }
  );


  loginForm?.addEventListener(
    "submit",
    async event => {
      event.preventDefault();

      const usernameInput = qs(
        "#picnic-username"
      );
      const passwordInput = qs(
        "#picnic-password"
      );
      const submitButton =
        loginForm.querySelector(
          "button[type='submit']"
        );

      const username =
        usernameInput?.value.trim();
      const password =
        passwordInput?.value || "";


      if (!username || !password) {
        return;
      }


      submitButton.disabled = true;
      setPicnicStatus(
        "Picnic-Anmeldung läuft...",
        "loading"
      );


      try {
        const response = await fetch(
          "/api/picnic/login",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              username,
              password,
              country_code: "DE"
            })
          }
        );
        const data = await response.json();

        passwordInput.value = "";


        if (!response.ok || !data.success) {
          setPicnicStatus(
            data.error || "Picnic-Anmeldung fehlgeschlagen",
            "error"
          );
          return;
        }


        picnicHasLoaded = false;
        await loadPicnic();

      } catch (error) {
        passwordInput.value = "";
        setPicnicStatus(
          "Picnic-Anmeldung fehlgeschlagen",
          "error"
        );

      } finally {
        submitButton.disabled = false;
      }
    }
  );


  requestButton?.addEventListener(
    "click",
    async () => {
      requestButton.disabled = true;


      try {
        const response = await fetch(
          "/api/picnic/2fa/request",
          {
            method: "POST"
          }
        );
        const data = await response.json();


        if (!response.ok || !data.success) {
          setPicnicStatus(
            data.error || "SMS-Code konnte nicht angefordert werden",
            "error"
          );
          return;
        }


        codeForm.hidden = false;
        requestButton.hidden = true;
        qs("#picnic-2fa-code")?.focus();
        setPicnicStatus(
          "SMS-Code wurde gesendet",
          "warning"
        );

      } finally {
        requestButton.disabled = false;
      }
    }
  );


  codeForm?.addEventListener(
    "submit",
    async event => {
      event.preventDefault();

      const input = qs(
        "#picnic-2fa-code"
      );
      const code = input?.value.trim();


      if (!code) {
        return;
      }


      const submitButton =
        codeForm.querySelector(
          "button[type='submit']"
        );

      submitButton.disabled = true;


      try {
        const response = await fetch(
          "/api/picnic/2fa/verify",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({ code })
          }
        );
        const data = await response.json();


        if (!response.ok || !data.success) {
          setPicnicStatus(
            data.error || "SMS-Code ist ungültig",
            "error"
          );
          return;
        }


        input.value = "";
        picnicHasLoaded = false;
        await loadPicnic();

      } finally {
        submitButton.disabled = false;
      }
    }
  );
}


// ============================================================
// ESSENSPLAN
// ============================================================

async function mealPlanRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok || data.success === false) {
    throw new Error(
      data.error || "Essensplan konnte nicht gespeichert werden"
    );
  }

  return data;
}


function updateMealPlanWeekState(weekOffset) {
  const list = qs(`[data-meal-plan-items="${weekOffset}"]`);
  const count = qs(`[data-meal-plan-count="${weekOffset}"]`);

  if (!list) {
    return;
  }

  const items = list.querySelectorAll(".meal-plan-item");
  if (count) {
    count.textContent = items.length === 1
      ? "1 Gericht"
      : `${items.length} Gerichte`;
  }

  if (!items.length && !list.querySelector(".meal-plan-empty")) {
    const empty = document.createElement("div");
    empty.className = "meal-plan-empty";
    empty.textContent = "Noch keine Gerichte eingetragen";
    list.append(empty);
  }
}


async function moveMealPlanItem(itemId, targetWeekOffset) {
  await mealPlanRequest(
    `/api/meal-plan/items/${itemId}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        week_offset: targetWeekOffset
      })
    }
  );
  await loadMealPlan(true);
}


function clearMealPlanDropTargets() {
  qsa("[data-meal-plan-week]").forEach(week => {
    week.classList.remove("is-drop-target");
  });
}


function createMealPlanItemElement(item, weekOffset) {
  const row = document.createElement("div");
  row.className = "meal-plan-item";
  row.draggable = true;
  row.dataset.mealPlanItemId = item.id;
  row.dataset.weekOffset = weekOffset;

  const handle = document.createElement("span");
  handle.className = "meal-plan-item-handle";
  handle.title = "In die andere Woche ziehen";
  handle.setAttribute("aria-hidden", "true");
  handle.innerHTML = '<i class="ti ti-grip-vertical"></i>';

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = item.checked;
  checkbox.setAttribute(
    "aria-label",
    `${item.name} abhaken`
  );

  const name = document.createElement("label");
  name.className = "meal-plan-item-name";
  name.textContent = item.name;
  name.addEventListener("click", () => checkbox.click());

  const remove = document.createElement("button");
  remove.className = "meal-plan-item-delete";
  remove.type = "button";
  remove.setAttribute("aria-label", `${item.name} löschen`);
  remove.innerHTML = '<i class="ti ti-trash"></i>';

  checkbox.addEventListener("change", async () => {
    checkbox.disabled = true;
    row.remove();
    updateMealPlanWeekState(weekOffset);

    try {
      await mealPlanRequest(
        `/api/meal-plan/items/${item.id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            checked: checkbox.checked
          })
        }
      );
    } catch (error) {
      await loadMealPlan(true);
      window.alert(error.message);
    }
  });

  remove.addEventListener("click", async () => {
    remove.disabled = true;

    try {
      await mealPlanRequest(
        `/api/meal-plan/items/${item.id}`,
        { method: "DELETE" }
      );
      await loadMealPlan(true);
    } catch (error) {
      remove.disabled = false;
      window.alert(error.message);
    }
  });

  row.addEventListener("dragstart", event => {
    draggedMealPlanItem = {
      id: item.id,
      sourceWeekOffset: weekOffset
    };
    row.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(item.id));
  });

  row.addEventListener("dragend", () => {
    draggedMealPlanItem = null;
    row.classList.remove("is-dragging");
    clearMealPlanDropTargets();
  });

  let touchTarget = null;
  handle.addEventListener("pointerdown", event => {
    if (event.pointerType === "mouse") {
      return;
    }

    event.preventDefault();
    draggedMealPlanItem = {
      id: item.id,
      sourceWeekOffset: weekOffset
    };
    row.classList.add("is-dragging");
    handle.setPointerCapture(event.pointerId);
  });

  handle.addEventListener("pointermove", event => {
    if (!draggedMealPlanItem || event.pointerType === "mouse") {
      return;
    }

    clearMealPlanDropTargets();
    touchTarget = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest("[data-meal-plan-week]");

    if (
      touchTarget
      && Number(touchTarget.dataset.mealPlanWeek) !== weekOffset
    ) {
      touchTarget.classList.add("is-drop-target");
    }
  });

  handle.addEventListener("pointerup", async event => {
    if (!draggedMealPlanItem || event.pointerType === "mouse") {
      return;
    }

    const targetOffset = touchTarget
      ? Number(touchTarget.dataset.mealPlanWeek)
      : weekOffset;
    row.classList.remove("is-dragging");
    clearMealPlanDropTargets();
    draggedMealPlanItem = null;
    touchTarget = null;

    if (targetOffset === weekOffset) {
      return;
    }

    try {
      await moveMealPlanItem(item.id, targetOffset);
    } catch (error) {
      window.alert(error.message);
    }
  });

  handle.addEventListener("pointercancel", event => {
    if (event.pointerType === "mouse") {
      return;
    }

    row.classList.remove("is-dragging");
    clearMealPlanDropTargets();
    draggedMealPlanItem = null;
    touchTarget = null;
  });

  row.append(handle, checkbox, name, remove);
  return row;
}


function renderMealPlan(data) {
  (data.weeks || []).forEach(week => {
    const list = qs(
      `[data-meal-plan-items="${week.offset}"]`
    );
    const count = qs(
      `[data-meal-plan-count="${week.offset}"]`
    );
    const items = week.items || [];

    if (count) {
      count.textContent = items.length === 1
        ? "1 Gericht"
        : `${items.length} Gerichte`;
    }

    if (!list) {
      return;
    }

    list.replaceChildren();

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "meal-plan-empty";
      empty.textContent = "Noch keine Gerichte eingetragen";
      list.append(empty);
      return;
    }

    items.forEach(item => {
      list.append(createMealPlanItemElement(item, week.offset));
    });
  });
}


async function loadMealPlan(force = false) {
  if (mealPlanIsLoading || (mealPlanHasLoaded && !force)) {
    return;
  }

  mealPlanIsLoading = true;

  try {
    const data = await mealPlanRequest("/api/meal-plan");
    renderMealPlan(data);
    mealPlanHasLoaded = true;
  } catch (error) {
    qsa("[data-meal-plan-items]").forEach(list => {
      const empty = document.createElement("div");
      empty.className = "meal-plan-empty";
      empty.textContent = error.message;
      list.replaceChildren(empty);
    });
  } finally {
    mealPlanIsLoading = false;
  }
}


function splitRecipeInstructions(value) {
  const text = String(value || "").trim();
  if (!text) {
    return ["Für dieses Gericht ist keine Zubereitung hinterlegt."];
  }

  const blocks = text
    .replace(/\r\n?/g, "\n")
    .replace(/([.!?])(?=[A-ZÄÖÜ])/g, "$1\n")
    .split(/\n+/)
    .map(block => block.trim())
    .filter(Boolean);
  const paragraphs = [];

  blocks.forEach(block => {
    const sentences = block.match(/[^.!?]+(?:[.!?]+|$)/g)
      ?.map(sentence => sentence.trim())
      .filter(Boolean) || [block];

    for (let index = 0; index < sentences.length; index += 2) {
      paragraphs.push(sentences.slice(index, index + 2).join(" "));
    }
  });

  return paragraphs;
}


function renderRandomRecipe(recipe) {
  const container = qs("[data-random-recipe]");
  const status = qs("[data-random-recipe-status]");
  const image = qs("[data-random-recipe-image]");
  const title = qs("[data-random-recipe-title]");
  const ingredients = qs("[data-random-recipe-ingredients]");
  const instructions = qs("[data-random-recipe-instructions]");
  const source = qs("[data-random-recipe-source]");
  const intro = qs(".meal-plan-recipe-intro");

  if (!container || !title || !ingredients || !instructions) {
    return;
  }

  title.textContent = recipe.title;
  currentMealPlanRecipe = recipe;
  instructions.replaceChildren();
  splitRecipeInstructions(recipe.instructions).forEach(text => {
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    instructions.append(paragraph);
  });

  if (image) {
    image.hidden = !recipe.image_url;
    image.onerror = () => {
      image.hidden = true;
      intro?.classList.remove("has-image");
    };
    image.src = recipe.image_url || "";
    image.alt = recipe.image_url ? recipe.title : "";
    intro?.classList.toggle("has-image", Boolean(recipe.image_url));
  }

  ingredients.replaceChildren();
  (recipe.ingredients || []).forEach(ingredient => {
    const item = document.createElement("li");
    const name = document.createElement("span");
    const measure = document.createElement("span");
    name.textContent = ingredient.name;
    measure.textContent = ingredient.measure;
    item.append(name, measure);
    ingredients.append(item);
  });

  if (source) {
    source.hidden = !recipe.source_url;
    source.href = recipe.source_url || "";
  }

  status.hidden = true;
  status.classList.remove("is-overlay");
  container.hidden = false;
  container.classList.remove("is-loading");
  updateRecipeBookmarkButton();
}


function currentRecipeBookmark() {
  const sourceId = currentMealPlanRecipe?.source_id
    || currentMealPlanRecipe?.id;
  return mealPlanBookmarks.find(recipe => (
    recipe.source_id === sourceId
  ));
}


function updateRecipeBookmarkButton() {
  const button = qs("[data-random-recipe-bookmark]");
  const saved = currentRecipeBookmark();

  if (!button) {
    return;
  }

  button.classList.toggle("is-saved", Boolean(saved));
  button.querySelector("i").className = saved
    ? "ti ti-bookmark-filled"
    : "ti ti-bookmark";
  button.querySelector("span").textContent = saved
    ? "Gemerkt"
    : "Merken";
  button.setAttribute("aria-pressed", saved ? "true" : "false");
}


function renderRecipeBookmarks() {
  const list = qs("[data-saved-recipes-list]");
  const count = qs("[data-saved-recipes-count]");

  if (count) {
    count.textContent = mealPlanBookmarks.length;
  }

  if (!list) {
    return;
  }

  list.replaceChildren();

  if (!mealPlanBookmarks.length) {
    const empty = document.createElement("div");
    empty.className = "meal-plan-empty";
    empty.textContent = "Noch keine Gerichte gespeichert";
    list.append(empty);
    updateRecipeBookmarkButton();
    return;
  }

  mealPlanBookmarks.forEach(recipe => {
    const row = document.createElement("div");
    row.className = "meal-plan-saved-item";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "meal-plan-saved-item-open";
    open.textContent = recipe.title;
    open.addEventListener("click", () => {
      qs("[data-saved-recipes]").hidden = true;
      renderRandomRecipe(recipe);
    });

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "meal-plan-saved-item-delete";
    remove.setAttribute("aria-label", `${recipe.title} entfernen`);
    remove.innerHTML = '<i class="ti ti-trash"></i>';
    remove.addEventListener("click", async () => {
      remove.disabled = true;
      try {
        await mealPlanRequest(
          `/api/meal-plan/bookmarks/${recipe.bookmark_id}`,
          { method: "DELETE" }
        );
        await loadRecipeBookmarks();
      } catch (error) {
        remove.disabled = false;
        window.alert(error.message);
      }
    });

    row.append(open, remove);
    list.append(row);
  });
  updateRecipeBookmarkButton();
}


async function loadRecipeBookmarks() {
  const data = await mealPlanRequest("/api/meal-plan/bookmarks");
  mealPlanBookmarks = data.recipes || [];
  renderRecipeBookmarks();
}


async function toggleRecipeBookmark() {
  if (!currentMealPlanRecipe) {
    return;
  }

  const button = qs("[data-random-recipe-bookmark]");
  const saved = currentRecipeBookmark();
  button.disabled = true;

  try {
    if (saved) {
      await mealPlanRequest(
        `/api/meal-plan/bookmarks/${saved.bookmark_id}`,
        { method: "DELETE" }
      );
    } else {
      await mealPlanRequest(
        "/api/meal-plan/bookmarks",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            recipe: currentMealPlanRecipe
          })
        }
      );
    }
    await loadRecipeBookmarks();
  } catch (error) {
    window.alert(error.message);
  } finally {
    button.disabled = false;
  }
}


async function loadRandomRecipe(force = false) {
  if (
    randomRecipeIsLoading
    || (randomRecipeHasLoaded && !force)
  ) {
    return;
  }

  const button = qs("[data-random-recipe-refresh]");
  const status = qs("[data-random-recipe-status]");
  const container = qs("[data-random-recipe]");
  const workspace = qs(".meal-plan-workspace");
  const preservedScrollTop = workspace?.scrollTop || 0;
  const hasVisibleRecipe = container && !container.hidden;
  randomRecipeIsLoading = true;
  button?.classList.add("is-loading");
  if (button) {
    button.disabled = true;
  }
  if (status && !hasVisibleRecipe) {
    status.hidden = false;
    status.textContent = "Gericht wird geladen...";
  }
  if (container && hasVisibleRecipe) {
    container.classList.add("is-loading");
  }

  try {
    const data = await mealPlanRequest(
      "/api/meal-plan/random-recipe"
    );
    renderRandomRecipe(data.recipe);
    randomRecipeHasLoaded = true;
    qs("[data-saved-recipes]").hidden = true;
    if (workspace) {
      workspace.scrollTop = preservedScrollTop;
      requestAnimationFrame(() => {
        workspace.scrollTop = preservedScrollTop;
      });
    }
  } catch (error) {
    if (status) {
      status.hidden = false;
      status.textContent = error.message;
      status.classList.toggle("is-overlay", hasVisibleRecipe);
      if (hasVisibleRecipe) {
        setTimeout(() => {
          status.hidden = true;
          status.classList.remove("is-overlay");
        }, 3000);
      }
    }
  } finally {
    randomRecipeIsLoading = false;
    button?.classList.remove("is-loading");
    if (button) {
      button.disabled = false;
    }
    container?.classList.remove("is-loading");
  }
}


function setupMealPlan() {
  qsa("[data-meal-plan-week]").forEach(week => {
    week.addEventListener("dragover", event => {
      if (!draggedMealPlanItem) {
        return;
      }

      const targetOffset = Number(week.dataset.mealPlanWeek);
      if (targetOffset === draggedMealPlanItem.sourceWeekOffset) {
        return;
      }

      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      clearMealPlanDropTargets();
      week.classList.add("is-drop-target");
    });

    week.addEventListener("dragleave", event => {
      if (!week.contains(event.relatedTarget)) {
        week.classList.remove("is-drop-target");
      }
    });

    week.addEventListener("drop", async event => {
      event.preventDefault();
      const dragged = draggedMealPlanItem;
      const targetOffset = Number(week.dataset.mealPlanWeek);
      clearMealPlanDropTargets();

      if (!dragged || targetOffset === dragged.sourceWeekOffset) {
        return;
      }

      try {
        await moveMealPlanItem(dragged.id, targetOffset);
      } catch (error) {
        window.alert(error.message);
      }
    });
  });

  qsa("[data-meal-plan-form]").forEach(form => {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const input = form.querySelector("input[name='name']");
      const name = input?.value.trim();

      if (!name) {
        return;
      }

      const submit = form.querySelector("button[type='submit']");
      submit.disabled = true;

      try {
        await mealPlanRequest(
          "/api/meal-plan/items",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              name,
              week_offset: Number(form.dataset.weekOffset)
            })
          }
        );
        input.value = "";
        await loadMealPlan(true);
        input.focus();
      } catch (error) {
        window.alert(error.message);
      } finally {
        submit.disabled = false;
      }
    });
  });

  qs("[data-random-recipe-refresh]")?.addEventListener(
    "click",
    () => loadRandomRecipe(true)
  );

  qs("[data-random-recipe-bookmark]")?.addEventListener(
    "click",
    toggleRecipeBookmark
  );

  qs("[data-saved-recipes-toggle]")?.addEventListener(
    "click",
    () => {
      const saved = qs("[data-saved-recipes]");
      saved.hidden = !saved.hidden;
    }
  );

  qs("[data-saved-recipes-close]")?.addEventListener(
    "click",
    () => {
      qs("[data-saved-recipes]").hidden = true;
    }
  );

  loadRecipeBookmarks().catch(error => {
    console.warn("Gespeicherte Rezepte konnten nicht geladen werden:", error);
  });
}


// ============================================================
// PET
// ============================================================

async function petRequest(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok || data.success === false) {
    throw new Error(
      data.error || "Haustier-Daten konnten nicht gespeichert werden"
    );
  }

  return data;
}


function formatPetDate(value) {
  const match = String(value || "").match(
    /^(\d{4})-(\d{2})-(\d{2})$/
  );

  if (!match) {
    return value;
  }

  return `${match[3]}/${match[2]}/${match[1]}`;
}


function parsePetDate(value) {
  const match = String(value || "").trim().match(
    /^(\d{2})\/(\d{2})\/(\d{4})$/
  );

  if (!match) {
    return null;
  }

  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const parsed = new Date(year, month - 1, day);

  if (
    parsed.getFullYear() !== year
    || parsed.getMonth() !== month - 1
    || parsed.getDate() !== day
  ) {
    return null;
  }

  return [
    String(year).padStart(4, "0"),
    String(month).padStart(2, "0"),
    String(day).padStart(2, "0"),
  ].join("-");
}


function normalizePetTime(value) {
  const time = String(value || "").trim();
  return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(time)
    ? time
    : null;
}


function maskPetInput(input, separator, firstPartLength, maxDigits) {
  const digits = input.value.replace(/\D/g, "").slice(0, maxDigits);

  input.value = digits.length > firstPartLength
    ? `${digits.slice(0, firstPartLength)}${separator}${digits.slice(firstPartLength)}`
    : digits;
}


function renderPetFeedings(feedings) {
  const list = qs("[data-pet-feeding-list]");
  const summary = qs("[data-pet-feeding-summary]");

  if (!list || !summary) {
    return;
  }

  const completedCount = feedings.filter(
    feeding => feeding.completed
  ).length;

  summary.textContent = feedings.length
    ? `${completedCount} von ${feedings.length} heute erledigt`
    : "Heute noch nichts geplant";

  if (!feedings.length) {
    list.innerHTML = `
      <div class="pet-empty">
        Lege deine erste tägliche Futterzeit an.
      </div>
    `;
    return;
  }

  list.innerHTML = feedings.map(feeding => `
    <div class="pet-row ${feeding.completed ? "is-complete" : ""}">
      <label class="pet-check" title="Als gefüttert markieren">
        <input
          type="checkbox"
          data-pet-feeding-toggle="${feeding.id}"
          ${feeding.completed ? "checked" : ""}
          aria-label="${escapeHtml(feeding.label)} als gefüttert markieren"
        />
        <i class="ti ti-check"></i>
      </label>
      <div class="pet-row-copy">
        <strong>${escapeHtml(feeding.label)}</strong>
        <span>${escapeHtml(feeding.time_of_day)} Uhr</span>
      </div>
      <button
        class="pet-row-action"
        type="button"
        data-pet-feeding-delete="${feeding.id}"
        aria-label="${escapeHtml(feeding.label)} löschen"
        title="Futterzeit löschen"
      >
        <i class="ti ti-trash"></i>
      </button>
    </div>
  `).join("");
}


function renderPetWeights(weights) {
  const summary = qs("[data-pet-weight-summary]");
  const history = qs("[data-pet-weight-list]");
  const empty = qs("[data-pet-weight-empty]");
  const chartWrap = empty?.closest(".pet-chart-wrap");

  if (!summary || !history || !chartWrap) {
    return;
  }

  const latest = weights.at(-1);
  summary.textContent = latest
    ? `${(latest.weight_grams / 1000).toLocaleString("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })} kg am ${formatPetDate(latest.recorded_on)}`
    : "Noch kein Eintrag";

  chartWrap.classList.toggle("has-data", weights.length > 0);

  if (petWeightChart) {
    petWeightChart.destroy();
    petWeightChart = null;
  }

  const canvas = qs("#pet-weight-chart");

  if (canvas && weights.length) {
    petWeightChart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: weights.map(entry => formatPetDate(entry.recorded_on)),
        datasets: [{
          data: weights.map(entry => entry.weight_grams / 1000),
          borderColor: "#76e69a",
          backgroundColor: "rgba(66, 214, 116, 0.10)",
          borderWidth: 2,
          pointRadius: weights.length === 1 ? 4 : 2,
          pointHoverRadius: 5,
          pointBackgroundColor: "#76e69a",
          tension: 0.28,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: context => `${context.parsed.y.toLocaleString("de-DE")} kg`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: getComputedStyle(document.body).getPropertyValue("--text-muted").trim(), maxTicksLimit: 6 },
            border: { color: "#26262a" },
          },
          y: {
            beginAtZero: false,
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: getComputedStyle(document.body).getPropertyValue("--text-muted").trim(),
              callback: value => `${value} kg`,
            },
            border: { display: false },
          },
        },
      },
    });
  }

  history.innerHTML = weights.length
    ? weights.slice().reverse().slice(0, 8).map(entry => `
        <div class="pet-weight-entry">
          <div>
            <strong>${(entry.weight_grams / 1000).toLocaleString("de-DE")} kg</strong>
            <span>${formatPetDate(entry.recorded_on)}</span>
          </div>
          <button
            type="button"
            data-pet-weight-delete="${entry.id}"
            aria-label="Gewicht vom ${formatPetDate(entry.recorded_on)} löschen"
            title="Eintrag löschen"
          >
            <i class="ti ti-x"></i>
          </button>
        </div>
      `).join("")
    : "";
}


function renderPetShopping(items) {
  const list = qs("[data-pet-shopping-list]");
  const summary = qs("[data-pet-shopping-summary]");

  if (!list || !summary) {
    return;
  }

  const openCount = items.filter(item => !item.checked).length;
  summary.textContent = openCount === 0
    ? (items.length ? "Alles erledigt" : "Liste ist leer")
    : (openCount === 1 ? "1 Artikel offen" : `${openCount} Artikel offen`);

  if (!items.length) {
    list.innerHTML = `
      <div class="pet-empty">
        Alles da. Neue Artikel kannst du oben ergänzen.
      </div>
    `;
    return;
  }

  list.innerHTML = items.map(item => `
    <div class="pet-row ${item.checked ? "is-complete" : ""}">
      <label class="pet-check" title="Artikel abhaken">
        <input
          type="checkbox"
          data-pet-shopping-toggle="${item.id}"
          ${item.checked ? "checked" : ""}
          aria-label="${escapeHtml(item.name)} abhaken"
        />
        <i class="ti ti-check"></i>
      </label>
      <div class="pet-row-copy">
        <strong>${escapeHtml(item.name)}</strong>
        <span>${item.checked ? "Erledigt" : "Noch besorgen"}</span>
      </div>
      <button
        class="pet-row-action"
        type="button"
        data-pet-shopping-delete="${item.id}"
        aria-label="${escapeHtml(item.name)} löschen"
        title="Artikel löschen"
      >
        <i class="ti ti-trash"></i>
      </button>
    </div>
  `).join("");
}


async function loadPet(force = false) {
  if (petIsLoading || (petHasLoaded && !force)) {
    return;
  }

  petIsLoading = true;

  try {
    const data = await petRequest("/api/pet");
    renderPetFeedings(data.feeding_times || []);
    renderPetWeights(data.weights || []);
    renderPetShopping(data.shopping_items || []);
    petHasLoaded = true;
  } catch (error) {
    [
      "[data-pet-feeding-list]",
      "[data-pet-shopping-list]",
    ].forEach(selector => {
      const element = qs(selector);
      if (element) {
        element.innerHTML = `
          <div class="pet-empty">${escapeHtml(error.message)}</div>
        `;
      }
    });
  } finally {
    petIsLoading = false;
  }
}


function setupPet() {
  const feedingForm = qs("[data-pet-feeding-form]");
  const weightForm = qs("[data-pet-weight-form]");
  const shoppingForm = qs("[data-pet-shopping-form]");

  if (!feedingForm || !weightForm || !shoppingForm) {
    return;
  }

  weightForm.elements.recorded_on.value = formatPetDate(
    packageDateKey()
  );

  feedingForm.elements.time_of_day.addEventListener(
    "input",
    event => maskPetInput(event.target, ":", 2, 4)
  );
  weightForm.elements.recorded_on.addEventListener(
    "input",
    event => {
      const digits = event.target.value.replace(/\D/g, "").slice(0, 8);
      const parts = [
        digits.slice(0, 2),
        digits.slice(2, 4),
        digits.slice(4, 8),
      ].filter(Boolean);
      event.target.value = parts.join("/");
    }
  );

  feedingForm.addEventListener("submit", async event => {
    event.preventDefault();
    const submitButton = feedingForm.querySelector("button[type='submit']");
    submitButton.disabled = true;

    try {
      const timeOfDay = normalizePetTime(
        feedingForm.elements.time_of_day.value
      );

      if (!timeOfDay) {
        throw new Error(
          "Bitte die Uhrzeit im 24-Stunden-Format HH:MM eingeben"
        );
      }

      await petRequest("/api/pet/feedings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: feedingForm.elements.label.value,
          time_of_day: timeOfDay,
        }),
      });
      feedingForm.reset();
      await loadPet(true);
    } catch (error) {
      window.alert(error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  weightForm.addEventListener("submit", async event => {
    event.preventDefault();
    const submitButton = weightForm.querySelector("button[type='submit']");
    submitButton.disabled = true;

    try {
      const recordedOn = parsePetDate(
        weightForm.elements.recorded_on.value
      );

      if (!recordedOn) {
        throw new Error(
          "Bitte das Datum im Format TT/MM/JJJJ eingeben"
        );
      }

      await petRequest("/api/pet/weights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          weight_kg: weightForm.elements.weight_kg.value,
          recorded_on: recordedOn,
        }),
      });
      weightForm.elements.weight_kg.value = "";
      await loadPet(true);
    } catch (error) {
      window.alert(error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  shoppingForm.addEventListener("submit", async event => {
    event.preventDefault();
    const submitButton = shoppingForm.querySelector("button[type='submit']");
    submitButton.disabled = true;

    try {
      await petRequest("/api/pet/shopping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: shoppingForm.elements.name.value }),
      });
      shoppingForm.reset();
      await loadPet(true);
    } catch (error) {
      window.alert(error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  qs("#dashboard-pet").addEventListener("change", async event => {
    const feedingId = event.target.dataset.petFeedingToggle;
    const shoppingId = event.target.dataset.petShoppingToggle;

    try {
      if (feedingId) {
        await petRequest(
          `/api/pet/feedings/${feedingId}/completion`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ completed: event.target.checked }),
          }
        );
      } else if (shoppingId) {
        await petRequest(`/api/pet/shopping/${shoppingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ checked: event.target.checked }),
        });
      } else {
        return;
      }

      await loadPet(true);
    } catch (error) {
      event.target.checked = !event.target.checked;
      window.alert(error.message);
    }
  });

  qs("#dashboard-pet").addEventListener("click", async event => {
    const feedingButton = event.target.closest("[data-pet-feeding-delete]");
    const weightButton = event.target.closest("[data-pet-weight-delete]");
    const shoppingButton = event.target.closest("[data-pet-shopping-delete]");
    let url = null;

    if (feedingButton) {
      url = `/api/pet/feedings/${feedingButton.dataset.petFeedingDelete}`;
    } else if (weightButton) {
      url = `/api/pet/weights/${weightButton.dataset.petWeightDelete}`;
    } else if (shoppingButton) {
      url = `/api/pet/shopping/${shoppingButton.dataset.petShoppingDelete}`;
    }

    if (!url) {
      return;
    }

    try {
      await petRequest(url, { method: "DELETE" });
      await loadPet(true);
    } catch (error) {
      window.alert(error.message);
    }
  });
}


// ============================================================
// PUSH NOTIFICATIONS
// ============================================================

function urlBase64ToUint8Array(value) {
  const padding = "=".repeat(
    (4 - value.length % 4) % 4
  );
  const base64 = (
    value
      + padding
  )
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const rawData = window.atob(base64);

  return Uint8Array.from(
    rawData,
    character => character.charCodeAt(0)
  );
}


function setPushButtonState(
  button,
  state,
  label
) {
  button.dataset.state = state;
  button.title = label;
  button.setAttribute(
    "aria-label",
    label
  );
  button.setAttribute(
    "aria-pressed",
    String(state === "active")
  );
  button.disabled = state === "loading";

  const icon = button.querySelector("i");

  if (icon) {
    icon.className = "ti ti-bell";
  }

  const visibleLabel = button.querySelector(
    "[data-push-button-label]"
  );

  if (visibleLabel) {
    visibleLabel.textContent = label;
  }

  const status = button.closest(
    ".settings-option"
  )?.querySelector(
    "[data-push-status]"
  );

  if (status) {
    const statusLabels = {
      active: "Aktiv",
      blocked: "In den Systemeinstellungen blockiert",
      inactive: "Deaktiviert",
      loading: "Wird eingerichtet"
    };

    status.dataset.state = state;
    status.textContent = statusLabels[state] || label;
  }
}


async function setupDesktopNotifications(
  button,
  desktopNotifications
) {
  const supported = await desktopNotifications.isSupported();

  if (!supported) {
    return false;
  }

  const storageKey = "monolith.desktop.notifications.enabled";
  let enabled = window.localStorage.getItem(storageKey) === "true";

  async function showDuePetReminders() {
    if (!enabled) {
      return;
    }

    try {
      const response = await fetch("/api/pet");
      const data = await response.json();

      if (!response.ok || !data.success) {
        return;
      }

      const now = new Date();
      const currentTime = [
        String(now.getHours()).padStart(2, "0"),
        String(now.getMinutes()).padStart(2, "0")
      ].join(":");

      for (const feeding of data.feeding_times || []) {
        if (
          feeding.completed
          || feeding.time_of_day > currentTime
        ) {
          continue;
        }

        const reminderKey = [
          "monolith.desktop.pet",
          data.date,
          feeding.id
        ].join(".");

        if (window.localStorage.getItem(reminderKey) === "shown") {
          continue;
        }

        const shown = await desktopNotifications.show({
          title: "Futterzeit für dein Haustier",
          body: `${feeding.label} ist jetzt dran.`,
          url: "/?tab=pet"
        });

        if (shown) {
          window.localStorage.setItem(reminderKey, "shown");
        }
      }
    } catch (error) {
      console.warn(
        "Desktop-Erinnerungen konnten nicht geprüft werden:",
        error
      );
    }
  }

  button.hidden = false;
  setPushButtonState(
    button,
    enabled ? "active" : "inactive",
    enabled
      ? "Desktop-Mitteilungen deaktivieren"
      : "Desktop-Mitteilungen aktivieren"
  );

  button.addEventListener("click", async () => {
    if (enabled) {
      enabled = false;
      window.localStorage.removeItem(storageKey);
      setPushButtonState(
        button,
        "inactive",
        "Desktop-Mitteilungen aktivieren"
      );
      return;
    }

    setPushButtonState(
      button,
      "loading",
      "Desktop-Mitteilungen werden eingerichtet"
    );

    try {
      const shown = await desktopNotifications.show({
        title: "MONOLITH",
        body: "Desktop-Benachrichtigungen sind aktiviert."
      });

      if (!shown) {
        throw new Error(
          "Desktop-Benachrichtigung konnte nicht angezeigt werden"
        );
      }

      enabled = true;
      window.localStorage.setItem(storageKey, "true");
      setPushButtonState(
        button,
        "active",
        "Desktop-Mitteilungen deaktivieren"
      );
      await showDuePetReminders();
    } catch (error) {
      console.error(
        "Desktop-Mitteilungen konnten nicht aktiviert werden:",
        error
      );
      setPushButtonState(
        button,
        "inactive",
        "Desktop-Mitteilungen aktivieren"
      );
      window.alert(
        error.message
        || "Desktop-Mitteilungen konnten nicht aktiviert werden."
      );
    }
  });

  void showDuePetReminders();
  window.setInterval(
    showDuePetReminders,
    30_000
  );

  return true;
}


async function sendPushSubscription(
  subscription,
  previousEndpoint = null
) {
  const response = await fetch(
    "/api/push/subscribe",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        ...subscription.toJSON(),
        previous_endpoint: previousEndpoint
      })
    }
  );

  if (!response.ok) {
    throw new Error(
      "Push-Abonnement konnte nicht gespeichert werden"
    );
  }
}


async function getPushSubscriptionStatus(subscription) {
  const response = await fetch("/api/push/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint: subscription.endpoint })
  });
  if (!response.ok) {
    return null;
  }
  const data = await response.json();
  return data.subscribed === true;
}


async function createPushSubscription(
  registration,
  previousEndpoint = null
) {
  const keyResponse = await fetch(
    "/api/push/public-key"
  );
  const keyData = await keyResponse.json();

  if (!keyResponse.ok || !keyData.public_key) {
    throw new Error(
      "Push-Schlüssel konnte nicht geladen werden"
    );
  }

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(
      keyData.public_key
    )
  });
  await sendPushSubscription(subscription, previousEndpoint);
  return subscription;
}


async function setupPushNotifications() {
  const button = qs("[data-push-button]");

  if (!button) {
    return;
  }

  const desktopNotifications = window.monolithDesktop?.notifications;

  if (
    desktopNotifications
    && await setupDesktopNotifications(
      button,
      desktopNotifications
    )
  ) {
    return;
  }

  const supported =
    window.isSecureContext
    && "serviceWorker" in navigator
    && "PushManager" in window
    && "Notification" in window;

  if (!supported) {
    return;
  }

  button.hidden = false;

  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();
  let reconciliationRunning = false;
  const pushPreferenceKey = "monolith.webpush.enabled";
  // Preserve existing subscriptions as opt-in, but remember explicit opt-out
  // independently of iOS' notification permission.
  let enabled = window.localStorage.getItem(pushPreferenceKey) === "true"
    || (window.localStorage.getItem(pushPreferenceKey) !== "false"
      && (subscription || Notification.permission === "granted"));

  async function reconcilePushSubscription() {
    if (reconciliationRunning || !enabled || button.dataset.state === "loading") {
      return;
    }

    reconciliationRunning = true;

    try {
      subscription = await registration.pushManager.getSubscription();
      let previousEndpoint = null;
      if (subscription && await getPushSubscriptionStatus(subscription) === false) {
        previousEndpoint = subscription.endpoint;
        await subscription.unsubscribe();
        subscription = null;
      }

      if (
        !subscription
        && Notification.permission === "granted"
      ) {
        subscription = await createPushSubscription(
          registration,
          previousEndpoint
        );
      } else if (subscription) {
        await sendPushSubscription(subscription);
      }

      if (subscription) {
        window.localStorage.setItem(pushPreferenceKey, "true");
        setPushButtonState(
          button,
          "active",
          "Mitteilungen deaktivieren"
        );
      }
    } finally {
      reconciliationRunning = false;
    }
  }

  if (enabled) {
    try {
      await reconcilePushSubscription();
    } catch (error) {
      console.warn("Push-Abgleich wird beim nächsten Öffnen wiederholt:", error);
    }
  }

  if (subscription && enabled) {
    setPushButtonState(
      button,
      "active",
      "Mitteilungen deaktivieren"
    );
  } else if (Notification.permission === "denied") {
    setPushButtonState(
      button,
      "blocked",
      "Mitteilungen sind in den Systemeinstellungen blockiert"
    );
  } else {
    setPushButtonState(
      button,
      "inactive",
      "Mitteilungen aktivieren"
    );
  }

  button.addEventListener(
    "click",
    async () => {
      if (reconciliationRunning) {
        return;
      }
      if (button.dataset.state === "blocked") {
        window.alert(
          "Mitteilungen sind für MONOLITH blockiert. Bitte erlaube sie in den iPhone-Einstellungen."
        );
        return;
      }

      setPushButtonState(
        button,
        "loading",
        "Mitteilungen werden eingerichtet"
      );

      try {
        if (subscription && enabled) {
          const response = await fetch(
            "/api/push/unsubscribe",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({
                endpoint: subscription.endpoint
              })
            }
          );
          if (!response.ok) {
            throw new Error("Mitteilungen konnten nicht deaktiviert werden");
          }
          enabled = false;
          window.localStorage.setItem(pushPreferenceKey, "false");
          await subscription.unsubscribe();
          subscription = null;
          setPushButtonState(
            button,
            "inactive",
            "Mitteilungen aktivieren"
          );
          return;
        }

        const permission = await Notification.requestPermission();

        if (permission !== "granted") {
          throw new Error(
            "Mitteilungen wurden nicht erlaubt"
          );
        }

        subscription = await createPushSubscription(
          registration
        );
        enabled = true;
        window.localStorage.setItem(pushPreferenceKey, "true");
        setPushButtonState(
          button,
          "active",
          "Mitteilungen deaktivieren"
        );

        const testResponse = await fetch(
          "/api/push/test",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              endpoint: subscription.endpoint
            })
          }
        );

        if (testResponse.status === 410) {
          await subscription.unsubscribe();
          subscription = null;
        }

        if (!testResponse.ok) {
          throw new Error(
            "Testbenachrichtigung konnte nicht gesendet werden"
          );
        }
      } catch (error) {
        console.error(
          "Push-Einrichtung fehlgeschlagen:",
          error
        );
        setPushButtonState(
          button,
          subscription ? "active" : "inactive",
          subscription
            ? "Mitteilungen deaktivieren"
            : "Mitteilungen aktivieren"
        );
        window.alert(
          error.message
          || "Mitteilungen konnten nicht eingerichtet werden."
        );
      }
    }
  );

  const syncPush = () => {
    void reconcilePushSubscription().catch(error => {
      console.warn("Push-Abgleich wird beim nächsten Öffnen wiederholt:", error);
    });
  };
  window.addEventListener(
    "online",
    syncPush
  );
  document.addEventListener(
    "visibilitychange",
    () => {
      if (document.visibilityState === "visible") {
        syncPush();
      }
    }
  );
}


// ============================================================
// WEATHER
// ============================================================

const WEATHER_CODES = {
  0: ["Klar", "ti-sun", "ti-moon"],
  1: ["Überwiegend klar", "ti-sun", "ti-moon"],
  2: ["Teilweise bewölkt", "ti-sun-low", "ti-moon-stars"],
  3: ["Bewölkt", "ti-cloud", "ti-cloud"],
  45: ["Nebel", "ti-mist", "ti-mist"],
  48: ["Raureifnebel", "ti-mist", "ti-mist"],
  51: ["Leichter Nieselregen", "ti-cloud-rain", "ti-cloud-rain"],
  53: ["Nieselregen", "ti-cloud-rain", "ti-cloud-rain"],
  55: ["Starker Nieselregen", "ti-cloud-rain", "ti-cloud-rain"],
  56: ["Leichter gefrierender Nieselregen", "ti-snowflake", "ti-snowflake"],
  57: ["Gefrierender Nieselregen", "ti-snowflake", "ti-snowflake"],
  61: ["Leichter Regen", "ti-cloud-rain", "ti-cloud-rain"],
  63: ["Regen", "ti-cloud-rain", "ti-cloud-rain"],
  65: ["Starker Regen", "ti-cloud-rain", "ti-cloud-rain"],
  66: ["Leichter gefrierender Regen", "ti-snowflake", "ti-snowflake"],
  67: ["Gefrierender Regen", "ti-snowflake", "ti-snowflake"],
  71: ["Leichter Schneefall", "ti-snowflake", "ti-snowflake"],
  73: ["Schneefall", "ti-snowflake", "ti-snowflake"],
  75: ["Starker Schneefall", "ti-snowflake", "ti-snowflake"],
  77: ["Schneegriesel", "ti-snowflake", "ti-snowflake"],
  80: ["Leichte Regenschauer", "ti-cloud-rain", "ti-cloud-rain"],
  81: ["Regenschauer", "ti-cloud-rain", "ti-cloud-rain"],
  82: ["Starke Regenschauer", "ti-cloud-rain", "ti-cloud-rain"],
  85: ["Leichte Schneeschauer", "ti-snowflake", "ti-snowflake"],
  86: ["Starke Schneeschauer", "ti-snowflake", "ti-snowflake"],
  95: ["Gewitter", "ti-cloud-storm", "ti-cloud-storm"],
  96: ["Gewitter mit Hagel", "ti-cloud-storm", "ti-cloud-storm"],
  99: ["Starkes Gewitter mit Hagel", "ti-cloud-storm", "ti-cloud-storm"],
};


function getWeatherCondition(code, isDay = 1) {
  const condition = WEATHER_CODES[Number(code)] || [
    "Unbekannt",
    "ti-cloud-question",
    "ti-cloud-question"
  ];
  return {
    label: condition[0],
    icon: isDay ? condition[1] : condition[2],
  };
}


function weatherValue(value, digits = 0, suffix = "") {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  return `${number.toFixed(digits)}${suffix}`;
}


function weatherTime(value) {
  return typeof value === "string" && value.length >= 16
    ? value.slice(11, 16)
    : "-";
}


function weatherDate(value, options = {}) {
  if (!value) {
    return "-";
  }
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleDateString("de-DE", options);
}


function weatherDirection(degrees) {
  const value = Number(degrees);
  if (!Number.isFinite(value)) {
    return "";
  }
  const directions = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"];
  return directions[Math.round(((value % 360) + 360) % 360 / 45) % 8];
}


function setWeatherStatus(message = "") {
  const status = qs("[data-weather-status]");
  if (!status) {
    return;
  }
  status.textContent = message;
  status.hidden = !message;
}


function setWeatherLoading(loading, initial = false) {
  const loader = qs("[data-weather-loading]");
  const empty = qs("[data-weather-empty]");
  const refresh = qs("[data-weather-refresh]");
  weatherIsLoading = loading;
  refresh?.classList.toggle("is-loading", loading);
  if (refresh) {
    refresh.disabled = loading;
  }
  if (loader) {
    loader.hidden = !(loading && initial);
  }
  if (empty && loading && initial) {
    empty.hidden = true;
  }
}


function renderWeatherEmpty() {
  qs("[data-weather-content]")?.setAttribute("hidden", "");
  const empty = qs("[data-weather-empty]");
  if (empty) {
    empty.hidden = false;
  }
  const title = qs("[data-weather-location-title]");
  const meta = qs("[data-weather-location-meta]");
  if (title) {
    title.textContent = "Wetter";
  }
  if (meta) {
    meta.textContent = "Wähle einen Ort für aktuelle Daten und Prognosen.";
  }
  const locationAttribution = qs("[data-weather-location-attribution]");
  if (locationAttribution) {
    locationAttribution.hidden = true;
  }
}


function findNearestWeatherHour(data) {
  const currentTime = data.current?.time || "";
  return data.hourly.find(item => item.time >= currentTime)
    || data.hourly[data.hourly.length - 1]
    || {};
}


function renderWeatherCurrent(data) {
  const current = data.current || {};
  const nearestHour = findNearestWeatherHour(data);
  const condition = getWeatherCondition(current.weather_code, current.is_day);
  const title = qs("[data-weather-location-title]");
  const meta = qs("[data-weather-location-meta]");
  const icon = qs("[data-weather-current-icon]");
  const postalLocality = [data.location.postal_code, data.location.city || data.location.name]
    .filter(Boolean)
    .join(" ");
  const locationMeta = (data.location.postal_code
    ? [postalLocality, data.location.country]
    : [data.location.admin1, data.location.country])
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index)
    .join(", ");

  if (title) {
    title.textContent = data.location.name;
  }
  if (meta) {
    meta.textContent = locationMeta || `${data.location.latitude.toFixed(2)}, ${data.location.longitude.toFixed(2)}`;
  }
  if (icon) {
    icon.className = `ti ${condition.icon}`;
  }

  const values = {
    "[data-weather-description]": condition.label,
    "[data-weather-current-detail]": `Gefühlt ${weatherValue(current.apparent_temperature, 1, " °C")}, Bewölkung ${weatherValue(current.cloud_cover, 0, " %")}`,
    "[data-weather-temperature]": weatherValue(current.temperature, 1, "°"),
    "[data-weather-humidity]": weatherValue(current.relative_humidity, 0, " %"),
    "[data-weather-rain-chance]": weatherValue(current.precipitation_probability ?? nearestHour.precipitation_probability, 0, " %"),
    "[data-weather-wind]": `${weatherDirection(current.wind_direction)} ${weatherValue(current.wind_speed, 0, " km/h")}`.trim(),
    "[data-weather-pressure]": weatherValue(current.pressure_msl ?? current.surface_pressure, 0, " hPa"),
    "[data-weather-visibility]": Number.isFinite(Number(current.visibility))
      ? weatherValue(Number(current.visibility) / 1000, 1, " km")
      : "-",
    "[data-weather-uv]": weatherValue(current.uv_index ?? nearestHour.uv_index, 1),
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = qs(selector);
    if (element) {
      element.textContent = value;
    }
  });
}


function renderWeatherHourly(data) {
  const list = qs("[data-weather-hourly-list]");
  if (!list) {
    return;
  }
  const currentTime = data.current?.time || "";
  const currentHour = currentTime.slice(0, 13);
  const hours = data.hourly
    .filter(item => item.time >= `${currentHour}:00`)
    .slice(0, 24);
  list.innerHTML = hours.map((item, index) => {
    const condition = getWeatherCondition(item.weather_code, item.is_day);
    const now = index === 0;
    return `
      <article class="weather-hour${now ? " is-now" : ""}">
        <time datetime="${escapeHtml(item.time)}">${now ? "Jetzt" : escapeHtml(weatherTime(item.time))}</time>
        <i class="ti ${condition.icon}" aria-hidden="true" title="${escapeHtml(condition.label)}"></i>
        <strong>${escapeHtml(weatherValue(item.temperature, 0, "°"))}</strong>
        <small><i class="ti ti-umbrella" aria-hidden="true"></i>${escapeHtml(weatherValue(item.precipitation_probability, 0, " %"))}</small>
      </article>
    `;
  }).join("");

  const today = data.daily.find(item => item.date === currentTime.slice(0, 10));
  const sunTimes = qs("[data-weather-sun-times]");
  if (sunTimes) {
    sunTimes.innerHTML = today
      ? `
          <span><i class="ti ti-sunrise" aria-hidden="true"></i>${escapeHtml(weatherTime(today.sunrise))}</span>
          <span><i class="ti ti-sunset" aria-hidden="true"></i>${escapeHtml(weatherTime(today.sunset))}</span>
        `
      : "";
  }
}


function renderWeatherDaily(data) {
  const list = qs("[data-weather-daily-list]");
  if (!list) {
    return;
  }
  const today = data.current?.time?.slice(0, 10) || "";
  const days = data.daily.filter(item => item.date >= today).slice(0, 10);
  list.style.setProperty("--weather-day-count", String(Math.max(days.length, 1)));
  list.innerHTML = days.map((item, index) => {
    const condition = getWeatherCondition(item.weather_code, 1);
    const label = index === 0
      ? "Heute"
      : weatherDate(item.date, { weekday: "short", day: "2-digit", month: "2-digit" });
    return `
      <article class="weather-day">
        <time datetime="${escapeHtml(item.date)}">${escapeHtml(label)}</time>
        <div class="weather-day-condition">
          <i class="ti ${condition.icon}" aria-hidden="true"></i>
          <span>${escapeHtml(condition.label)}</span>
        </div>
        <div class="weather-day-temperatures">
          <strong>${escapeHtml(weatherValue(item.temperature_max, 0, "°"))}</strong>
          <span>${escapeHtml(weatherValue(item.temperature_min, 0, "°"))}</span>
        </div>
        <div class="weather-day-meta">
          <span><i class="ti ti-umbrella" aria-hidden="true"></i>${escapeHtml(weatherValue(item.precipitation_probability_max, 0, " %"))}, ${escapeHtml(weatherValue(item.precipitation_sum, 1, " mm"))}</span>
          <span><i class="ti ti-wind" aria-hidden="true"></i>${escapeHtml(weatherValue(item.wind_speed_max, 0, " km/h"))}</span>
          <span><i class="ti ti-sun-high" aria-hidden="true"></i>UV ${escapeHtml(weatherValue(item.uv_index_max, 1))}</span>
        </div>
      </article>
    `;
  }).join("");

  const history = data.daily.filter(item => item.source === "history");
  const summary = qs("[data-weather-history-summary]");
  if (summary && history.length) {
    const lows = history.map(item => Number(item.temperature_min)).filter(Number.isFinite);
    const highs = history.map(item => Number(item.temperature_max)).filter(Number.isFinite);
    const rain = history.reduce((total, item) => total + (Number(item.precipitation_sum) || 0), 0);
    summary.innerHTML = `Letzte ${history.length} Tage: <strong>${escapeHtml(weatherValue(Math.min(...lows), 0, "°"))} bis ${escapeHtml(weatherValue(Math.max(...highs), 0, "°"))}</strong>, <strong>${escapeHtml(weatherValue(rain, 1, " mm"))}</strong> Niederschlag`;
  } else if (summary) {
    summary.textContent = "Der Rückblick wird mit der nächsten Synchronisierung aufgebaut.";
  }
}


function getWeatherChartRows() {
  if (!weatherData) {
    return [];
  }
  if (weatherChartRange === "history") {
    return weatherData.hourly.filter(item => item.source === "history");
  }
  const current = new Date(weatherData.current?.time || Date.now());
  const beforeHours = weatherChartRange === "48" ? 12 : 24;
  const afterHours = weatherChartRange === "48" ? 36 : 144;
  const start = current.getTime() - beforeHours * 3600000;
  const end = current.getTime() + afterHours * 3600000;
  return weatherData.hourly.filter(item => {
    const timestamp = new Date(item.time).getTime();
    return Number.isFinite(timestamp) && timestamp >= start && timestamp <= end;
  });
}


function weatherChartOptions(unit, yOptions = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 220 },
    interaction: { intersect: false, mode: "index" },
    plugins: {
      legend: {
        display: true,
        position: "bottom",
        labels: { color: getComputedStyle(document.body).getPropertyValue("--text-muted").trim(), boxWidth: 10, boxHeight: 2, padding: 12, font: { size: 11, weight: 450 } },
      },
      tooltip: {
        backgroundColor: "#171719",
        borderColor: "#2f2f35",
        borderWidth: 1,
        titleColor: "#f5f5f5",
        bodyColor: "#c9c9cf",
        callbacks: {
          label(context) {
            const datasetUnit = context.dataset.unit ?? unit;
            return `${context.dataset.label}: ${context.parsed.y ?? "-"} ${datasetUnit}`.trim();
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { color: getComputedStyle(document.body).getPropertyValue("--text-muted").trim(), maxTicksLimit: 7, maxRotation: 0, minRotation: 0 },
        grid: { color: "rgba(255, 255, 255, 0.045)" },
      },
      y: {
        ...yOptions,
        ticks: { color: getComputedStyle(document.body).getPropertyValue("--text-muted").trim(), callback: value => `${value}${unit}` },
        grid: { color: "rgba(255, 255, 255, 0.045)" },
      },
    },
  };
}


function ensureWeatherCharts() {
  if (typeof Chart === "undefined") {
    return;
  }
  const temperatureCanvas = qs("#weather-temperature-chart");
  const precipitationCanvas = qs("#weather-precipitation-chart");
  if (!weatherTemperatureChart && temperatureCanvas) {
    weatherTemperatureChart = new Chart(temperatureCanvas.getContext("2d"), {
      type: "line",
      data: { labels: [], datasets: [
        { label: "Temperatur", data: [], unit: "°C", borderColor: "#76e69a", backgroundColor: "rgba(66, 214, 116, 0.09)", borderWidth: 2, pointRadius: 0, tension: 0.28, fill: true, spanGaps: true },
        { label: "Gefühlt", data: [], unit: "°C", borderColor: "#888890", borderWidth: 1, borderDash: [4, 4], pointRadius: 0, tension: 0.28, fill: false, spanGaps: true },
      ] },
      options: weatherChartOptions("°"),
    });
  }
  if (!weatherPrecipitationChart && precipitationCanvas) {
    const options = weatherChartOptions(" %", { min: 0, max: 100 });
    options.scales.y1 = {
      position: "right",
      beginAtZero: true,
      ticks: { color: getComputedStyle(document.body).getPropertyValue("--text-muted").trim(), callback: value => `${value} mm` },
      grid: { drawOnChartArea: false },
    };
    weatherPrecipitationChart = new Chart(precipitationCanvas.getContext("2d"), {
      data: { labels: [], datasets: [
        { type: "bar", label: "Wahrscheinlichkeit", data: [], unit: "%", yAxisID: "y", backgroundColor: "rgba(66, 214, 116, 0.28)", borderColor: "rgba(118, 230, 154, 0.55)", borderWidth: 1, borderRadius: 2, barPercentage: 0.78, categoryPercentage: 0.9 },
        { type: "line", label: "Menge", data: [], unit: "mm", yAxisID: "y1", borderColor: "#d0d0d6", borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: false, spanGaps: true },
      ] },
      options,
    });
  }
}


function updateWeatherCharts() {
  ensureWeatherCharts();
  const rows = getWeatherChartRows();
  const labels = rows.map(item => {
    const includeDate = weatherChartRange !== "48";
    return includeDate
      ? `${weatherDate(item.time, { day: "2-digit", month: "2-digit" })} ${weatherTime(item.time)}`
      : weatherTime(item.time);
  });
  if (weatherTemperatureChart) {
    weatherTemperatureChart.data.labels = labels;
    weatherTemperatureChart.data.datasets[0].data = rows.map(item => item.temperature);
    weatherTemperatureChart.data.datasets[1].data = rows.map(item => item.apparent_temperature);
    weatherTemperatureChart.update();
  }
  if (weatherPrecipitationChart) {
    weatherPrecipitationChart.data.labels = labels;
    weatherPrecipitationChart.data.datasets[0].data = rows.map(item => item.precipitation_probability);
    weatherPrecipitationChart.data.datasets[1].data = rows.map(item => item.precipitation);
    weatherPrecipitationChart.update();
  }
}


function renderWeather(data) {
  weatherData = data;
  weatherHasLoaded = true;
  const content = qs("[data-weather-content]");
  const empty = qs("[data-weather-empty]");
  if (content) {
    content.hidden = false;
  }
  if (empty) {
    empty.hidden = true;
  }
  const locationAttribution = qs("[data-weather-location-attribution]");
  if (locationAttribution) {
    locationAttribution.hidden = data.location.geocoding_provider !== "nominatim";
  }
  renderWeatherCurrent(data);
  renderWeatherHourly(data);
  renderWeatherDaily(data);
  const updated = qs("[data-weather-updated]");
  if (updated) {
    const timestamp = Number(data.updated_at) * 1000;
    updated.textContent = Number.isFinite(timestamp)
      ? `Zuletzt aktualisiert: ${new Date(timestamp).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}${data.stale ? " (gespeichert)" : ""}`
      : "Zuletzt aktualisiert: -";
  }
  setWeatherStatus(data.warning || "");
  requestAnimationFrame(() => {
    updateWeatherCharts();
    weatherTemperatureChart?.resize();
    weatherPrecipitationChart?.resize();
  });
}


async function loadWeather(force = false) {
  if (weatherIsLoading) {
    return;
  }
  setWeatherLoading(true, !weatherHasLoaded);
  if (!weatherHasLoaded) {
    setWeatherStatus("");
  }
  try {
    const response = await fetch(`/api/weather${force ? "?refresh=1" : ""}`);
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "Wetterdaten konnten nicht geladen werden.");
    }
    if (!data.configured) {
      weatherHasLoaded = false;
      weatherData = null;
      renderWeatherEmpty();
      return;
    }
    renderWeather(data);
  } catch (error) {
    setWeatherStatus(error.message || "Wetterdaten konnten nicht geladen werden.");
    if (!weatherData) {
      renderWeatherEmpty();
    }
  } finally {
    setWeatherLoading(false);
  }
}


function renderWeatherSearchResults(locations, message = "") {
  const results = qs("[data-weather-search-results]");
  const input = qs("[data-weather-search-input]");
  if (!results || !input) {
    return;
  }
  weatherSearchLocations = locations;
  if (message) {
    results.innerHTML = `<div class="weather-search-message">${escapeHtml(message)}</div>`;
  } else {
    const options = locations.map((location, index) => {
      const meta = (location.postal_code
        ? [location.city, location.country]
        : [location.admin1, location.country])
        .filter(Boolean)
        .filter((value, metaIndex, values) => values.indexOf(value) === metaIndex)
        .join(", ");
      const title = [location.postal_code, location.name].filter(Boolean).join(" ");
      return `
        <button class="weather-location-result" type="button" role="option" data-weather-location-index="${index}" aria-selected="false">
          <span><strong>${escapeHtml(title)}</strong><span>${escapeHtml(meta)}</span></span>
          <small>${location.postal_code ? "PLZ" : escapeHtml(location.country_code)}</small>
        </button>
      `;
    }).join("");
    const attribution = locations.some(location => location.geocoding_provider === "nominatim")
      ? `<div class="weather-search-attribution">PLZ-Suche mit <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a></div>`
      : "";
    results.innerHTML = `${options}${attribution}`;
  }
  results.hidden = false;
  input.setAttribute("aria-expanded", "true");
}


function closeWeatherSearchResults() {
  const results = qs("[data-weather-search-results]");
  const input = qs("[data-weather-search-input]");
  if (results) {
    results.hidden = true;
  }
  input?.setAttribute("aria-expanded", "false");
}


async function searchWeatherLocations() {
  const input = qs("[data-weather-search-input]");
  const query = input?.value.trim() || "";
  const isNumericQuery = /^\d+$/.test(query);
  if (query.length < 2) {
    closeWeatherSearchResults();
    return;
  }
  if (isNumericQuery && query.length < 5) {
    renderWeatherSearchResults([], "Bitte gib die vollständige fünfstellige PLZ ein.");
    return;
  }
  if (isNumericQuery && query.length > 5) {
    renderWeatherSearchResults([], "Eine deutsche PLZ besteht aus fünf Ziffern.");
    return;
  }
  renderWeatherSearchResults([], "Orte werden gesucht...");
  try {
    const response = await fetch(`/api/weather/locations?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "Ortssuche nicht verfügbar.");
    }
    renderWeatherSearchResults(
      data.locations || [],
      data.locations?.length ? "" : "Kein passender Ort gefunden."
    );
  } catch (error) {
    renderWeatherSearchResults([], error.message || "Ortssuche nicht verfügbar.");
  }
}


async function selectWeatherLocation(location) {
  closeWeatherSearchResults();
  setWeatherLoading(true, !weatherHasLoaded);
  setWeatherStatus("");
  try {
    const response = await fetch("/api/weather/location", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(location),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || "Der Ort konnte nicht gespeichert werden.");
    }
    const input = qs("[data-weather-search-input]");
    if (input) {
      input.value = "";
    }
    renderWeather(data);
  } catch (error) {
    setWeatherStatus(error.message || "Der Ort konnte nicht gespeichert werden.");
    if (!weatherData) {
      renderWeatherEmpty();
    }
  } finally {
    setWeatherLoading(false);
  }
}


function setupWeather() {
  const form = qs("[data-weather-search-form]");
  const input = qs("[data-weather-search-input]");
  const results = qs("[data-weather-search-results]");
  form?.addEventListener("submit", event => {
    event.preventDefault();
    void searchWeatherLocations();
  });
  input?.addEventListener("input", () => {
    clearTimeout(weatherSearchTimer);
    weatherSearchTimer = setTimeout(() => void searchWeatherLocations(), 320);
  });
  input?.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      closeWeatherSearchResults();
      return;
    }
    if (!results || results.hidden || !["ArrowDown", "ArrowUp"].includes(event.key)) {
      return;
    }
    const options = Array.from(results.querySelectorAll("[role='option']"));
    if (!options.length) {
      return;
    }
    event.preventDefault();
    const target = event.key === "ArrowDown" ? options[0] : options[options.length - 1];
    target.focus();
    target.setAttribute("aria-selected", "true");
  });
  results?.addEventListener("click", event => {
    const button = event.target.closest("[data-weather-location-index]");
    if (!button) {
      return;
    }
    const location = weatherSearchLocations[Number(button.dataset.weatherLocationIndex)];
    if (location) {
      void selectWeatherLocation(location);
    }
  });
  results?.addEventListener("keydown", event => {
    const options = Array.from(results.querySelectorAll("[role='option']"));
    const current = event.target.closest("[role='option']");
    const index = options.indexOf(current);
    if (event.key === "Enter" && current) {
      event.preventDefault();
      current.click();
      return;
    }
    if (!["ArrowDown", "ArrowUp"].includes(event.key) || index < 0) {
      return;
    }
    event.preventDefault();
    options.forEach(option => option.setAttribute("aria-selected", "false"));
    const nextIndex = event.key === "ArrowDown"
      ? (index + 1) % options.length
      : (index - 1 + options.length) % options.length;
    options[nextIndex].setAttribute("aria-selected", "true");
    options[nextIndex].focus();
  });
  document.addEventListener("click", event => {
    if (!form?.contains(event.target)) {
      closeWeatherSearchResults();
    }
  });
  qs("[data-weather-focus-search]")?.addEventListener("click", () => input?.focus());
  qs("[data-weather-refresh]")?.addEventListener("click", () => void loadWeather(true));
  qsa("[data-weather-range]").forEach(button => {
    button.addEventListener("click", () => {
      weatherChartRange = button.dataset.weatherRange;
      qsa("[data-weather-range]").forEach(item => item.classList.toggle("active", item === button));
      updateWeatherCharts();
    });
  });
}


// ============================================================
// INIT
// ============================================================

document.addEventListener(
  "DOMContentLoaded",
  () => {

    if (
      "serviceWorker"
      in navigator
    ) {
      navigator.serviceWorker
        .register(
          "/service-worker.js"
        )
        .catch(
          error => {
            console.warn(
              "Service Worker konnte nicht registriert werden:",
              error
            );
          }
        );
    }

    setupHeaderClock();

    setupPushNotifications().catch(
      error => {
        console.warn(
          "Push-Status konnte nicht geladen werden:",
          error
        );
      }
    );

    setupDashboardTabs();

    setupCamera();

    setupPlanner();

    setupMealPlan();

    setupPackages();

    setupFinances();

    setupPet();

    setupServices();

    setupServerStatus();

    setupNetworkStatus();

    setupPicnic();

    setupWeather();

    setupClimateRoomSelection();

    setupHistoryControls();

    setupFeedInfiniteScroll();

    updateDevices();

    updateSensors();

    updateFeed();

    setInterval(
      updateDevices,
      1000
    );


    setInterval(
      updateFeed,
      1000
    );


    setInterval(
      updateSensors,
      10000
    );


    setInterval(
      () => {
        const layout = qs(
          ".main-layout"
        );


        if (
          layout?.dataset.activeDashboardTab
          === "shopping"
        ) {
          loadPicnic();
        }
      },
      300000
    );


    document.addEventListener("visibilitychange", () => {
      const layout = qs(".main-layout");

      if (
        document.visibilityState !== "visible"
      ) {
        stopCameraLive();
      }

      if (
        document.visibilityState === "visible"
        && layout?.dataset.activeDashboardTab === "packages"
      ) {
        loadPackages(true);
      }

      if (
        document.visibilityState === "visible"
        && layout?.dataset.activeDashboardTab === "services"
      ) {
        loadServices(true);
        loadServiceLogs(
          !serviceLogsInitialized
        );
      }

      if (
        document.visibilityState === "visible"
        && layout?.dataset.activeDashboardTab === "server"
      ) {
        loadServerStatus(true);
      }

      if (
        document.visibilityState === "visible"
        && layout?.dataset.activeDashboardTab === "network"
      ) {
        loadNetworkStatus(true);
      }

      if (
        document.visibilityState === "visible"
        && layout?.dataset.activeDashboardTab === "weather"
      ) {
        loadWeather();
      }

      if (
        document.visibilityState === "visible"
        && layout?.dataset.activeDashboardTab === "cameras"
      ) {
        startCameraLive();
        loadCameraEvents();
      }
    });


    setInterval(
      () => {
        const layout = qs(".main-layout");

        if (
          layout?.dataset.activeDashboardTab
          === "packages"
        ) {
          loadPackages(true);
        }
      },
      60000
    );


    setInterval(
      () => {
        const layout = qs(
          ".main-layout"
        );

        if (
          layout?.dataset.activeDashboardTab
          === "services"
        ) {
          loadServices(true);
        }
      },
      30000
    );


    setInterval(
      () => {
        const layout = qs(".main-layout");

        if (
          document.visibilityState === "visible"
          && layout?.dataset.activeDashboardTab === "server"
        ) {
          loadServerStatus(true);
        }
      },
      15000
    );


    setInterval(
      () => {
        const layout = qs(".main-layout");

        if (
          document.visibilityState === "visible"
          && layout?.dataset.activeDashboardTab === "network"
        ) {
          loadNetworkStatus(true);
        }
      },
      15000
    );


    setInterval(
      () => {
        const layout = qs(
          ".main-layout"
        );

        if (
          document.visibilityState === "visible"
          && layout?.dataset.activeDashboardTab
          === "services"
        ) {
          loadServiceLogs();
        }
      },
      2000
    );


    setInterval(
      () => {
        const layout = qs(
          ".main-layout"
        );

        if (
          layout?.dataset.activeDashboardTab
          === "planner"
        ) {
          loadPlanner();
        }
      },
      300000
    );


    setInterval(
      () => {
        const layout = qs(".main-layout");

        if (
          document.visibilityState === "visible"
          && layout?.dataset.activeDashboardTab === "weather"
        ) {
          loadWeather();
        }
      },
      600000
    );


    setInterval(
      () => {
        const layout = qs(".main-layout");

        if (
          document.visibilityState === "visible"
          && layout?.dataset.activeDashboardTab === "cameras"
        ) {
          loadCameraEvents();
        }
      },
      30000
    );


    setInterval(
      () => {

        if (
          isHistoryTabActive()
        ) {
          loadHistory();
        }

      },
      60000
    );
  }
);
