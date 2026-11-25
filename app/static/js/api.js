const API = {
  tokenKey: "af_token",
  userKey: "af_user",

  getToken() {
    return localStorage.getItem(this.tokenKey);
  },

  getUser() {
    const raw = localStorage.getItem(this.userKey);
    return raw ? JSON.parse(raw) : null;
  },

  setSession(token, user) {
    localStorage.setItem(this.tokenKey, token);
    localStorage.setItem(this.userKey, JSON.stringify(user));
  },

  clearSession() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
  },

  mostrarSuspension(mensaje) {
    if (document.getElementById("af-suspendido")) return;
    const capa = document.createElement("div");
    capa.id = "af-suspendido";
    capa.setAttribute("role", "alertdialog");
    capa.style.cssText = "position:fixed;inset:0;z-index:99999;display:grid;place-items:center;padding:24px;"
      + "background:#f1f5f9;color:#0f172a;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif";
    const caja = document.createElement("div");
    caja.style.cssText = "max-width:460px;background:#fff;border-radius:16px;padding:32px;text-align:center;"
      + "box-shadow:0 10px 30px rgba(15,23,42,.08)";
    const titulo = document.createElement("h1");
    titulo.style.cssText = "font-size:1.3rem;margin:0 0 .6rem";
    titulo.textContent = "Servicio suspendido";
    const texto = document.createElement("p");
    texto.style.cssText = "color:#475569;line-height:1.5;margin:0";
    texto.textContent = mensaje || "El servicio está suspendido temporalmente.";
    caja.append(titulo, texto);
    capa.append(caja);
    document.body.append(capa);
  },

  async request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (!(options.body instanceof FormData) && options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const token = this.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;

    const res = await fetch(path, { ...options, headers });
    const isAuthEndpoint = path.startsWith("/api/auth/login") || path.startsWith("/api/auth/registro");
    if (res.status === 401 && !isAuthEndpoint) {
      this.clearSession();
      throw new Error("Sesión expirada. Inicie sesión nuevamente.");
    }

    const contentType = res.headers.get("content-type") || "";
    const isBlob =
      contentType.includes("application/pdf") ||
      contentType.includes("image/") ||
      contentType.includes("application/octet-stream") ||
      options.asBlob;
    if (isBlob) {
      if (!res.ok) throw new Error("No se pudo descargar el archivo");
      return res.blob();
    }

    const data = contentType.includes("application/json") ? await res.json() : await res.text();
    if (res.status === 503 && data?.motivo === "suspendido") {
      // El proveedor suspendio el servicio desde su panel: el aviso ocupa la pantalla
      this.mostrarSuspension(data.detail);
    }
    if (!res.ok) {
      const detail = data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(", ")
        : detail || data?.mensaje || "Error en la solicitud";
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  },

  registro(body) {
    return this.request("/api/auth/registro", { method: "POST", body: JSON.stringify(body) });
  },
  login(body) {
    return this.request("/api/auth/login", { method: "POST", body: JSON.stringify(body) });
  },
  me() {
    return this.request("/api/auth/me");
  },
  meta() {
    return this.request("/api/meta");
  },
  dashboard(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/dashboard${qs ? `?${qs}` : ""}`);
  },
  listComprobantes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/comprobantes${qs ? `?${qs}` : ""}`);
  },
  resumenComprobantes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/comprobantes/resumen${qs ? `?${qs}` : ""}`);
  },
  createComprobante(body) {
    return this.request("/api/comprobantes", { method: "POST", body: JSON.stringify(body) });
  },
  updateComprobante(id, body) {
    return this.request(`/api/comprobantes/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  cambiarEstado(id, estado) {
    return this.request(`/api/comprobantes/${id}/estado?estado=${encodeURIComponent(estado)}`, {
      method: "PATCH",
    });
  },
  deleteComprobante(id) {
    return this.request(`/api/comprobantes/${id}`, { method: "DELETE" });
  },
  pdfComprobante(id) {
    return this.request(`/api/comprobantes/${id}/pdf`);
  },
  uploadAdjuntosComprobante(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/comprobantes/${id}/adjuntos`, { method: "POST", body: fd });
  },
  listAdjuntosComprobante(id) {
    return this.request(`/api/comprobantes/${id}/adjuntos`);
  },
  downloadAdjunto(id) {
    return this.request(`/api/adjuntos/${id}`, { asBlob: true });
  },
  replaceAdjunto(id, file) {
    const fd = new FormData();
    fd.append("archivo", file);
    return this.request(`/api/adjuntos/${id}/reemplazar`, { method: "POST", body: fd });
  },
  deleteAdjunto(id) {
    return this.request(`/api/adjuntos/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosAgenda(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/agenda/${id}/adjuntos`, { method: "POST", body: fd });
  },
  reporteComprobantes(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/comprobantes/reporte${qs ? `?${qs}` : ""}`);
  },
  reporteComprobantesExcel(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/comprobantes/reporte-excel${qs ? `?${qs}` : ""}`, { asBlob: true });
  },
  emailComprobante(id, body) {
    return this.request(`/api/comprobantes/${id}/enviar-correo`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  whatsappComprobante(id, telefono) {
    const qs = telefono ? `?telefono=${encodeURIComponent(telefono)}` : "";
    return this.request(`/api/comprobantes/${id}/whatsapp${qs}`);
  },
  listAgenda(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/agenda${qs ? `?${qs}` : ""}`);
  },
  createAgenda(body) {
    return this.request("/api/agenda", { method: "POST", body: JSON.stringify(body) });
  },
  updateAgenda(id, body) {
    return this.request(`/api/agenda/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  reprogramarAgenda(id, body) {
    return this.request(`/api/agenda/${id}/reprogramar`, { method: "POST", body: JSON.stringify(body) });
  },
  cambiarEstadoAgenda(id, estado) {
    return this.request(`/api/agenda/${id}/estado?estado=${encodeURIComponent(estado)}`, {
      method: "PATCH",
    });
  },
  pdfAgenda(id) {
    return this.request(`/api/agenda/${id}/pdf`, { asBlob: true });
  },
  deleteAgenda(id) {
    return this.request(`/api/agenda/${id}`, { method: "DELETE" });
  },
  listNotificaciones() {
    return this.request("/api/notificaciones");
  },
  leerNotificacion(id) {
    return this.request(`/api/notificaciones/${id}/leer`, { method: "POST" });
  },
  leerTodas() {
    return this.request("/api/notificaciones/leer-todas", { method: "POST" });
  },
  vapidKey() {
    return this.request("/api/notificaciones/vapid-public-key");
  },
  pushSubscribe(body) {
    return this.request("/api/notificaciones/push-subscribe", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  procesarRecordatorios() {
    return this.request("/api/notificaciones/procesar-ahora", { method: "POST" });
  },
  probarPush() {
    return this.request("/api/notificaciones/probar-push", { method: "POST" });
  },
  obtenerPreferencias() {
    return this.request("/api/notificaciones/preferencias");
  },
  guardarPreferencias(body) {
    return this.request("/api/notificaciones/preferencias", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  probarTelegram() {
    return this.request("/api/notificaciones/telegram-probar", { method: "POST" });
  },
  consultaDocumento(numero) {
    return this.request(`/api/consulta/documento?numero=${encodeURIComponent(numero)}`);
  },
  listClientes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/clientes${qs ? `?${qs}` : ""}`);
  },
  createCliente(body) {
    return this.request("/api/clientes", { method: "POST", body: JSON.stringify(body) });
  },
  updateCliente(id, body) {
    return this.request(`/api/clientes/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteCliente(id) {
    return this.request(`/api/clientes/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosCliente(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/clientes/${id}/adjuntos`, { method: "POST", body: fd });
  },
  listProductos(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/productos${qs ? `?${qs}` : ""}`);
  },
  createProducto(body) {
    return this.request("/api/productos", { method: "POST", body: JSON.stringify(body) });
  },
  updateProducto(id, body) {
    return this.request(`/api/productos/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteProducto(id) {
    return this.request(`/api/productos/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosProducto(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/productos/${id}/adjuntos`, { method: "POST", body: fd });
  },
  listCajas(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/cajas${qs ? `?${qs}` : ""}`);
  },
  createCaja(body) {
    return this.request("/api/cajas", { method: "POST", body: JSON.stringify(body) });
  },
  updateCaja(id, body) {
    return this.request(`/api/cajas/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteCaja(id, { permanente = false } = {}) {
    const qs = permanente ? "?permanente=1" : "";
    return this.request(`/api/cajas/${id}${qs}`, { method: "DELETE" });
  },
  dashboardCajas(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/cajas/dashboard${qs ? `?${qs}` : ""}`);
  },
  reporteCajas(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/cajas/reporte${qs ? `?${qs}` : ""}`);
  },
  reporteCajasExcel(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/cajas/reporte-excel${qs ? `?${qs}` : ""}`, { asBlob: true });
  },
  listMovimientosCaja(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/cajas/movimientos${qs ? `?${qs}` : ""}`);
  },
  createMovimientoCaja(body) {
    return this.request("/api/cajas/movimientos", { method: "POST", body: JSON.stringify(body) });
  },
  updateMovimientoCaja(id, body) {
    return this.request(`/api/cajas/movimientos/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteMovimientoCaja(id) {
    return this.request(`/api/cajas/movimientos/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosCaja(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/cajas/movimientos/${id}/adjuntos`, { method: "POST", body: fd });
  },
  listContactos(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/contactos${qs ? `?${qs}` : ""}`);
  },
  createContacto(body) {
    return this.request("/api/contactos", { method: "POST", body: JSON.stringify(body) });
  },
  updateContacto(id, body) {
    return this.request(`/api/contactos/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteContacto(id) {
    return this.request(`/api/contactos/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosContacto(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/contactos/${id}/adjuntos`, { method: "POST", body: fd });
  },
  importarContactos(contactos) {
    return this.request("/api/contactos/importar", {
      method: "POST",
      body: JSON.stringify({ contactos }),
    });
  },
  contactoACliente(id) {
    return this.request(`/api/contactos/${id}/a-cliente`, { method: "POST" });
  },
  resumenCombustibles(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/combustibles/resumen${qs ? `?${qs}` : ""}`);
  },
  reporteCombustibles(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/combustibles/reporte${qs ? `?${qs}` : ""}`);
  },
  reporteCombustiblesExcel(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/combustibles/reporte-excel${qs ? `?${qs}` : ""}`, { asBlob: true });
  },
  listCombustibles(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/combustibles${qs ? `?${qs}` : ""}`);
  },

  createCombustible(body) {
    return this.request("/api/combustibles", { method: "POST", body: JSON.stringify(body) });
  },
  updateCombustible(id, body) {
    return this.request(`/api/combustibles/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteCombustible(id) {
    return this.request(`/api/combustibles/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosCombustible(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/combustibles/${id}/adjuntos`, { method: "POST", body: fd });
  },
  resumenGastos(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/gastos-externos/resumen${qs ? `?${qs}` : ""}`);
  },
  createGasto(body) {
    return this.request("/api/gastos-externos", { method: "POST", body: JSON.stringify(body) });
  },
  updateGasto(id, body) {
    return this.request(`/api/gastos-externos/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  deleteGasto(id) {
    return this.request(`/api/gastos-externos/${id}`, { method: "DELETE" });
  },
  uploadAdjuntosGasto(id, files) {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("archivos", f));
    return this.request(`/api/gastos-externos/${id}/adjuntos`, { method: "POST", body: fd });
  },
  formatosReportes() {
    return this.request("/api/reportes/formatos");
  },
  conteoReportes() {
    return this.request("/api/reportes/conteo");
  },
  listReportes(params = {}) {
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    );
    const qs = new URLSearchParams(cleaned).toString();
    return this.request(`/api/reportes${qs ? `?${qs}` : ""}`);
  },
  getReporte(id) {
    return this.request(`/api/reportes/${id}`);
  },
  siguienteReporte(formato) {
    return this.request(`/api/reportes/siguiente?formato=${encodeURIComponent(formato)}`);
  },
  ultimoReporte(formato) {
    return this.request(`/api/reportes/ultimo?formato=${encodeURIComponent(formato)}`);
  },
  createReporte(body) {
    return this.request("/api/reportes", { method: "POST", body: JSON.stringify(body) });
  },
  updateReporte(id, body) {
    return this.request(`/api/reportes/${id}`, { method: "PUT", body: JSON.stringify(body) });
  },
  duplicarReporte(id) {
    return this.request(`/api/reportes/${id}/duplicar`, { method: "POST" });
  },
  deleteReporte(id) {
    return this.request(`/api/reportes/${id}`, { method: "DELETE" });
  },
  pdfReporte(id) {
    return this.request(`/api/reportes/${id}/pdf`, { asBlob: true });
  },
};
