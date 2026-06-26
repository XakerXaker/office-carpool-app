const API = window.location.origin;
const TOKEN_KEY = "carpool_token";

const state = {
  token: null,
  user: null,
  config: null,
  offices: [],
  trips: [],
  map: null,
  officePlacemarks: [],
  originPlacemark: null,
  pickupPlacemark: null,
  routeObject: null,
  mode: null,
  activeTripId: null,
  joinTrip: null,
};

async function api(path, { method, body, form, auth = true } = {}) {
  const headers = {};
  if (auth && state.token) headers["Authorization"] = `Bearer ${state.token}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(form);
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  const httpMethod = method || (payload ? "POST" : "GET");
  const resp = await fetch(API + path, { method: httpMethod, headers, body: payload });
  const data = resp.status === 204 ? null : await resp.json().catch(() => null);
  if (!resp.ok) {
    const err = new Error("API error");
    err.status = resp.status;
    err.data = data;
    throw err;
  }
  return data;
}

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function toast(msg, kind = "") {
  const t = $("#toast");
  if (Array.isArray(msg)) {
    msg = msg.map((e) => e.msg || JSON.stringify(e)).join("; ");
  } else if (msg && typeof msg === "object") {
    msg = msg.msg || msg.detail || JSON.stringify(msg);
  }
  t.textContent = msg;
  t.className = "toast " + kind;
  t.classList.remove("hidden");
  setTimeout(() => t.classList.add("hidden"), 3500);
}

function setupAuthUI() {
  $$(".tab").forEach((tab) =>
    tab.addEventListener("click", () => {
      $$(".tab").forEach((t) => t.classList.remove("is-active"));
      tab.classList.add("is-active");
      const isLogin = tab.dataset.tab === "login";
      $("#login-form").classList.toggle("hidden", !isLogin);
      $("#register-form").classList.toggle("hidden", isLogin);
    })
  );

  $$(".chip[data-demo]").forEach((chip) =>
    chip.addEventListener("click", () => {
      $("#login-form [name=email]").value = chip.dataset.demo;
      $("#login-form [name=password]").value = "password123";
    })
  );

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        auth: false,
        form: { username: f.email.value, password: f.password.value },
      });
      onAuthSuccess(data);
    } catch (err) {
      $("#auth-error").textContent = err.data?.detail || "Не удалось войти";
    }
  });

  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    try {
      const data = await api("/api/auth/register", {
        method: "POST",
        auth: false,
        body: {
          full_name: f.full_name.value,
          email: f.email.value,
          password: f.password.value,
          company_id: Number(f.company_id.value),
          home_city: f.home_city.value || null,
        },
      });
      onAuthSuccess(data);
    } catch (err) {
      $("#auth-error").textContent = err.data?.detail || "Ошибка регистрации";
    }
  });

  $("#logout-btn").addEventListener("click", logout);
}

function onAuthSuccess(data) {
  state.token = data.access_token;
  state.user = data.user;
  localStorage.setItem(TOKEN_KEY, state.token);
  enterApp();
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  location.reload();
}

async function enterApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app-screen").classList.remove("hidden");
  $("#user-name").textContent = state.user.full_name;

  await loadConfig();
  await loadOffices();
  await initMap();
  await loadTrips();
  setupAppUI();
}

function setupAppUI() {
  $$(".seg-btn").forEach((b) =>
    b.addEventListener("click", () => {
      $$(".seg-btn").forEach((x) => x.classList.remove("is-active"));
      b.classList.add("is-active");
      const view = b.dataset.view;
      $("#view-trips").classList.toggle("hidden", view !== "trips");
      $("#view-create").classList.toggle("hidden", view !== "create");
      setMode(view === "create" ? "create" : null);
    })
  );

  $("#filter-office").addEventListener("change", loadTrips);
  $("#create-form").addEventListener("submit", onCreateTrip);

  $("#join-close").addEventListener("click", closeJoinModal);
  $("#join-confirm").addEventListener("click", confirmJoin);
}

async function loadConfig() {
  state.config = await api("/api/config", { auth: false });
}

function showMapFallback(text) {
  $("#map-fallback").classList.remove("hidden");
  $("#map-fallback-text").textContent = text;
}

function loadYandexScript(apiKey) {
  return new Promise((resolve, reject) => {
    if (window.ymaps) return resolve();
    const s = document.createElement("script");
    const keyPart = apiKey ? `apikey=${apiKey}&` : "";
    s.src = `https://api-maps.yandex.ru/2.1/?${keyPart}lang=ru_RU`;
    s.onload = resolve;
    s.onerror = () => reject(new Error("script load failed"));
    document.head.appendChild(s);
  });
}

