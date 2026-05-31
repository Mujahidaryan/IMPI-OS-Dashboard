"""
tools/check_infra.py
Run this before starting main.py to verify all external infrastructure
dependencies are reachable and correctly configured.

Usage (run from the project root):
    python tools/check_infra.py

Exit code:
    0  — all checks pass
    1  — one or more checks failed
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PASS = "✅"
FAIL = "❌"
WARN = "⚠ "

results = []


# ─────────────────────────────────────────────
# 1. Redis check
# ─────────────────────────────────────────────
async def check_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"  [Redis] Connecting to {redis_url} …")
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url, socket_connect_timeout=3)
        await r.ping()
        await r.close()
        print(f"  {PASS} Redis is reachable and responding.")
        results.append(("Redis", True, None))
    except Exception as e:
        msg = str(e)
        print(f"  {FAIL} Redis connection FAILED: {msg}")
        print()
        print("     HOW TO FIX:")
        print("       Download Memurai (Windows Redis-compatible server):")
        print("       https://www.memurai.com/get-memurai")
        print("       Install and start the Memurai service, then re-run this script.")
        print()
        print("     OR — if you already installed Memurai/Redis, start it with:")
        print('       net start memurai    (if installed as Windows service)')
        print('       memurai              (if running standalone binary)')
        print()
        results.append(("Redis", False, msg))


# ─────────────────────────────────────────────
# 2. PostgreSQL (Neon) check
# ─────────────────────────────────────────────
async def check_postgres():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "user:pass@host" in db_url:
        print(f"  {FAIL} DATABASE_URL not configured in .env")
        results.append(("PostgreSQL", False, "DATABASE_URL missing"))
        return

    print(f"  [PostgreSQL] Connecting to {db_url[:50]}… ")
    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()

        # Check whether schema is applied
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        """)
        tables = {r[0] for r in cur.fetchall()}
        required = {"predictions", "actual_outcomes", "strategy_weights", "anomaly_log"}
        missing = required - tables

        cur.close()
        conn.close()

        if missing:
            print(f"  {WARN} Connected to PostgreSQL but schema missing: {', '.join(missing)}")
            print()
            print("     HOW TO FIX — apply the schema migration:")
            print("       python tools/db/apply_migrations.py")
            print()
            results.append(("PostgreSQL", False, f"Missing tables: {missing}"))
        else:
            print(f"  {PASS} PostgreSQL connected and all 4 tables verified.")
            results.append(("PostgreSQL", True, None))

    except Exception as e:
        msg = str(e)
        print(f"  {FAIL} PostgreSQL connection FAILED: {msg}")
        print()
        print("     HOW TO FIX:")
        print("       1. Check DATABASE_URL in your .env is correct.")
        print("       2. Ensure your Neon project is active at https://console.neon.tech")
        print("       3. Verify the SSL mode — must include ?sslmode=require")
        print()
        results.append(("PostgreSQL", False, msg))


# ─────────────────────────────────────────────
# 3. MetaTrader 5 check
# ─────────────────────────────────────────────
async def check_mt5():
    terminal_path = os.getenv("MT5_TERMINAL_PATH", "")
    login_str = os.getenv("MT5_LOGIN", "0")
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")

    # First validate path exists
    if not terminal_path:
        print(f"  {FAIL} MT5_TERMINAL_PATH is not set in .env")
        print()
        print("     HOW TO FIX:")
        print("       python tools/mt5_path_finder.py")
        print("       Then add MT5_TERMINAL_PATH=<discovered path> to your .env")
        print()
        results.append(("MetaTrader5", False, "MT5_TERMINAL_PATH not set"))
        return

    from pathlib import Path as P
    if not P(terminal_path).exists():
        print(f"  {FAIL} MT5_TERMINAL_PATH does not exist: {terminal_path}")
        print()
        print("     HOW TO FIX:")
        print("       python tools/mt5_path_finder.py")
        print()
        results.append(("MetaTrader5", False, f"File not found: {terminal_path}"))
        return

    print(f"  [MT5] terminal64.exe found at: {terminal_path}")

    if login_str == "0" or not password or not server:
        print(f"  {WARN} MT5 credentials incomplete — login={login_str}, server={server}")
        results.append(("MetaTrader5", False, "Credentials missing"))
        return

    # Try to initialize MT5
    try:
        import MetaTrader5 as mt5

        def _init():
            return mt5.initialize(
                path=terminal_path,
                login=int(login_str),
                password=password,
                server=server,
                timeout=15000,
            )

        ok = await asyncio.to_thread(_init)
        if ok:
            info = mt5.account_info()
            mt5.shutdown()
            if info:
                print(f"  {PASS} MT5 connected — Account #{info.login} on {info.server} | Balance: ${info.balance:.2f}")
                results.append(("MetaTrader5", True, None))
            else:
                print(f"  {PASS} MT5 initialized (account_info() returned None — terminal may still be loading)")
                results.append(("MetaTrader5", True, None))
        else:
            err = mt5.last_error()
            mt5.shutdown()
            print(f"  {FAIL} MT5 initialization failed: {err}")
            print()
            print("     HOW TO FIX:")
            print("       1. Ensure MetaTrader 5 terminal is open and logged in.")
            print("       2. Verify login, password and server match your Exness account.")
            print("       3. Allow API connections: Tools → Options → Expert Advisors")
            print("          → Check 'Allow automated trading' and 'Allow DLL imports'")
            print()
            results.append(("MetaTrader5", False, str(err)))
    except ImportError:
        print(f"  {FAIL} MetaTrader5 Python package not installed.")
        print("       pip install MetaTrader5")
        results.append(("MetaTrader5", False, "Package not installed"))
    except Exception as e:
        print(f"  {FAIL} MT5 check exception: {e}")
        results.append(("MetaTrader5", False, str(e)))


# ─────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("  IPMI-OS 2.0 — Infrastructure Connectivity Check")
    print("=" * 60)
    print()

    await check_redis()
    print()
    await check_postgres()
    print()
    await check_mt5()
    print()

    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    all_ok = True
    for name, ok, err in results:
        icon = PASS if ok else FAIL
        print(f"  {icon}  {name:<20} {'OK' if ok else 'FAILED'}")
        if err:
            print(f"       └─ {err[:80]}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("  🚀  All checks passed! You can now run: python main.py")
    else:
        print("  ⚠   Fix the issues above before running main.py")
    print("=" * 60)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
