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
    if (res.status === 401) {
      this.clearSession();
      throw new Error("Sesión expirada. Inicie sesión nuevamente.");
    }

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/pdf")) {
      if (!res.ok) throw new Error("No se pudo descargar el PDF");
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
  deleteComprobante(id) {
    return this.request(`/api/comprobantes/${id}`, { method: "DELETE" });
  },
  pdfComprobante(id) {
    return this.request(`/api/comprobantes/${id}/pdf`);
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
};
