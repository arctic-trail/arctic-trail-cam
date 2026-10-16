#!/usr/bin/env python3
# File: collector_hub/receiver_hub.py
# Description: Production-Hardened Passive UDP Optical Diode Receiver & Cryptographic Reassembler
# License: MIT
import os
import sys
import time
import json
import socket
import struct
import hashlib
import errno
import argparse
import subprocess
from collections import OrderedDict
try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
except ModuleNotFoundError:
    if __name__ == "__main__":
        _venv_py = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".venv", "bin", "python3")
        if os.path.isfile(_venv_py) and os.path.realpath(sys.executable) != os.path.realpath(_venv_py):
            os.execv(_venv_py, [_venv_py, "-B"] + sys.argv)
    raise

# ==============================================================================
# Configuration & Security Parameters
# ==============================================================================
UDP_PORT = int(os.getenv("UDP_PORT", "5514"))
OUT_DIR = os.getenv("OUT_DIR", "./verified_alerts")
CHUNK_TTL_SECONDS = 15.0     # Maximum time to hold partial frames in memory
MAX_CLOCK_SKEW_SEC = int(os.getenv("MAX_CLOCK_SKEW_SEC", "300"))  # Max clock drift threshold
STRICT_CLOCK_SKEW = os.getenv("STRICT_CLOCK_SKEW", "0") == "1"    # Drop vs warn on off-grid clock skew
MAX_CHUNKS_PER_FRAME = 1024  # Cap at 1 MB per image to prevent memory DoS
MAX_PENDING_FRAMES = 64      # Hard cap on concurrent partial frames in memory
MAX_SAVED_ALERTS = int(os.getenv("MAX_SAVED_ALERTS", "0"))  # 0 = unlimited; >0 = circular cap for buried dead-drop vaults

# Map of authorized camera Node IDs to their 32-byte Ed25519 Public Keys
DEFAULT_EXAMPLE_PUBKEYS = {
    "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
}

KNOWN_NODE_PUBKEYS = {
    "NODE-NORTH-01": VerifyKey(bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")),
}

# ==============================================================================
# Replay Tracking & Buffer State
# ==============================================================================
# node_id -> {"last_ts": int, "seen_nonces": OrderedDict(nonce -> ts)}
node_security_state = {}

# prefix (16-char hex nonce) -> {"meta": dict, "created_at": float}
pending_meta = {}

# prefix (16-char hex nonce) -> {"chunks": dict(int -> bytes), "total": int, "created_at": float}
pending_chunks = {}

# prefix -> {"nonce": str, "completed_at": float} (tracks recently completed carousel bursts)
completed_prefixes = OrderedDict()


def load_authorized_nodes(out_dir=None):
    """Loads provisioned node public keys from authorized_nodes.json if present."""
    target_dir = out_dir or OUT_DIR
    reg_file = os.getenv("AUTHORIZED_NODES_FILE", os.path.join(target_dir, "authorized_nodes.json"))
    if os.path.isfile(reg_file):
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for nid, pub_hex in data.items():
                if isinstance(pub_hex, str) and len(pub_hex) == 64:
                    KNOWN_NODE_PUBKEYS[nid] = VerifyKey(bytes.fromhex(pub_hex))
        except Exception as e:
            print(f"[!] Warning loading {reg_file}: {e}", file=sys.stderr)


def load_seen_nonces_from_disk(out_dir=None):
    """Loads persisted (node_id, nonce, ts) records from disk so anti-replay survives restarts."""
    target_dir = out_dir or OUT_DIR
    cache_path = os.path.join(target_dir, "seen_nonces.jsonl")
    if not os.path.isfile(cache_path):
        return
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    nid = rec.get("node")
                    nonce = rec.get("nonce")
                    ts = int(rec.get("ts", 0))
                    if nid and nonce:
                        if nid not in node_security_state:
                            node_security_state[nid] = {"last_ts": ts, "seen_nonces": OrderedDict()}
                        seen = node_security_state[nid]["seen_nonces"]
                        seen[nonce] = ts
                        if len(seen) > 500:
                            seen.popitem(last=False)
                        node_security_state[nid]["last_ts"] = max(node_security_state[nid]["last_ts"], ts)
                except Exception:
                    pass
    except Exception:
        pass


def _persist_seen_nonce(node_id, nonce, ts, out_dir=None):
    """Appends a verified nonce to disk cache in OUT_DIR."""
    target_dir = out_dir or OUT_DIR
    cache_path = os.path.join(target_dir, "seen_nonces.jsonl")
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"node": node_id, "nonce": nonce, "ts": int(ts)}) + "\n")
    except OSError:
        pass


