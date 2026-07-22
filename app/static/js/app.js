/* Agenda Facturas Perú — SPA PWA + Web */
(() => {
  const state = {
    route: "dashboard",
    user: null,
    meta: null,
    docs: [],
    agendas: [],
    notifs: [],
    clientes: [],
    productos: [],
    cajas: [],
    movimientosCaja: [],
    cajaDash: null,
    contactos: [],
    combustibles: [],
    combustibleResumen: null,
    filtersCaja: { caja_id: "", tipo: "", q: "", fecha_desde: "", fecha_hasta: "" },
    filtersContacto: { q: "" },
    filtersCombustible: { tipo: "", q: "", fecha_desde: "", fecha_hasta: "" },
    draftFromContact: null,
    charts: { estado: null, tipo: null, mes: null, cajaDia: null, cajaPie: null, combDia: null, combPlaca: null, combConductor: null, combMarca: null },
    editingDoc: null,
    editingAgenda: null,
    editingCliente: null,
    editingProducto: null,
    filters: { q: "", estado: "", tipo: "", zona: "", fecha_desde: "", fecha_hasta: "" },
  };

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const money = (n) =>
    `S/ ${Number(n || 0).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const tipoLabel = (v) => state.meta?.tipos_documento.find((t) => t.value === v)?.label || v;
  const estadoLabel = (v) => state.meta?.estados.find((t) => t.value === v)?.label || v;
  const agendaLabel = (v) => state.meta?.tipos_agenda.find((t) => t.value === v)?.label || v;
  const movCajaLabel = (v) =>
    state.meta?.tipos_movimiento_caja?.find((t) => t.value === v)?.label || v;
  const movCombustibleLabel = (v) =>
    state.meta?.tipos_movimiento_combustible?.find((t) => t.value === v)?.label || v;
  const galones = (n) =>
    `${Number(n || 0).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 3 })} gal`;

  function toast(msg) {
    let wrap = $(".toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  function parseHash() {
    const hash = location.hash.replace(/^#\/?/, "");
    const [route, query = ""] = hash.split("?");
    const params = Object.fromEntries(new URLSearchParams(query));
    if (params.estado) state.filters.estado = params.estado;
    return { route: route || "dashboard", params };
  }

  function navigate(route, query = "") {
    const next = query ? `#/${route}?${query}` : `#/${route}`;
    if (location.hash !== next) {
      location.hash = next;
    }
    renderApp();
  }

  function isDesktop() {
    return window.matchMedia("(min-width: 981px)").matches;
  }

  /* ---------- Auth ---------- */
  function renderAuth() {
    const root = $("#app");
    root.innerHTML = `
      <div class="auth-screen">
        <div class="auth-wrap">
          <header class="auth-header">
            <img class="auth-brand-logo" src="/static/img/logo-jaelin.png" alt="JAELIN Transporte & Maquinaria" />
            <h1 class="auth-logo">Agenda Facturas</h1>
            <p class="auth-tagline">Comprobantes, agenda y recordatorios</p>
          </header>

          <section class="auth-panel">
            <div class="auth-mode" role="tablist">
              <button type="button" class="active" data-tab="login" role="tab">Ingresar</button>
              <button type="button" data-tab="register" role="tab">Crear cuenta</button>
            </div>
            <h2 class="auth-form-title" id="auth-title">Bienvenido de nuevo</h2>
            <p class="auth-form-lead" id="auth-lead">Usa tu correo para continuar.</p>
            <div class="auth-error" id="auth-error"></div>
            <form id="auth-form" class="auth-form">
              <div class="field register-only" hidden>
                <label>Nombre completo</label>
                <input name="nombre" placeholder="Ej. María Quispe" autocomplete="name" />
              </div>
              <div class="field">
                <label>Correo electrónico</label>
                <input name="email" type="email" required placeholder="tu@correo.com" autocomplete="email" />
              </div>
              <div class="field">
                <label>Contraseña</label>
                <input name="password" type="password" required minlength="6" placeholder="Mínimo 6 caracteres" autocomplete="current-password" />
              </div>
              <div class="auth-form-row register-only" hidden>
                <div class="field">
                  <label>RUC empresa</label>
                  <input name="ruc_empresa" maxlength="11" placeholder="20XXXXXXXXX" />
                </div>
                <div class="field">
                  <label>Razón social</label>
                  <input name="razon_social" placeholder="Mi Negocio SAC" />
                </div>
              </div>
              <div class="field register-only" hidden>
                <label>Teléfono / WhatsApp</label>
                <input name="telefono" placeholder="999888777" autocomplete="tel" />
              </div>
              <button class="btn btn-primary auth-submit" type="submit" id="auth-submit">Ingresar</button>
            </form>
          </section>
        </div>
      </div>`;

    let mode = "login";
    const setMode = (next) => {
      mode = next;
      $$(".auth-mode button").forEach((b) => b.classList.toggle("active", b.dataset.tab === mode));
      $$(".register-only").forEach((el) => {
        el.hidden = mode !== "register";
      });
      const title = $("#auth-title");
      const lead = $("#auth-lead");
      const submit = $("#auth-submit");
      const pass = $('input[name="password"]');
      if (mode === "login") {
        title.textContent = "Bienvenido de nuevo";
        lead.textContent = "Usa tu correo para continuar.";
        submit.textContent = "Ingresar";
        if (pass) pass.autocomplete = "current-password";
      } else {
        title.textContent = "Crea tu cuenta";
        lead.textContent = "Registra tu negocio en minutos.";
        submit.textContent = "Crear cuenta";
        if (pass) pass.autocomplete = "new-password";
      }
    };

    $$(".auth-mode button").forEach((btn) => {
      btn.addEventListener("click", () => setMode(btn.dataset.tab));
    });
    setMode("login");

    $("#auth-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      const err = $("#auth-error");
      err.classList.remove("show");
      try {
        const data = mode === "login" ? await API.login(body) : await API.registro(body);
        API.setSession(data.access_token, data.usuario);
        state.user = data.usuario;
        await bootApp();
      } catch (ex) {
        const msg = String(ex.message || "");
        err.textContent =
          msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("Network request failed")
            ? "No hay conexión con el servidor. Ejecuta: python run.py"
            : msg;
        err.classList.add("show");
      }
    });
  }

  /* ---------- Shell ---------- */
  function shell(html) {
    const unread = state.notifs.filter((n) => !n.leida).length;
    return `
      <div class="app-shell">
        <header class="topbar">
          <a class="brand" href="#/dashboard">
            <div class="brand-mark"><img src="/static/img/logo-jaelin.png" alt="JAELIN" /></div>
            <div class="brand-text">
              <strong>Agenda Facturas</strong>
              <span>${state.user?.razon_social || state.user?.nombre || "JAELIN"}</span>
            </div>
          </a>
          <div class="top-actions" style="position:relative">
            <button class="btn btn-secondary btn-sm" id="btn-push" title="Activar notificaciones">🔔 Avisos</button>
            <button class="btn btn-secondary btn-sm" id="btn-notif">
              Notificaciones ${unread ? `(${unread})` : ""}
            </button>
            <button class="btn btn-ghost btn-sm" id="btn-logout">Salir</button>
            <div class="notif-panel" id="notif-panel">
              <div style="padding:.8rem;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line)">
                <strong>Notificaciones</strong>
                <button class="btn btn-ghost btn-sm" id="btn-read-all">Marcar leídas</button>
              </div>
              ${
                state.notifs.length
                  ? state.notifs
                      .map(
                        (n) => `
                  <div class="notif-item ${n.leida ? "" : "unread"}" data-id="${n.id}">
                    <strong>${escapeHtml(n.titulo)}</strong>
                    <p>${escapeHtml(n.mensaje)}</p>
                  </div>`
                      )
                      .join("")
                  : `<div class="empty"><p>Sin notificaciones</p></div>`
              }
            </div>
          </div>
        </header>
        <div class="layout">
          <aside class="sidebar">
            <div class="nav-label">Menú</div>
            ${navButtons()}
          </aside>
          <main class="content">${html}</main>
        </div>
        <nav class="mobile-nav" aria-label="Navegación principal">
          ${mobileNavHtml()}
        </nav>
        <div class="mobile-more" id="mobile-more" hidden>
          <button type="button" class="mobile-more-backdrop" data-close-more aria-label="Cerrar"></button>
          <div class="mobile-more-sheet" role="dialog" aria-label="Más opciones">
            <div class="mobile-more-handle"></div>
            <p class="mobile-more-title">Más</p>
            ${mobileMoreHtml()}
          </div>
        </div>
      </div>`;
  }

  function navIcon(name) {
    const icons = {
      home: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z"/></svg>`,
      docs: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Zm7 1.5V9h4.5L14 4.5ZM8 12h8v1.5H8V12Zm0 3.5h8V17H8v-1.5Z"/></svg>`,
      plus: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z"/></svg>`,
      agenda: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3.5h1.5V5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1.5V3.5H17V5h-1.5V3.5h-7V5H7V3.5Zm-1.5 6h13V19a.5.5 0 0 1-.5.5H7a.5.5 0 0 1-.5-.5V9.5Z"/></svg>`,
      more: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>`,
      clients: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm6 1.2a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6ZM3.5 19.5c0-2.8 2.7-5 5.5-5s5.5 2.2 5.5 5V20H3.5v-.5Zm11.2-.5c0-1.5.6-2.8 1.6-3.7 1 .5 2.1.7 3.2.7 1.4 0 2.7-.4 3.8-1.1v4.1h-8.6V19Z"/></svg>`,
      box: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.8 7.2 12 3l8.2 4.2v9.6L12 21l-8.2-4.2V7.2Zm8.2 1.1 6.2-3.2L12 4.4 5.8 7.6 12 8.3Zm-6.7.9v7.4L11 20v-8.2L5.3 9.2Zm13.4 0L13 11.8V20l5.7-2.9V9.2Z"/></svg>`,
      cash: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h13A2.5 2.5 0 0 1 21 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 16.5v-9ZM12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm-7.2-6.5h2.2v-.9H4.8v.9Zm12.4 0h2.2v-.9h-2.2v.9Zm-12.4 8.1h2.2v-.9H4.8v.9Zm12.4 0h2.2v-.9h-2.2v.9Z"/></svg>`,
      fuel: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h7.5A1.5 1.5 0 0 1 15 5v12.5a2.5 2.5 0 0 1-2.5 2.5h-4A2.5 2.5 0 0 1 6 17.5V5A1.5 1.5 0 0 1 7.5 3.5H6Zm9.5 3.2 2.2 2.2v7.6a1.8 1.8 0 1 0 1.8-1.8h-.3V9.2L16.8 6.7h-1.3V6.7ZM8 8h4.5v2H8V8Z"/></svg>`,
      bell: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 22a2.2 2.2 0 0 0 2.1-1.6H9.9A2.2 2.2 0 0 0 12 22Zm7-5.2V11a7 7 0 1 0-14 0v5.8L3 19v1h18v-1l-2-2.2Z"/></svg>`,
      phone: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.2 3.8c.5-.5 1.3-.6 1.9-.2l2 1.3c.6.4.8 1.2.5 1.8l-.9 1.8a1.4 1.4 0 0 0 .3 1.6l2.9 2.9c.4.4 1 .5 1.6.3l1.8-.9c.6-.3 1.4-.1 1.8.5l1.3 2c.4.6.3 1.4-.2 1.9l-1.2 1.2c-.6.6-1.5.9-2.4.7-2.2-.4-4.7-1.9-7.3-4.5S5.4 10.2 5 8c-.2-.9.1-1.8.7-2.4L8.2 3.8Z"/></svg>`,
    };
    return icons[name] || "";
  }

  function mobileNavHtml() {
    const moreActive = ["clientes", "productos", "cajas", "combustibles", "contactos", "recordatorios"].includes(state.route);
    const items = [
      ["dashboard", "home", "Inicio"],
      ["comprobantes", "docs", "Docs"],
      ["nuevo", "plus", "Nuevo", true],
      ["agenda", "agenda", "Agenda"],
    ];
    const buttons = items
      .map(([route, ico, label, primary]) => {
        const active = state.route === route ? "active" : "";
        const cls = primary ? `nav-primary ${active}` : active;
        return `<button type="button" data-route="${route}" class="${cls}"><span class="mico">${navIcon(ico)}</span><span class="mlabel">${label}</span></button>`;
      })
      .join("");
    return `${buttons}<button type="button" id="btn-mobile-more" class="${moreActive ? "active" : ""}"><span class="mico">${navIcon("more")}</span><span class="mlabel">Más</span></button>`;
  }

  function mobileMoreHtml() {
    const items = [
      ["clientes", "clients", "Clientes"],
      ["contactos", "phone", "Teléfonos"],
      ["productos", "box", "Productos"],
      ["cajas", "cash", "Cajas"],
      ["combustibles", "fuel", "Combustibles"],
      ["recordatorios", "bell", "Avisos"],
    ];
    return items
      .map(
        ([route, ico, label]) =>
          `<button type="button" data-route="${route}" class="mobile-more-item ${state.route === route ? "active" : ""}"><span class="mico">${navIcon(ico)}</span><span>${label}</span></button>`
      )
      .join("");
  }

  function navButtons(mobile = false) {
    if (mobile) return mobileNavHtml();
    const items = [
      ["dashboard", "📊", "Dashboard"],
      ["comprobantes", "🧾", "Comprobantes"],
      ["clientes", "👥", "Clientes"],
      ["contactos", "📞", "Agenda tel."],
      ["productos", "📦", "Productos"],
      ["cajas", "💵", "Cajas"],
      ["combustibles", "⛽", "Combustibles"],
      ["nuevo", "＋", "Nuevo"],
      ["agenda", "📅", "Agenda"],
      ["recordatorios", "⏰", "Avisos"],
    ];
    return items
      .map(
        ([route, ico, label]) => `<button class="nav-btn ${state.route === route ? "active" : ""}" data-route="${route}">
          <span class="nav-ico">${ico}</span>${label}
        </button>`
      )
      .join("");
  }

  function bindShell() {
    $$("[data-route]").forEach((btn) =>
      btn.addEventListener("click", () => {
        $("#mobile-more")?.setAttribute("hidden", "");
        navigate(btn.dataset.route);
      })
    );
    $("#btn-mobile-more")?.addEventListener("click", () => {
      const panel = $("#mobile-more");
      if (!panel) return;
      if (panel.hasAttribute("hidden")) panel.removeAttribute("hidden");
      else panel.setAttribute("hidden", "");
    });
    $$("[data-close-more]").forEach((el) =>
      el.addEventListener("click", () => $("#mobile-more")?.setAttribute("hidden", ""))
    );
    $("#btn-logout")?.addEventListener("click", () => {
      API.clearSession();
      state.user = null;
      renderAuth();
    });
    $("#btn-notif")?.addEventListener("click", () => {
      $("#notif-panel")?.classList.toggle("open");
    });
    $("#btn-read-all")?.addEventListener("click", async () => {
      await API.leerTodas();
      state.notifs = await API.listNotificaciones();
      renderApp();
    });
    $$(".notif-item").forEach((el) =>
      el.addEventListener("click", async () => {
        await API.leerNotificacion(el.dataset.id);
        state.notifs = await API.listNotificaciones();
        renderApp();
      })
    );
    $("#btn-push")?.addEventListener("click", () => enablePush().catch((e) => toast(e.message)));
  }

  /* ---------- Views ---------- */
  async function viewDashboard() {
    const d = await API.dashboard();
    const hero = isDesktop()
      ? `<div class="dashboard-hero desktop-only">
          <div class="hero-panel">
            <img class="dash-brand-logo" src="/static/img/logo-jaelin.png" alt="JAELIN" />
            <h2>Panel de control</h2>
            <p>Resumen de tu facturación, cobranzas y agenda. Los datos se sincronizan en tiempo real con tu app móvil.</p>
            <div class="hero-metrics">
              <div><span>Facturado</span><strong>${money(d.total_facturado)}</strong></div>
              <div><span>Cobrado</span><strong>${money(d.total_cobrado)}</strong></div>
              <div><span>Pendiente</span><strong>${money(d.total_pendiente)}</strong></div>
            </div>
          </div>
          <div class="panel">
            <h3>Hoy en agenda</h3>
            <p style="margin:0 0 .8rem;color:var(--muted)">${d.agendas_hoy} evento(s) hoy · ${d.agendas_proximas} en los próximos 7 días</p>
            <p style="margin:0;color:${d.documentos_vencidos ? "var(--danger)" : "var(--ok)"};font-weight:700">
              ${d.documentos_vencidos} documento(s) vencido(s) sin pago
            </p>
            <div style="margin-top:1rem;display:flex;gap:.5rem;flex-wrap:wrap">
              <button class="btn btn-primary btn-sm" data-go="nuevo">Nuevo comprobante</button>
              <button class="btn btn-secondary btn-sm" data-go="agenda">Programar cita</button>
            </div>
          </div>
        </div>`
      : `<div class="panel mobile-hint" style="margin-bottom:1rem">
          <img class="dash-brand-logo" src="/static/img/logo-jaelin.png" alt="JAELIN" style="width:56px;height:56px" />
          <h3 style="margin:0 0 .4rem;font-family:var(--font-display)">Resumen rápido</h3>
          <p style="margin:0;color:var(--muted)">Misma información que en PC, optimizada para móvil.</p>
        </div>`;

    return `
      <div class="page-head">
        <div>
          <h1>Dashboard</h1>
          <p>Indicadores clave de comprobantes y agenda.</p>
        </div>
        <button class="btn btn-primary" data-go="nuevo">＋ Registrar comprobante</button>
      </div>
      ${hero}
      <div class="grid-stats">
        <div class="stat"><label>Comprobantes</label><strong>${d.total_comprobantes}</strong></div>
        <div class="stat ok"><label>Cobrado</label><strong>${money(d.total_cobrado)}</strong></div>
        <div class="stat warn"><label>Por cobrar</label><strong>${money(d.total_pendiente)}</strong></div>
        <div class="stat danger"><label>Anulado</label><strong>${money(d.total_anulado)}</strong></div>
      </div>
      <div class="charts">
        <div class="panel chart-box"><h3>Facturación mensual</h3><canvas id="chart-mes"></canvas></div>
        <div class="panel chart-box"><h3>Por estado</h3><canvas id="chart-estado"></canvas></div>
      </div>
      <div class="charts">
        <div class="panel chart-box"><h3>Por tipo de documento</h3><canvas id="chart-tipo"></canvas></div>
        <div class="panel">
          <h3>Últimos comprobantes</h3>
          ${
            d.recientes.length
              ? `<div class="table-wrap"><table>
                  <thead><tr><th>Documento</th><th>Cliente</th><th>Total</th><th>Estado</th></tr></thead>
                  <tbody>
                  ${d.recientes
                    .map(
                      (r) => `<tr>
                      <td>${tipoLabel(r.tipo)} ${r.serie}-${r.numero}</td>
                      <td>${escapeHtml(r.cliente_nombre)}</td>
                      <td>${money(r.total)}</td>
                      <td><span class="badge ${r.estado}">${estadoLabel(r.estado)}</span></td>
                    </tr>`
                    )
                    .join("")}
                  </tbody></table></div>`
              : `<div class="empty"><strong>Sin datos aún</strong>Registra tu primer comprobante.</div>`
          }
        </div>
      </div>`;
  }

  function paintCharts(d) {
    destroyCharts();
    if (typeof Chart === "undefined") return;
    const mesLabels = d.por_mes.map((x) => x.mes);
    const mesData = d.por_mes.map((x) => x.total);
    state.charts.mes = new Chart($("#chart-mes"), {
      type: "bar",
      data: {
        labels: mesLabels,
        datasets: [
          {
            label: "Total S/",
            data: mesData,
            backgroundColor: "rgba(15, 61, 46, 0.75)",
            borderRadius: 8,
          },
        ],
      },
      options: { responsive: true, plugins: { legend: { display: false } } },
    });

    const estLabels = Object.keys(d.por_estado).map(estadoLabel);
    const estData = Object.values(d.por_estado);
    state.charts.estado = new Chart($("#chart-estado"), {
      type: "doughnut",
      data: {
        labels: estLabels,
        datasets: [
          {
            data: estData,
            backgroundColor: ["#175cd3", "#067647", "#b54708", "#b42318"],
          },
        ],
      },
      options: { responsive: true },
    });

    const tipoLabels = Object.keys(d.por_tipo);
    const tipoData = Object.values(d.por_tipo);
    state.charts.tipo = new Chart($("#chart-tipo"), {
      type: "pie",
      data: {
        labels: tipoLabels,
        datasets: [
          {
            data: tipoData,
            backgroundColor: ["#0f3d2e", "#1f6b4f", "#c9852a", "#175cd3", "#6941c6", "#0f766e", "#b54708", "#475467"],
          },
        ],
      },
      options: { responsive: true },
    });
  }

  function destroyCharts() {
    Object.values(state.charts).forEach((c) => c?.destroy?.());
    state.charts = {
      estado: null,
      tipo: null,
      mes: null,
      cajaDia: null,
      cajaPie: null,
      combDia: null,
      combPlaca: null,
      combConductor: null,
      combMarca: null,
    };
  }

  function defaultCajaDates() {
    const hoy = new Date();
    const hasta = hoy.toISOString().slice(0, 10);
    const desde = new Date(hoy.getFullYear(), hoy.getMonth(), 1).toISOString().slice(0, 10);
    return { desde, hasta };
  }

  function paintCajaCharts(dash) {
    if (typeof Chart === "undefined" || !dash) return;
    state.charts.cajaDia?.destroy?.();
    state.charts.cajaPie?.destroy?.();
    state.charts.cajaDia = null;
    state.charts.cajaPie = null;

    const diaEl = $("#chart-caja-dia");
    if (diaEl && dash.por_dia?.length) {
      state.charts.cajaDia = new Chart(diaEl, {
        type: "bar",
        data: {
          labels: dash.por_dia.map((x) => x.fecha.slice(5)),
          datasets: [
            {
              label: "Ingresos",
              data: dash.por_dia.map((x) => x.ingresos),
              backgroundColor: "rgba(6, 118, 71, 0.75)",
              borderRadius: 6,
            },
            {
              label: "Egresos",
              data: dash.por_dia.map((x) => x.egresos),
              backgroundColor: "rgba(180, 35, 24, 0.7)",
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { position: "bottom" } },
          scales: { x: { stacked: false }, y: { beginAtZero: true } },
        },
      });
    }

    const pieEl = $("#chart-caja-pie");
    if (pieEl && dash.por_caja?.length) {
      state.charts.cajaPie = new Chart(pieEl, {
        type: "doughnut",
        data: {
          labels: dash.por_caja.map((x) => x.caja),
          datasets: [
            {
              data: dash.por_caja.map((x) => Math.abs(x.ingresos) + Math.abs(x.egresos)),
              backgroundColor: ["#0f3d2e", "#1f6b4f", "#c9852a", "#175cd3", "#0f766e", "#b54708", "#475467"],
            },
          ],
        },
        options: { responsive: true, plugins: { legend: { position: "bottom" } } },
      });
    }
  }

  function paintCombustibleCharts(resumen) {
    if (typeof Chart === "undefined" || !resumen) return;
    ["combDia", "combPlaca", "combConductor", "combMarca"].forEach((k) => {
      state.charts[k]?.destroy?.();
      state.charts[k] = null;
    });

    const diaEl = $("#chart-comb-dia");
    if (diaEl && resumen.por_dia?.length) {
      state.charts.combDia = new Chart(diaEl, {
        type: "line",
        data: {
          labels: resumen.por_dia.map((x) => x.fecha.slice(5)),
          datasets: [
            {
              label: "Ingresos",
              data: resumen.por_dia.map((x) => x.ingresos),
              borderColor: "#067647",
              backgroundColor: "rgba(6, 118, 71, 0.15)",
              fill: true,
              tension: 0.3,
            },
            {
              label: "Salidas",
              data: resumen.por_dia.map((x) => x.salidas),
              borderColor: "#b54708",
              backgroundColor: "rgba(181, 71, 8, 0.12)",
              fill: true,
              tension: 0.3,
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { position: "bottom" } },
          scales: { y: { beginAtZero: true, title: { display: true, text: "Galones" } } },
        },
      });
    }

    const placaEl = $("#chart-comb-placa");
    if (placaEl && resumen.por_placa?.length) {
      state.charts.combPlaca = new Chart(placaEl, {
        type: "bar",
        data: {
          labels: resumen.por_placa.map((x) => x.placa),
          datasets: [
            {
              label: "Salidas (gal)",
              data: resumen.por_placa.map((x) => x.salidas),
              backgroundColor: "rgba(180, 35, 24, 0.72)",
              borderRadius: 6,
            },
            {
              label: "Ingresos (gal)",
              data: resumen.por_placa.map((x) => x.ingresos),
              backgroundColor: "rgba(6, 118, 71, 0.7)",
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          indexAxis: "y",
          plugins: { legend: { position: "bottom" } },
          scales: { x: { beginAtZero: true } },
        },
      });
    }

    const condEl = $("#chart-comb-conductor");
    if (condEl && resumen.por_conductor?.length) {
      state.charts.combConductor = new Chart(condEl, {
        type: "doughnut",
        data: {
          labels: resumen.por_conductor.map((x) => x.conductor),
          datasets: [
            {
              data: resumen.por_conductor.map((x) => x.salidas),
              backgroundColor: ["#0f3d2e", "#1f6b4f", "#c9852a", "#175cd3", "#0f766e", "#b54708", "#475467", "#6941c6"],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 1.15,
          plugins: {
            legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } },
            title: { display: false },
          },
        },
      });
    }

    const marcaEl = $("#chart-comb-marca");
    if (marcaEl && resumen.por_marca?.length) {
      state.charts.combMarca = new Chart(marcaEl, {
        type: "pie",
        data: {
          labels: resumen.por_marca.map((x) => x.marca),
          datasets: [
            {
              data: resumen.por_marca.map((x) => x.salidas),
              backgroundColor: ["#0f3d2e", "#c9852a", "#175cd3", "#b54708", "#1f6b4f", "#0f766e", "#475467", "#6941c6"],
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          aspectRatio: 1.15,
          plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
        },
      });
    }
  }

  async function viewComprobantes() {
    const zonas = ["Salaverry", "Cerro de Pasco", "Chaparril", "El Ingenio", "Otros"];
    const params = {};
    if (state.filters.q) params.q = state.filters.q;
    if (state.filters.estado) params.estado = state.filters.estado;
    if (state.filters.tipo) params.tipo = state.filters.tipo;
    if (state.filters.zona) params.zona = state.filters.zona;
    if (state.filters.fecha_desde) params.fecha_desde = state.filters.fecha_desde;
    if (state.filters.fecha_hasta) params.fecha_hasta = state.filters.fecha_hasta;
    state.docs = await API.listComprobantes(params);

    return `
      <div class="page-head">
        <div>
          <h1>Comprobantes</h1>
          <p>Facturas, boletas, notas de venta y más, según legislación peruana.</p>
        </div>
        <button class="btn btn-primary" data-go="nuevo">＋ Nuevo</button>
      </div>
      <div class="toolbar panel">
        <input id="f-q" placeholder="Buscar cliente, serie o número..." value="${escapeHtml(state.filters.q)}" style="flex:1;min-width:160px" />
        <select id="f-estado">
          <option value="">Todos los estados</option>
          ${(state.meta?.estados || [])
            .map((e) => `<option value="${e.value}" ${state.filters.estado === e.value ? "selected" : ""}>${e.label}</option>`)
            .join("")}
        </select>
        <select id="f-tipo">
          <option value="">Todos los tipos</option>
          ${(state.meta?.tipos_documento || [])
            .map((e) => `<option value="${e.value}" ${state.filters.tipo === e.value ? "selected" : ""}>${e.label}</option>`)
            .join("")}
        </select>
        <select id="f-zona">
          <option value="">Todas las zonas</option>
          ${zonas
            .map((z) => `<option value="${z}" ${state.filters.zona === z ? "selected" : ""}>${z}</option>`)
            .join("")}
        </select>
        <input id="f-desde" type="date" title="Desde" value="${escapeHtml(state.filters.fecha_desde)}" />
        <input id="f-hasta" type="date" title="Hasta" value="${escapeHtml(state.filters.fecha_hasta)}" />
        <button class="btn btn-secondary" id="btn-filtrar">Filtrar</button>
        <button class="btn btn-ghost" id="btn-limpiar-filtros">Limpiar</button>
      </div>
      <div class="panel" style="padding:0;overflow:hidden">
        ${
          state.docs.length
            ? `<div class="table-wrap"><table>
              <thead><tr>
                <th>Documento</th><th>Cliente</th><th>Zona</th><th>Fecha</th><th>Total</th><th>Estado</th><th>Acciones</th>
              </tr></thead>
              <tbody>
              ${state.docs
                .map(
                  (d) => `<tr>
                  <td><strong>${tipoLabel(d.tipo)}</strong><br><span style="color:var(--muted)">${d.serie}-${d.numero}</span></td>
                  <td>${escapeHtml(d.cliente_nombre)}<br><span style="color:var(--muted);font-size:.8rem">${d.cliente_documento || ""}</span></td>
                  <td>${escapeHtml(d.zona || "—")}</td>
                  <td>${fmtDate(d.fecha_emision)}</td>
                  <td>${money(d.total)}</td>
                  <td>
                    <label class="estado-quick-wrap" title="Cambiar estado">
                      <span class="sr-only">Estado</span>
                      <select class="estado-quick badge ${d.estado}" data-estado-id="${d.id}" aria-label="Cambiar estado">
                        ${(state.meta?.estados || [])
                          .map(
                            (e) =>
                              `<option value="${e.value}" ${d.estado === e.value ? "selected" : ""}>${e.label}</option>`
                          )
                          .join("")}
                      </select>
                    </label>
                  </td>
                  <td class="actions">
                    <button type="button" class="btn btn-secondary btn-sm" data-edit="${d.id}">Editar</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-pdf="${d.id}">PDF</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-mail="${d.id}">Correo</button>
                    <button type="button" class="btn btn-accent btn-sm" data-wa="${d.id}">WhatsApp</button>
                    <button type="button" class="btn btn-danger btn-sm" data-del="${d.id}">Eliminar</button>
                  </td>
                </tr>`
                )
                .join("")}
              </tbody></table></div>`
            : `<div class="empty"><strong>No hay comprobantes</strong>Registra facturas, boletas u otros documentos.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-share"></div>`;
  }

  function viewNuevoForm(doc = null) {
    const draft = !doc ? state.draftFromContact : null;
    const items = doc?.items?.length
      ? doc.items
      : [{ descripcion: "", cantidad: 1, precio_unitario: 0, unidad: "NIU", aplica_igv: true }];
    const today = new Date().toISOString().slice(0, 10);
    const clienteNombre = doc?.cliente_nombre || draft?.nombre || "";
    const clienteEmail = doc?.cliente_email || draft?.email || "";
    const clienteTel = doc?.cliente_telefono || draft?.telefono || "";
    const clienteDoc = doc?.cliente_documento || "";
    if (draft) state.draftFromContact = null;
    return `
      <div class="page-head">
        <div>
          <h1>${doc ? "Editar comprobante" : "Nuevo comprobante"}</h1>
          <p>Completa los datos del documento tributario / comercial.</p>
        </div>
        <button class="btn btn-secondary" data-go="comprobantes">Volver</button>
      </div>
      <form class="panel" id="form-comprobante">
        <div class="form-grid">
          <div class="field">
            <label>Tipo de documento</label>
            <select name="tipo" id="c-tipo" required>
              ${(state.meta?.tipos_documento || [])
                .map(
                  (t) =>
                    `<option value="${t.value}" data-serie="${t.serie}" ${doc?.tipo === t.value ? "selected" : ""}>${t.label}</option>`
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>Estado</label>
            <select name="estado" required>
              ${(state.meta?.estados || [])
                .map((e) => `<option value="${e.value}" ${(!doc && e.value === "emitido") || doc?.estado === e.value ? "selected" : ""}>${e.label}</option>`)
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>Serie</label>
            <input name="serie" id="c-serie" required value="${doc?.serie || "F001"}" />
          </div>
          <div class="field">
            <label>Número</label>
            <input name="numero" required value="${doc?.numero || ""}" placeholder="00001234" />
          </div>
          <div class="field">
            <label>Fecha de emisión</label>
            <input type="date" name="fecha_emision" required value="${doc?.fecha_emision || today}" />
          </div>
          <div class="field">
            <label>Fecha de vencimiento</label>
            <input type="date" name="fecha_vencimiento" value="${doc?.fecha_vencimiento || ""}" />
          </div>
          <div class="field">
            <label>RUC / DNI</label>
            <div class="doc-search">
              <input name="cliente_documento" id="c-documento" list="lista-docs-cliente" value="${escapeHtml(clienteDoc)}" placeholder="RUC 11 dígitos o DNI 8 dígitos" inputmode="numeric" />
              <button type="button" class="btn btn-secondary" id="btn-buscar-sunat" title="Buscar en SUNAT">Buscar</button>
            </div>
            <small class="field-hint" id="sunat-hint">Busca en SUNAT o elige un cliente del catálogo.</small>
          </div>
          <div class="field">
            <label>Cliente</label>
            <input name="cliente_nombre" id="c-cliente" list="lista-clientes" required value="${escapeHtml(clienteNombre)}" placeholder="Nombre o razón social" />
            <datalist id="lista-clientes">
              ${state.clientes
                .map(
                  (c) =>
                    `<option value="${escapeHtml(c.nombre)}" data-doc="${escapeHtml(c.documento || "")}" data-email="${escapeHtml(c.email || "")}" data-tel="${escapeHtml(c.telefono || "")}"></option>`
                )
                .join("")}
            </datalist>
            <datalist id="lista-docs-cliente">
              ${state.clientes
                .filter((c) => c.documento)
                .map((c) => `<option value="${escapeHtml(c.documento)}">${escapeHtml(c.nombre)}</option>`)
                .join("")}
            </datalist>
          </div>
          <div class="field">
            <label>Email del cliente</label>
            <input name="cliente_email" type="email" placeholder="cliente@correo.com" value="${escapeHtml(clienteEmail)}" />
          </div>
          <div class="field">
            <label>Teléfono / WhatsApp</label>
            <input name="cliente_telefono" placeholder="999888777" value="${escapeHtml(clienteTel)}" />
          </div>
          <div class="field">
            <label>Zona</label>
            <select name="zona">
              <option value="">Seleccionar zona…</option>
              ${["Salaverry", "Cerro de Pasco", "Chaparril", "El Ingenio", "Otros"]
                .map(
                  (z) =>
                    `<option value="${z}" ${doc?.zona === z ? "selected" : ""}>${z}</option>`
                )
                .join("")}
              ${
                doc?.zona && !["Salaverry", "Cerro de Pasco", "Chaparril", "El Ingenio", "Otros"].includes(doc.zona)
                  ? `<option value="${escapeHtml(doc.zona)}" selected>${escapeHtml(doc.zona)} (anterior)</option>`
                  : ""
              }
            </select>
          </div>
          <div class="field">
            <label>Motivo</label>
            <input name="motivo" maxlength="300" value="${escapeHtml(doc?.motivo || "")}" placeholder="Ej. Servicio de transporte, alquiler de maquinaria" />
          </div>
          <div class="field full">
            <label>Observaciones</label>
            <textarea name="observaciones" rows="2">${escapeHtml(doc?.observaciones || "")}</textarea>
          </div>
        </div>

        <h3 style="margin:1.2rem 0 .6rem;font-family:var(--font-display)">Detalle de productos / servicios</h3>
        <datalist id="lista-productos">
          ${state.productos
            .map(
              (p) =>
                `<option value="${escapeHtml(p.nombre)}" data-precio="${p.precio_unitario}" data-unidad="${escapeHtml(p.unidad || "NIU")}"></option>`
            )
            .join("")}
        </datalist>
        <div class="items-editor" id="items-editor">
          ${items.map((it, i) => itemRowHtml(i, it)).join("")}
        </div>
        <button type="button" class="btn btn-secondary btn-sm" id="btn-add-item" style="margin-top:.6rem">＋ Agregar ítem</button>
        <div class="totals-box">
          <div><span>Subtotal / Op. gravada</span><br><strong id="t-sub">S/ 0.00</strong></div>
          <div><span>IGV 18%</span><br><strong id="t-igv">S/ 0.00</strong></div>
          <div><span>Total</span><br><strong id="t-total">S/ 0.00</strong></div>
        </div>
        <div style="margin-top:1rem;display:flex;gap:.6rem;flex-wrap:wrap">
          <button class="btn btn-primary" type="submit">${doc ? "Guardar cambios" : "Registrar comprobante"}</button>
          <button class="btn btn-ghost" type="button" data-go="comprobantes">Cancelar</button>
        </div>
      </form>`;
  }

  function tipoPermiteIgv(tipo) {
    return ["factura", "boleta", "nota_credito", "nota_debito", "ticket"].includes(tipo);
  }

  function itemRowHtml(i, it = {}) {
    const tipo = $("#c-tipo")?.value || "factura";
    const permite = tipoPermiteIgv(tipo);
    const checked = it.aplica_igv !== false && permite;
    return `
      <div class="item-row" data-item>
        <div class="field item-desc">
          ${i === 0 ? "<label>Descripción</label>" : ""}
          <input data-k="descripcion" list="lista-productos" required value="${escapeHtml(it.descripcion || "")}" placeholder="Producto o servicio" />
        </div>
        <div class="field item-qty">
          ${i === 0 ? "<label>Cantidad</label>" : ""}
          <input data-k="cantidad" type="number" min="0.001" step="0.001" inputmode="decimal" required value="${it.cantidad ?? 1}" />
        </div>
        <div class="field item-price">
          ${i === 0 ? "<label>P. unitario</label>" : ""}
          <input data-k="precio_unitario" type="number" min="0" step="0.01" inputmode="decimal" required value="${it.precio_unitario ?? 0}" />
        </div>
        <div class="field item-igv">
          ${i === 0 ? "<label>IGV</label>" : ""}
          <label class="igv-toggle" title="Incluir IGV 18% en este ítem">
            <input data-k="aplica_igv" type="checkbox" ${checked ? "checked" : ""} ${permite ? "" : "disabled"} />
            <span>${permite ? "Sí" : "N/A"}</span>
          </label>
        </div>
        <button type="button" class="btn btn-danger btn-sm btn-remove-item" title="Quitar">✕</button>
      </div>`;
  }

  function syncItemIgvControls() {
    const permite = tipoPermiteIgv($("#c-tipo")?.value);
    $$("[data-item]").forEach((row) => {
      const chk = $('[data-k="aplica_igv"]', row);
      const label = $(".igv-toggle span", row);
      if (!chk) return;
      chk.disabled = !permite;
      if (!permite) {
        chk.checked = false;
        if (label) label.textContent = "N/A";
      } else if (label) {
        label.textContent = chk.checked ? "Sí" : "No";
      }
    });
  }

  function recalcItems() {
    let gravado = 0;
    let sinIgv = 0;
    const tipo = $("#c-tipo")?.value;
    const permite = tipoPermiteIgv(tipo);
    $$("[data-item]").forEach((row) => {
      const cant = Number($('[data-k="cantidad"]', row).value || 0);
      const pu = Number($('[data-k="precio_unitario"]', row).value || 0);
      const line = cant * pu;
      const chk = $('[data-k="aplica_igv"]', row);
      const aplica = permite && chk?.checked;
      if (aplica) gravado += line;
      else sinIgv += line;
      const label = $(".igv-toggle span", row);
      if (label && permite) label.textContent = chk?.checked ? "Sí" : "No";
    });
    let sub = gravado + sinIgv;
    let igv = 0;
    let total = gravado + sinIgv;
    if (permite && gravado > 0) {
      const baseGravada = gravado / 1.18;
      igv = gravado - baseGravada;
      sub = baseGravada + sinIgv;
      total = gravado + sinIgv;
    }
    $("#t-sub").textContent = money(sub);
    $("#t-igv").textContent = money(igv);
    $("#t-total").textContent = money(total);
  }

  async function viewAgenda() {
    state.agendas = await API.listAgenda();
    return `
      <div class="page-head">
        <div>
          <h1>Agenda</h1>
          <p>Reuniones, citas detalladas y notas. Recibirás avisos en el celular.</p>
        </div>
        <button class="btn btn-primary" id="btn-new-agenda">＋ Programar</button>
      </div>
      <div class="agenda-list">
        ${
          state.agendas.length
            ? state.agendas
                .map((a) => {
                  const dt = new Date(a.fecha_inicio);
                  const day = dt.getDate();
                  const mon = dt.toLocaleDateString("es-PE", { month: "short" });
                  return `
                  <article class="agenda-card">
                    <div class="agenda-date"><div class="d">${day}</div><div class="m">${mon}</div></div>
                    <div>
                      <span class="badge ${a.tipo}">${agendaLabel(a.tipo)}</span>
                      <h3>${escapeHtml(a.titulo)} ${a.completado ? "✓" : ""}</h3>
                      <p>${fmtDateTime(a.fecha_inicio)}${a.ubicacion ? " · " + escapeHtml(a.ubicacion) : ""}</p>
                      <p>${escapeHtml(a.descripcion || "Sin descripción")}</p>
                      ${a.participantes ? `<p><strong>Participantes:</strong> ${escapeHtml(a.participantes)}</p>` : ""}
                      <p style="margin-top:.35rem">Recordatorio: ${a.recordatorio_minutos} min antes</p>
                    </div>
                    <div class="actions" style="flex-direction:column">
                      <button class="btn btn-secondary btn-sm" data-a-edit="${a.id}">Editar</button>
                      <button class="btn btn-secondary btn-sm" data-a-done="${a.id}">${a.completado ? "Reabrir" : "Completar"}</button>
                      <button class="btn btn-danger btn-sm" data-a-del="${a.id}">Eliminar</button>
                    </div>
                  </article>`;
                })
                .join("")
            : `<div class="panel empty"><strong>Agenda vacía</strong>Programa tu primera reunión o cita.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-agenda"></div>`;
  }

  async function viewClientes() {
    state.clientes = await API.listClientes();
    return `
      <div class="page-head">
        <div>
          <h1>Clientes</h1>
          <p>Catálogo de clientes. También se guardan solos al usarlos en un comprobante.</p>
        </div>
        <button class="btn btn-primary" id="btn-new-cliente">＋ Nuevo cliente</button>
      </div>
      <div class="panel" style="padding:0;overflow:hidden">
        ${
          state.clientes.length
            ? `<div class="table-wrap"><table>
              <thead><tr><th>Cliente</th><th>Documento</th><th>Contacto</th><th>Acciones</th></tr></thead>
              <tbody>
              ${state.clientes
                .map(
                  (c) => `<tr>
                  <td><strong>${escapeHtml(c.nombre)}</strong>
                    ${c.direccion ? `<br><span style="color:var(--muted);font-size:.8rem">${escapeHtml(c.direccion)}</span>` : ""}</td>
                  <td>${escapeHtml(c.tipo_documento || "")} ${escapeHtml(c.documento || "—")}</td>
                  <td>${escapeHtml(c.email || "—")}<br><span style="color:var(--muted);font-size:.8rem">${escapeHtml(c.telefono || "")}</span></td>
                  <td class="actions">
                    <button class="btn btn-secondary btn-sm" data-cli-edit="${c.id}">Editar</button>
                    <button class="btn btn-danger btn-sm" data-cli-del="${c.id}">Eliminar</button>
                  </td>
                </tr>`
                )
                .join("")}
              </tbody></table></div>`
            : `<div class="empty"><strong>Sin clientes</strong>Agrégalos manualmente o al emitir un comprobante.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-cliente"></div>`;
  }

  function whatsappUrl(phone, text = "") {
    const digits = String(phone || "").replace(/\D/g, "");
    if (!digits) return null;
    let n = digits;
    if (n.length === 9) n = `51${n}`;
    const msg = text ? `?text=${encodeURIComponent(text)}` : "";
    return `https://wa.me/${n}${msg}`;
  }

  function supportsPhoneContacts() {
    return typeof navigator !== "undefined" && "contacts" in navigator && "ContactsManager" in window;
  }

  async function pickPhoneContacts() {
    if (!supportsPhoneContacts()) {
      throw new Error(
        "Tu navegador no permite leer la agenda del teléfono. Usa Chrome en Android (HTTPS) o agrega contactos manualmente."
      );
    }
    const selected = await navigator.contacts.select(["name", "tel", "email"], { multiple: true });
    return (selected || [])
      .map((c) => {
        const rawNames = Array.isArray(c.name) ? c.name : c.name ? [c.name] : [];
        const nombres = rawNames
          .map((n) => (typeof n === "string" ? n : n?.formatted || n?.givenName || ""))
          .map((n) => String(n || "").trim())
          .filter(Boolean);
        const tels = (Array.isArray(c.tel) ? c.tel : [])
          .map((t) => String(t || "").trim())
          .filter(Boolean);
        const emails = (Array.isArray(c.email) ? c.email : [])
          .map((e) => String(e || "").trim())
          .filter(Boolean);
        return {
          nombre: nombres[0] || tels[0] || emails[0] || "Sin nombre",
          telefono: tels[0] || null,
          telefono_alt: tels[1] || null,
          email: emails[0] || null,
          empresa: null,
        };
      })
      .filter((c) => c.telefono || c.email);
  }

  async function viewContactos() {
    const params = {};
    if (state.filtersContacto.q) params.q = state.filtersContacto.q;
    state.contactos = await API.listContactos(params);
    const canSync = supportsPhoneContacts();

    return `
      <div class="page-head">
        <div>
          <h1>Agenda telefónica</h1>
          <p>Contactos del teléfono sincronizados con clientes, agenda, WhatsApp y comprobantes.</p>
        </div>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap">
          <button class="btn btn-secondary" id="btn-sync-phone" ${canSync ? "" : "title=\"Disponible en Chrome Android\""}>
            📲 Importar del teléfono
          </button>
          <button class="btn btn-primary" id="btn-new-contacto">＋ Contacto</button>
        </div>
      </div>
      ${
        canSync
          ? `<div class="panel" style="margin-bottom:1rem"><p style="margin:0;color:var(--muted)">Puedes importar varios contactos desde la agenda del teléfono. Se actualizan si el número ya existe.</p></div>`
          : `<div class="panel" style="margin-bottom:1rem"><p style="margin:0;color:var(--muted)">La sincronización con la agenda del teléfono funciona en <strong>Chrome Android</strong> (app instalada o HTTPS). En PC agrega contactos manualmente.</p></div>`
      }
      <div class="toolbar panel">
        <input id="f-contacto-q" placeholder="Buscar nombre, teléfono, email..." value="${escapeHtml(state.filtersContacto.q)}" style="flex:1;min-width:180px" />
        <button class="btn btn-secondary" id="btn-filtrar-contacto">Buscar</button>
      </div>
      <div class="panel" style="padding:0;overflow:hidden">
        ${
          state.contactos.length
            ? `<div class="contact-card-list">
              ${state.contactos
                .map((c) => {
                  const tel = c.telefono || c.telefono_alt || "";
                  const wa = whatsappUrl(tel, `Hola ${c.nombre}, te escribo desde JAELIN.`);
                  return `<article class="contact-card">
                    <div class="contact-card-head">
                      <div>
                        <strong>${escapeHtml(c.nombre)}</strong>
                        ${c.empresa ? `<div class="contact-meta">${escapeHtml(c.empresa)}</div>` : ""}
                      </div>
                      <span class="badge ${c.origen === "telefono" ? "emitido" : "cita"}">${c.origen === "telefono" ? "Teléfono" : "Manual"}</span>
                    </div>
                    <div class="contact-meta">
                      ${tel ? `<div>📞 ${escapeHtml(tel)}${c.telefono_alt && c.telefono_alt !== tel ? ` · ${escapeHtml(c.telefono_alt)}` : ""}</div>` : "<div>Sin teléfono</div>"}
                      ${c.email ? `<div>✉️ ${escapeHtml(c.email)}</div>` : ""}
                      ${c.cliente_id ? `<div style="color:var(--ok)">Vinculado a cliente #${c.cliente_id}</div>` : ""}
                    </div>
                    <div class="contact-actions">
                      ${tel ? `<a class="btn btn-secondary btn-sm" href="tel:${escapeHtml(tel)}">Llamar</a>` : ""}
                      ${wa ? `<a class="btn btn-secondary btn-sm" href="${wa}" target="_blank" rel="noopener">WhatsApp</a>` : ""}
                      <button class="btn btn-secondary btn-sm" data-ct-cliente="${c.id}">A cliente</button>
                      <button class="btn btn-secondary btn-sm" data-ct-factura="${c.id}">Comprobante</button>
                      <button class="btn btn-secondary btn-sm" data-ct-agenda="${c.id}">Agendar</button>
                      <button class="btn btn-ghost btn-sm" data-ct-edit="${c.id}">Editar</button>
                      <button class="btn btn-danger btn-sm" data-ct-del="${c.id}">Eliminar</button>
                    </div>
                  </article>`;
                })
                .join("")}
            </div>`
            : `<div class="empty"><strong>Sin contactos</strong>Importa desde el teléfono o agrega uno manualmente.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-contacto"></div>`;
  }

  async function viewProductos() {
    state.productos = await API.listProductos();
    return `
      <div class="page-head">
        <div>
          <h1>Productos y servicios</h1>
          <p>Catálogo reutilizable. Se actualiza automáticamente al facturar.</p>
        </div>
        <button class="btn btn-primary" id="btn-new-producto">＋ Nuevo ítem</button>
      </div>
      <div class="panel" style="padding:0;overflow:hidden">
        ${
          state.productos.length
            ? `<div class="table-wrap"><table>
              <thead><tr><th>Nombre</th><th>Tipo</th><th>Unidad</th><th>P. unitario</th><th>Acciones</th></tr></thead>
              <tbody>
              ${state.productos
                .map(
                  (p) => `<tr>
                  <td><strong>${escapeHtml(p.nombre)}</strong>
                    ${p.codigo ? `<br><span style="color:var(--muted);font-size:.8rem">${escapeHtml(p.codigo)}</span>` : ""}</td>
                  <td><span class="badge ${p.tipo === "servicio" ? "cita" : "emitido"}">${p.tipo === "servicio" ? "Servicio" : "Producto"}</span></td>
                  <td>${escapeHtml(p.unidad || "NIU")}</td>
                  <td>${money(p.precio_unitario)}</td>
                  <td class="actions">
                    <button class="btn btn-secondary btn-sm" data-prod-edit="${p.id}">Editar</button>
                    <button class="btn btn-danger btn-sm" data-prod-del="${p.id}">Eliminar</button>
                  </td>
                </tr>`
                )
                .join("")}
              </tbody></table></div>`
            : `<div class="empty"><strong>Sin productos</strong>Agrégalos manualmente o al emitir un comprobante.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-producto"></div>`;
  }

  async function viewCajas() {
    const defaults = defaultCajaDates();
    if (!state.filtersCaja.fecha_desde) state.filtersCaja.fecha_desde = defaults.desde;
    if (!state.filtersCaja.fecha_hasta) state.filtersCaja.fecha_hasta = defaults.hasta;

    const params = {
      fecha_desde: state.filtersCaja.fecha_desde,
      fecha_hasta: state.filtersCaja.fecha_hasta,
    };
    if (state.filtersCaja.caja_id) params.caja_id = state.filtersCaja.caja_id;
    if (state.filtersCaja.tipo) params.tipo = state.filtersCaja.tipo;
    if (state.filtersCaja.q) params.q = state.filtersCaja.q;

    const [cajas, dash] = await Promise.all([API.listCajas(), API.dashboardCajas(params)]);
    state.cajas = cajas;
    state.cajaDash = dash;
    state.movimientosCaja = dash.movimientos || [];
    const saldoTotal = cajas.reduce((acc, c) => acc + Number(c.saldo || 0), 0);
    const today = new Date().toISOString().slice(0, 10);

    return `
      <div class="page-head">
        <div>
          <h1>Cajas</h1>
          <p>Dashboard de movimientos, ingresos y egresos por caja.</p>
        </div>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap">
          <button class="btn btn-secondary" id="btn-new-caja">＋ Nueva caja</button>
          <button class="btn btn-primary" id="btn-new-mov">＋ Movimiento</button>
        </div>
      </div>
      <div class="toolbar panel">
        <input id="f-caja-desde" type="date" value="${escapeHtml(state.filtersCaja.fecha_desde)}" title="Desde" />
        <input id="f-caja-hasta" type="date" value="${escapeHtml(state.filtersCaja.fecha_hasta)}" title="Hasta" />
        <select id="f-caja-id">
          <option value="">Todas las cajas</option>
          ${cajas
            .map(
              (c) =>
                `<option value="${c.id}" ${String(state.filtersCaja.caja_id) === String(c.id) ? "selected" : ""}>${escapeHtml(c.nombre)}</option>`
            )
            .join("")}
        </select>
        <select id="f-caja-tipo">
          <option value="">Todos los tipos</option>
          <option value="ingreso" ${state.filtersCaja.tipo === "ingreso" ? "selected" : ""}>Ingreso</option>
          <option value="egreso" ${state.filtersCaja.tipo === "egreso" ? "selected" : ""}>Egreso</option>
        </select>
        <input id="f-caja-q" placeholder="N° o concepto..." value="${escapeHtml(state.filtersCaja.q)}" style="flex:1;min-width:140px" />
        <button class="btn btn-secondary" id="btn-filtrar-caja">Filtrar</button>
        <button class="btn btn-ghost" id="btn-caja-mes">Mes actual</button>
      </div>
      <div class="grid-stats">
        <div class="stat ok"><label>Ingresos del período</label><strong>${money(dash.total_ingresos)}</strong></div>
        <div class="stat warn"><label>Egresos del período</label><strong>${money(dash.total_egresos)}</strong></div>
        <div class="stat"><label>Saldo del período</label><strong>${money(dash.saldo_periodo)}</strong></div>
        <div class="stat"><label>Movimientos</label><strong>${dash.cantidad_movimientos}</strong></div>
      </div>
      <div class="charts">
        <div class="panel chart-box"><h3>Movimientos por día</h3><canvas id="chart-caja-dia"></canvas></div>
        <div class="panel chart-box"><h3>Actividad por caja</h3><canvas id="chart-caja-pie"></canvas></div>
      </div>
      <div class="panel" style="margin-bottom:1rem;padding:0;overflow:hidden">
        <div style="padding:.9rem 1rem;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:.5rem;flex-wrap:wrap;align-items:center">
          <strong style="font-family:var(--font-display)">Saldo acumulado por caja</strong>
          <span style="color:var(--muted);font-size:.85rem">Total: ${money(saldoTotal)}</span>
        </div>
        ${
          cajas.length
            ? `<div class="table-wrap"><table>
              <thead><tr><th>Caja</th><th>Ingresos</th><th>Egresos</th><th>Saldo</th><th>Acciones</th></tr></thead>
              <tbody>
              ${cajas
                .map(
                  (c) => `<tr>
                  <td><strong>${escapeHtml(c.nombre)}</strong>
                    ${c.descripcion ? `<br><span style="color:var(--muted);font-size:.8rem">${escapeHtml(c.descripcion)}</span>` : ""}</td>
                  <td style="color:var(--ok)">${money(c.total_ingresos)}</td>
                  <td style="color:var(--danger)">${money(c.total_egresos)}</td>
                  <td><strong>${money(c.saldo)}</strong></td>
                  <td class="actions">
                    <button class="btn btn-secondary btn-sm" data-caja-edit="${c.id}">Editar</button>
                    <button class="btn btn-danger btn-sm" data-caja-del="${c.id}">Archivar</button>
                  </td>
                </tr>`
                )
                .join("")}
              </tbody></table></div>`
            : `<div class="empty"><strong>Sin cajas</strong>Crea tu primera caja (ej. Caja principal, Yape, Banco).</div>`
        }
      </div>
      ${
        dash.por_caja?.length
          ? `<div class="panel" style="margin-bottom:1rem;padding:0;overflow:hidden">
              <div style="padding:.9rem 1rem;border-bottom:1px solid var(--line)">
                <strong style="font-family:var(--font-display)">Resumen del período por caja</strong>
                <span style="color:var(--muted);font-size:.85rem;margin-left:.5rem">${fmtDate(dash.fecha_desde)} — ${fmtDate(dash.fecha_hasta)}</span>
              </div>
              <div class="table-wrap"><table>
                <thead><tr><th>Caja</th><th>Ingresos</th><th>Egresos</th><th>Saldo período</th></tr></thead>
                <tbody>
                ${dash.por_caja
                  .map(
                    (c) => `<tr>
                    <td>${escapeHtml(c.caja)}</td>
                    <td style="color:var(--ok)">${money(c.ingresos)}</td>
                    <td style="color:var(--danger)">${money(c.egresos)}</td>
                    <td><strong>${money(c.saldo)}</strong></td>
                  </tr>`
                  )
                  .join("")}
                </tbody>
              </table></div>
            </div>`
          : ""
      }
      <div class="panel" style="padding:0;overflow:hidden">
        <div style="padding:.9rem 1rem;border-bottom:1px solid var(--line)">
          <strong style="font-family:var(--font-display)">Movimientos del período</strong>
        </div>
        ${
          state.movimientosCaja.length
            ? `<div class="table-wrap"><table>
              <thead><tr><th>Fecha</th><th>Caja</th><th>Tipo</th><th>N° transacción</th><th>Concepto</th><th>Monto</th><th>Acciones</th></tr></thead>
              <tbody>
              ${state.movimientosCaja
                .map(
                  (m) => `<tr>
                  <td>${fmtDate(m.fecha)}</td>
                  <td>${escapeHtml(m.caja_nombre)}</td>
                  <td><span class="badge ${m.tipo === "ingreso" ? "pagado" : "anulado"}">${movCajaLabel(m.tipo)}</span></td>
                  <td>${escapeHtml(m.numero_transaccion || "—")}</td>
                  <td>${escapeHtml(m.concepto)}</td>
                  <td style="color:${m.tipo === "ingreso" ? "var(--ok)" : "var(--danger)"}"><strong>${m.tipo === "egreso" ? "−" : "+"}${money(m.monto)}</strong></td>
                  <td class="actions">
                    <button class="btn btn-secondary btn-sm" data-mov-edit="${m.id}">Editar</button>
                    <button class="btn btn-danger btn-sm" data-mov-del="${m.id}">Eliminar</button>
                  </td>
                </tr>`
                )
                .join("")}
              </tbody></table></div>`
            : `<div class="empty"><strong>Sin movimientos</strong>No hay movimientos en el rango de fechas seleccionado.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-caja"></div>
      <div class="modal-backdrop" id="modal-mov" data-today="${today}"></div>`;
  }

  async function viewCombustibles() {
    const params = {};
    if (state.filtersCombustible.tipo) params.tipo = state.filtersCombustible.tipo;
    if (state.filtersCombustible.q) params.q = state.filtersCombustible.q;
    if (state.filtersCombustible.fecha_desde) params.fecha_desde = state.filtersCombustible.fecha_desde;
    if (state.filtersCombustible.fecha_hasta) params.fecha_hasta = state.filtersCombustible.fecha_hasta;
    const resumen = await API.resumenCombustibles(params);
    state.combustibleResumen = resumen;
    state.combustibles = resumen.movimientos || [];
    const today = new Date().toISOString().slice(0, 10);

    return `
      <div class="page-head">
        <div>
          <h1>Combustibles</h1>
          <p>Control de ingresos y salidas de combustible (galones) por vehículo.</p>
        </div>
        <button class="btn btn-primary" id="btn-new-combustible">＋ Movimiento</button>
      </div>
      <div class="toolbar panel">
        <select id="f-comb-tipo">
          <option value="">Todos</option>
          <option value="ingreso" ${state.filtersCombustible.tipo === "ingreso" ? "selected" : ""}>Ingresos</option>
          <option value="salida" ${state.filtersCombustible.tipo === "salida" ? "selected" : ""}>Salidas</option>
        </select>
        <input id="f-comb-desde" type="date" title="Desde" value="${escapeHtml(state.filtersCombustible.fecha_desde)}" />
        <input id="f-comb-hasta" type="date" title="Hasta" value="${escapeHtml(state.filtersCombustible.fecha_hasta)}" />
        <input id="f-comb-q" placeholder="Conductor, marca o placa..." value="${escapeHtml(state.filtersCombustible.q)}" style="flex:1;min-width:160px" />
        <button class="btn btn-secondary" id="btn-filtrar-comb">Filtrar</button>
        <button class="btn btn-ghost" id="btn-limpiar-comb">Limpiar</button>
      </div>
      <div class="grid-stats">
        <div class="stat ok"><label>Ingresos</label><strong>${galones(resumen.total_ingresos)}</strong></div>
        <div class="stat warn"><label>Salidas</label><strong>${galones(resumen.total_salidas)}</strong></div>
        <div class="stat"><label>Saldo disponible</label><strong>${galones(resumen.saldo_galones)}</strong></div>
        <div class="stat"><label>Registros</label><strong>${resumen.cantidad_movimientos}</strong></div>
      </div>
      <div class="charts">
        <div class="panel chart-box">
          <h3>Ingresos vs salidas por día</h3>
          <p style="margin:-.2rem 0 .7rem;color:var(--muted);font-size:.85rem">Tendencia de abastecimiento y consumo</p>
          <canvas id="chart-comb-dia"></canvas>
        </div>
        <div class="panel chart-box">
          <h3>Consumo por placa</h3>
          <p style="margin:-.2rem 0 .7rem;color:var(--muted);font-size:.85rem">Top vehículos por salidas de combustible</p>
          <canvas id="chart-comb-placa"></canvas>
        </div>
      </div>
      <div class="charts">
        <div class="panel chart-box chart-box-pie">
          <h3>Salidas por conductor</h3>
          <p style="margin:-.2rem 0 .7rem;color:var(--muted);font-size:.85rem">Quién consume más galones</p>
          <div class="chart-pie-wrap"><canvas id="chart-comb-conductor"></canvas></div>
        </div>
        <div class="panel chart-box chart-box-pie">
          <h3>Salidas por marca</h3>
          <p style="margin:-.2rem 0 .7rem;color:var(--muted);font-size:.85rem">Distribución por marca de vehículo</p>
          <div class="chart-pie-wrap"><canvas id="chart-comb-marca"></canvas></div>
        </div>
      </div>
      <div class="panel" style="padding:0;overflow:hidden">
        ${
          state.combustibles.length
            ? `<div class="table-wrap"><table>
              <thead><tr>
                <th>Fecha</th><th>Tipo</th><th>Galones</th><th>Conductor</th><th>Marca</th><th>Placa</th><th>Acciones</th>
              </tr></thead>
              <tbody>
              ${state.combustibles
                .map(
                  (m) => `<tr>
                  <td>${fmtDate(m.fecha)}</td>
                  <td><span class="badge ${m.tipo === "ingreso" ? "pagado" : "anulado"}">${movCombustibleLabel(m.tipo)}</span></td>
                  <td style="color:${m.tipo === "ingreso" ? "var(--ok)" : "var(--danger)"}"><strong>${m.tipo === "salida" ? "−" : "+"}${galones(m.galones)}</strong></td>
                  <td>${escapeHtml(m.conductor)}</td>
                  <td>${escapeHtml(m.marca || "—")}</td>
                  <td><strong>${escapeHtml(m.placa || "—")}</strong></td>
                  <td class="actions">
                    <button class="btn btn-secondary btn-sm" data-comb-edit="${m.id}">Editar</button>
                    <button class="btn btn-danger btn-sm" data-comb-del="${m.id}">Eliminar</button>
                  </td>
                </tr>`
                )
                .join("")}
              </tbody></table></div>`
            : `<div class="empty"><strong>Sin movimientos</strong>Registra un ingreso o salida de combustible.</div>`
        }
      </div>
      <div class="modal-backdrop" id="modal-combustible" data-today="${today}"></div>`;
  }

  function openCombustibleModal(mov = null) {
    const modal = $("#modal-combustible");
    if (!modal) return;
    const today = modal.dataset.today || new Date().toISOString().slice(0, 10);
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${mov ? "Editar movimiento" : "Nuevo movimiento de combustible"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-comb">Cerrar</button>
        </div>
        <form id="form-combustible" class="form-grid">
          <div class="field">
            <label>Tipo</label>
            <select name="tipo" required>
              <option value="ingreso" ${!mov || mov?.tipo === "ingreso" ? "selected" : ""}>Ingreso (galones)</option>
              <option value="salida" ${mov?.tipo === "salida" ? "selected" : ""}>Salida (galones)</option>
            </select>
          </div>
          <div class="field">
            <label>Galones</label>
            <input name="galones" type="number" min="0.001" step="0.001" required value="${mov?.galones ?? ""}" placeholder="0.000" />
          </div>
          <div class="field">
            <label>Fecha</label>
            <input name="fecha" type="date" required value="${mov?.fecha || today}" />
          </div>
          <div class="field">
            <label>Conductor</label>
            <input name="conductor" required maxlength="150" value="${escapeHtml(mov?.conductor || "")}" placeholder="Nombre del conductor" />
          </div>
          <div class="field">
            <label>Marca del vehículo</label>
            <input name="marca" maxlength="80" value="${escapeHtml(mov?.marca || "")}" placeholder="Ej. Volvo, Toyota" />
          </div>
          <div class="field">
            <label>Placa</label>
            <input name="placa" maxlength="20" value="${escapeHtml(mov?.placa || "")}" placeholder="ABC-123" style="text-transform:uppercase" />
          </div>
          <div class="field full">
            <label>Notas (opcional)</label>
            <input name="notas" maxlength="300" value="${escapeHtml(mov?.notas || "")}" placeholder="Detalle adicional" />
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">${mov ? "Guardar" : "Registrar"}</button>
          </div>
        </form>
      </div>`;
    $("#close-comb").onclick = () => modal.classList.remove("open");
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.remove("open");
    };
    $("#form-combustible").onsubmit = async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      body.galones = Number(body.galones);
      body.marca = (body.marca || "").trim() || null;
      body.placa = (body.placa || "").trim().toUpperCase() || null;
      body.notas = (body.notas || "").trim() || null;
      try {
        if (mov) await API.updateCombustible(mov.id, body);
        else await API.createCombustible(body);
        toast(mov ? "Movimiento actualizado" : "Movimiento registrado");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  function openCajaModal(caja = null) {
    const modal = $("#modal-caja");
    if (!modal) return;
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${caja ? "Editar caja" : "Nueva caja"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-caja">Cerrar</button>
        </div>
        <form id="form-caja" class="form-grid">
          <div class="field full">
            <label>Nombre</label>
            <input name="nombre" required maxlength="120" value="${escapeHtml(caja?.nombre || "")}" placeholder="Ej. Caja principal, Yape, BCP" />
          </div>
          <div class="field full">
            <label>Descripción (opcional)</label>
            <input name="descripcion" maxlength="250" value="${escapeHtml(caja?.descripcion || "")}" placeholder="Detalle de la caja" />
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">${caja ? "Guardar" : "Crear caja"}</button>
          </div>
        </form>
      </div>`;
    $("#close-caja").onclick = () => modal.classList.remove("open");
    $("#form-caja").onsubmit = async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      try {
        if (caja) await API.updateCaja(caja.id, body);
        else await API.createCaja(body);
        toast(caja ? "Caja actualizada" : "Caja creada");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  function openMovimientoModal(mov = null) {
    const modal = $("#modal-mov");
    if (!modal) return;
    if (!state.cajas.length) {
      toast("Primero crea una caja");
      return openCajaModal();
    }
    const today = modal.dataset.today || new Date().toISOString().slice(0, 10);
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${mov ? "Editar movimiento" : "Nuevo movimiento"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-mov">Cerrar</button>
        </div>
        <form id="form-mov" class="form-grid">
          <div class="field">
            <label>Caja</label>
            <select name="caja_id" required>
              ${state.cajas
                .map(
                  (c) =>
                    `<option value="${c.id}" ${String(mov?.caja_id || state.filtersCaja.caja_id) === String(c.id) ? "selected" : ""}>${escapeHtml(c.nombre)}</option>`
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>Tipo</label>
            <select name="tipo" required>
              <option value="ingreso" ${!mov || mov?.tipo === "ingreso" ? "selected" : ""}>Ingreso</option>
              <option value="egreso" ${mov?.tipo === "egreso" ? "selected" : ""}>Egreso</option>
            </select>
          </div>
          <div class="field">
            <label>Monto (S/)</label>
            <input name="monto" type="number" min="0.01" step="0.01" required value="${mov?.monto ?? ""}" placeholder="0.00" />
          </div>
          <div class="field">
            <label>Fecha</label>
            <input name="fecha" type="date" required value="${mov?.fecha || today}" />
          </div>
          <div class="field">
            <label>N° de transacción</label>
            <input name="numero_transaccion" maxlength="80" value="${escapeHtml(mov?.numero_transaccion || "")}" placeholder="Ej. OP-123456, Yape ref." />
          </div>
          <div class="field full">
            <label>Concepto de transacción</label>
            <input name="concepto" required maxlength="300" value="${escapeHtml(mov?.concepto || "")}" placeholder="Ej. Venta del día, pago proveedor, transferencia" />
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">${mov ? "Guardar" : "Registrar movimiento"}</button>
          </div>
        </form>
      </div>`;
    $("#close-mov").onclick = () => modal.classList.remove("open");
    $("#form-mov").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.caja_id = Number(body.caja_id);
      body.monto = Number(body.monto);
      body.numero_transaccion = (body.numero_transaccion || "").trim() || null;
      try {
        if (mov) await API.updateMovimientoCaja(mov.id, body);
        else await API.createMovimientoCaja(body);
        toast(mov ? "Movimiento actualizado" : "Movimiento registrado");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  function openClienteModal(cliente = null) {
    const modal = $("#modal-cliente");
    if (!modal) return;
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${cliente ? "Editar cliente" : "Nuevo cliente"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-cli">Cerrar</button>
        </div>
        <form id="form-cliente" class="form-grid">
          <div class="field full">
            <label>Nombre / Razón social</label>
            <input name="nombre" required value="${escapeHtml(cliente?.nombre || "")}" />
          </div>
          <div class="field">
            <label>Tipo doc.</label>
            <select name="tipo_documento">
              ${["RUC", "DNI", "CE", "OTRO"]
                .map((t) => `<option value="${t}" ${cliente?.tipo_documento === t ? "selected" : ""}>${t}</option>`)
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>RUC / DNI</label>
            <input name="documento" value="${escapeHtml(cliente?.documento || "")}" />
          </div>
          <div class="field">
            <label>Email</label>
            <input name="email" type="email" value="${escapeHtml(cliente?.email || "")}" />
          </div>
          <div class="field">
            <label>Teléfono</label>
            <input name="telefono" value="${escapeHtml(cliente?.telefono || "")}" />
          </div>
          <div class="field full">
            <label>Dirección</label>
            <input name="direccion" value="${escapeHtml(cliente?.direccion || "")}" />
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">Guardar</button>
          </div>
        </form>
      </div>`;
    $("#close-cli").onclick = () => modal.classList.remove("open");
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.remove("open");
    };
    $("#form-cliente").onsubmit = async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      try {
        if (cliente) await API.updateCliente(cliente.id, body);
        else await API.createCliente(body);
        toast("Cliente guardado");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  function openContactoModal(contacto = null) {
    const modal = $("#modal-contacto");
    if (!modal) return;
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${contacto ? "Editar contacto" : "Nuevo contacto"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-ct">Cerrar</button>
        </div>
        <form id="form-contacto" class="form-grid">
          <div class="field full">
            <label>Nombre</label>
            <input name="nombre" required maxlength="200" value="${escapeHtml(contacto?.nombre || "")}" placeholder="Nombre completo" />
          </div>
          <div class="field">
            <label>Teléfono</label>
            <input name="telefono" maxlength="40" value="${escapeHtml(contacto?.telefono || "")}" placeholder="999888777" inputmode="tel" />
          </div>
          <div class="field">
            <label>Teléfono alterno</label>
            <input name="telefono_alt" maxlength="40" value="${escapeHtml(contacto?.telefono_alt || "")}" placeholder="Opcional" inputmode="tel" />
          </div>
          <div class="field">
            <label>Email</label>
            <input name="email" type="email" maxlength="180" value="${escapeHtml(contacto?.email || "")}" />
          </div>
          <div class="field">
            <label>Empresa</label>
            <input name="empresa" maxlength="200" value="${escapeHtml(contacto?.empresa || "")}" />
          </div>
          <div class="field full">
            <label>Notas</label>
            <input name="notas" maxlength="500" value="${escapeHtml(contacto?.notas || "")}" placeholder="Referencia, cargo, etc." />
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">Guardar</button>
          </div>
        </form>
      </div>`;
    $("#close-ct").onclick = () => modal.classList.remove("open");
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.remove("open");
    };
    $("#form-contacto").onsubmit = async (e) => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(e.target).entries());
      body.origen = contacto?.origen || "manual";
      try {
        if (contacto) await API.updateContacto(contacto.id, body);
        else await API.createContacto(body);
        toast("Contacto guardado");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  function openProductoModal(producto = null) {
    const modal = $("#modal-producto");
    if (!modal) return;
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${producto ? "Editar producto/servicio" : "Nuevo producto/servicio"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-prod">Cerrar</button>
        </div>
        <form id="form-producto" class="form-grid">
          <div class="field full">
            <label>Nombre / descripción</label>
            <input name="nombre" required value="${escapeHtml(producto?.nombre || "")}" />
          </div>
          <div class="field">
            <label>Tipo</label>
            <select name="tipo">
              <option value="producto" ${producto?.tipo !== "servicio" ? "selected" : ""}>Producto</option>
              <option value="servicio" ${producto?.tipo === "servicio" ? "selected" : ""}>Servicio</option>
            </select>
          </div>
          <div class="field">
            <label>Código (opcional)</label>
            <input name="codigo" value="${escapeHtml(producto?.codigo || "")}" />
          </div>
          <div class="field">
            <label>Unidad</label>
            <input name="unidad" value="${escapeHtml(producto?.unidad || "NIU")}" />
          </div>
          <div class="field">
            <label>Precio unitario</label>
            <input name="precio_unitario" type="number" min="0" step="0.01" required value="${producto?.precio_unitario ?? 0}" />
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">Guardar</button>
          </div>
        </form>
      </div>`;
    $("#close-prod").onclick = () => modal.classList.remove("open");
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.remove("open");
    };
    $("#form-producto").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.precio_unitario = Number(body.precio_unitario);
      try {
        if (producto) await API.updateProducto(producto.id, body);
        else await API.createProducto(body);
        toast("Producto guardado");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  async function viewRecordatorios() {
    state.notifs = await API.listNotificaciones();
    const pendientes = await API.listComprobantes({ estado: "no_pagado" });
    const agendas = await API.listAgenda({ pendientes: "true" });
    let prefs = { telegram_chat_id: "", notificar_email: true };
    try {
      prefs = await API.obtenerPreferencias();
    } catch (_) {
      /* ignore */
    }
    return `
      <div class="page-head">
        <div>
          <h1>Recordatorios</h1>
          <p>Para recibir avisos aunque cierres la página, activa las notificaciones del navegador (Web Push).</p>
        </div>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap">
          <button class="btn btn-primary" id="btn-enable-push">Activar avisos en segundo plano</button>
          <button class="btn btn-secondary" id="btn-check-now">Revisar avisos ahora</button>
          <button class="btn btn-accent" id="btn-test-push">Probar aviso</button>
        </div>
      </div>
      <div class="panel" style="margin-bottom:1rem">
        <h3 style="margin:0 0 .4rem;font-family:var(--font-display)">Cómo deberían verse</h3>
        <p style="margin:0;color:var(--muted);font-size:.92rem;line-height:1.5">
          <strong>Celular:</strong> el aviso debe vibrar y aparecer como banner (no solo en el historial).
          Si llega en silencio: Ajustes → Apps → Chrome (o Agenda Facturas) → Notificaciones →
          activa <em>Alertas / Sonido</em> para este sitio (no «Silencioso»).
          Instala la PWA (menú Chrome → «Instalar app» / «Agregar a inicio»).<br><br>
          <strong>PC:</strong> hay que pulsar <em>Activar avisos</em> también en Chrome de la PC
          (cada dispositivo tiene su propia suscripción). Desactiva «No molestar» / Focus Assist de Windows.
          En Chrome: candado de la URL → Notificaciones → Permitir.<br><br>
          Si aun así sigue llegando en silencio, el navegador/SO está fuera de tu control — activa
          también <strong>Telegram</strong> abajo: no depende de canales de notificación ni de que la
          app esté abierta, y siempre suena.
        </p>
      </div>
      <div class="panel" style="margin-bottom:1rem">
        <h3 style="margin:0 0 .4rem;font-family:var(--font-display)">Activación</h3>
        <p style="margin:0;color:var(--muted);font-size:.92rem;line-height:1.45">
          1) Pulsa <strong>Activar avisos en segundo plano</strong> y acepta el permiso.<br>
          2) Debe decir <strong>Push OK</strong> y llegar una prueba con sonido/vibración.<br>
          3) Repite este paso en cada celular y en la PC donde quieras recibir avisos.
        </p>
      </div>
      <div class="panel" style="margin-bottom:1rem">
        <h3 style="margin:0 0 .4rem;font-family:var(--font-display)">Aviso por Telegram (recomendado)</h3>
        <p style="margin:0 0 .6rem;color:var(--muted);font-size:.92rem;line-height:1.45">
          1) Abre Telegram y busca <strong>@userinfobot</strong>, mándale cualquier mensaje.<br>
          2) Copia el número <strong>Id</strong> que te responde.<br>
          3) Pégalo aquí y guarda. Telegram avisa con sonido aunque la app esté cerrada.
        </p>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center">
          <input id="input-telegram-chat" placeholder="Tu chat_id de Telegram" value="${escapeHtml(prefs.telegram_chat_id || "")}" style="flex:1;min-width:180px" />
          <button class="btn btn-primary" id="btn-save-telegram">Guardar Telegram</button>
          <button class="btn btn-secondary" id="btn-test-telegram">Probar Telegram</button>
        </div>
        <label style="display:flex;gap:.5rem;align-items:center;margin-top:.8rem;font-size:.92rem">
          <input type="checkbox" id="chk-notif-email" ${prefs.notificar_email ? "checked" : ""} />
          También avisarme por email a ${escapeHtml(state.user?.email || "")}
        </label>
      </div>
      <div class="grid-stats">
        <div class="stat warn"><label>Docs. no pagados</label><strong>${pendientes.length}</strong></div>
        <div class="stat"><label>Agendas próximas</label><strong>${agendas.length}</strong></div>
        <div class="stat"><label>Notificaciones</label><strong>${state.notifs.length}</strong></div>
        <div class="stat ok"><label>No leídas</label><strong>${state.notifs.filter((n) => !n.leida).length}</strong></div>
      </div>
      <div class="charts">
        <div class="panel">
          <h3>Documentos pendientes de pago</h3>
          ${
            pendientes.length
              ? `<div class="table-wrap"><table><thead><tr><th>Documento</th><th>Cliente</th><th>Vence</th><th>Total</th></tr></thead><tbody>
                ${pendientes
                  .map(
                    (d) => `<tr>
                    <td>${d.serie}-${d.numero}</td>
                    <td>${escapeHtml(d.cliente_nombre)}</td>
                    <td>${d.fecha_vencimiento ? fmtDate(d.fecha_vencimiento) : "—"}</td>
                    <td>${money(d.total)}</td>
                  </tr>`
                  )
                  .join("")}
              </tbody></table></div>`
              : `<div class="empty"><p>No hay documentos pendientes 🎉</p></div>`
          }
        </div>
        <div class="panel">
          <h3>Agendas pendientes</h3>
          ${
            agendas.length
              ? agendas
                  .map(
                    (a) => `<div class="notif-item">
                    <strong>${escapeHtml(a.titulo)}</strong>
                    <p>${agendaLabel(a.tipo)} · ${fmtDateTime(a.fecha_inicio)}</p>
                  </div>`
                  )
                  .join("")
              : `<div class="empty"><p>Sin agendas pendientes</p></div>`
          }
        </div>
      </div>`;
  }

  /* ---------- Modals helpers ---------- */
  function openAgendaModal(agenda = null, prefill = null) {
    const modal = $("#modal-agenda");
    if (!modal) return;
    const draft = prefill || state.draftFromContact;
    const start = agenda?.fecha_inicio
      ? agenda.fecha_inicio.slice(0, 16)
      : new Date(Date.now() + 3600000).toISOString().slice(0, 16);
    const tituloDefault = agenda?.titulo || (draft ? `Reunión con ${draft.nombre}` : "");
    const participantesDefault =
      agenda?.participantes ||
      (draft
        ? [draft.nombre, draft.telefono || draft.telefono_alt, draft.email].filter(Boolean).join(" · ")
        : "");
    if (draft && !agenda) state.draftFromContact = null;
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head">
          <h2>${agenda ? "Editar evento" : "Nuevo evento"}</h2>
          <button class="btn btn-ghost btn-sm" id="close-agenda">Cerrar</button>
        </div>
        <form id="form-agenda" class="form-grid">
          <div class="field">
            <label>Tipo</label>
            <select name="tipo" required>
              ${(state.meta?.tipos_agenda || [])
                .map((t) => `<option value="${t.value}" ${agenda?.tipo === t.value ? "selected" : ""}>${t.label}</option>`)
                .join("")}
            </select>
          </div>
          <div class="field">
            <label>Recordatorio (minutos antes)</label>
            <input type="number" name="recordatorio_minutos" min="0" value="${agenda?.recordatorio_minutos ?? 30}" />
          </div>
          <div class="field full">
            <label>Título</label>
            <input name="titulo" required value="${escapeHtml(tituloDefault)}" />
          </div>
          <div class="field">
            <label>Inicio</label>
            <input type="datetime-local" name="fecha_inicio" required value="${start}" />
          </div>
          <div class="field">
            <label>Fin</label>
            <input type="datetime-local" name="fecha_fin" value="${agenda?.fecha_fin ? agenda.fecha_fin.slice(0, 16) : ""}" />
          </div>
          <div class="field full">
            <label>Ubicación</label>
            <input name="ubicacion" value="${escapeHtml(agenda?.ubicacion || "")}" placeholder="Oficina, Zoom, dirección..." />
          </div>
          <div class="field full">
            <label>Participantes</label>
            <input name="participantes" value="${escapeHtml(participantesDefault)}" />
          </div>
          <div class="field full">
            <label>Descripción detallada</label>
            <textarea name="descripcion" rows="4">${escapeHtml(agenda?.descripcion || "")}</textarea>
          </div>
          <div class="field full">
            <button class="btn btn-primary" type="submit">Guardar</button>
          </div>
        </form>
      </div>`;
    $("#close-agenda").onclick = () => modal.classList.remove("open");
    modal.onclick = (e) => {
      if (e.target === modal) modal.classList.remove("open");
    };
    $("#form-agenda").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      body.recordatorio_minutos = Number(body.recordatorio_minutos || 30);
      if (!body.fecha_fin) delete body.fecha_fin;
      try {
        if (agenda) await API.updateAgenda(agenda.id, body);
        else await API.createAgenda(body);
        toast("Agenda guardada");
        modal.classList.remove("open");
        renderApp();
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  async function openShareModal(docId, mode) {
    let modal = $("#modal-share");
    if (!modal) {
      modal = document.createElement("div");
      modal.className = "modal-backdrop";
      modal.id = "modal-share";
      document.body.appendChild(modal);
    }
    modal.classList.add("open");
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head"><h2>${mode === "mail" ? "Enviar por correo" : "Compartir por WhatsApp"}</h2><button class="btn btn-ghost btn-sm" id="x">Cerrar</button></div>
        <div class="empty" style="padding:1.2rem"><p>Cargando agenda…</p></div>
      </div>`;
    $("#x").onclick = () => modal.classList.remove("open");

    let contactos = state.contactos || [];
    try {
      contactos = await API.listContactos();
      state.contactos = contactos;
    } catch (_) {
      /* keep cached */
    }

    const doc = (state.docs || []).find((d) => String(d.id) === String(docId));
    const defaultTel = doc?.cliente_telefono || "";
    const defaultEmail = doc?.cliente_email || "";

    if (mode === "mail") {
      const conEmail = contactos.filter((c) => c.email);
      modal.innerHTML = `
        <div class="modal">
          <div class="modal-head"><h2>Enviar por correo</h2><button class="btn btn-ghost btn-sm" id="x">Cerrar</button></div>
          <form id="form-mail" class="form-grid">
            <div class="field full">
              <label>Agenda de contactos</label>
              <select id="share-contacto">
                <option value="">Seleccionar contacto…</option>
                ${conEmail
                  .map(
                    (c) =>
                      `<option value="${escapeHtml(c.email)}" data-nombre="${escapeHtml(c.nombre)}">${escapeHtml(c.nombre)} — ${escapeHtml(c.email)}</option>`
                  )
                  .join("")}
              </select>
              ${
                conEmail.length
                  ? ""
                  : `<small class="field-hint">No hay contactos con email. Agrégalos en Agenda tel.</small>`
              }
            </div>
            <div class="field full"><label>Correo del destinatario</label><input type="email" name="email" id="share-email" required value="${escapeHtml(defaultEmail)}" list="lista-emails-share" /></div>
            <datalist id="lista-emails-share">
              ${conEmail.map((c) => `<option value="${escapeHtml(c.email)}">${escapeHtml(c.nombre)}</option>`).join("")}
            </datalist>
            <div class="field full"><label>Mensaje (opcional)</label><textarea name="mensaje" rows="3"></textarea></div>
            <div class="field full"><button class="btn btn-primary" type="submit">Enviar PDF</button></div>
          </form>
        </div>`;
      $("#x").onclick = () => modal.classList.remove("open");
      $("#share-contacto")?.addEventListener("change", (e) => {
        const email = e.target.value;
        if (email) $("#share-email").value = email;
      });
      $("#form-mail").onsubmit = async (e) => {
        e.preventDefault();
        const body = Object.fromEntries(new FormData(e.target).entries());
        try {
          await API.emailComprobante(docId, body);
          toast("Correo enviado");
          modal.classList.remove("open");
        } catch (ex) {
          toast(ex.message);
        }
      };
      return;
    }

    const conTel = contactos.filter((c) => c.telefono || c.telefono_alt);
    modal.innerHTML = `
      <div class="modal">
        <div class="modal-head"><h2>Compartir por WhatsApp</h2><button class="btn btn-ghost btn-sm" id="x">Cerrar</button></div>
        <form id="form-wa" class="form-grid">
          <div class="field full">
            <label>Agenda de contactos</label>
            <select id="share-contacto">
              <option value="">Seleccionar contacto…</option>
              ${conTel
                .map((c) => {
                  const tel = c.telefono || c.telefono_alt || "";
                  return `<option value="${escapeHtml(tel)}" data-nombre="${escapeHtml(c.nombre)}">${escapeHtml(c.nombre)} — ${escapeHtml(tel)}</option>`;
                })
                .join("")}
            </select>
            ${
              conTel.length
                ? `<small class="field-hint">Elige un contacto o escribe el número abajo.</small>`
                : `<small class="field-hint">Sin contactos con teléfono. Ve a <strong>Agenda tel.</strong> o escribe el número.</small>`
            }
          </div>
          <div class="field full">
            <label>Celular (9 dígitos Perú, opcional)</label>
            <input name="telefono" id="share-tel" placeholder="999888777" value="${escapeHtml(defaultTel)}" list="lista-tels-share" inputmode="tel" />
            <datalist id="lista-tels-share">
              ${conTel
                .map((c) => {
                  const tel = c.telefono || c.telefono_alt || "";
                  return `<option value="${escapeHtml(tel)}">${escapeHtml(c.nombre)}</option>`;
                })
                .join("")}
            </datalist>
          </div>
          <div class="field full"><button class="btn btn-accent" type="submit">Abrir WhatsApp</button></div>
        </form>
      </div>`;
    $("#x").onclick = () => modal.classList.remove("open");
    $("#share-contacto")?.addEventListener("change", (e) => {
      const tel = e.target.value;
      if (tel) $("#share-tel").value = tel.replace(/\D/g, "").slice(-9) || tel;
    });
    $("#form-wa").onsubmit = async (e) => {
      e.preventDefault();
      const tel = new FormData(e.target).get("telefono");
      try {
        const data = await API.whatsappComprobante(docId, tel);
        window.open(data.url, "_blank");
        modal.classList.remove("open");
      } catch (ex) {
        toast(ex.message);
      }
    };
  }

  /* ---------- Bind per view ---------- */
  function bindView() {
    $$("[data-go]").forEach((b) => b.addEventListener("click", () => navigate(b.dataset.go)));

    if (state.route === "comprobantes") {
      $("#btn-filtrar")?.addEventListener("click", () => {
        state.filters.q = $("#f-q").value.trim();
        state.filters.estado = $("#f-estado").value;
        state.filters.tipo = $("#f-tipo").value;
        state.filters.zona = $("#f-zona")?.value || "";
        state.filters.fecha_desde = $("#f-desde")?.value || "";
        state.filters.fecha_hasta = $("#f-hasta")?.value || "";
        renderApp();
      });
      $("#btn-limpiar-filtros")?.addEventListener("click", () => {
        state.filters = { q: "", estado: "", tipo: "", zona: "", fecha_desde: "", fecha_hasta: "" };
        renderApp();
      });
      $$("[data-edit]").forEach((b) =>
        b.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          const id = b.getAttribute("data-edit");
          if (!id) return;
          navigate("nuevo", `id=${id}`);
        })
      );
      $$("[data-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este comprobante?")) return;
          await API.deleteComprobante(b.dataset.del);
          toast("Eliminado");
          renderApp();
        })
      );
      $$("[data-pdf]").forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            const blob = await API.pdfComprobante(b.dataset.pdf);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `comprobante-${b.dataset.pdf}.pdf`;
            a.click();
            URL.revokeObjectURL(url);
          } catch (ex) {
            toast(ex.message);
          }
        })
      );
      $$("[data-mail]").forEach((b) =>
        b.addEventListener("click", () => openShareModal(b.dataset.mail, "mail"))
      );
      $$("[data-wa]").forEach((b) =>
        b.addEventListener("click", () => openShareModal(b.dataset.wa, "wa"))
      );
      $$("[data-estado-id]").forEach((sel) => {
        sel.addEventListener("change", async () => {
          const id = sel.getAttribute("data-estado-id");
          const estado = sel.value;
          const prev = [...sel.classList].find((c) =>
            ["emitido", "pagado", "no_pagado", "anulado"].includes(c)
          );
          sel.disabled = true;
          try {
            await API.cambiarEstado(id, estado);
            sel.classList.remove("emitido", "pagado", "no_pagado", "anulado");
            sel.classList.add(estado);
            toast(`Estado: ${estadoLabel(estado)}`);
          } catch (ex) {
            if (prev) sel.value = prev;
            toast(ex.message || "No se pudo cambiar el estado");
          } finally {
            sel.disabled = false;
          }
        });
      });
    }

    if (state.route === "nuevo") {
      const tipo = $("#c-tipo");
      tipo?.addEventListener("change", () => {
        const opt = tipo.selectedOptions[0];
        if (opt && !state.editingDoc) $("#c-serie").value = opt.dataset.serie || "F001";
        syncItemIgvControls();
        recalcItems();
      });
      $("#btn-add-item")?.addEventListener("click", () => {
        $("#items-editor").insertAdjacentHTML("beforeend", itemRowHtml(1));
        bindItemEvents();
      });
      $("#btn-buscar-sunat")?.addEventListener("click", () => buscarSunat());
      $("#c-documento")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          buscarSunat();
        }
      });
      $("#c-documento")?.addEventListener("change", fillClienteFromCatalog);
      $("#c-cliente")?.addEventListener("change", fillClienteFromCatalog);
      bindItemEvents();
      syncItemIgvControls();
      recalcItems();
      $("#form-comprobante")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const body = Object.fromEntries(fd.entries());
        if (!body.fecha_vencimiento) body.fecha_vencimiento = null;
        body.zona = (body.zona || "").trim() || null;
        body.motivo = (body.motivo || "").trim() || null;
        body.observaciones = (body.observaciones || "").trim() || null;
        const permiteIgv = tipoPermiteIgv(body.tipo);
        body.items = $$("[data-item]").map((row) => ({
          descripcion: $('[data-k="descripcion"]', row).value,
          cantidad: Number($('[data-k="cantidad"]', row).value),
          precio_unitario: Number($('[data-k="precio_unitario"]', row).value),
          unidad: "NIU",
          aplica_igv: permiteIgv && Boolean($('[data-k="aplica_igv"]', row)?.checked),
        }));
        try {
          if (state.editingDoc) {
            await API.updateComprobante(state.editingDoc.id, body);
            toast("Comprobante actualizado");
          } else {
            await API.createComprobante(body);
            toast("Comprobante registrado");
          }
          state.editingDoc = null;
          navigate("comprobantes");
        } catch (ex) {
          toast(ex.message);
        }
      });
    }

    if (state.route === "agenda") {
      $("#btn-new-agenda")?.addEventListener("click", () => openAgendaModal());
      $$("[data-a-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const ag = state.agendas.find((a) => a.id === Number(b.dataset.aEdit));
          openAgendaModal(ag);
        })
      );
      $$("[data-a-done]").forEach((b) =>
        b.addEventListener("click", async () => {
          const ag = state.agendas.find((a) => a.id === Number(b.dataset.aDone));
          await API.updateAgenda(ag.id, { completado: !ag.completado });
          renderApp();
        })
      );
      $$("[data-a-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este evento?")) return;
          await API.deleteAgenda(b.dataset.aDel);
          toast("Evento eliminado");
          renderApp();
        })
      );
    }

    if (state.route === "recordatorios") {
      $("#btn-enable-push")?.addEventListener("click", () =>
        enablePush().catch((e) => toast(e.message))
      );
      $("#btn-check-now")?.addEventListener("click", async () => {
        try {
          await API.procesarRecordatorios();
          await pollNotificaciones(true);
          toast("Avisos revisados");
          renderApp();
        } catch (ex) {
          toast(ex.message);
        }
      });
      $("#btn-test-push")?.addEventListener("click", async () => {
        try {
          if (localStorage.getItem("af_push_ok") !== "1") {
            await enablePush();
            return;
          }
          const prueba = await API.probarPush();
          toast(prueba.mensaje || "Prueba enviada");
        } catch (ex) {
          toast(ex.message);
        }
      });
      $("#btn-save-telegram")?.addEventListener("click", async () => {
        try {
          const chatId = $("#input-telegram-chat")?.value.trim() || null;
          const notificarEmail = $("#chk-notif-email")?.checked ?? true;
          await API.guardarPreferencias({ telegram_chat_id: chatId, notificar_email: notificarEmail });
          toast("Preferencias guardadas");
        } catch (ex) {
          toast(ex.message);
        }
      });
      $("#btn-test-telegram")?.addEventListener("click", async () => {
        try {
          const prueba = await API.probarTelegram();
          toast(prueba.mensaje || "Prueba enviada");
        } catch (ex) {
          toast(ex.message);
        }
      });
      $("#chk-notif-email")?.addEventListener("change", async (e) => {
        try {
          const chatId = $("#input-telegram-chat")?.value.trim() || null;
          await API.guardarPreferencias({ telegram_chat_id: chatId, notificar_email: e.target.checked });
          toast("Preferencias guardadas");
        } catch (ex) {
          toast(ex.message);
        }
      });
    }

    if (state.route === "clientes") {
      $("#btn-new-cliente")?.addEventListener("click", () => openClienteModal());
      $$("[data-cli-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const cli = state.clientes.find((c) => c.id === Number(b.dataset.cliEdit));
          openClienteModal(cli);
        })
      );
      $$("[data-cli-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este cliente del catálogo?")) return;
          await API.deleteCliente(b.dataset.cliDel);
          toast("Cliente eliminado");
          renderApp();
        })
      );
    }

    if (state.route === "contactos") {
      $("#btn-new-contacto")?.addEventListener("click", () => openContactoModal());
      $("#btn-filtrar-contacto")?.addEventListener("click", () => {
        state.filtersContacto.q = ($("#f-contacto-q")?.value || "").trim();
        renderApp();
      });
      $("#btn-sync-phone")?.addEventListener("click", async () => {
        try {
          const picked = await pickPhoneContacts();
          if (!picked.length) return toast("No se seleccionaron contactos");
          const res = await API.importarContactos(picked);
          toast(`Importados: ${res.creados} nuevos, ${res.actualizados} actualizados`);
          renderApp();
        } catch (ex) {
          if (String(ex.name || "").includes("Abort") || String(ex.message || "").includes("cancel")) {
            return;
          }
          toast(ex.message || String(ex));
        }
      });
      $$("[data-ct-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const ct = state.contactos.find((c) => c.id === Number(b.dataset.ctEdit));
          openContactoModal(ct);
        })
      );
      $$("[data-ct-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este contacto?")) return;
          await API.deleteContacto(b.dataset.ctDel);
          toast("Contacto eliminado");
          renderApp();
        })
      );
      $$("[data-ct-cliente]").forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            const cli = await API.contactoACliente(b.dataset.ctCliente);
            toast(`Cliente creado/actualizado: ${cli.nombre}`);
            renderApp();
          } catch (ex) {
            toast(ex.message);
          }
        })
      );
      $$("[data-ct-factura]").forEach((b) =>
        b.addEventListener("click", () => {
          const ct = state.contactos.find((c) => c.id === Number(b.dataset.ctFactura));
          if (!ct) return;
          state.draftFromContact = {
            nombre: ct.nombre,
            telefono: ct.telefono || ct.telefono_alt || "",
            email: ct.email || "",
          };
          location.hash = "#/nuevo";
        })
      );
      $$("[data-ct-agenda]").forEach((b) =>
        b.addEventListener("click", async () => {
          const ct = state.contactos.find((c) => c.id === Number(b.dataset.ctAgenda));
          if (!ct) return;
          state.draftFromContact = ct;
          location.hash = "#/agenda";
          await renderApp();
          openAgendaModal(null, ct);
        })
      );
    }

    if (state.route === "productos") {
      $("#btn-new-producto")?.addEventListener("click", () => openProductoModal());
      $$("[data-prod-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const prod = state.productos.find((p) => p.id === Number(b.dataset.prodEdit));
          openProductoModal(prod);
        })
      );
      $$("[data-prod-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este producto del catálogo?")) return;
          await API.deleteProducto(b.dataset.prodDel);
          toast("Producto eliminado");
          renderApp();
        })
      );
    }

    if (state.route === "cajas") {
      $("#btn-new-caja")?.addEventListener("click", () => openCajaModal());
      $("#btn-new-mov")?.addEventListener("click", () => openMovimientoModal());
      $("#btn-filtrar-caja")?.addEventListener("click", () => {
        state.filtersCaja.q = ($("#f-caja-q")?.value || "").trim();
        state.filtersCaja.caja_id = $("#f-caja-id")?.value || "";
        state.filtersCaja.tipo = $("#f-caja-tipo")?.value || "";
        state.filtersCaja.fecha_desde = $("#f-caja-desde")?.value || "";
        state.filtersCaja.fecha_hasta = $("#f-caja-hasta")?.value || "";
        renderApp();
      });
      $("#btn-caja-mes")?.addEventListener("click", () => {
        const d = defaultCajaDates();
        state.filtersCaja.fecha_desde = d.desde;
        state.filtersCaja.fecha_hasta = d.hasta;
        renderApp();
      });
      $$("[data-caja-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const caja = state.cajas.find((c) => c.id === Number(b.dataset.cajaEdit));
          openCajaModal(caja);
        })
      );
      $$("[data-caja-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Archivar esta caja? Los movimientos se conservan.")) return;
          await API.deleteCaja(b.dataset.cajaDel);
          toast("Caja archivada");
          renderApp();
        })
      );
      $$("[data-mov-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const mov = state.movimientosCaja.find((m) => m.id === Number(b.dataset.movEdit));
          openMovimientoModal(mov);
        })
      );
      $$("[data-mov-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este movimiento?")) return;
          await API.deleteMovimientoCaja(b.dataset.movDel);
          toast("Movimiento eliminado");
          renderApp();
        })
      );
    }

    if (state.route === "combustibles") {
      $("#btn-new-combustible")?.addEventListener("click", () => openCombustibleModal());
      $("#btn-filtrar-comb")?.addEventListener("click", () => {
        state.filtersCombustible.tipo = $("#f-comb-tipo")?.value || "";
        state.filtersCombustible.q = ($("#f-comb-q")?.value || "").trim();
        state.filtersCombustible.fecha_desde = $("#f-comb-desde")?.value || "";
        state.filtersCombustible.fecha_hasta = $("#f-comb-hasta")?.value || "";
        renderApp();
      });
      $("#btn-limpiar-comb")?.addEventListener("click", () => {
        state.filtersCombustible = { tipo: "", q: "", fecha_desde: "", fecha_hasta: "" };
        renderApp();
      });
      $$("[data-comb-edit]").forEach((b) =>
        b.addEventListener("click", () => {
          const mov = state.combustibles.find((m) => m.id === Number(b.dataset.combEdit));
          openCombustibleModal(mov);
        })
      );
      $$("[data-comb-del]").forEach((b) =>
        b.addEventListener("click", async () => {
          if (!confirm("¿Eliminar este movimiento de combustible?")) return;
          await API.deleteCombustible(b.dataset.combDel);
          toast("Movimiento eliminado");
          renderApp();
        })
      );
    }
  }

  function bindItemEvents() {
    $$(".btn-remove-item").forEach((btn) => {
      btn.onclick = () => {
        if ($$("[data-item]").length <= 1) return toast("Debe haber al menos un ítem");
        btn.closest("[data-item]").remove();
        recalcItems();
      };
    });
    $$("[data-item] input").forEach((inp) => {
      inp.oninput = recalcItems;
      inp.onchange = recalcItems;
      if (inp.dataset.k === "descripcion") {
        inp.addEventListener("change", () => {
          const prod = state.productos.find(
            (p) => p.nombre.toLowerCase() === (inp.value || "").trim().toLowerCase()
          );
          if (!prod) return;
          const row = inp.closest("[data-item]");
          const precio = $('[data-k="precio_unitario"]', row);
          if (precio && Number(precio.value || 0) === 0) precio.value = prod.precio_unitario;
          recalcItems();
        });
      }
    });
  }

  function fillClienteFromCatalog() {
    const nombre = ($("#c-cliente")?.value || "").trim().toLowerCase();
    const doc = ($("#c-documento")?.value || "").trim();
    let cli =
      state.clientes.find((c) => (c.documento || "") === doc) ||
      state.clientes.find((c) => c.nombre.toLowerCase() === nombre);
    if (!cli) return;
    if ($("#c-cliente") && !nombre) $("#c-cliente").value = cli.nombre;
    if ($("#c-documento") && cli.documento) $("#c-documento").value = cli.documento;
    const email = $('input[name="cliente_email"]');
    const tel = $('input[name="cliente_telefono"]');
    if (email && cli.email && !email.value) email.value = cli.email;
    if (tel && cli.telefono && !tel.value) tel.value = cli.telefono;
  }

  async function buscarSunat() {
    const input = $("#c-documento");
    const hint = $("#sunat-hint");
    const btn = $("#btn-buscar-sunat");
    const numero = (input?.value || "").replace(/\D/g, "");
    if (!input || !btn) return;
    if (![8, 11].includes(numero.length)) {
      toast("Ingrese un DNI (8) o RUC (11 dígitos)");
      return;
    }
    input.value = numero;
    btn.disabled = true;
    btn.textContent = "Buscando…";
    if (hint) {
      hint.textContent = "Consultando SUNAT…";
      hint.classList.remove("ok", "err");
    }
    try {
      const data = await API.consultaDocumento(numero);
      const nombre = $("#c-cliente");
      if (nombre && data.nombre) nombre.value = data.nombre;
      const partes = [];
      if (data.tipo) partes.push(data.tipo.toUpperCase());
      if (data.estado) partes.push(data.estado);
      if (data.condicion) partes.push(data.condicion);
      if (data.direccion) partes.push(data.direccion);
      if (hint) {
        hint.textContent = partes.filter(Boolean).join(" · ") || "Datos encontrados";
        hint.classList.add("ok");
      }
      toast("Datos cargados desde SUNAT");
    } catch (ex) {
      if (hint) {
        hint.textContent = ex.message;
        hint.classList.add("err");
      }
      toast(ex.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Buscar";
    }
  }

  /* ---------- Push ---------- */
  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  async function enablePush() {
    if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
      throw new Error(
        "Para avisos fuera de la página necesitas HTTPS. Abre la app desde Railway e instálala como PWA."
      );
    }
    if (!("Notification" in window)) {
      throw new Error("Este navegador no soporta notificaciones");
    }
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      throw new Error("Este navegador no soporta avisos en segundo plano (Web Push)");
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") throw new Error("Permiso de notificaciones denegado");

    localStorage.setItem("af_notif_local", "1");
    localStorage.removeItem("af_push_ok");
    localStorage.removeItem("af_vapid_pub");

    const { publicKey } = await API.vapidKey();
    if (!publicKey) {
      throw new Error("No hay clave VAPID del servidor. Reinicia la aplicación.");
    }

    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    await navigator.serviceWorker.ready;
    if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });

    // Forzar suscripción nueva con la clave pública actual (evita 403 VAPID)
    const existing = await reg.pushManager.getSubscription();
    if (existing) await existing.unsubscribe().catch(() => undefined);

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
    const json = sub.toJSON();
    if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
      throw new Error("No se pudo crear la suscripción push");
    }
    await API.pushSubscribe({
      endpoint: json.endpoint,
      keys: json.keys,
      reemplazar_todas: true,
    });
    localStorage.setItem("af_push_ok", "1");
    localStorage.setItem("af_vapid_pub", publicKey);

    try {
      const prueba = await API.probarPush();
      if (prueba.ok && prueba.enviados > 0) {
        toast("Push OK. Cierra la app por completo: debes ver la prueba.");
      } else {
        toast(prueba.mensaje || "No se envió el push. Reintenta activar avisos.");
        localStorage.removeItem("af_push_ok");
      }
    } catch (ex) {
      toast("Dispositivo registrado, pero la prueba falló: " + ex.message);
      localStorage.removeItem("af_push_ok");
    }
  }

  let lastNotifIds = new Set();
  async function pollNotificaciones(showNative = true) {
    if (!API.getToken()) return;
    try {
      const lista = await API.listNotificaciones();
      const unread = lista.filter((n) => !n.leida);
      const btn = $("#btn-notif");
      if (btn) {
        const pushOk = localStorage.getItem("af_push_ok") === "1";
        btn.textContent = unread.length
          ? `Notificaciones (${unread.length})`
          : pushOk
            ? "Notificaciones ✓"
            : "Notificaciones";
      }
      // Solo mostrar Notification() si la pestaña está abierta; el segundo plano lo hace el Service Worker
      if (
        showNative &&
        document.visibilityState === "visible" &&
        localStorage.getItem("af_notif_local") === "1" &&
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        for (const n of unread) {
          if (lastNotifIds.has(n.id)) continue;
          lastNotifIds.add(n.id);
          try {
            playAlertBeep();
            new Notification(n.titulo, {
              body: n.mensaje,
              icon: "/static/icons/icon-192.png",
              tag: `af-${n.id}`,
            });
          } catch (_) {
            /* ignore */
          }
        }
      } else {
        unread.forEach((n) => lastNotifIds.add(n.id));
      }
      state.notifs = lista;
    } catch (_) {
      /* sesión inválida u offline */
    }
  }

  function startNotifPolling() {
    pollNotificaciones(false);
    setInterval(() => pollNotificaciones(true), 20000);
  }

  async function ensureBackgroundPush() {
    if (!API.getToken()) return;
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
    try {
      const { publicKey } = await API.vapidKey();
      if (!publicKey) return;
      const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      await navigator.serviceWorker.ready;
      const storedKey = localStorage.getItem("af_vapid_pub");
      let sub = await reg.pushManager.getSubscription();
      const keyChanged = !storedKey || storedKey !== publicKey;
      if (!sub || keyChanged) {
        if (sub) await sub.unsubscribe().catch(() => undefined);
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        });
        const json = sub.toJSON();
        if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) return;
        await API.pushSubscribe({
          endpoint: json.endpoint,
          keys: json.keys,
          reemplazar_todas: true,
        });
      } else {
        const json = sub.toJSON();
        await API.pushSubscribe({
          endpoint: json.endpoint,
          keys: json.keys,
          reemplazar_todas: false,
        });
      }
      localStorage.setItem("af_push_ok", "1");
      localStorage.setItem("af_vapid_pub", publicKey);
    } catch (_) {
      localStorage.removeItem("af_push_ok");
    }
  }

  /* ---------- Render ---------- */
  let renderSeq = 0;
  async function renderApp() {
    if (!state.user) return renderAuth();
    const seq = ++renderSeq;
    const { route, params } = parseHash();
    state.route = route;

    if (route !== "nuevo") {
      state.editingDoc = null;
    }

    let html = "";
    try {
      if (state.route === "dashboard") html = await viewDashboard();
      else if (state.route === "comprobantes") html = await viewComprobantes();
      else if (state.route === "clientes") html = await viewClientes();
      else if (state.route === "contactos") html = await viewContactos();
      else if (state.route === "productos") html = await viewProductos();
      else if (state.route === "cajas") html = await viewCajas();
      else if (state.route === "combustibles") html = await viewCombustibles();
      else if (state.route === "nuevo") {
        const editId = params.id ? Number(params.id) : null;
        const [clientes, productos, doc] = await Promise.all([
          API.listClientes(),
          API.listProductos(),
          editId ? API.request(`/api/comprobantes/${editId}`) : Promise.resolve(null),
        ]);
        if (seq !== renderSeq) return;
        state.clientes = clientes;
        state.productos = productos;
        state.editingDoc = doc;
        html = viewNuevoForm(doc);
      } else if (state.route === "agenda") {
        html = await viewAgenda();
        if (state.draftFromContact && !params.id) {
          // Modal se abre tras bindView si venimos de contactos
        }
      } else if (state.route === "recordatorios") html = await viewRecordatorios();
      else html = await viewDashboard();
    } catch (ex) {
      html = `<div class="panel empty"><strong>Error</strong>${escapeHtml(ex.message)}</div>`;
    }

    if (seq !== renderSeq) return;
    $("#app").innerHTML = shell(html);
    bindShell();
    bindView();

    if (state.route === "dashboard") {
      try {
        const d = await API.dashboard();
        if (seq !== renderSeq) return;
        paintCharts(d);
      } catch (_) {
        /* ignore */
      }
    }
    if (state.route === "cajas" && state.cajaDash) {
      paintCajaCharts(state.cajaDash);
    }
    if (state.route === "combustibles" && state.combustibleResumen) {
      paintCombustibleCharts(state.combustibleResumen);
    }
  }

  function playAlertBeep() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = new Ctx();
      const schedule = () => {
        const now = ctx.currentTime;
        [0, 0.18, 0.36].forEach((offset, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = "sine";
          osc.frequency.value = i === 2 ? 880 : 660;
          gain.gain.setValueAtTime(0.0001, now + offset);
          gain.gain.exponentialRampToValueAtTime(0.22, now + offset + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, now + offset + 0.15);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + offset);
          osc.stop(now + offset + 0.16);
        });
        setTimeout(() => ctx.close().catch(() => undefined), 800);
      };
      // Safari/iOS y Chrome crean el AudioContext suspendido hasta reanudarlo:
      // sin esto el beep se agenda pero nunca suena.
      if (ctx.state === "suspended") {
        ctx.resume().then(schedule).catch(() => undefined);
      } else {
        schedule();
      }
    } catch (_) {
      /* ignore */
    }
  }

  function bindPushMessages() {
    if (!("serviceWorker" in navigator) || bindPushMessages._done) return;
    bindPushMessages._done = true;
    navigator.serviceWorker.addEventListener("message", (event) => {
      const msg = event.data;
      if (!msg || msg.type !== "AF_PUSH") return;
      playAlertBeep();
      toast(`${msg.title || "Aviso"}: ${msg.body || ""}`);
      if (
        document.visibilityState === "visible" &&
        "Notification" in window &&
        Notification.permission === "granted"
      ) {
        try {
          new Notification(msg.title || "Agenda Facturas", {
            body: msg.body || "",
            icon: "/static/icons/icon-192.png",
            requireInteraction: true,
            silent: false,
            tag: `af-local-${Date.now()}`,
          });
        } catch (_) {
          /* ignore */
        }
      }
      pollNotificaciones(false);
    });
  }

  async function bootApp() {
    state.meta = await API.meta();
    try {
      state.notifs = await API.listNotificaciones();
    } catch (_) {
      state.notifs = [];
    }
    bindPushMessages();
    startNotifPolling();
    await renderApp();
    ensureBackgroundPush();
  }

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }

  function fmtDateTime(iso) {
    const d = new Date(iso);
    return d.toLocaleString("es-PE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  async function init() {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
    bindPushMessages();
    window.addEventListener("hashchange", () => renderApp());
    window.addEventListener("resize", () => {
      if (state.user && state.route === "dashboard") renderApp();
    });

    const token = API.getToken();
    state.user = API.getUser();
    if (!token || !state.user) {
      renderAuth();
      return;
    }
    try {
      state.user = await API.me();
      await bootApp();
    } catch (_) {
      API.clearSession();
      renderAuth();
    }
  }

  init();
})();