async function initMap() {
  if (!state.config.yandex_js_api_key) {
    showMapFallback(
      "Не задан ключ Yandex JS API. Укажите YANDEX_JS_API_KEY в окружении сервера " +
      "Логика приложения работает и без карты."
    );
  }
  try {
    await loadYandexScript(state.config.yandex_js_api_key);
    await new Promise((res) => ymaps.ready(res));
  } catch {
    showMapFallback("Не удалось загрузить Yandex Maps. Проверьте интернет и ключ API.");
    return;
  }

  const center = state.offices[0]
    ? [state.offices[0].lat, state.offices[0].lng]
    : [55.751244, 37.618423];

  state.map = new ymaps.Map("map", { center, zoom: 11, controls: ["zoomControl"] });

  state.map.events.add("click", (e) => {
    const coords = e.get("coords");
    if (state.mode === "create") setOriginPoint(coords);
    else if (state.mode === "pickup") setPickupPoint(coords);
  });

  renderOfficePlacemarks();
}

function renderOfficePlacemarks() {
  if (!state.map) return;
  state.officePlacemarks.forEach((p) => state.map.geoObjects.remove(p));
  state.officePlacemarks = [];
  state.offices.forEach((o) => {
    const pm = new ymaps.Placemark(
      [o.lat, o.lng],
      { balloonContentHeader: o.name, balloonContentBody: o.address, hintContent: o.name },
      { preset: "islands#blueHomeCircleIcon" }
    );
    state.officePlacemarks.push(pm);
    state.map.geoObjects.add(pm);
  });
}

function setMode(mode) {
  state.mode = mode;
  const banner = $("#mode-banner");
  if (mode === "create") {
    banner.textContent = "Кликните по карте — точка старта";
    banner.classList.remove("hidden");
  } else if (mode === "pickup") {
    banner.textContent = "Кликните по карте — точка посадки";
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }
}

function setOriginPoint(coords) {
  if (state.originPlacemark) state.map.geoObjects.remove(state.originPlacemark);
  state.originPlacemark = new ymaps.Placemark(
    coords, { hintContent: "Точка старта" },
    { preset: "islands#nightDotIcon", draggable: true }
  );
  state.map.geoObjects.add(state.originPlacemark);
  $("#origin-coords").textContent = `координаты: ${coords[0].toFixed(5)}, ${coords[1].toFixed(5)}`;
  $("#create-form").dataset.lat = coords[0];
  $("#create-form").dataset.lng = coords[1];

  const coordText = `${coords[0].toFixed(5)}, ${coords[1].toFixed(5)}`;
  reverseGeocode(coords).then((info) => {
    $("#origin-address").value = (info && info.address) || `Точка на карте (${coordText})`;
    $("#origin-city").value = (info && info.city) || "Не определён";
  });
}

function setPickupPoint(coords) {
  if (state.pickupPlacemark) state.map.geoObjects.remove(state.pickupPlacemark);
  state.pickupPlacemark = new ymaps.Placemark(
    coords, { hintContent: "Точка посадки" },
    { preset: "islands#redDotIcon", draggable: true }
  );
  state.map.geoObjects.add(state.pickupPlacemark);
  $("#pickup-address").dataset.lat = coords[0];
  $("#pickup-address").dataset.lng = coords[1];
  const pickupCoordText = `${coords[0].toFixed(5)}, ${coords[1].toFixed(5)}`;
  reverseGeocode(coords).then((info) => {
    $("#pickup-address").value = (info && info.address) || `Точка на карте (${pickupCoordText})`;
    $("#pickup-city").value = (info && info.city) || "Не определён";
    runConstraintCheck();
  });
}

