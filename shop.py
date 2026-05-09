#!/usr/bin/env python3
"""
FunkPay merchant catalog service — shop.funkpay.dev
Implements the standard FunkPay product catalog interface:

  GET /products          → list active products
  GET /products/{sku}    → product info (price_sat, name, description…)

Admin UI (Basic Auth):
  GET  /admin/products             → product list + CRUD
  POST /admin/products             → create product
  POST /admin/products/{sku}       → update product
  POST /admin/products/{sku}/delete → delete product

Usage:
  SHOP_DB_PATH=/opt/btcfunkpay-testnet/products.sqlite \
  SHOP_IMAGES_DIR=/opt/btcfunkpay-testnet/static/product-images \
  SHOP_STATIC_DIR=/opt/btcfunkpay-testnet/static \
  SHOP_ADMIN_PASS=secret \
  uvicorn shop:app --host 127.0.0.1 --port 8003
"""
import json
import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

_DB_PATH     = Path(os.environ.get("SHOP_DB_PATH",     "products.sqlite"))
_IMAGES_DIR  = Path(os.environ.get("SHOP_IMAGES_DIR",  "static/product-images"))
_STATIC_DIR  = Path(os.environ.get("SHOP_STATIC_DIR",  "static"))
_ADMIN_USER  = os.environ.get("SHOP_ADMIN_USER", "admin")
_ADMIN_PASS  = os.environ.get("SHOP_ADMIN_PASS", "")
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

_SEED = [
    ("FUNK-001", "FunkPay Sticker Pack",
     "3 vinyl stickers — FunkPay, Bitcoin, AI Agent logos.", 5_000, "product"),
    ("FUNK-002", "Monthly Dev Access",
     "One month of access to the FunkPay developer sandbox and testnet API.", 50_000, "subscription"),
    ("FUNK-003", "FunkPay T-Shirt",
     "100% cotton T-shirt, orange print on black. Sizes S–XXL.", 150_000, "product"),
]


# ── DB ────────────────────────────────────────────────────────────────────────

def _conn():
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    _IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku         TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                price_sat   INTEGER NOT NULL,
                type        TEXT DEFAULT 'product',
                image       TEXT DEFAULT '',
                active      INTEGER DEFAULT 1,
                created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            )
        """)
        if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            c.executemany(
                "INSERT INTO products (sku,name,description,price_sat,type) VALUES (?,?,?,?,?)",
                _SEED,
            )


def _row(row) -> dict:
    return {
        "sku":         row["sku"],
        "name":        row["name"],
        "description": row["description"] or "",
        "price_sat":   row["price_sat"],
        "type":        row["type"],
        "image":       row["image"] or "",
        "active":      bool(row["active"]),
    }


# ── App ───────────────────────────────────────────────────────────────────────

_init_db()
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_http_basic = HTTPBasic()


def _require_admin(creds: HTTPBasicCredentials = Depends(_http_basic)):
    if not _ADMIN_PASS:
        raise HTTPException(status_code=503, detail="Admin password not configured")
    ok_u = secrets.compare_digest(creds.username.encode(), _ADMIN_USER.encode())
    ok_p = secrets.compare_digest(creds.password.encode(), _ADMIN_PASS.encode())
    if not (ok_u and ok_p):
        raise HTTPException(status_code=401, detail="Unauthorized",
                            headers={"WWW-Authenticate": "Basic"})


# ── Public catalog API ────────────────────────────────────────────────────────

@app.get("/products")
def list_products():
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM products WHERE active=1 ORDER BY created_at"
        ).fetchall()
    return [_row(r) for r in rows]


@app.get("/products/{sku}")
def get_product(sku: str):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM products WHERE sku=? AND active=1", (sku.upper(),)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Product not found: {sku}")
    return _row(row)


# ── Admin helpers ─────────────────────────────────────────────────────────────

async def _save_image(sku: str, image: UploadFile) -> str:
    ext = Path(image.filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=422, detail=f"Image type not allowed: {ext}")
    filename = f"{sku.upper()}{ext}"
    content = await image.read()
    (_IMAGES_DIR / filename).write_bytes(content)
    return f"/static/product-images/{filename}"


def _render_admin(products: list[dict]) -> str:
    rows = ""
    for p in products:
        sku  = p["sku"]
        img  = p["image"]
        thumb = f'<img class="thumb" src="{img}" onerror="this.style.visibility=\'hidden\'">' if img else '<div class="thumb-empty"></div>'
        active_badge = '<span class="badge badge-yes">yes</span>' if p["active"] else '<span class="badge badge-no">no</span>'
        js_data = json.dumps(p).replace("'", "\\'").replace('"', '&quot;')
        desc_safe = p["description"].replace("'", "\\'")
        rows += f"""
        <tr>
          <td>{thumb}</td>
          <td style="font-family:monospace;font-size:12px;color:#94a3b8">{sku}</td>
          <td>{p["name"]}</td>
          <td style="text-align:right">{p["price_sat"]:,}</td>
          <td style="color:#64748b;font-size:12px">{p["type"]}</td>
          <td>{active_badge}</td>
          <td>
            <button class="btn-edit" onclick='openForm({js_data})'>Edit</button>
            <form method="post" action="/admin/products/{sku}/delete" style="display:inline">
              <button class="btn-del" type="submit" onclick="return confirm('Delete {sku}?')">Delete</button>
            </form>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Products — shop.funkpay.dev</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:sans-serif;background:#0f0f0f;color:#eee;padding:2rem}}
