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
  dashboard() {
    return this.request("/api/dashboard");
  },
  listComprobantes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.request(`/api/comprobantes${qs ? `?${qs}` : ""}`);
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
  downloadAdjunto(id) {
    return this.request(`/api/adjuntos/${id}`, { asBlob: true });
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
};
