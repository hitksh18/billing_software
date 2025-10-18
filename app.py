import os, io, json, datetime, re, socket
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from OpenSSL import crypto

# ----------------- Setup -----------------
load_dotenv()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

DATA_DIR = "data"
INVOICE_DIR = "invoices"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(INVOICE_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
SALES_FILE = os.path.join(DATA_DIR, "sales.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# ----------------- Local JSON Helpers -----------------
def read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return default

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ----------------- Utility Functions -----------------
def pad3(n):
    return str(int(n)).zfill(3)

def parse_price_any(s):
    """Accepts Rs. formats and converts to float."""
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).replace(",", "")
    m = re.search(r"(\d+(\.\d+)?)", s)
    return float(m.group(1)) if m else 0.0

def get_next_counters():
    config = read_json(CONFIG_FILE, {"sale_no": 0, "invoice_no": 0})
    config["sale_no"] += 1
    config["invoice_no"] += 1
    write_json(CONFIG_FILE, config)
    return config["sale_no"], config["invoice_no"]

# ----------------- SSL Auto Generator -----------------
def generate_self_signed_cert(cert_file="cert.pem", key_file="key.pem"):
    """Generate self-signed SSL certificate if missing."""
    if os.path.exists(cert_file) and os.path.exists(key_file):
        return True

    try:
        print("🔒 Generating new SSL certificate...")
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)
        cert = crypto.X509()
        cert.get_subject().CN = "localhost"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(key, "sha256")

        with open(cert_file, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(key_file, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

        print("✅ SSL certificate created successfully.")
        return True
    except Exception as e:
        print(f"⚠️ SSL certificate generation failed: {e}")
        return False

# ----------------- Helper: Get Local IP -----------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ----------------- PDF Generator -----------------
def make_invoice_pdf(invoice_code, sale_code, items, total, pay_mode, logo_path=None, discount=0.0, final_cost=None):
    """Create invoice PDF with discount and final cost."""
    filename = f"Sale_{sale_code}_{invoice_code}.pdf"
    path = os.path.join(INVOICE_DIR, filename)
    c = canvas.Canvas(path, pagesize=A4)
    W, H = A4

    y = H - 30 * mm
    if logo_path and os.path.exists(logo_path):
        c.drawImage(logo_path, 20 * mm, y - 20 * mm, width=25 * mm, height=25 * mm, preserveAspectRatio=True, mask='auto')

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50 * mm, y, "SRI AYYAPPA FIRE WORKS")
    c.setFont("Helvetica", 10)
    c.drawString(50 * mm, y - 6 * mm, "DEEPAVALI CRACKERS MEGA SALE (Sivakasi Factory Outlet)")

    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y - 14 * mm, f"Invoice: {invoice_code}")
    c.drawString(80 * mm, y - 14 * mm, f"Sale No: {sale_code}")
    c.drawString(20 * mm, y - 20 * mm, f"Date: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}")
    c.drawString(80 * mm, y - 20 * mm, f"Payment: {pay_mode}")

    y_table = y - 30 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y_table, "Product")
    c.drawString(110 * mm, y_table, "Qty")
    c.drawString(140 * mm, y_table, "Price")
    c.drawString(170 * mm, y_table, "Subtotal")
    c.line(20 * mm, y_table - 2 * mm, 190 * mm, y_table - 2 * mm)

    y_row = y_table - 8 * mm
    c.setFont("Helvetica", 10)
    for idx, it in enumerate(items, start=1):
        pname = str(it.get("product_name", ""))[:48]
        qty = int(it.get("qty", 1))
        price = float(it.get("price", 0))
        sub = price * qty
        c.drawString(20 * mm, y_row, f"{idx}. {pname}")
        c.drawRightString(125 * mm, y_row, str(qty))
        c.drawRightString(155 * mm, y_row, f"{price:.2f}")
        c.drawRightString(190 * mm, y_row, f"{sub:.2f}")
        y_row -= 6 * mm
        if y_row < 30 * mm:
            c.showPage()
            y_row = H - 20 * mm

    # Summary Section
    y_tot = y_row - 6 * mm
    c.line(120 * mm, y_tot, 190 * mm, y_tot)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(150 * mm, y_tot - 8 * mm, "Total:")
    c.drawRightString(190 * mm, y_tot - 8 * mm, f"{total:.2f}")
    c.drawRightString(150 * mm, y_tot - 15 * mm, "Discount:")
    c.drawRightString(190 * mm, y_tot - 15 * mm, f"{discount:.2f}")
    c.drawRightString(150 * mm, y_tot - 22 * mm, "Final Amount:")
    c.drawRightString(190 * mm, y_tot - 22 * mm, f"{final_cost if final_cost else total:.2f}")

    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, 15 * mm, "Thank you for shopping with SRI AYYAPPA FIRE WORKS — Sivakasi Factory Outlet")
    c.showPage()
    c.save()
    return filename, path

