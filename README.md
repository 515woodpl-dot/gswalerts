# GSW Alerts

Standalone fullscreen order alert display. Runs on port **7001**.

Connects to the inventory Pi's SSE stream via Tailscale and shows a big
animated alert whenever a new store order is placed. Runs on any device
on your Tailscale network — a second Pi, tablet, laptop, or phone.

---

## How it fits in

```
Customer places order
  → Next.js store (DigitalOcean)
  → POST /api/orders/notify → Inventory Pi (100.x.x.x:7000)
  → Inventory Pi broadcasts SSE event
  → gsw-alerts bridges that stream → your alert screen (:7001)
```

The alerts app never talks directly to the store or Supabase.
It only talks to the inventory Pi over Tailscale.

---

## Setup

### 1. Clone onto the alerts Pi (or any Tailscale device)

```bash
git clone https://github.com/515woodpl-dot/gswalerts.git
cd gswalerts
pip install flask
```

### 2. Set your inventory Pi's Tailscale IP

Edit `gswalerts.service` — replace `YOUR_INVENTORY_PI_TAILSCALE_IP`
with the actual Tailscale IP of the Pi running gswinventory.

Or just export env vars and run directly:

```bash
export INVENTORY_SSE_URL=http://100.x.x.x:7000/api/sse/orders
export INVENTORY_ORDERS_URL=http://100.x.x.x:7000/api/orders/store
python3 app.py
```

### 3. Open in browser

```
http://localhost:7001
```

Or from another device on Tailscale:
```
http://<alerts-device-tailscale-ip>:7001
```

---

## Run as a service (auto-start on boot)

```bash
# Copy service file
sudo cp gswalerts.service /etc/systemd/system/

# Edit the Tailscale IP inside it first
sudo nano /etc/systemd/system/gswalerts.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable gswalerts
sudo systemctl start gswalerts

# Check status
sudo systemctl status gswalerts
```

---

## Ports summary

| App              | Port | Purpose                        |
|------------------|------|--------------------------------|
| gswinventory     | 7000 | Inventory admin + store API    |
| gsw-alerts       | 7001 | Fullscreen order alert display |

---

## What the UI does

- **Left panel (big):** Shows a full animated alert card on every new order —
  order number, customer name, total, item count. Auto-dismisses after 30s.
- **Right panel:** Running list of recent orders with live status updates.
- **Top bar:** Live connection status, clock, sound toggle.
- **Sound:** Four-note alert chime on each new order (toggle off if needed).