def write_receiver_heartbeat(port=UDP_PORT, out_dir=None):
    """Writes a lightweight heartbeat file so dashboard_server.py can verify receiver liveness."""
    target_dir = out_dir or OUT_DIR
    hb_path = os.path.join(target_dir, "receiver_heartbeat.json")
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(hb_path, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "port": port, "updated_at": time.time()}, f)
    except OSError:
        pass


def cleanup_stale_buffers():
    """Sliding-window garbage collector to prevent memory leaks from dropped packets or orphaned metadata."""
    now = time.time()
    stale_chunk_prefixes = [
        p for p, data in pending_chunks.items()
        if now - data["created_at"] > CHUNK_TTL_SECONDS
    ]
    for p in stale_chunk_prefixes:
        del pending_chunks[p]
        if p in pending_meta:
            del pending_meta[p]

    stale_meta_prefixes = [
        p for p, data in pending_meta.items()
        if now - data["created_at"] > CHUNK_TTL_SECONDS
    ]
    for p in stale_meta_prefixes:
        del pending_meta[p]

    stale_completed = [
        p for p, data in completed_prefixes.items()
        if now - data["completed_at"] > CHUNK_TTL_SECONDS
    ]
    for p in stale_completed:
        del completed_prefixes[p]


def _enforce_queue_cap(store_dict, max_entries=MAX_PENDING_FRAMES):
    """Evicts oldest entries if store_dict is still at capacity after stale cleanup."""
    if len(store_dict) >= max_entries:
        cleanup_stale_buffers()
    while len(store_dict) >= max_entries and store_dict:
        oldest_key = min(store_dict, key=lambda k: store_dict[k].get("created_at", 0.0))
        del store_dict[oldest_key]


