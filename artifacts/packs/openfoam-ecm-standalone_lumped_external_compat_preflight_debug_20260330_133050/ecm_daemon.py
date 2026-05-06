#!/usr/bin/env python3
"""
Persistent ECM computation daemon.

Runs as a long-lived background process that accepts ECM step requests over
a Unix domain socket. Loads all Python modules (numpy, pandas, ecm_step) once
at startup, eliminating the ~45 ms per-call process spawn + import overhead.

Usage (auto-started by ecm_coupling_wrapper.py --persistent-ecm):
    python3 ecm_daemon.py \\
        --socket ecm/ecm_daemon.sock \\
        --pid    ecm/ecm_daemon.pid \\
        --backend ecm-step \\
        --ecm-step-params   params.csv \\
        --ecm-step-cellprops cellprops.csv

Wire protocol (newline-delimited JSON over Unix socket):
    Request  {"dt_s": 0.5, "current_a": 79.0, "t_cell_degc": 40.0, "state": {...}}
    Response {"status": "ok",    "q_gen_w": ..., "v_t_v": ..., "state_next": {...}, "diagnostics": {...}}
    Response {"status": "error", "message": "..."}

Special requests:
    {"ping": true}          → {"pong": true}
    {"shutdown": true}      → {"bye": true}   (daemon exits)
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
from pathlib import Path


def _build_backend(args: argparse.Namespace):
    """Instantiate the ECM backend (mirrors logic in ecm_coupling_wrapper.py)."""
    from ecm_backend import (
        EcmStepBackend,
        MockECMBackend,
        MockECMConfig,
        ECMBackendError,
    )

    if args.backend == "mock-inproc":
        config = MockECMConfig(
            capacity_ah=args.capacity_ah,
            ocv_min_v=args.ocv_min_v,
            ocv_max_v=args.ocv_max_v,
            r0_ohm=args.r0_ohm,
            r1_ohm=args.r1_ohm,
            r2_ohm=args.r2_ohm,
            tau1_s=args.tau1_s,
            tau2_s=args.tau2_s,
            hyst_mag_v=args.hyst_mag_v,
        )
        config.validate()
        return MockECMBackend(config)

    if args.backend == "ecm-step":
        return EcmStepBackend(
            params_path=args.ecm_step_params,
            cellprops_path=args.ecm_step_cellprops,
            ecm_step_module_path=args.ecm_step_module,
        )

    raise ValueError(f"Unsupported backend for daemon: {args.backend!r}")


def _handle_request(backend, raw: str) -> str:
    """Process one JSON request line; return a JSON response line."""
    from ecm_backend import ECMBackendError, ECMState

    try:
        req = json.loads(raw)
    except json.JSONDecodeError as exc:
        return json.dumps({"status": "error", "message": f"JSON parse error: {exc}"})

    # Ping / shutdown
    if req.get("ping"):
        return json.dumps({"pong": True})
    if req.get("shutdown"):
        return json.dumps({"bye": True})

    # ECM step
    try:
        dt_s        = float(req["dt_s"])
        current_a   = float(req["current_a"])
        t_cell_degc = float(req["t_cell_degc"])
        state       = ECMState.from_dict(req["state"])
    except (KeyError, TypeError, ValueError, ECMBackendError) as exc:
        return json.dumps({"status": "error", "message": f"Bad request: {exc}"})

    try:
        result = backend.step(
            dt_s=dt_s,
            current_a=current_a,
            t_cell_degc=t_cell_degc,
            state=state,
        )
    except ECMBackendError as exc:
        return json.dumps({"status": "error", "message": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"status": "error", "message": f"Unhandled: {exc}"})

    resp: dict = {
        "status": "ok",
        "q_gen_w": float(result.q_gen_w),
        "state_next": result.state_next.to_dict(),
        "diagnostics": result.diagnostics,
    }
    if result.v_t_v is not None:
        resp["v_t_v"] = float(result.v_t_v)
    return json.dumps(resp)


def _serve(backend, sock_path: str, pid_path: str) -> None:
    """Main server loop: accept connections, handle requests, loop forever."""
    # Remove stale socket if present
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)
    os.chmod(sock_path, 0o600)

    # Write PID file
    Path(pid_path).write_text(str(os.getpid()))

    # Graceful shutdown on SIGTERM / SIGINT
    _stop = [False]

    def _sig(signum, frame):  # noqa: ANN001
        _stop[0] = True
        server.close()

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    print(f"[ecm_daemon] listening on {sock_path} (pid={os.getpid()})", flush=True)

    while not _stop[0]:
        try:
            conn, _ = server.accept()
        except OSError:
            break  # socket closed by signal handler

        try:
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk

            if buf:
                raw = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
                resp = _handle_request(backend, raw)
                conn.sendall((resp + "\n").encode("utf-8"))

                # Honour shutdown request
                if raw.strip().startswith('{"shutdown"') or '"shutdown": true' in raw:
                    conn.close()
                    break
        except Exception as exc:  # noqa: BLE001
            print(f"[ecm_daemon] connection error: {exc}", file=sys.stderr, flush=True)
        finally:
            conn.close()

    # Cleanup
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass
    try:
        os.unlink(pid_path)
    except FileNotFoundError:
        pass
    print("[ecm_daemon] stopped", flush=True)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Persistent ECM daemon (Unix socket server).")
    p.add_argument("--socket", required=True, help="Path for Unix domain socket.")
    p.add_argument("--pid", required=True, help="Path for PID file.")
    p.add_argument(
        "--backend",
        choices=["mock-inproc", "ecm-step"],
        default="ecm-step",
        help="Backend type.",
    )

    # ecm-step backend
    _here = Path(__file__).resolve().parent
    p.add_argument("--ecm-step-module", default=None)
    p.add_argument("--ecm-step-params",   default=str(_here / "params.csv"))
    p.add_argument("--ecm-step-cellprops", default=str(_here / "cellprops.csv"))

    # mock-inproc backend (4680 NCA defaults)
    p.add_argument("--capacity-ah",  type=float, default=9.0)
    p.add_argument("--ocv-min-v",    type=float, default=2.7)
    p.add_argument("--ocv-max-v",    type=float, default=4.2)
    p.add_argument("--r0-ohm",       type=float, default=0.007)
    p.add_argument("--r1-ohm",       type=float, default=0.0027)
    p.add_argument("--r2-ohm",       type=float, default=0.0015)
    p.add_argument("--tau1-s",       type=float, default=1.0)
    p.add_argument("--tau2-s",       type=float, default=45.0)
    p.add_argument("--hyst-mag-v",   type=float, default=0.003)

    return p.parse_args()


def main() -> None:
    args = _parse_args()

    sock_path = str(Path(args.socket).resolve())
    pid_path  = str(Path(args.pid).resolve())

    # Ensure parent directories exist
    Path(sock_path).parent.mkdir(parents=True, exist_ok=True)
    Path(pid_path).parent.mkdir(parents=True, exist_ok=True)

    print("[ecm_daemon] loading backend...", flush=True)
    backend = _build_backend(args)
    print(f"[ecm_daemon] backend ready ({args.backend})", flush=True)

    _serve(backend, sock_path, pid_path)


if __name__ == "__main__":
    main()
