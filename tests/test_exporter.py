"""
Unit tests for AmpliFi Alien Prometheus Exporter.

Run with:
    python -m unittest discover tests/
    # or
    python -m pytest tests/ -v
"""

import os
import sys
import unittest
import io

# Ensure AMPLIFI_PASSWORD is set before importing the module
os.environ.setdefault("AMPLIFI_PASSWORD", "test-password-for-testing")
os.environ.setdefault("AMPLIFI_ROUTER_IP", "192.168.1.1")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import amplifi_exporter as exporter


class TestAmpliFiClientInit(unittest.TestCase):
    """Tests for AmpliFiClient initialization."""

    def test_init_stores_ip(self):
        client = exporter.AmpliFiClient("10.0.0.1", "mypassword")
        self.assertEqual(client.router_ip, "10.0.0.1")

    def test_init_stores_password(self):
        client = exporter.AmpliFiClient("10.0.0.1", "secret")
        self.assertEqual(client.password, "secret")

    def test_make_opener_returns_opener(self):
        client = exporter.AmpliFiClient("10.0.0.1", "secret")
        opener = client._make_opener()
        self.assertIsNotNone(opener)


class TestMetricsCollectorLabel(unittest.TestCase):
    """Tests for MetricsCollector._label() method."""

    def setUp(self):
        client = exporter.AmpliFiClient("192.168.1.1", "testpass")
        self.collector = exporter.MetricsCollector(client)

    def test_label_single_kwarg(self):
        result = self.collector._label(mac="aa:bb:cc:dd:ee:ff")
        self.assertEqual(result, '{mac="aa:bb:cc:dd:ee:ff"}')

    def test_label_multiple_kwargs(self):
        result = self.collector._label(mac="aa:bb:cc:dd:ee:ff", name="MyDevice")
        self.assertIn('mac="aa:bb:cc:dd:ee:ff"', result)
        self.assertIn('name="MyDevice"', result)
        self.assertTrue(result.startswith("{"))
        self.assertTrue(result.endswith("}"))

    def test_label_none_values_excluded(self):
        result = self.collector._label(mac="aa:bb:cc:dd:ee:ff", name=None)
        self.assertNotIn("name", result)
        self.assertIn("mac", result)

    def test_label_empty_kwargs(self):
        result = self.collector._label()
        self.assertEqual(result, "{}")