def try_reconstruct_image(prefix):
    """
    Reconstructs JPEG frame and verifies SHA-256 integrity when both
    signed metadata and 100% of binary chunks are present.
    If SHA-256 fails on Pass 1 (bit error), retains pending_meta and clears
    chunk buffer so Pass 2 / Pass 3 carousel copies can repair the image.
    """
    if prefix not in pending_meta or prefix not in pending_chunks:
        return False

    meta = pending_meta[prefix]["meta"]
    chunk_store = pending_chunks[prefix]
    total = chunk_store["total"]

    if total == 0:
        # Valid telemetry-only alert with no image payload
        completed_prefixes[prefix] = {"nonce": meta.get("nonce", ""), "completed_at": time.time()}
        del pending_meta[prefix]
        del pending_chunks[prefix]
        return True

    if len(chunk_store["chunks"]) == total and all(i in chunk_store["chunks"] for i in range(total)):
        full_img = b"".join(chunk_store["chunks"][i] for i in range(total))
        computed_sha256 = hashlib.sha256(full_img).hexdigest()

        if computed_sha256 == meta.get("img_sha256"):
            node_id = meta.get("node", "UNKNOWN")
            ts = meta.get("ts", int(time.time()))
            nonce_val = meta.get("nonce", prefix)
            rel_name = f"{node_id}_{ts}_{nonce_val[:8]}.jpg"
            fname = os.path.join(OUT_DIR, rel_name)
            try:
                os.makedirs(OUT_DIR, exist_ok=True)
                with open(fname, "wb") as f:
                    f.write(full_img)
                print(f"    [+] Image verified ({len(full_img)} bytes) -> Saved to {fname}")
            except OSError as e:
                print(f"    [!] Storage error writing {fname}: {e}", file=sys.stderr)

            # Structured event logging to JSONL journal
            journal_path = os.path.join(OUT_DIR, "alerts_journal.jsonl")
            alert_entry = {
                "timestamp": ts,
                "received_at": int(time.time()),
                "node": node_id,
                "nonce": nonce_val,
                "image_file": f"./verified_alerts/{rel_name}",
                "image_bytes": len(full_img),
                "image_sha256": meta.get("img_sha256"),
                "detections": meta.get("detections", []),
                "pico_trig": meta.get("pico_trig", ""),
                "camera_ok": meta.get("camera_ok", True),
                "inference_backend": meta.get("inference_backend", "unknown"),
                "clock_drift_warning": bool(meta.get("_clock_drift_warning", False)),
                "verified": True
            }
            try:
                with open(journal_path, "a", encoding="utf-8") as jf:
                    jf.write(json.dumps(alert_entry) + "\n")
                    jf.flush()
                    os.fsync(jf.fileno())
            except OSError:
                pass

            # Optional circular disk retention cap for unattended buried Dead-Drop Collector Vaults
            if MAX_SAVED_ALERTS and MAX_SAVED_ALERTS > 0:
                enforce_storage_retention(OUT_DIR, MAX_SAVED_ALERTS)

            # Optional external dispatch hook (e.g. Telegram / Signal / Home Assistant / Decoupled Relay)
            hook_script = os.getenv("ALERT_HOOK_SCRIPT")
            if hook_script and os.path.exists(hook_script):
                try:
                    subprocess.Popen([hook_script, fname, json.dumps(alert_entry)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    print(f"    [!] Alert hook error: {e}", file=sys.stderr)

            completed_prefixes[prefix] = {"nonce": nonce_val, "completed_at": time.time()}
            if len(completed_prefixes) > 256:
                completed_prefixes.popitem(last=False)
            del pending_meta[prefix]
            del pending_chunks[prefix]
            return True
        else:
            # Do NOT mark completed or delete pending_meta: clear corrupted chunks
            # so redundant Pass 2 / Pass 3 carousel packets can repair the frame!
            print(
                f"    [!] SHA-256 mismatch for {prefix} on current pass! "
                f"Retaining metadata and clearing chunks for next carousel pass repair.",
                file=sys.stderr
            )
            chunk_store["chunks"].clear()
            return False

    return False


def is_valid_fresh_packet(node_id, ts, nonce, strict_clock_skew=True):
    """
    Enforces strict anti-replay protection, non-empty 16-char hex nonce validation,
    persistent disk nonce caching, and configurable clock-skew handling.
    """
    if not nonce or not isinstance(nonce, str) or len(nonce) != 16:
        print(f"[!] Replay/Format rejection: Missing or invalid 16-char hex nonce from {node_id}", file=sys.stderr)
        return False
    try:
        bytes.fromhex(nonce)
    except ValueError:
        print(f"[!] Replay/Format rejection: Non-hex nonce '{nonce}' from {node_id}", file=sys.stderr)
        return False

    now = time.time()
    if abs(now - ts) > MAX_CLOCK_SKEW_SEC:
        if strict_clock_skew:
            print(f"[!] Replay/ClockSkew rejection: Alert ts {ts} exceeds {MAX_CLOCK_SKEW_SEC}s drift", file=sys.stderr)
            return False
        else:
            print(
                f"[*] Notice: Cold-boot clock skew ({int(now - ts)}s) on {node_id}; "
                f"accepting based on cryptographic signature + unique nonce {nonce}.",
                file=sys.stderr
            )

    if node_id not in node_security_state:
        node_security_state[node_id] = {"last_ts": ts, "seen_nonces": OrderedDict()}

    state = node_security_state[node_id]
    seen = state["seen_nonces"]
    if nonce in seen:
        print(f"[!] Replay rejection: Duplicate nonce {nonce} detected for {node_id}!", file=sys.stderr)
        return False

    # Store nonce in FIFO order (bound RAM to last 500 nonces) and persist to disk
    seen[nonce] = ts
    if len(seen) > 500:
        seen.popitem(last=False)

    state["last_ts"] = max(state["last_ts"], ts)
    _persist_seen_nonce(node_id, nonce, ts)
    return True


def process_datagram(pkt, now=None, strict_clock_skew=None):
    """Processes a single raw UDP datagram (Type 0x01 Metadata or Type 0x02 Image Chunk)."""
    if now is None:
        now = time.time()
    if strict_clock_skew is None:
        strict_clock_skew = STRICT_CLOCK_SKEW

    # Validate Diode sync preamble 'DD'
    if len(pkt) < 4 or pkt[:2] != b"DD":
        return False

    pkt_type = pkt[2]

    # ----------------------------------------------------------------------
    # Type 0x01: Signed Metadata Packet (Ed25519)
    # ----------------------------------------------------------------------
    if pkt_type == 1 and len(pkt) > 67:
        sig = pkt[3:67]
        meta_bytes = pkt[67:]
        try:
            meta = json.loads(meta_bytes.decode("utf-8"))
            node_id = meta.get("node")
            if node_id not in KNOWN_NODE_PUBKEYS:
                print(f"[!] Rejected alert from unauthorized node: {node_id}", file=sys.stderr)
                return False

            # Verify Ed25519 cryptographic signature over JSON bytes
            KNOWN_NODE_PUBKEYS[node_id].verify(meta_bytes, sig)

            nonce = meta.get("nonce", "")
            img_prefix = meta.get("img_sha256", "")[:16]
            # Primary correlation key is the 8-byte (16 hex char) per-burst nonce
            prefix = nonce if (isinstance(nonce, str) and len(nonce) == 16) else img_prefix

            # Deduplicate redundant Pass 2 / Pass 3 header packets from the same 3x carousel burst
            if prefix in pending_meta and pending_meta[prefix]["meta"].get("nonce") == nonce:
                try_reconstruct_image(prefix)
                return True
            if prefix in completed_prefixes and completed_prefixes[prefix].get("nonce") == nonce:
                return True

            # Anti-replay check for genuinely new alert bursts
            ts = meta.get("ts", int(now))
            if abs(now - ts) > MAX_CLOCK_SKEW_SEC:
                meta["_clock_drift_warning"] = True
            if not is_valid_fresh_packet(node_id, ts, nonce, strict_clock_skew=strict_clock_skew):
                return False

            if prefix and prefix not in pending_meta:
                _enforce_queue_cap(pending_meta, MAX_PENDING_FRAMES)
                pending_meta[prefix] = {"meta": meta, "created_at": now}
                print(f"[+] VERIFIED ALERT from [{node_id}] | Detections: {meta.get('detections')} | Trigger: {meta.get('pico_trig')}")
                # Trigger reconstruction in case chunks arrived before this metadata packet
                try_reconstruct_image(prefix)
                return True

        except (BadSignatureError, Exception) as e:
            print(f"[!] Dropped corrupted or forged packet: {e}", file=sys.stderr)
            return False

    # ----------------------------------------------------------------------
    # Type 0x02: Image Binary Chunk Packet
    # ----------------------------------------------------------------------
    elif pkt_type == 2 and len(pkt) > 15:
        prefix = pkt[3:11].hex()
        # Ignore redundant Pass 2 / Pass 3 chunks for already-reconstructed bursts
        if prefix in completed_prefixes:
            return True

        idx, total = struct.unpack(">HH", pkt[11:15])
        if total == 0 or total > MAX_CHUNKS_PER_FRAME or idx >= total:
            return False

        chunk_data = pkt[15:]

        if prefix not in pending_chunks:
            _enforce_queue_cap(pending_chunks, MAX_PENDING_FRAMES)
            pending_chunks[prefix] = {
                "chunks": {},
                "total": total,
                "created_at": now
            }

        pending_chunks[prefix]["chunks"][idx] = chunk_data
        pending_chunks[prefix]["total"] = total

        # Trigger reconstruction if all chunks and metadata are assembled
        return try_reconstruct_image(prefix)

    return False


# ==============================================================================
def run_hub(port=UDP_PORT, bind_addr="0.0.0.0", out_dir=OUT_DIR, max_clock_skew=MAX_CLOCK_SKEW_SEC, strict_clock_skew=STRICT_CLOCK_SKEW):
    global OUT_DIR, UDP_PORT, MAX_CLOCK_SKEW_SEC, STRICT_CLOCK_SKEW
    OUT_DIR = out_dir
    UDP_PORT = port
    MAX_CLOCK_SKEW_SEC = max_clock_skew
    STRICT_CLOCK_SKEW = strict_clock_skew
    os.makedirs(OUT_DIR, exist_ok=True)
    load_authorized_nodes(OUT_DIR)
    load_seen_nonces_from_disk(OUT_DIR)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass

    try:
        sock.bind((bind_addr, port))
    except OSError as e:
        if e.errno in (errno.EADDRINUSE, 48):
            print(f"[!] ERROR: UDP port {port} on {bind_addr} is already in use by another process.", file=sys.stderr)
            print(f"[*] TIP: Specify an alternate port using '--port <PORT>' or check running processes.", file=sys.stderr)
            sys.exit(1)
        raise

    # Optimize OS socket receive buffer to handle multi-chunk bursts
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    except OSError:
        pass
    sock.settimeout(2.0)
    write_receiver_heartbeat(port=port, out_dir=OUT_DIR)

    print("==================================================")
    print("[*] PI-DIODE COLLECTOR HUB ACTIVE")
    print(f"[*] Listening on UDP {bind_addr}:{port}")
    print("[*] Physical Diode Isolation: ENFORCED")
    print(f"[*] Storage Directory: {OUT_DIR}")
    for nid, vk in KNOWN_NODE_PUBKEYS.items():
        if vk.encode().hex() in DEFAULT_EXAMPLE_PUBKEYS:
            print(f"[!] SECURITY WARNING: {nid} is using a default repository example key! Run generate_keys.py before field deployment.")
    print("==================================================")

    last_gc_time = time.time()

    while True:
        try:
            pkt, _ = sock.recvfrom(2048)
        except socket.timeout:
            now = time.time()
            write_receiver_heartbeat(port=port, out_dir=OUT_DIR)
            if now - last_gc_time > 5.0:
                cleanup_stale_buffers()
                last_gc_time = now
            continue
        except KeyboardInterrupt:
            print("\n[*] Receiver Hub shutting down cleanly.")
            break
        except Exception as e:
            print(f"[!] Socket read error: {e}", file=sys.stderr)
            continue

        # Periodic sliding-window buffer cleanup & heartbeat update
        now = time.time()
        if now - last_gc_time > 5.0:
            cleanup_stale_buffers()
            write_receiver_heartbeat(port=port, out_dir=OUT_DIR)
            last_gc_time = now

        process_datagram(pkt, now=now, strict_clock_skew=STRICT_CLOCK_SKEW)

    sock.close()


def enforce_storage_retention(out_dir=None, max_files=None):
    """
    Prunes the oldest saved .jpg files in out_dir when total count exceeds max_files.
    Designed for unattended off-grid 'Dead-Drop' Collector Vaults running for months.
    """
    target_dir = out_dir or OUT_DIR
    limit = max_files if max_files is not None else MAX_SAVED_ALERTS
    if not limit or limit <= 0 or not os.path.isdir(target_dir):
        return 0
    try:
        jpgs = [
            os.path.join(target_dir, f)
            for f in os.listdir(target_dir)
            if f.lower().endswith(".jpg")
        ]
        if len(jpgs) <= limit:
            return 0
        jpgs.sort(key=lambda p: (os.path.getmtime(p), p))
        to_remove = jpgs[: len(jpgs) - limit]
        removed = 0
        for p in to_remove:
            try:
                os.remove(p)
                removed += 1
            except OSError:
                pass
        return removed
    except OSError:
        return 0


def export_dead_drop_bundle(bundle_path, out_dir=None):
    """
    Packages all verified JPEGs, alerts_journal.jsonl, seen_nonces.jsonl, and
    authorized_nodes.json from out_dir into a portable ZIP archive for rapid
    field extraction from an unattended Dead-Drop Collector Vault.
    """
    import zipfile
    target_dir = out_dir or OUT_DIR
    if not os.path.isdir(target_dir):
        raise FileNotFoundError(f"Alert directory not found: {target_dir}")
    count = 0
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(target_dir)):
            if fname.endswith((".jpg", ".jsonl", ".json")):
                full_p = os.path.join(target_dir, fname)
                if os.path.isfile(full_p):
                    zf.write(full_p, arcname=fname)
                    count += 1
    return count


def valid_port(value):
    try:
        p = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid integer")
    if not (1 <= p <= 65535):
        raise argparse.ArgumentTypeError(f"port {p} is out of range (must be 1-65535)")
    return p


def main():
    global MAX_SAVED_ALERTS
    parser = argparse.ArgumentParser(
        description="Production-Hardened Passive UDP Optical Diode Receiver & Cryptographic Reassembler"
    )
    parser.add_argument(
        "-p", "--port",
        type=valid_port,
        default=UDP_PORT,
        help=f"UDP port to listen on (default: {UDP_PORT})"
    )
    parser.add_argument(
        "-b", "--bind",
        type=str,
        default="0.0.0.0",
        help="Local IP address to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "-o", "--out-dir",
        type=str,
        default=OUT_DIR,
        help=f"Directory to store verified alert JPEGs and JSONL journal (default: {OUT_DIR})"
    )
    parser.add_argument(
        "-s", "--skew",
        type=int,
        default=MAX_CLOCK_SKEW_SEC,
        help=f"Max clock skew drift in seconds for replay warning/rejection (default: {MAX_CLOCK_SKEW_SEC})"
    )
    parser.add_argument(
        "--strict-clock-skew",
        action="store_true",
        default=STRICT_CLOCK_SKEW,
        help="Drop alerts exceeding max clock skew (enable when field nodes have RTC battery backup)"
    )
    parser.add_argument(
        "--max-alerts",
        type=int,
        default=MAX_SAVED_ALERTS,
        help="Circular cap on saved JPEGs for unattended Dead-Drop Vaults (0 = unlimited)"
    )
    parser.add_argument(
        "--export-bundle",
        type=str,
        default="",
        help="Export all verified JPEGs and journals from --out-dir into the specified .zip file and exit"
    )
    args = parser.parse_args()
    MAX_SAVED_ALERTS = args.max_alerts

    if args.export_bundle:
        n_files = export_dead_drop_bundle(args.export_bundle, out_dir=args.out_dir)
        print(f"[+] Exported {n_files} verified artifacts from '{args.out_dir}' to '{args.export_bundle}'")
        return

    run_hub(
        port=args.port,
        bind_addr=args.bind,
        out_dir=args.out_dir,
        max_clock_skew=args.skew,
        strict_clock_skew=args.strict_clock_skew
    )


if __name__ == "__main__":
    main()