# ----------------- Pages -----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/sales")
def sales_page():
    return render_template("sales.html")

# ----------------- Products API -----------------
@app.get("/api/products")
def api_products():
    """Search through all categories in products.json."""
    q = (request.args.get("q") or "").strip().lower()
    data = read_json(PRODUCTS_FILE, {})

    all_products = []
    for category, items in data.items():
        for item in items:
            all_products.append({
                "category": category,
                "product_no": item.get("Product No", ""),
                "product_name": item.get("Product Name", ""),
                "price": parse_price_any(item.get("Price", "")),
                "description": item.get("Description", "")
            })

    if q:
        filtered = [
            p for p in all_products
            if q in p["product_name"].lower()
            or q in p["product_no"].lower()
            or q in p["category"].lower()
        ]
        return jsonify(filtered)
    return jsonify(all_products)

# ----------------- Checkout & Sales -----------------
@app.post("/api/checkout")
def api_checkout():
    """Handles billing with optional discount/final cost."""
    data = request.get_json(force=True)
    cart = data.get("cart", [])
    payment_mode = data.get("payment_mode", "Cash")
    final_cost_input = data.get("final_cost")

    if not cart:
        return jsonify({"ok": False, "error": "Empty cart"}), 400

    for i in cart:
        i["qty"] = int(i.get("qty", 1))
        i["price"] = float(parse_price_any(i.get("price", 0)))

    total = sum(i["price"] * i["qty"] for i in cart)
    final_cost = float(final_cost_input) if final_cost_input else total
    discount = total - final_cost if final_cost_input else 0.0

    sale_no, invoice_no = get_next_counters()
    invoice_code = f"INV-2025-{pad3(invoice_no)}"
    sale_code = pad3(sale_no)

    logo_path = os.path.join("static", "logo.png")
    pdf_name, pdf_path = make_invoice_pdf(
        invoice_code, sale_code, cart, total, payment_mode, logo_path,
        discount=discount, final_cost=final_cost
    )

    # Record sale locally
    sales = read_json(SALES_FILE, [])
    sales.append({
        "sale_no": sale_no,
        "invoice_no": invoice_no,
        "invoice_code": invoice_code,
        "date": datetime.datetime.now().isoformat(),
        "items": cart,
        "total": total,
        "discount": discount,
        "final_cost": final_cost,
        "payment_mode": payment_mode,
        "pdf_file": pdf_name
    })
    write_json(SALES_FILE, sales)

    return jsonify({
        "ok": True,
        "invoice_code": invoice_code,
        "total": total,
        "discount": discount,
        "final_cost": final_cost,
        "payment_mode": payment_mode,
        "pdf_url": f"/invoices/{pdf_name}"
    })

# ----------------- Sales API -----------------
@app.get("/api/sales")
def api_sales():
    sales = read_json(SALES_FILE, [])
    return jsonify(sorted(sales, key=lambda x: x.get("date", ""), reverse=True))

# ----------------- Serve Invoices (Open in Browser) -----------------
@app.get("/invoices/<path:fname>")
def serve_invoice(fname):
    return send_from_directory(INVOICE_DIR, fname, as_attachment=False)

# ----------------- Run -----------------
if __name__ == "__main__":
    cert_exists = generate_self_signed_cert()
    ip = get_local_ip()

    if cert_exists:
        context = ("cert.pem", "key.pem")
        print(f"\n🔗 Secure Billing Server running at:")
        print(f"   🌐 Local: https://localhost:{PORT}")
        print(f"   🖥️  LAN:   https://{ip}:{PORT}\n")
        app.run(host=HOST, port=PORT, ssl_context=context, debug=False)
    else:
        print(f"\n⚡ SSL unavailable — running on HTTP mode.")
        print(f"   🌐 Local: http://localhost:{PORT}")
        print(f"   🖥️  LAN:   http://{ip}:{PORT}\n")
        app.run(host=HOST, port=PORT, debug=False)
