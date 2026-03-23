#!/usr/bin/env python3
"""
AmpliFi Alien Prometheus Exporter
Exposes metrics from all AmpliFi API sections via /metrics endpoint.

Metrics exported:
  - amplifi_router_uptime_seconds         - Router uptime
  - amplifi_router_info                   - Router info (labels: friendly_name, role, platform, ip)
  - amplifi_wifi_client_happiness_score   - Client happiness score (0-100)
  - amplifi_wifi_client_signal_quality    - Client signal quality (0-100)
  - amplifi_wifi_client_rx_bitrate_kbps   - Client RX bitrate (kbps)
  - amplifi_wifi_client_tx_bitrate_kbps   - Client TX bitrate (kbps)
  - amplifi_wifi_client_rx_bytes_total    - Client total RX bytes
  - amplifi_wifi_client_tx_bytes_total    - Client total TX bytes
  - amplifi_wifi_client_rx_bytes_per_sec  - Client RX bytes in last 5s window
  - amplifi_wifi_client_tx_bytes_per_sec  - Client TX bytes in last 5s window
  - amplifi_wifi_client_inactive          - Client inactive flag
  - amplifi_wifi_client_max_bandwidth_mhz - Client max bandwidth (MHz)
  - amplifi_wifi_client_max_spatial_streams - Client max spatial streams
  - amplifi_wifi_client_lease_validity_sec  - Client DHCP lease remaining (seconds)
  - amplifi_ethernet_port_link            - Ethernet port link status (0/1)
  - amplifi_ethernet_port_link_speed_mbps - Ethernet port link speed (Mbps)
  - amplifi_ethernet_port_rx_bitrate_kbps - Ethernet port RX bitrate (kbps)
  - amplifi_ethernet_port_tx_bitrate_kbps - Ethernet port TX bitrate (kbps)
  - amplifi_client_connected              - Currently connected client info gauge
  - amplifi_clients_total                 - Total connected clients
  - amplifi_wifi_clients_total            - Total WiFi clients
  - amplifi_ethernet_clients_total        - Total Ethernet clients
  - amplifi_scrape_success                - 1 if last scrape succeeded, 0 otherwise
  - amplifi_scrape_duration_seconds       - Duration of last scrape
"""

import os
import re
import ssl
import sys
import time
import json
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

VERSION = "1.0.2"

# Config from env or defaults
ROUTER_IP = os.environ.get("AMPLIFI_ROUTER_IP", "192.168.1.1")
ROUTER_PASSWORD = os.environ.get("AMPLIFI_PASSWORD", "")
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "15"))
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9877"))
LISTEN_ADDR = os.environ.get("LISTEN_ADDR", "0.0.0.0")

# Validate required config
if not ROUTER_PASSWORD:
    print("[ERROR] AMPLIFI_PASSWORD environment variable is required but not set.", file=sys.stderr)
    print("[ERROR] Please set AMPLIFI_PASSWORD to your AmpliFi router password.", file=sys.stderr)
    sys.exit(1)


class AmpliFiClient:
    """Handles authentication and data fetching from AmpliFi router."""

    def __init__(self, router_ip: str, password: str):
        self.router_ip = router_ip
        self.password = password

    def _make_opener(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        jar = http.cookiejar.CookieJar()
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar),
            urllib.request.HTTPSHandler(context=ctx)
        )

    def fetch(self) -> dict:
        opener = self._make_opener()

        # Step 1: GET login page for CSRF token
        resp = opener.open(f"https://{self.router_ip}/login.php", timeout=15)
        html = resp.read().decode()
        m = re.search(r"name=['\"]token['\"] value=['\"]([a-f0-9]+)['\"]", html)
        if not m:
            raise RuntimeError("Cannot extract CSRF token")
        csrf_token = m.group(1)

        # Step 2: POST login
        data = urllib.parse.urlencode({"token": csrf_token, "password": self.password}).encode()
        req = urllib.request.Request(f"https://{self.router_ip}/login.php", data=data, method="POST")
        opener.open(req, timeout=15)

        # Step 3: GET info.php for data token
        resp = opener.open(f"https://{self.router_ip}/info.php", timeout=15)
        html = resp.read().decode()
        m = re.search(r"var token='([a-f0-9]+)'", html)
        if not m:
            raise RuntimeError("Cannot extract data token")
        data_token = m.group(1)

        # Step 4: POST info-async.php for full data
        post_data = urllib.parse.urlencode({"do": "full", "token": data_token}).encode()
        req = urllib.request.Request(
            f"https://{self.router_ip}/info-async.php", data=post_data, method="POST"
        )
        resp = opener.open(req, timeout=15)
        return json.loads(resp.read().decode())