async function reverseGeocode(coords) {
  if (!window.ymaps) return null;
  try {
    const res = await ymaps.geocode(coords);
    const first = res.geoObjects.get(0);
    if (!first) return null;
    const address = first.getAddressLine();

    let city = "";

    if (typeof first.getLocalities === "function") {
      const loc = first.getLocalities();
      if (loc && loc.length) city = loc[0];
    }
    if (!city) {
      const comps =
        first.properties.get("metaDataProperty.GeocoderMetaData.Address.Components") || [];
      const byKind = (k) => {
        const c = comps.find((x) => x.kind === k);
        return c ? c.name : "";
      };
      city = byKind("locality") || byKind("area") || byKind("province");
    }
    if (!city && typeof first.getAdministrativeAreas === "function") {
      const areas = first.getAdministrativeAreas();
      if (areas && areas.length) city = areas[0];
    }

    return { address, city };
  } catch {
    return null;
  }
}

function drawRoute(trip) {
  if (!state.map || !window.ymaps) return;
  if (state.routeObject) state.map.geoObjects.remove(state.routeObject);
  const office = state.offices.find((o) => o.id === trip.office_id);
  if (!office) return;
  state.routeObject = new ymaps.multiRouter.MultiRoute(
    {
      referencePoints: [[trip.origin_lat, trip.origin_lng], [office.lat, office.lng]],
      params: { routingMode: "auto" },
    },
    { boundsAutoApply: true, routeActiveStrokeColor: "F2A900", routeActiveStrokeWidth: 5 }
  );
  state.map.geoObjects.add(state.routeObject);
}

async function loadOffices() {
  state.offices = await api("/api/offices");
  const optionsHtml = state.offices
    .map((o) => `<option value="${o.id}">${o.name} (${o.city})</option>`)
    .join("");
  $("#create-office").innerHTML = optionsHtml;
  $("#filter-office").innerHTML =
    `<option value="">Все офисы</option>` + optionsHtml;
}

async function loadTrips() {
  const officeId = $("#filter-office").value;
  const q = officeId ? `?office_id=${officeId}` : "";
  state.trips = await api("/api/trips" + q);
  renderTrips();
}

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function renderTrips() {
  const list = $("#trips-list");
  if (!state.trips.length) {
    list.innerHTML = `<div class="empty">Открытых поездок пока нет.<br/>Создайте первую во вкладке «Создать поездку».</div>`;
    return;
  }
  list.innerHTML = state.trips
    .map((t) => {
      const seatsClass = t.seats_left > 0 ? "seats" : "seats none";
      const isMine = t.driver_id === state.user.id;
      const joinBtn = isMine
        ? `<button class="btn btn-danger btn-sm" data-cancel="${t.id}">Отменить</button>`
        : `<button class="btn btn-primary btn-sm" data-join="${t.id}">Присоединиться</button>`;
      return `
        <article class="trip-card ${state.activeTripId === t.id ? "is-active" : ""}" data-trip="${t.id}">
          <div class="trip-route">
            <span class="dot"></span>
            <span>${t.origin_address}</span>
            <span class="arrow">→</span>
            <span class="trip-office">${t.office_name}</span>
          </div>
          <div class="trip-meta">
            <span class="data-chip">🕘 ${fmtTime(t.departure_time)}</span>
            ${t.est_duration_min != null ? `<span class="data-chip">~${t.est_duration_min} мин</span>` : ""}
            ${t.est_distance_km != null ? `<span class="data-chip">${t.est_distance_km} км</span>` : ""}
            <span class="data-chip ${seatsClass}">мест: ${t.seats_left}/${t.total_seats}</span>
          </div>
          <div class="trip-driver">Водитель: ${t.driver_name}${isMine ? " (вы)" : ""}</div>
          <div class="card-actions">${joinBtn}</div>
        </article>`;
    })
    .join("");

  $$(".trip-card").forEach((card) =>
    card.addEventListener("click", () => selectTrip(Number(card.dataset.trip)))
  );
  $$("[data-join]").forEach((b) =>
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      openJoinModal(Number(b.dataset.join));
    })
  );
  $$("[data-cancel]").forEach((b) =>
    b.addEventListener("click", async (e) => {
      e.stopPropagation();
      await api(`/api/trips/${b.dataset.cancel}/cancel`, { method: "POST" });
      toast("Поездка отменена");
      loadTrips();
    })
  );
}

function selectTrip(tripId) {
  state.activeTripId = tripId;
  const trip = state.trips.find((t) => t.id === tripId);
  if (trip) drawRoute(trip);
  renderTrips();
}

