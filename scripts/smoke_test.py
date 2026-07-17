import httpx

base = "http://127.0.0.1:8000"
c = httpx.Client(base_url=base, timeout=30)

r = c.post(
    "/api/auth/registro",
    json={
        "nombre": "Demo Usuario",
        "email": "demo@agenda.pe",
        "password": "demo1234",
        "ruc_empresa": "20123456789",
        "razon_social": "Demo Negocios SAC",
        "telefono": "999888777",
        "direccion": "Av. Arequipa 123, Lima",
    },
)
print("registro", r.status_code)
if r.status_code >= 400:
    # maybe already exists
    r = c.post("/api/auth/login", json={"email": "demo@agenda.pe", "password": "demo1234"})
    print("login", r.status_code)
data = r.json()
token = data["access_token"]
h = {"Authorization": f"Bearer {token}"}

r = c.post(
    "/api/comprobantes",
    headers=h,
    json={
        "tipo": "factura",
        "serie": "F001",
        "numero": "1",
        "fecha_emision": "2026-07-16",
        "fecha_vencimiento": "2026-07-30",
        "estado": "no_pagado",
        "cliente_nombre": "Cliente Prueba SAC",
        "cliente_documento": "20999888777",
        "items": [
            {"descripcion": "Consultoría contable", "cantidad": 2, "precio_unitario": 150.00},
            {"descripcion": "Asesoría SUNAT", "cantidad": 1, "precio_unitario": 80.50},
        ],
    },
)
print("comprobante", r.status_code, r.text[:250])
doc = r.json()
doc_id = doc["id"]

r = c.get(f"/api/comprobantes/{doc_id}/pdf", headers=h)
print("pdf", r.status_code, r.headers.get("content-type"), len(r.content))

r = c.post(
    "/api/agenda",
    headers=h,
    json={
        "tipo": "reunion",
        "titulo": "Reunión con cliente",
        "descripcion": "Revisar estados financieros",
        "fecha_inicio": "2026-07-17T10:00:00",
        "ubicacion": "Oficina Lima",
        "recordatorio_minutos": 30,
    },
)
print("agenda", r.status_code)

r = c.get("/api/dashboard", headers=h)
d = r.json()
print("dashboard", r.status_code, d["total_comprobantes"], d["total_pendiente"])

r = c.get(f"/api/comprobantes/{doc_id}/whatsapp", headers=h, params={"telefono": "999888777"})
print("wa", r.status_code, r.json()["url"][:80])

print("meta", c.get("/api/meta").status_code)
print("index", c.get("/").status_code)
print("manifest", c.get("/manifest.webmanifest").status_code)
print("sw", c.get("/sw.js").status_code)
print("OK")
