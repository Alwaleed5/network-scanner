from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress, subprocess, platform, sys

PY39_PLUS = sys.version_info >= (3, 9)

def ping_host(ip, cmd, **kwargs):
    try:
        r = subprocess.run(cmd + [str(ip)],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           timeout=3, **kwargs)
        return str(ip) if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None

def network_scan():
    try:
        raw = input("Enter network (e.g. 192.168.1.0/24): ").strip()
        net = ipaddress.ip_network(raw, strict=False)

        # ipaddress.hosts() فارغة لـ /31 و /32 — تجاوزها
        if net.prefixlen > 30:
            print(f"⚠️ /{net.prefixlen} has no scannable hosts via ipaddress.hosts()\n")
            return

        num_hosts = net.num_addresses - 2

        if net.num_addresses > 4096:
            if input(f"⚠️ {net.num_addresses} addresses. Continue? (y/n): ").strip().lower() != 'y':
                return

        is_win = platform.system().lower() == "windows"
        ping_cmd = (["ping", "-n", "1", "-w", "1000"]
                    if is_win else ["ping", "-c", "1", "-W", "1"])
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if is_win else {}

        print(f"\nScanning {net} ({num_hosts} hosts)...\n")
        found = checked = 0
        cancelled = False
        workers = min(100, num_hosts)

        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {ex.submit(ping_host, ip, ping_cmd, **kwargs): ip
                       for ip in net.hosts()}
            for future in as_completed(futures):
                checked += 1
                result = future.result()
                if result:
                    print("✅ Online:", result, flush=True)
                    found += 1
        except KeyboardInterrupt:
            cancelled = True
            print(f"\n⚠️ Scan cancelled — checked {checked}/{num_hosts}, found {found}")
        finally:
            ex.shutdown(
                wait=not cancelled,
                cancel_futures=cancelled if PY39_PLUS else False
            )

        if cancelled:
            return

        print(f"\n📊 Devices found: {found}/{num_hosts}\n")

    except ValueError:
        print("❌ Invalid network\n")

if __name__ == "__main__":
    network_scan()