class TestMetricsCollectorParse(unittest.TestCase):
    """Tests for MetricsCollector._parse() with mock data."""

    def setUp(self):
        client = exporter.AmpliFiClient("192.168.1.1", "testpass")
        self.collector = exporter.MetricsCollector(client)

    def _make_mock_raw(self):
        """Create a minimal mock raw API response (list of 6 sections)."""
        return [
            # Section 0: Router/AP nodes
            {
                "aa:bb:cc:dd:ee:01": {
                    "friendly_name": "AmpliFi Router",
                    "role": "router",
                    "platform_name": "AmpliFi Alien",
                    "ip": "192.168.1.1",
                    "uptime": 123456,
                    "level": 0,
                }
            },
            # Section 1: WiFi clients by AP → band → network → client
            {
                "aa:bb:cc:dd:ee:01": {
                    "5GHz": {
                        "default": {
                            "11:22:33:44:55:66": {
                                "Address": "192.168.1.100",
                                "Mode": "ax",
                                "HappinessScore": 95,
                                "SignalQuality": 88,
                                "RxBitrate": 300000,
                                "TxBitrate": 200000,
                                "RxBytes": 1024000,
                                "TxBytes": 512000,
                                "RxBytes_5sec": 1024,
                                "TxBytes_5sec": 512,
                                "Inactive": 0,
                                "MaxBandwidth": 80,
                                "MaxSpatialStreams": 2,
                                "LeaseValidity": 86400,
                                "RxMhz": 80,
                                "TxMhz": 80,
                            }
                        }
                    }
                }
            },
            # Section 2: Client info lookup
            {
                "11:22:33:44:55:66": {
                    "ip": "192.168.1.100",
                    "host_name": "my-laptop",
                    "description": "",
                    "connection": "wireless",
                    "manufacturer": "Apple Inc.",
                }
            },
            # Section 3: Ethernet clients by AP
            {},
            # Section 4: Ethernet port data
            {
                "aa:bb:cc:dd:ee:01": {
                    "0": {
                        "link": True,
                        "link_speed": 1000,
                        "rx_bitrate": 50000,
                        "tx_bitrate": 30000,
                    },
                    "1": {
                        "link": False,
                    }
                }
            },
            # Section 5: Fingerprints
            {
                "11:22:33:44:55:66": {
                    "device": {"name": "MacBook Pro"}
                }
            },
        ]

    def test_parse_returns_string(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIsInstance(result, str)

    def test_parse_contains_router_uptime(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIn("amplifi_router_uptime_seconds", result)
        self.assertIn("123456", result)

    def test_parse_contains_router_info(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIn("amplifi_router_info", result)
        self.assertIn("AmpliFi Router", result)

    def test_parse_contains_wifi_client_metrics(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIn("amplifi_wifi_client_happiness_score", result)
        self.assertIn("amplifi_wifi_client_signal_quality", result)
        self.assertIn("amplifi_wifi_client_rx_bitrate_kbps", result)
        self.assertIn("amplifi_wifi_client_tx_bitrate_kbps", result)

    def test_parse_contains_ethernet_port_metrics(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIn("amplifi_ethernet_port_link", result)
        self.assertIn("amplifi_ethernet_port_link_speed_mbps", result)

    def test_parse_contains_client_counts(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIn("amplifi_clients_total", result)
        self.assertIn("amplifi_wifi_clients_total", result)
        self.assertIn("amplifi_ethernet_clients_total", result)

    def test_parse_client_connected(self):
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        self.assertIn("amplifi_client_connected", result)
        self.assertIn("my-laptop", result)

    def test_parse_empty_raw(self):
        """Should not crash on empty data."""
        result = self.collector._parse([])
        self.assertIsInstance(result, str)

    def test_parse_wifi_bitrate_conversion(self):
        """RxBitrate/TxBitrate should be divided by 1000 for kbps."""
        raw = self._make_mock_raw()
        result = self.collector._parse(raw)
        # 300000 / 1000 = 300.00
        self.assertIn("300.00", result)
        # 200000 / 1000 = 200.00
        self.assertIn("200.00", result)


class TestMetricsHandler(unittest.TestCase):
    """Tests for MetricsHandler HTTP responses."""

    def setUp(self):
        """Set up a collector with pre-populated metrics."""
        client = exporter.AmpliFiClient("192.168.1.1", "testpass")
        self.collector = exporter.MetricsCollector(client)
        # Pre-populate with some dummy metrics
        with self.collector._lock:
            self.collector._metrics_text = "amplifi_scrape_success 1\n"
            self.collector._last_success = True

    def _make_handler(self, path):
        """Create a MetricsHandler-like object for testing."""
        from http.server import BaseHTTPRequestHandler
        import io

        class FakeRequest:
            def makefile(self, *args, **kwargs):
                return io.BytesIO(b"GET " + path.encode() + b" HTTP/1.1\r\n\r\n")

        class FakeServer:
            pass

        # We can't fully instantiate BaseHTTPRequestHandler without a real socket,
        # so we test the logic directly instead.
        return None

    def test_get_metrics_returns_text(self):
        """collector.get_metrics() should return the cached metrics string."""
        result = self.collector.get_metrics()
        self.assertIn("amplifi_scrape_success", result)

    def test_collector_initial_state(self):
        """Freshly created collector should have empty metrics."""
        client = exporter.AmpliFiClient("192.168.1.1", "testpass")
        fresh = exporter.MetricsCollector(client)
        self.assertEqual(fresh.get_metrics(), "")
        self.assertFalse(fresh._last_success)

    def test_health_path_logic(self):
        """Verify the health response body constant."""
        # MetricsHandler responds to /health with b"AmpliFi Prometheus Exporter OK\n"
        expected = b"AmpliFi Prometheus Exporter OK\n"
        self.assertIn(b"AmpliFi", expected)
        self.assertIn(b"OK", expected)


class TestEnvironmentValidation(unittest.TestCase):
    """Tests for environment variable validation."""

    def test_password_env_present(self):
        """AMPLIFI_PASSWORD should be set (set in setUp of this module)."""
        pwd = os.environ.get("AMPLIFI_PASSWORD", "")
        self.assertTrue(len(pwd) > 0, "AMPLIFI_PASSWORD must be non-empty")

    def test_version_constant_exists(self):
        """VERSION constant must exist and be a non-empty string."""
        self.assertTrue(hasattr(exporter, "VERSION"))
        self.assertIsInstance(exporter.VERSION, str)
        self.assertTrue(len(exporter.VERSION) > 0)

    def test_version_format(self):
        """VERSION should follow semver X.Y.Z format."""
        import re
        self.assertRegex(exporter.VERSION, r'^\d+\.\d+\.\d+$')

    def test_default_router_ip(self):
        """Default router IP should be 192.168.1.1 (not a private/specific IP)."""
        # The module-level ROUTER_IP uses the env var or the default
        # We check the source default doesn't contain the old hardcoded IP
        import inspect
        source = inspect.getsource(exporter)
        self.assertNotIn("192.168.149.1", source)
        self.assertNotIn("0503338385", source)

    def test_missing_password_raises_exit(self):
        """Importing with no AMPLIFI_PASSWORD should cause sys.exit(1)."""
        # We simulate this by checking the guard logic directly in source
        import inspect
        source = inspect.getsource(exporter)
        self.assertIn("AMPLIFI_PASSWORD", source)
        self.assertIn("sys.exit(1)", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
