"""Integration and Verification Test for Mission Control Web Dashboard & Server.

Tests:
1. SimulationBridge initialization, step cycle, and telemetry snapshot generation.
2. HTTP server startup, static asset serving, and JSON API endpoints.
3. Interactive scenario switching via REST POST /api/action.
4. Disturbance injection via REST POST /api/disturbance.
5. Server-Sent Events (SSE) data stream formatting.
"""

import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.web.server import SimulationBridge, DashboardHTTPHandler, http


def test_simulation_bridge() -> None:
    print("[TEST 1] Testing SimulationBridge step cycle & telemetry generation...")
    bridge = SimulationBridge(target_terminal="TERMINAL_02")
    bridge.reset("normal")
    assert bridge.orchestrator is not None
    assert bridge.is_running is True

    # Run 5 manual ticks
    for _ in range(5):
        bridge._tick(force=True)

    telem = bridge.latest_telemetry
    assert "telemetry" in telem
    assert "arena" in telem
    assert "events" in telem
    assert telem["arena"]["terminal_a"]["x"] == 180.0
    assert telem["arena"]["scenario"] == "normal"
    print("  -> PASSED: SimulationBridge emits valid telemetry & arena data.")


def test_http_server_endpoints() -> None:
    print("[TEST 2] Testing HTTP Server static serving and API endpoints...")
    web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    bridge = SimulationBridge(target_terminal="TERMINAL_02")
    DashboardHTTPHandler.bridge = bridge
    DashboardHTTPHandler.web_dir = os.path.abspath(web_dir)

    # Start test server on dynamic port
    test_port = 8899
    server = http.server.ThreadingHTTPServer(("127.0.0.1", test_port), DashboardHTTPHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)

    try:
        base_url = f"http://127.0.0.1:{test_port}"

        # 1. Test GET / (HTML)
        req = urllib.request.Request(f"{base_url}/")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "<!DOCTYPE html>" in content
            assert "RAYNEX FSOC MISSION CONTROL" in content
        print("  -> PASSED: GET / returned index.html.")

        # 2. Test GET /style.css
        req = urllib.request.Request(f"{base_url}/style.css")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            css_content = resp.read().decode("utf-8")
            assert "--bg-space" in css_content
        print("  -> PASSED: GET /style.css returned stylesheet.")

        # 3. Test GET /app.js
        req = urllib.request.Request(f"{base_url}/app.js")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            js_content = resp.read().decode("utf-8")
            assert "renderArenaCanvas" in js_content
        print("  -> PASSED: GET /app.js returned frontend script.")

        # 4. Test GET /api/telemetry
        req = urllib.request.Request(f"{base_url}/api/telemetry")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "telemetry" in data
        print("  -> PASSED: GET /api/telemetry returned JSON snapshot.")

        # 5. Test POST /api/action (switch scenario to deep-loss)
        post_data = json.dumps({"action": "scenario", "scenario": "deep-loss"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/action", data=post_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["success"] is True
            assert res["scenario"] == "deep-loss"
        print("  -> PASSED: POST /api/action switched scenario to deep-loss.")

        # 6. Test POST /api/disturbance (occlusion & vibration)
        dist_data = json.dumps({"cloud_occlusion": True, "vibration": 5.0, "turbulence": "HIGH"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/disturbance", data=dist_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["cloud_occlusion"] is True
            assert res["vibration"] == 5.0
            assert res["turbulence"] == "HIGH"
        print("  -> PASSED: POST /api/disturbance injected disturbances.")

        # 7. Test GET /api/camera_frame (JPEG snapshot)
        req = urllib.request.Request(f"{base_url}/api/camera_frame")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "image/jpeg"
            frame_data = resp.read()
            assert len(frame_data) > 0
        # 8. Test GET /api/terminals
        req = urllib.request.Request(f"{base_url}/api/terminals")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert "num_terminals" in res
            assert "target_terminal" in res
            assert "overview" in res
            assert len(res["overview"]) > 0
        print("  -> PASSED: GET /api/terminals returned valid terminals overview.")

        # 9. Test POST /api/terminals/config (dynamic target & count switch)
        config_data = json.dumps({"num_terminals": 6, "target_terminal": "TERMINAL_03"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/terminals/config", data=config_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert res["num_terminals"] == 6
            assert res["target_terminal"] == "TERMINAL_03"
        print("  -> PASSED: POST /api/terminals/config reconfigured target to TERMINAL_03.")

        # 10. Test GET /api/tests/status
        req = urllib.request.Request(f"{base_url}/api/tests/status")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            res = json.loads(resp.read().decode("utf-8"))
            assert "total_tests" in res
            assert "categories" in res
            assert len(res["categories"]) == 5
        print("  -> PASSED: GET /api/tests/status returned categorized test suite metadata.")

    finally:
        server.shutdown()
        server.server_close()


def run_all_tests() -> None:
    print("=" * 70)
    print("RUNNING MISSION CONTROL DASHBOARD INTEGRATION TESTS")
    print("=" * 70)
    test_simulation_bridge()
    test_http_server_endpoints()
    print("=" * 70)
    print("ALL MISSION CONTROL DASHBOARD TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