class MetricsCollector:
    """Collects and caches metrics from AmpliFi."""

    def __init__(self, client: AmpliFiClient):
        self.client = client
        self._lock = threading.Lock()
        self._metrics_text = ""
        self._last_success = False
        self._last_duration = 0.0

    def collect(self):
        """Fetch data and update cached metrics."""
        start = time.time()
        try:
            raw = self.client.fetch()
            metrics = self._parse(raw)
            duration = time.time() - start
            metrics += f"\n# HELP amplifi_scrape_success 1 if last scrape succeeded\n"
            metrics += f"# TYPE amplifi_scrape_success gauge\n"
            metrics += f"amplifi_scrape_success 1\n"
            metrics += f"\n# HELP amplifi_scrape_duration_seconds Duration of last scrape\n"
            metrics += f"# TYPE amplifi_scrape_duration_seconds gauge\n"
            metrics += f"amplifi_scrape_duration_seconds {duration:.3f}\n"
            with self._lock:
                self._metrics_text = metrics
                self._last_success = True
                self._last_duration = duration
        except Exception as e:
            duration = time.time() - start
            print(f"[ERROR] Scrape failed: {e}")
            fail_metrics = f"# HELP amplifi_scrape_success 1 if last scrape succeeded\n"
            fail_metrics += f"# TYPE amplifi_scrape_success gauge\n"
            fail_metrics += f"amplifi_scrape_success 0\n"
            fail_metrics += f"# HELP amplifi_scrape_duration_seconds Duration of last scrape\n"
            fail_metrics += f"# TYPE amplifi_scrape_duration_seconds gauge\n"
            fail_metrics += f"amplifi_scrape_duration_seconds {duration:.3f}\n"
            with self._lock:
                # Keep old metrics but update scrape status
                if self._metrics_text:
                    # Replace scrape_success in existing metrics
                    self._metrics_text = fail_metrics
                else:
                    self._metrics_text = fail_metrics
                self._last_success = False

    def get_metrics(self) -> str:
        with self._lock:
            return self._metrics_text

    def _label(self, **kwargs) -> str:
        parts = [f'{k}="{v}"' for k, v in kwargs.items() if v is not None]
        return "{" + ",".join(parts) + "}"

    def _parse(self, raw: list) -> str:
        lines = []

        # Build client info lookup from section [2]
        client_info = {}  # mac -> dict
        if len(raw) > 2 and isinstance(raw[2], dict):
            client_info = raw[2]

        # Build fingerprint/device name lookup from section [5]
        fingerprints = {}  # mac -> device name
        if len(raw) > 5 and isinstance(raw[5], dict):
            for mac, fp in raw[5].items():
                if isinstance(fp, dict):
                    dev = fp.get("device", {})
                    if dev.get("name"):
                        fingerprints[mac] = dev.get("name", "")

        # Helper: get friendly name for a MAC
        def friendly_name(mac: str) -> str:
            info = client_info.get(mac, {})
            return (info.get("description") or info.get("host_name") or
                    fingerprints.get(mac, "") or mac)

        # ── Section [0]: Router / AP node info ──────────────────────────────
        lines.append("# HELP amplifi_router_uptime_seconds Router uptime in seconds")
        lines.append("# TYPE amplifi_router_uptime_seconds gauge")
        lines.append("# HELP amplifi_router_info Router metadata (value always 1)")
        lines.append("# TYPE amplifi_router_info gauge")

        if len(raw) > 0 and isinstance(raw[0], dict):
            for mac, node in raw[0].items():
                if not isinstance(node, dict):
                    continue
                fname = node.get("friendly_name", "")
                role = node.get("role", "")
                platform = node.get("platform_name", "")
                ip = node.get("ip", "")
                uptime = node.get("uptime", 0)
                level = node.get("level", 0)
                lbl = self._label(mac=mac, friendly_name=fname, role=role,
                                  platform=platform, ip=ip, level=str(level))
                lines.append(f"amplifi_router_uptime_seconds{self._label(mac=mac, friendly_name=fname)} {uptime}")
                lines.append(f"amplifi_router_info{lbl} 1")

        # ── Section [1]: WiFi client metrics ────────────────────────────────
        wifi_clients = {}  # mac -> enriched data for later use

        lines.append("\n# HELP amplifi_wifi_client_happiness_score WiFi client happiness score (0-100)")
        lines.append("# TYPE amplifi_wifi_client_happiness_score gauge")
        lines.append("# HELP amplifi_wifi_client_signal_quality WiFi client signal quality (0-100)")
        lines.append("# TYPE amplifi_wifi_client_signal_quality gauge")
        lines.append("# HELP amplifi_wifi_client_rx_bitrate_kbps WiFi client RX bitrate in kbps")
        lines.append("# TYPE amplifi_wifi_client_rx_bitrate_kbps gauge")
        lines.append("# HELP amplifi_wifi_client_tx_bitrate_kbps WiFi client TX bitrate in kbps")
        lines.append("# TYPE amplifi_wifi_client_tx_bitrate_kbps gauge")
        lines.append("# HELP amplifi_wifi_client_rx_bytes_total WiFi client total RX bytes")
        lines.append("# TYPE amplifi_wifi_client_rx_bytes_total counter")
        lines.append("# HELP amplifi_wifi_client_tx_bytes_total WiFi client total TX bytes")
        lines.append("# TYPE amplifi_wifi_client_tx_bytes_total counter")
        lines.append("# HELP amplifi_wifi_client_rx_bytes_5sec WiFi client RX bytes in last 5s")
        lines.append("# TYPE amplifi_wifi_client_rx_bytes_5sec gauge")
        lines.append("# HELP amplifi_wifi_client_tx_bytes_5sec WiFi client TX bytes in last 5s")
        lines.append("# TYPE amplifi_wifi_client_tx_bytes_5sec gauge")
        lines.append("# HELP amplifi_wifi_client_rx_bytes_15sec WiFi client RX bytes in last 15s")
        lines.append("# TYPE amplifi_wifi_client_rx_bytes_15sec gauge")
        lines.append("# HELP amplifi_wifi_client_tx_bytes_15sec WiFi client TX bytes in last 15s")
        lines.append("# TYPE amplifi_wifi_client_tx_bytes_15sec gauge")
        lines.append("# HELP amplifi_wifi_client_rx_bytes_60sec WiFi client RX bytes in last 60s")
        lines.append("# TYPE amplifi_wifi_client_rx_bytes_60sec gauge")
        lines.append("# HELP amplifi_wifi_client_tx_bytes_60sec WiFi client TX bytes in last 60s")
        lines.append("# TYPE amplifi_wifi_client_tx_bytes_60sec gauge")
        lines.append("# HELP amplifi_wifi_client_inactive WiFi client inactive flag")
        lines.append("# TYPE amplifi_wifi_client_inactive gauge")
        lines.append("# HELP amplifi_wifi_client_max_bandwidth_mhz WiFi client max bandwidth (MHz)")
        lines.append("# TYPE amplifi_wifi_client_max_bandwidth_mhz gauge")
        lines.append("# HELP amplifi_wifi_client_max_spatial_streams WiFi client max spatial streams")
        lines.append("# TYPE amplifi_wifi_client_max_spatial_streams gauge")
        lines.append("# HELP amplifi_wifi_client_lease_validity_seconds DHCP lease validity remaining (seconds)")
        lines.append("# TYPE amplifi_wifi_client_lease_validity_seconds gauge")
        lines.append("# HELP amplifi_wifi_client_rx_mhz WiFi client RX channel width (MHz)")
        lines.append("# TYPE amplifi_wifi_client_rx_mhz gauge")
        lines.append("# HELP amplifi_wifi_client_tx_mhz WiFi client TX channel width (MHz)")
        lines.append("# TYPE amplifi_wifi_client_tx_mhz gauge")

        if len(raw) > 1 and isinstance(raw[1], dict):
            for ap_mac, bands in raw[1].items():
                ap_name = raw[0].get(ap_mac, {}).get("friendly_name", ap_mac) if len(raw) > 0 else ap_mac
                if not isinstance(bands, dict):
                    continue
                for band, networks in bands.items():
                    if not isinstance(networks, dict):
                        continue
                    for network, clients in networks.items():
                        if not isinstance(clients, dict):
                            continue
                        for client_mac, c in clients.items():
                            if not isinstance(c, dict):
                                continue
                            name = friendly_name(client_mac)
                            ip = c.get("Address", client_info.get(client_mac, {}).get("ip", ""))
                            mode = c.get("Mode", "")
                            wifi_clients[client_mac] = {
                                "ap_mac": ap_mac, "ap_name": ap_name,
                                "band": band, "network": network,
                                "name": name, "ip": ip, "mode": mode
                            }

                            lbl = self._label(
                                mac=client_mac, name=name, ip=ip,
                                ap_mac=ap_mac, ap_name=ap_name,
                                band=band, network=network, mode=mode
                            )

                            # Use 64-bit RxBytes if available
                            rx_bytes = c.get("RxBytes64", c.get("RxBytes", 0))
                            tx_bytes = c.get("TxBytes", 0)

                            if "HappinessScore" in c:
                                lines.append(f"amplifi_wifi_client_happiness_score{lbl} {c['HappinessScore']}")
                            if "SignalQuality" in c:
                                lines.append(f"amplifi_wifi_client_signal_quality{lbl} {c['SignalQuality']}")
                            if "RxBitrate" in c:
                                lines.append(f"amplifi_wifi_client_rx_bitrate_kbps{lbl} {c['RxBitrate'] / 1000:.2f}")
                            if "TxBitrate" in c:
                                lines.append(f"amplifi_wifi_client_tx_bitrate_kbps{lbl} {c['TxBitrate'] / 1000:.2f}")
                            lines.append(f"amplifi_wifi_client_rx_bytes_total{lbl} {rx_bytes}")
                            lines.append(f"amplifi_wifi_client_tx_bytes_total{lbl} {tx_bytes}")
                            if "RxBytes_5sec" in c:
                                lines.append(f"amplifi_wifi_client_rx_bytes_5sec{lbl} {c['RxBytes_5sec']}")
                            if "TxBytes_5sec" in c:
                                lines.append(f"amplifi_wifi_client_tx_bytes_5sec{lbl} {c['TxBytes_5sec']}")
                            if "RxBytes_15sec" in c:
                                lines.append(f"amplifi_wifi_client_rx_bytes_15sec{lbl} {c['RxBytes_15sec']}")
                            if "TxBytes_15sec" in c:
                                lines.append(f"amplifi_wifi_client_tx_bytes_15sec{lbl} {c['TxBytes_15sec']}")
                            if "RxBytes_60sec" in c:
                                lines.append(f"amplifi_wifi_client_rx_bytes_60sec{lbl} {c['RxBytes_60sec']}")
                            if "TxBytes_60sec" in c:
                                lines.append(f"amplifi_wifi_client_tx_bytes_60sec{lbl} {c['TxBytes_60sec']}")
                            if "Inactive" in c:
                                lines.append(f"amplifi_wifi_client_inactive{lbl} {c['Inactive']}")
                            if "MaxBandwidth" in c:
                                lines.append(f"amplifi_wifi_client_max_bandwidth_mhz{lbl} {c['MaxBandwidth']}")
                            if "MaxSpatialStreams" in c:
                                lines.append(f"amplifi_wifi_client_max_spatial_streams{lbl} {c['MaxSpatialStreams']}")
                            if "LeaseValidity" in c:
                                lines.append(f"amplifi_wifi_client_lease_validity_seconds{lbl} {c['LeaseValidity']}")
                            if "RxMhz" in c:
                                lines.append(f"amplifi_wifi_client_rx_mhz{lbl} {c['RxMhz']}")
                            if "TxMhz" in c:
                                lines.append(f"amplifi_wifi_client_tx_mhz{lbl} {c['TxMhz']}")

        # ── Section [4]: Ethernet port throughput ───────────────────────────
        lines.append("\n# HELP amplifi_ethernet_port_link Ethernet port link status (1=up, 0=down)")
        lines.append("# TYPE amplifi_ethernet_port_link gauge")
        lines.append("# HELP amplifi_ethernet_port_link_speed_mbps Ethernet port link speed in Mbps")
        lines.append("# TYPE amplifi_ethernet_port_link_speed_mbps gauge")
        lines.append("# HELP amplifi_ethernet_port_rx_bitrate_kbps Ethernet port RX bitrate in kbps")
        lines.append("# TYPE amplifi_ethernet_port_rx_bitrate_kbps gauge")
        lines.append("# HELP amplifi_ethernet_port_tx_bitrate_kbps Ethernet port TX bitrate in kbps")
        lines.append("# TYPE amplifi_ethernet_port_tx_bitrate_kbps gauge")

        if len(raw) > 4 and isinstance(raw[4], dict):
            for ap_mac, ports in raw[4].items():
                ap_name = raw[0].get(ap_mac, {}).get("friendly_name", ap_mac) if len(raw) > 0 else ap_mac
                if not isinstance(ports, dict):
                    continue
                for port_id, port in ports.items():
                    if not isinstance(port, dict):
                        continue
                    lbl = self._label(ap_mac=ap_mac, ap_name=ap_name, port=port_id)
                    link = 1 if port.get("link", False) else 0
                    lines.append(f"amplifi_ethernet_port_link{lbl} {link}")
                    if port.get("link"):
                        lines.append(f"amplifi_ethernet_port_link_speed_mbps{lbl} {port.get('link_speed', 0)}")
                        lines.append(f"amplifi_ethernet_port_rx_bitrate_kbps{lbl} {port.get('rx_bitrate', 0)}")
                        lines.append(f"amplifi_ethernet_port_tx_bitrate_kbps{lbl} {port.get('tx_bitrate', 0)}")

        # ── Section [2] + [3]: Connected client info metrics ─────────────────
        lines.append("\n# HELP amplifi_client_connected Connected client info (value=1 while connected)")
        lines.append("# TYPE amplifi_client_connected gauge")

        eth_clients_by_ap = raw[3] if len(raw) > 3 and isinstance(raw[3], dict) else {}
        eth_client_macs = set()
        for ap_mac, eth_map in eth_clients_by_ap.items():
            if isinstance(eth_map, dict):
                eth_client_macs.update(eth_map.keys())

        wifi_count = 0
        eth_count = 0
        total_count = 0

        if len(raw) > 2 and isinstance(raw[2], dict):
            for mac, info in raw[2].items():
                if not isinstance(info, dict) or "ip" not in info:
                    continue
                name = friendly_name(mac)
                ip = info.get("ip", "")
                connection = info.get("connection", "wireless")
                manufacturer = info.get("manufacturer", "")

                # Determine band for wifi clients
                band = ""
                if mac in wifi_clients:
                    band = wifi_clients[mac].get("band", "")
                    wifi_count += 1
                elif mac in eth_client_macs or connection == "ethernet":
                    connection = "ethernet"
                    eth_count += 1
                else:
                    wifi_count += 1

                total_count += 1
                lbl = self._label(
                    mac=mac, name=name, ip=ip,
                    connection=connection, band=band,
                    manufacturer=manufacturer[:40] if manufacturer else ""
                )
                lines.append(f"amplifi_client_connected{lbl} 1")

        # ── Summary counts ───────────────────────────────────────────────────
        lines.append("\n# HELP amplifi_clients_total Total connected clients")
        lines.append("# TYPE amplifi_clients_total gauge")
        lines.append(f"amplifi_clients_total {total_count}")
        lines.append("# HELP amplifi_wifi_clients_total Total WiFi connected clients")
        lines.append("# TYPE amplifi_wifi_clients_total gauge")
        lines.append(f"amplifi_wifi_clients_total {wifi_count}")
        lines.append("# HELP amplifi_ethernet_clients_total Total Ethernet connected clients")
        lines.append("# TYPE amplifi_ethernet_clients_total gauge")
        lines.append(f"amplifi_ethernet_clients_total {eth_count}")

        return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves Prometheus metrics."""

    collector: MetricsCollector = None

    def do_GET(self):
        if self.path in ("/metrics", "/metrics/"):
            text = self.collector.get_metrics()
            if not text:
                # Trigger immediate collect if no data yet
                self.collector.collect()
                text = self.collector.get_metrics()
            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"AmpliFi Prometheus Exporter OK\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        # Only log non-metrics requests
        if "/metrics" not in (args[0] if args else ""):
            print(f"[HTTP] {fmt % args}")


def background_scraper(collector: MetricsCollector, interval: int):
    """Background thread that refreshes metrics every interval seconds."""
    while True:
        try:
            collector.collect()
            print(f"[INFO] Scraped OK (success={collector._last_success}, duration={collector._last_duration:.2f}s)")
        except Exception as e:
            print(f"[ERROR] Background scrape error: {e}")
        time.sleep(interval)


def main():
    print(f"[INFO] AmpliFi Exporter v{VERSION} starting")
    print(f"[INFO] Router: https://{ROUTER_IP}")
    print(f"[INFO] Scrape interval: {SCRAPE_INTERVAL}s")
    print(f"[INFO] Listening on {LISTEN_ADDR}:{LISTEN_PORT}")

    client = AmpliFiClient(ROUTER_IP, ROUTER_PASSWORD)
    collector = MetricsCollector(client)

    # Initial scrape
    print("[INFO] Running initial scrape...")
    collector.collect()

    # Start background scraper thread
    t = threading.Thread(target=background_scraper, args=(collector, SCRAPE_INTERVAL), daemon=True)
    t.start()

    # Start HTTP server
    MetricsHandler.collector = collector
    server = HTTPServer((LISTEN_ADDR, LISTEN_PORT), MetricsHandler)
    print(f"[INFO] Serving metrics at http://{LISTEN_ADDR}:{LISTEN_PORT}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[INFO] Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()

# trigger build