async function onCreateTrip(e) {
  e.preventDefault();
  const f = e.target;
  if (!f.dataset.lat) {
    toast("Сначала укажите точку старта на карте", "bad");
    return;
  }
  try {
    const trip = await api("/api/trips", {
      method: "POST",
      body: {
        office_id: Number(f.office_id.value),
        origin_address: f.origin_address.value,
        origin_city: f.origin_city.value,
        origin_lat: Number(f.dataset.lat),
        origin_lng: Number(f.dataset.lng),
        departure_time: new Date(f.departure_time.value).toISOString(),
        total_seats: Number(f.total_seats.value),
      },
    });
    toast("Поездка опубликована", "good");
    f.reset();
    delete f.dataset.lat;
    $("#origin-coords").textContent = "координаты: —";
    if (state.originPlacemark) { state.map.geoObjects.remove(state.originPlacemark); state.originPlacemark = null; }
    document.querySelector('.seg-btn[data-view="trips"]').click();
    await loadTrips();
    selectTrip(trip.id);
  } catch (err) {
    toast(err.data?.detail || "Не удалось создать поездку", "bad");
  }
}

function openJoinModal(tripId) {
  const trip = state.trips.find((t) => t.id === tripId);
  if (!trip) return;
  state.joinTrip = trip;
  drawRoute(trip);
  $("#join-trip-summary").innerHTML = `
    <strong>${trip.origin_address} → ${trip.office_name}</strong><br/>
    Отправление: ${fmtTime(trip.departure_time)} · мест: ${trip.seats_left}/${trip.total_seats}`;
  $("#pickup-address").value = "";
  $("#pickup-city").value = "";
  delete $("#pickup-address").dataset.lat;
  $("#check-result").classList.add("hidden");
  $("#join-confirm").disabled = true;
  $("#join-modal").classList.remove("hidden");
  setMode("pickup");
}

function closeJoinModal() {
  $("#join-modal").classList.add("hidden");
  state.joinTrip = null;
  if (state.pickupPlacemark) { state.map?.geoObjects.remove(state.pickupPlacemark); state.pickupPlacemark = null; }
  setMode(null);
}

async function runConstraintCheck() {
  const addr = $("#pickup-address");
  if (!addr.dataset.lat || !state.joinTrip) return;
  let res;
  try {
    res = await api(`/api/trips/${state.joinTrip.id}/check`, {
      method: "POST",
      body: {
        pickup_address: addr.value,
        pickup_city: $("#pickup-city").value,
        pickup_lat: Number(addr.dataset.lat),
        pickup_lng: Number(addr.dataset.lng),
      },
    });
  } catch {
    return;
  }
  const box = $("#check-result");
  box.classList.remove("hidden");
  if (res.allowed) {
    box.className = "check-result ok";
    box.innerHTML = `<h4>✓ Вы можете присоединиться</h4>
      <div>Расстояние до точки старта: <span class="dist">${res.distance_to_origin_km} км</span></div>`;
    $("#join-confirm").disabled = false;
  } else {
    box.className = "check-result bad";
    box.innerHTML = `<h4>✕ Присоединение невозможно</h4>
      <ul>${res.violations.map((v) => `<li>${v}</li>`).join("")}</ul>`;
    $("#join-confirm").disabled = true;
  }
}

async function confirmJoin() {
  const addr = $("#pickup-address");
  try {
    await api(`/api/trips/${state.joinTrip.id}/join`, {
      method: "POST",
      body: {
        pickup_address: addr.value,
        pickup_city: $("#pickup-city").value,
        pickup_lat: Number(addr.dataset.lat),
        pickup_lng: Number(addr.dataset.lng),
      },
    });
    toast("Вы присоединились к поездке", "good");
    closeJoinModal();
    await loadTrips();
  } catch (err) {
    const v = err.data?.detail?.violations;
    toast(v ? v[0] : "Не удалось присоединиться", "bad");
  }
}

async function bootstrap() {
  setupAuthUI();
  try {
    const companies = await api("/api/companies", { auth: false });
    $("#company-select").innerHTML = companies
      .map((c) => `<option value="${c.id}">${c.name}</option>`)
      .join("");
  } catch {}

  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) {
    state.token = saved;
    try {
      state.user = await api("/api/auth/me");
      await enterApp();
      return;
    } catch {
      localStorage.removeItem(TOKEN_KEY);
    }
  }
}

bootstrap();