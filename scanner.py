"""
Network Tool — أداة شبكات شاملة
تتضمن: معلومات IP، معلومات الشبكة الفرعية، معلومات المضيفين،
        موقع IP العام، وفحص الشبكة (ping sweep).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import platform
import subprocess
import sys

import requests


# ============================================================
# إعدادات عامة
# ============================================================

PY39_PLUS = sys.version_info >= (3, 9)
IS_WINDOWS = platform.system().lower() == "windows"


# ============================================================
# 1) معلومات عنوان IP
# ============================================================

def ip_info():
    """عرض معلومات تفصيلية عن عنوان IP."""
    try:
        ip_input = input("Enter IP address: ").strip()
        ip = ipaddress.ip_address(ip_input)

        print("\n--- IP Information ---")
        print("Version:  ", ip.version)
        print("Address:  ", ip)
        print("Private:  ", ip.is_private)
        print("Global:   ", ip.is_global)
        print("Loopback: ", ip.is_loopback)
        print("Reserved: ", ip.is_reserved)
        print("Link-local:", ip.is_link_local)
        print()

    except ValueError:
        print("❌ Invalid IP address\n")


# ============================================================
# 2) معلومات الشبكة الفرعية
# ============================================================

def subnet_info():
    """عرض معلومات الشبكة الفرعية (Network, Broadcast, Mask...)."""
    try:
        network_input = input(
            "Enter network (example: 192.168.1.0/24): "
        ).strip()

        network = ipaddress.ip_network(network_input, strict=False)

        print("\n--- Subnet Information ---")
        print("Network:        ", network.network_address)
        print("Broadcast:      ", network.broadcast_address)
        print("Subnet mask:    ", network.netmask)
        print("Prefix length:  ", network.prefixlen)
        print("Total addresses:", network.num_addresses)
        print("Usable hosts:   ", max(0, network.num_addresses - 2))
        print()

    except ValueError:
        print("❌ Invalid network\n")


# ============================================================
# 3) معلومات المضيفين
# ============================================================

def host_info():
    """عرض أول وآخر مضيف في الشبكة وعدد المضيفين القابلين للاستخدام."""
    try:
        network_input = input(
            "Enter network (example: 192.168.1.0/24): "
        ).strip()

        network = ipaddress.ip_network(network_input, strict=False)
        hosts = list(network.hosts())

        if not hosts:
            print("⚠️ No usable hosts in this network\n")
            return

        print("\n--- Host Information ---")
        print("First Host:  ", hosts[0])
        print("Last Host:   ", hosts[-1])
        print("Usable Hosts:", len(hosts))
        print()

    except ValueError:
        print("❌ Invalid network\n")


# ============================================================
# 4) موقع IP العام
# ============================================================

def ip_location():
    """جلب موقع IP العام باستخدام خدمات خارجية."""
    try:
        print("Fetching your public IP...")

        response = requests.get(
            "https://api.ipify.org?format=json",
            timeout=10
        )
        response.raise_for_status()
        public_ip = response.json()["ip"]
        print("Your public IP:", public_ip)

        response = requests.get(
            f"https://ipapi.co/{public_ip}/json/",
            timeout=10,
            headers={"User-Agent": "NetworkTool/1.0"}
        )
        response.raise_for_status()
        data = response.json()

        print("\n--- IP Location ---")
        print("IP:       ", data.get("ip"))
        print("Country:  ", data.get("country_name"))
        print("City:     ", data.get("city"))
        print("Region:   ", data.get("region"))
        print("ISP:      ", data.get("org"))
        print("Timezone: ", data.get("timezone"))
        print("Latitude: ", data.get("latitude"))
        print("Longitude:", data.get("longitude"))
        print()

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}\n")
    except Exception as e:
        print(f"❌ Unable to get IP location: {e}\n")


# ============================================================
# 5) فحص الشبكة (Ping Sweep)
# ============================================================

def ping_host(ip, command, **kwargs):
    """إرسال ping إلى عنوان IP وإرجاعه إذا كان متصلًا."""
    try:
        result = subprocess.run(
            command + [str(ip)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            **kwargs
        )
        return str(ip) if result.returncode == 0 else None

    except (subprocess.TimeoutExpired, OSError):
        return None


def get_scan_hosts(network):
    """إرجاع iterator للعناوين المراد فحصها (بدون تخزين في الذاكرة)."""
    if network.prefixlen >= 31:
        return iter(network)
    return network.hosts()


def count_hosts(network):
    """حساب عدد الـ hosts رياضياً بدون تخزين."""
    if network.prefixlen >= 31:
        return network.num_addresses
    return network.num_addresses - 2


def get_ping_config():
    """إرجاع أمر ping والخيارات حسب نظام التشغيل."""
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", "1000"]
        kwargs = {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)
        }
    else:
        cmd = ["ping", "-c", "1", "-W", "1"]
        kwargs = {}
    return cmd, kwargs


def network_scan():
    """فحص الشبكة بالكامل باستخدام ThreadPoolExecutor."""
    try:
        raw_network = input(
            "Enter network (example: 192.168.1.0/24): "
        ).strip()

        network = ipaddress.ip_network(raw_network, strict=False)
        num_hosts = count_hosts(network)

        if num_hosts == 0:
            print("❌ لا توجد عناوين قابلة للفحص\n")
            return

        if network.num_addresses > 4096:
            answer = input(
                f"⚠️ الشبكة تحتوي على {network.num_addresses} عنوانًا. "
                "هل تريد المتابعة؟ (y/n): "
            ).strip().lower()

            if answer != "y":
                print("تم الإلغاء.\n")
                return

        ping_command, subprocess_kwargs = get_ping_config()

        print(f"\nScanning {network} ({num_hosts} hosts)...\n")

        found = 0
        checked = 0
        cancelled = False
        workers = min(100, num_hosts)

        executor = ThreadPoolExecutor(max_workers=workers)

        try:
            hosts = get_scan_hosts(network)
            futures = {
                executor.submit(
                    ping_host, ip, ping_command, **subprocess_kwargs
                ): ip
                for ip in hosts
            }

            for future in as_completed(futures):
                checked += 1
                try:
                    result = future.result()
                except (subprocess.SubprocessError, OSError):
                    result = None

                if result:
                    print(f"✅ متصل: {result}", flush=True)
                    found += 1

        except KeyboardInterrupt:
            cancelled = True
            print(
                f"\n⚠️ تم إلغاء الفحص — "
                f"تم فحص {checked}/{num_hosts}، "
                f"وتم العثور على {found} جهازًا."
            )

        finally:
            if PY39_PLUS:
                executor.shutdown(
                    wait=not cancelled,
                    cancel_futures=cancelled
                )
            else:
                executor.shutdown(wait=not cancelled)

        if cancelled:
            return

        print(f"\n📊 الأجهزة المكتشفة: {found}/{num_hosts}\n")

    except ValueError:
        print("❌ صيغة الشبكة غير صحيحة\n")

    except KeyboardInterrupt:
        print("\n⚠️ تم إلغاء العملية.")


# ============================================================
# القائمة الرئيسية
# ============================================================

def show_menu():
    """عرض القائمة الرئيسية."""
    print("=" * 40)
    print("           Network Tool")
    print("=" * 40)
    print("1. IP Information")
    print("2. Subnet Information")
    print("3. Host Information")
    print("4. My IP Location")
    print("5. Network Scan")
    print("6. Exit")
    print("=" * 40)


def main():
    """الحلقة الرئيسية للبرنامج."""
    while True:
        show_menu()

        try:
            choice = input("Choose an option: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Good bye!")
            break

        print()

        if choice == "1":
            ip_info()
        elif choice == "2":
            subnet_info()
        elif choice == "3":
            host_info()
        elif choice == "4":
            ip_location()
        elif choice == "5":
            network_scan()
        elif choice == "6":
            print("Good bye! 👋")
            break
        else:
            print("[!] Invalid choice\n")


# ============================================================
# نقطة الدخول
# ============================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Good bye!")
