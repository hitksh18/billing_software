const state = { cart: [], discount: 0, payment_mode: null, upi_vpa: "" };

function formatINR(n){ return "₹" + Number(n||0).toFixed(2); }

function renderCart(){
  const tb = document.getElementById("cart-body");
  tb.innerHTML = state.cart.map((it, i) => `
    <tr>
      <td>${it.product_name}</td>
      <td>
        <input type="number" min="1" class="form-control form-control-sm" style="max-width:90px"
          value="${it.qty}" onchange="updateQty(${i}, this.value)" />
      </td>
      <td>${formatINR(it.price)}</td>
      <td>${formatINR(it.price * it.qty)}</td>
      <td><button class="btn btn-sm btn-outline-light" onclick="removeItem(${i})">Remove</button></td>
    </tr>
  `).join("");

  let subtotal = state.cart.reduce((s, it) => s + it.price*it.qty, 0);
  const total = subtotal - Number(state.discount||0);
  document.getElementById("grand").textContent = formatINR(total);
}
window.updateQty = (i,v)=>{ state.cart[i].qty = Math.max(1, Number(v||1)); renderCart(); }
window.removeItem = (i)=>{ state.cart.splice(i,1); renderCart(); }

const searchEl = document.getElementById("search");
const sugg = document.getElementById("suggestions");
let timer; 
searchEl && searchEl.addEventListener("input", () => {
  clearTimeout(timer);
  const q = searchEl.value.trim();
  if (!q) { sugg.innerHTML=""; return; }
  timer = setTimeout(async () => {
    const r = await fetch(`/api/products?q=${encodeURIComponent(q)}`);
    const arr = await r.json();
    sugg.innerHTML = arr.map(p => `
      <button class="list-group-item list-group-item-action" onclick='addToCart(${JSON.stringify(p).replace(/'/g,"")})'>
        ${p.product_name} — ${formatINR(p.price)}
      </button>`).join("");
  }, 200);
});

window.addToCart = (p) => {
  const ex = state.cart.find(x => x.product_name === p.product_name);
  if (ex) ex.qty++;
  else state.cart.push({ product_name: p.product_name, price: Number(p.price), qty: 1 });
  sugg.innerHTML = ""; searchEl.value = "";
  renderCart();
};

document.getElementById("discount").addEventListener("input", e => {
  state.discount = Number(e.target.value || 0);
  renderCart();
});

const payModal = new bootstrap.Modal(document.getElementById("payModal"));
document.getElementById("checkout").onclick = () => {
  if (!state.cart.length) return alert("Cart is empty");
  document.getElementById("pay-area").innerHTML = "<div>Select a payment mode.</div>";
  document.getElementById("confirm-pay").disabled = true;
  state.payment_mode = null;
  payModal.show();
};

document.getElementById("btn-upi").onclick = async () => {
  const amt = state.cart.reduce((s,it)=>s+it.price*it.qty,0) - Number(state.discount||0);
  const vpa = prompt("Enter UPI ID (e.g., upi@sbi):", "upi@sbi") || "upi@sbi";
  state.upi_vpa = vpa; state.payment_mode = "UPI";
  const img = document.createElement("img");
  img.src = `/api/upi-qr?vpa=${encodeURIComponent(vpa)}&amount=${amt}`;
  img.style = "width:220px;height:220px;border-radius:12px;border:1px solid rgba(255,255,255,.1)";
  const area = document.getElementById("pay-area"); area.innerHTML = ""; area.appendChild(img);
  document.getElementById("confirm-pay").disabled = false;
};

document.getElementById("btn-cash").onclick = () => {
  state.payment_mode = "Cash";
  document.getElementById("pay-area").innerHTML = `<div>Collect cash and proceed.</div>`;
  document.getElementById("confirm-pay").disabled = false;
};

document.getElementById("btn-card").onclick = () => {
  state.payment_mode = "Card";
  document.getElementById("pay-area").innerHTML = `<div>Please complete payment on the POS machine, then click Confirm.</div>`;
  document.getElementById("confirm-pay").disabled = false;
};

document.getElementById("confirm-pay").onclick = async () => {
  const payload = { cart: state.cart, discount: Number(state.discount||0), payment_mode: state.payment_mode, upi_vpa: state.upi_vpa };
  const r = await fetch("/api/checkout", { method:"POST", headers: { "Content-Type":"application/json" }, body: JSON.stringify(payload) });
  const j = await r.json();
  if (!j.ok) return alert(j.error || "Checkout failed");
  payModal.hide();
  const doneModal = new bootstrap.Modal(document.getElementById("doneModal"));
  document.getElementById("done-body").innerHTML = `
    <div class="mb-2">Invoice: <b>${j.invoice_code}</b></div>
    <div>Total: <b>${formatINR(j.total)}</b></div>
    <div class="mt-2">Drive: ${j.drive_link ? `<a target="_blank" href="${j.drive_link}">Open in Drive</a>` : "-"}</div>
  `;
  document.getElementById("btn-print").href = j.pdf_url;
  doneModal.show();
};