h1{{font-size:1.2rem;color:#f7931a;margin-bottom:1.5rem}}
.toolbar{{display:flex;gap:12px;align-items:center;margin-bottom:1.5rem}}
.btn-add{{background:#f7931a;color:#000;border:none;padding:8px 16px;border-radius:6px;font-weight:700;cursor:pointer;font-size:13px}}
.btn-edit{{background:none;border:1px solid #2d3048;color:#94a3b8;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px}}
.btn-del{{background:none;border:1px solid #7f1d1d;color:#f87171;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px}}
a.back{{color:#f7931a;text-decoration:none;font-size:13px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#666;font-size:11px;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid #222}}
td{{padding:8px;border-bottom:1px solid #1a1a1a;vertical-align:middle}}
tr:hover td{{background:#1a1a1a}}
.thumb{{width:44px;height:44px;object-fit:cover;border-radius:4px;background:#1a1a1a;display:block}}
.thumb-empty{{width:44px;height:44px;background:#1a1a1a;border-radius:4px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.badge-yes{{background:#14532d33;color:#22c55e;border:1px solid #22c55e55}}
.badge-no{{background:#7f1d1d33;color:#f87171;border:1px solid #f8717155}}
.overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:10}}
.panel{{display:none;position:fixed;top:0;right:0;bottom:0;width:440px;background:#1a1d27;border-left:1px solid #2d3048;z-index:11;overflow-y:auto;padding:2rem}}
.panel h2{{font-size:1rem;margin-bottom:1.5rem;color:#f7931a}}
label{{display:block;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;margin-top:14px}}
input[type=text],input[type=number],textarea,select{{width:100%;background:#0f1117;border:1px solid #2d3048;color:#eee;padding:8px 10px;border-radius:6px;font-size:13px;outline:none}}
textarea{{resize:vertical;min-height:80px}}
input[type=file]{{background:none;border:none;color:#94a3b8;padding:4px 0;font-size:12px}}
.checkbox-row{{display:flex;align-items:center;gap:8px;margin-top:14px}}
.checkbox-row label{{margin:0;text-transform:none;font-size:13px;color:#eee;letter-spacing:0}}
.form-btns{{display:flex;gap:10px;margin-top:24px}}
.btn-save{{background:#f7931a;color:#000;border:none;padding:10px 24px;border-radius:6px;font-weight:700;cursor:pointer}}
.btn-cancel{{background:none;border:1px solid #2d3048;color:#94a3b8;padding:10px 24px;border-radius:6px;cursor:pointer}}
#img-preview{{margin-top:8px;max-width:120px;max-height:120px;border-radius:6px;object-fit:cover;display:none}}
.cur-img{{margin-top:6px;font-size:11px;color:#64748b}}
</style>
</head><body>
<h1>shop.funkpay.dev — Products ({len(products)})</h1>
<div class="toolbar">
  <button class="btn-add" onclick="openForm(null)">+ Add Product</button>
  <a class="back" href="/invoice">← Invoices</a>
</div>
<table>
  <thead><tr><th>Image</th><th>SKU</th><th>Name</th><th style="text-align:right">Price (sat)</th><th>Type</th><th>Active</th><th>Actions</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<div class="overlay" id="overlay" onclick="closeForm()"></div>
<div class="panel" id="panel">
  <h2 id="panel-title">Add Product</h2>
  <form id="prod-form" method="post" action="/admin/products" enctype="multipart/form-data">
    <label>SKU *</label>
    <input type="text" name="sku" id="f-sku" required maxlength="32" placeholder="FUNK-004" style="text-transform:uppercase">
    <label>Name *</label>
    <input type="text" name="name" id="f-name" required maxlength="128">
    <label>Description</label>
    <textarea name="description" id="f-desc"></textarea>
    <label>Price (sat) *</label>
    <input type="number" name="price_sat" id="f-price" required min="1000">
    <label>Type</label>
    <select name="type" id="f-type">
      <option value="product">product</option>
      <option value="subscription">subscription</option>
    </select>
    <div class="checkbox-row">
      <input type="checkbox" name="active" id="f-active" value="1" checked>
      <label for="f-active">Active</label>
    </div>
    <label>Image</label>
    <input type="file" name="image" id="f-image" accept="image/*" onchange="previewImg(this)">
    <div id="cur-img-wrap" class="cur-img"></div>
    <img id="img-preview" alt="preview">
    <div class="form-btns">
      <button type="submit" class="btn-save">Save</button>
      <button type="button" class="btn-cancel" onclick="closeForm()">Cancel</button>
    </div>
  </form>
</div>

<script>
function openForm(p) {{
  const form = document.getElementById('prod-form');
  const skuInput = document.getElementById('f-sku');
  if (p) {{
    document.getElementById('panel-title').textContent = 'Edit ' + p.sku;
    form.action = '/admin/products/' + p.sku;
    skuInput.value = p.sku; skuInput.readOnly = true; skuInput.style.opacity = '.5';
    document.getElementById('f-name').value = p.name;
    document.getElementById('f-desc').value = p.description;
    document.getElementById('f-price').value = p.price_sat;
    document.getElementById('f-type').value = p.type;
    document.getElementById('f-active').checked = p.active;
    const preview = document.getElementById('img-preview');
    const curWrap = document.getElementById('cur-img-wrap');
    if (p.image) {{
      preview.src = p.image; preview.style.display = 'block';
      curWrap.textContent = 'Current: ' + p.image;
    }} else {{
      preview.style.display = 'none'; curWrap.textContent = '';
    }}
  }} else {{
    document.getElementById('panel-title').textContent = 'Add Product';
    form.action = '/admin/products';
    form.reset();
    skuInput.readOnly = false; skuInput.style.opacity = '1';
    document.getElementById('img-preview').style.display = 'none';
    document.getElementById('cur-img-wrap').textContent = '';
  }}
  document.getElementById('panel').style.display = 'block';
  document.getElementById('overlay').style.display = 'block';
}}
function closeForm() {{
  document.getElementById('panel').style.display = 'none';
  document.getElementById('overlay').style.display = 'none';
}}
function previewImg(input) {{
  const preview = document.getElementById('img-preview');
  if (input.files && input.files[0]) {{
    preview.src = URL.createObjectURL(input.files[0]);
    preview.style.display = 'block';
  }}
}}
</script>
</body></html>"""


# ── Admin CRUD routes ─────────────────────────────────────────────────────────

@app.get("/admin/products", response_class=HTMLResponse)
def admin_list(_: HTTPBasicCredentials = Depends(_require_admin)):
    with _conn() as c:
        rows = c.execute("SELECT * FROM products ORDER BY created_at").fetchall()
    return _render_admin([_row(r) for r in rows])


@app.post("/admin/products")
async def admin_create(
    sku:         str = Form(...),
    name:        str = Form(...),
    description: str = Form(""),
    price_sat:   int = Form(...),
    type:        str = Form("product"),
    active:      str = Form(None),
    image: UploadFile = File(None),
    _: HTTPBasicCredentials = Depends(_require_admin),
):
    sku = sku.upper().strip()
    img = await _save_image(sku, image) if (image and image.filename) else ""
    with _conn() as c:
        try:
            c.execute(
                "INSERT INTO products (sku,name,description,price_sat,type,image,active) VALUES (?,?,?,?,?,?,?)",
                (sku, name.strip(), description.strip(), price_sat, type, img, 1 if active else 0),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail=f"SKU already exists: {sku}")
    return RedirectResponse("/admin/products", status_code=303)


@app.post("/admin/products/{sku}")
async def admin_update(
    sku:         str,
    name:        str = Form(...),
    description: str = Form(""),
    price_sat:   int = Form(...),
    type:        str = Form("product"),
    active:      str = Form(None),
    image: UploadFile = File(None),
    _: HTTPBasicCredentials = Depends(_require_admin),
):
    sku = sku.upper()
    img = await _save_image(sku, image) if (image and image.filename) else None
    with _conn() as c:
        row = c.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Product not found: {sku}")
        c.execute(
            "UPDATE products SET name=?,description=?,price_sat=?,type=?,image=?,active=? WHERE sku=?",
            (name.strip(), description.strip(), price_sat, type,
             img if img is not None else row["image"],
             1 if active else 0, sku),
        )
    return RedirectResponse("/admin/products", status_code=303)


@app.post("/admin/products/{sku}/delete")
def admin_delete(sku: str, _: HTTPBasicCredentials = Depends(_require_admin)):
    with _conn() as c:
        c.execute("DELETE FROM products WHERE sku=?", (sku.upper(),))
    return RedirectResponse("/admin/products", status_code=303)
