"""
mt5_path_finder.py
Run this script to automatically discover the correct MetaTrader 5 terminal64.exe
path on this Windows machine and print it so you can update your .env file.

Usage:
    python tools/mt5_path_finder.py
"""

import os
import sys
from pathlib import Path

SEARCH_DIRS = [
    r"C:\Program Files\MetaTrader 5",
    r"C:\Program Files (x86)\MetaTrader 5",
    r"C:\MetaTrader 5",
    r"C:\MT5",
    # Exness-branded installs
    r"C:\Program Files\Exness MT5",
    r"C:\Program Files (x86)\Exness MT5",
    r"C:\Program Files\Exness Group\MetaTrader 5",
    r"C:\Program Files (x86)\Exness Group\MetaTrader 5",
    # User-level AppData installs
    os.path.join(os.environ.get("APPDATA", ""), "MetaQuotes", "Terminal"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "MetaTrader 5"),
]


def find_via_filesystem() -> list[str]:
    found = []
    for base in SEARCH_DIRS:
        p = Path(base)
        # Direct match
        exe = p / "terminal64.exe"
        if exe.exists():
            found.append(str(exe))
        # Scan one level deeper (AppData/Terminal/<hash>/terminal64.exe)
        if p.exists():
            for child in p.iterdir():
                if child.is_dir():
                    nested_exe = child / "terminal64.exe"
                    if nested_exe.exists():
                        found.append(str(nested_exe))
    return found


def find_via_registry() -> list[str]:
    found = []
    try:
        import winreg
        # Locations MetaTrader installer writes to
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MetaQuotes Software\MetaTrader 5"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\MetaQuotes Software\MetaTrader 5"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\MetaQuotes Software\MetaTrader 5"),
        ]
        for hive, reg_path in reg_paths:
            try:
                with winreg.OpenKey(hive, reg_path) as key:
                    install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                    exe = Path(install_dir) / "terminal64.exe"
                    if exe.exists():
                        found.append(str(exe))
            except FileNotFoundError:
                pass
    except ImportError:
        pass  # Not on Windows
    return found


def main():
    print("=" * 60)
    print("  IPMI-OS 2.0 — MetaTrader 5 Path Auto-Discovery")
    print("=" * 60)

    all_found = list(set(find_via_registry() + find_via_filesystem()))

    if not all_found:
        print("\n[FAIL] No MetaTrader 5 terminal64.exe found on this machine.")
        print("\n  Please install MetaTrader 5 from your Exness account:")
        print("  https://www.exness.com/platforms/")
        print("  After installing, re-run this script to get the correct path.")
        sys.exit(1)

    print(f"\n[OK] Found {len(all_found)} installation(s):\n")
    for i, path in enumerate(all_found, 1):
        print(f"  [{i}] {path}")

    print("\n  Copy the correct path above into your .env file:")
    print(f"\n  MT5_TERMINAL_PATH={all_found[0]}")

    if len(all_found) > 1:
        print("\n  [WARN] Multiple installations found. Use the one that corresponds")
        print("         to your logged-in Exness account terminal.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
