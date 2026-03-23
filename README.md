# AmpliFi Alien Prometheus Exporter

[![Tests](https://github.com/matanbaruch/amplifi-alien-exporter/actions/workflows/test.yml/badge.svg)](https://github.com/matanbaruch/amplifi-alien-exporter/actions/workflows/test.yml)
[![GitHub release](https://img.shields.io/github/v/release/matanbaruch/amplifi-alien-exporter)](https://github.com/matanbaruch/amplifi-alien-exporter/releases)
[![Docker Image](https://ghcr-badge.egpl.dev/matanbaruch/amplifi-alien-exporter/size)](https://github.com/matanbaruch/amplifi-alien-exporter/pkgs/container/amplifi-alien-exporter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Prometheus exporter for **AmpliFi Alien** routers. Scrapes the AmpliFi web interface and exposes rich metrics about connected clients, WiFi quality, Ethernet ports, and router health — all with zero external dependencies (pure Python stdlib).

---

## Features

- 📡 **Per-client WiFi metrics**: happiness score, signal quality, bitrates, bytes, spatial streams
- 🌐 **Ethernet port metrics**: link status, speed, RX/TX bitrates
- 📊 **Client inventory**: all connected clients with MAC, IP, name, manufacturer, connection type
- 🔁 **Background scraping**: non-blocking refresh every N seconds
- 🏥 **Health endpoint**: `/health` for liveness probes
- 🐳 **Docker-ready**: single-file, no pip installs needed

---

## Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `amplifi_router_uptime_seconds` | gauge | Router uptime in seconds |
| `amplifi_router_info` | gauge | Router metadata (labels: mac, friendly_name, role, platform, ip, level) |
| `amplifi_wifi_client_happiness_score` | gauge | WiFi client happiness score (0–100) |
| `amplifi_wifi_client_signal_quality` | gauge | WiFi client signal quality (0–100) |
| `amplifi_wifi_client_rx_bitrate_kbps` | gauge | WiFi client RX bitrate (kbps) |
| `amplifi_wifi_client_tx_bitrate_kbps` | gauge | WiFi client TX bitrate (kbps) |
| `amplifi_wifi_client_rx_bytes_total` | counter | WiFi client total RX bytes |
| `amplifi_wifi_client_tx_bytes_total` | counter | WiFi client total TX bytes |
| `amplifi_wifi_client_rx_bytes_5sec` | gauge | WiFi client RX bytes in last 5s |
| `amplifi_wifi_client_tx_bytes_5sec` | gauge | WiFi client TX bytes in last 5s |
| `amplifi_wifi_client_rx_bytes_15sec` | gauge | WiFi client RX bytes in last 15s |
| `amplifi_wifi_client_tx_bytes_15sec` | gauge | WiFi client TX bytes in last 15s |
| `amplifi_wifi_client_rx_bytes_60sec` | gauge | WiFi client RX bytes in last 60s |
| `amplifi_wifi_client_tx_bytes_60sec` | gauge | WiFi client TX bytes in last 60s |
| `amplifi_wifi_client_inactive` | gauge | WiFi client inactive flag (1=inactive) |
| `amplifi_wifi_client_max_bandwidth_mhz` | gauge | WiFi client max channel bandwidth (MHz) |
| `amplifi_wifi_client_max_spatial_streams` | gauge | WiFi client max spatial streams |
| `amplifi_wifi_client_lease_validity_seconds` | gauge | DHCP lease remaining (seconds) |
| `amplifi_wifi_client_rx_mhz` | gauge | WiFi client RX channel width (MHz) |
| `amplifi_wifi_client_tx_mhz` | gauge | WiFi client TX channel width (MHz) |
| `amplifi_ethernet_port_link` | gauge | Ethernet port link status (1=up, 0=down) |
| `amplifi_ethernet_port_link_speed_mbps` | gauge | Ethernet port link speed (Mbps) |
| `amplifi_ethernet_port_rx_bitrate_kbps` | gauge | Ethernet port RX bitrate (kbps) |
| `amplifi_ethernet_port_tx_bitrate_kbps` | gauge | Ethernet port TX bitrate (kbps) |
| `amplifi_client_connected` | gauge | Connected client info (1 while connected) |
| `amplifi_clients_total` | gauge | Total connected clients |
| `amplifi_wifi_clients_total` | gauge | Total WiFi connected clients |
| `amplifi_ethernet_clients_total` | gauge | Total Ethernet connected clients |
| `amplifi_scrape_success` | gauge | 1 if last scrape succeeded, 0 otherwise |
| `amplifi_scrape_duration_seconds` | gauge | Duration of last scrape in seconds |

---

## Quick Start

### Docker (recommended)

```bash
docker run -d \
  --name amplifi-exporter \
  --restart unless-stopped \
  -p 9877:9877 \
  -e AMPLIFI_ROUTER_IP=192.168.1.1 \
  -e AMPLIFI_PASSWORD=your-router-password \
  ghcr.io/matanbaruch/amplifi-alien-exporter:latest
```

Then verify:
```bash
curl http://localhost:9877/health
curl http://localhost:9877/metrics
```

### Docker Compose

```yaml
version: "3.8"
services:
  amplifi-exporter:
    image: ghcr.io/matanbaruch/amplifi-alien-exporter:latest
    restart: unless-stopped
    ports:
      - "9877:9877"
    environment:
      AMPLIFI_ROUTER_IP: "192.168.1.1"
      AMPLIFI_PASSWORD: "${AMPLIFI_PASSWORD}"   # from .env file
      SCRAPE_INTERVAL: "15"
```

Create a `.env` file (never commit this):
```bash
AMPLIFI_PASSWORD=your-router-password
```

### Run with Python

```bash
export AMPLIFI_ROUTER_IP=192.168.1.1
export AMPLIFI_PASSWORD=your-router-password
python amplifi_exporter.py
```

---

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AMPLIFI_ROUTER_IP` | `192.168.1.1` | No | AmpliFi router IP address |
| `AMPLIFI_PASSWORD` | — | **Yes** | AmpliFi router admin password |
| `SCRAPE_INTERVAL` | `15` | No | Metrics refresh interval (seconds) |
| `LISTEN_PORT` | `9877` | No | HTTP server port |
| `LISTEN_ADDR` | `0.0.0.0` | No | HTTP server bind address |

> **Security note**: `AMPLIFI_PASSWORD` has no default and the exporter will exit immediately if it is not set.

---

## Prometheus Configuration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: amplifi
    static_configs:
      - targets: ['amplifi-exporter:9877']
    scrape_interval: 15s
    scrape_timeout: 10s
```

---

## Grafana Dashboard

A Grafana dashboard is planned. In the meantime, you can import a custom dashboard using the metrics listed above. Key panels to build:

- **Connected clients over time** (`amplifi_clients_total`)
- **Per-client happiness score** (gauge panel)
- **WiFi throughput heatmap** (RX/TX bitrate per client)
- **Ethernet port utilization** (kbps per port)
- **Scrape health** (`amplifi_scrape_success`)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to submit improvements and bug fixes.

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability disclosure policy.

## License

[MIT](LICENSE) © 2025 Matan Baruch
