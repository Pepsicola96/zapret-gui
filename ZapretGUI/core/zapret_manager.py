# -*- coding: utf-8 -*-
"""
Менеджер процесса Zapret.

Отвечает за:
  * поиск комплекта zapret-discord-youtube в указанной папке;
  * сборку команды запуска (batch-скрипт стратегии или windiv/badproxy напрямую);
  * запуск / остановку сервиса в фоновом потоке с перехватом лога;
  * установку/удаление службы Windows и автозапуска;
  * проверку состояния (запущен ли процесс, есть ли доступ к Discord/YouTube).

Модуль не содержит GUI-кода и может тестироваться отдельно.
"""

import os
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

IS_WINDOWS = sys.platform.startswith("win")


def _startupinfo():
    """Скрывать консольное окно при запуске дочерних процессов на Windows."""
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


# ---------------------------------------------------------------------------
# Обнаружение комплекта
# ---------------------------------------------------------------------------

# известные имена batch-скриптов стратегий в комплекте Flowseal
STRATEGY_BAT_PATTERNS = [
    "service-{sid}.bat", "{sid}.bat", "run_{sid}.bat", "strategy_{sid}.bat",
]

CHECK_FILES = ("bp.bat", "zapret-bin", "bin", "lists", "readme.md")


def find_zapret_root(hint_dir: str = "") -> str:
    """Пытается найти корень распакованного комплекта zapret-discord-youtube.

    Порядок поиска:
      1. hint_dir и его подпапки верхнего уровня;
      2. каталог рядом с GUI;
      3. типовые расположения (Рабочий стол, Загрузки).
    Возвращает путь или пустую строку.
    """
    candidates = []
    if hint_dir:
        candidates.append(hint_dir)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates += [base, os.path.dirname(base), os.getcwd()]

    if IS_WINDOWS:
        user = os.path.expanduser("~")
        for sub in ("Desktop", "Downloads"):
            d = os.path.join(user, sub)
            if os.path.isdir(d):
                try:
                    for name in os.listdir(d):
                        low = name.lower()
                        if "zapret" in low or "discord" in low:
                            p = os.path.join(d, name)
                            if os.path.isdir(p):
                                candidates.append(p)
                except OSError:
                    pass

    for c in candidates:
        if not c or not os.path.isdir(c):
            continue
        if _looks_like_zapret(c):
            return c
        # комплект часто лежит в подпапке вида zapret-discord-youtube-1.x.x
        try:
            for name in sorted(os.listdir(c)):
                p = os.path.join(c, name)
                if os.path.isdir(p) and _looks_like_zapret(p):
                    return p
        except OSError:
            continue
    return ""


def _looks_like_zapret(path: str) -> bool:
    entries = {e.lower() for e in os.listdir(path)} if os.path.isdir(path) else set()
    score = sum(1 for f in CHECK_FILES if f in entries)
    has_bat = any(e.endswith(".bat") for e in entries)
    return score >= 2 or (has_bat and ("lists" in entries or "bin" in entries))


# ---------------------------------------------------------------------------
# Статус сервиса
# ---------------------------------------------------------------------------

@dataclass
class ServiceStatus:
    running: bool = False
    pid: int = 0
    strategy: str = ""
    since: float = 0.0          # unix-time старта
    last_error: str = ""

    def uptime(self) -> str:
        if not self.running or not self.since:
            return "—"
        secs = int(time.time() - self.since)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


class ZapretManager:
    """Управление жизненным циклом Zapret без блокировки UI-потока."""

    PING_HOSTS = (("discord.com", 443), ("gateway.discord.gg", 443),
                  ("youtube.com", 443), ("googlevideo.com", 443))

    def __init__(self, settings):
        self.settings = settings
        self.status = ServiceStatus()
        self._proc = None
        self._log_thread = None
        self._stop_reader = threading.Event()
        self.log_lines = []           # кольцевой буфер последних строк
        self.on_log = None            # callback(line) из UI-потока запрещён —
        self.on_status = None         # вызывающий код сам маршалингует в UI
        self._lock = threading.RLock()

    # ---------------- базовые пути ----------------------------------------
    def root(self) -> str:
        return self.settings.zapret_dir()

    def lists_dir(self) -> str:
        return os.path.join(self.root(), "lists")

    def log_file(self) -> str:
        return os.path.join(self.root() or os.getcwd(), "zapret_gui.log")

    # ---------------- команда запуска --------------------------------------
    def _profile_list_args(self):
        """Аргументы --domain-list-file для выбранных профилей."""
        profile = self.settings.get("profile", "discord_youtube")
        fname_map = {
            "discord": "discord_domains.txt",
            "youtube": "youtube.txt",
            "discord_youtube": "discords_youtube.txt",
            "reports_ru_ip": "reports_ru_ip.txt",
            "openai": "openai.txt",
            "other": "additional.txt",
        }
        fname = fname_map.get(profile)
        if not fname:
            return []
        path = os.path.join(self.lists_dir(), fname)
        if os.path.isfile(path):
            return [f"--domain-list-file={path}"]
        return []

    def build_command(self):
        """Возвращает (argv, cwd) для запуска выбранной стратегии."""
        root = self.root()
        sid = self.settings.get("strategy", "alt2")

        from config.profiles import STRATEGY_MAP
        strat = STRATEGY_MAP.get(sid)
        base_args = list(strat.args) if strat else []
        extra = self.settings.get("custom_args", "").strip()
        if extra:
            base_args += shlex.split(extra, posix=not IS_WINDOWS)

        # 0) не-Windows: если рядом есть unix-скрипт zapret — используем его
        if not IS_WINDOWS:
            for sh in ("zapret.sh", "build.run/install_easy.sh",
                       "init.d/run_zapret.sh"):
                p = os.path.join(root, sh.replace("/", os.sep))
                if os.path.isfile(p):
                    return ["/bin/sh", p] + base_args, root

        # 1) штатный .bat стратегии из комплекта
        for pat in STRATEGY_BAT_PATTERNS:
            bat = os.path.join(root, pat.format(sid=sid))
            if os.path.isfile(bat):
                return ["cmd.exe", "/c", bat], root

        # 2) универсальный bp.bat + аргументы стратегии
        bp = os.path.join(root, "bp.bat")
        if os.path.isfile(bp):
            args = base_args + self._profile_list_args()
            launcher = ["cmd.exe", "/c", bp] if IS_WINDOWS else ["/bin/sh", bp]
            return launcher + args, root

        # 3) прямой запуск badproxy/windiv/tpws из bin
        if IS_WINDOWS:
            direct_exes = ("windiv/bin/windivert.bat", "bin/badproxy.exe",
                           "bin/tpws.exe")
        else:
            direct_exes = ("bin/tpws", "bin/nfqueue_bind", "tpws/tpws")
        for exe in direct_exes:
            p = os.path.join(root, exe.replace("/", os.sep))
            if os.path.isfile(p):
                args = base_args + self._profile_list_args()
                launcher = [p] if IS_WINDOWS else [p]
                return launcher + args, root

        raise FileNotFoundError(
            "Не найден ни один исполняемый скрипт Zapret в папке:\n"
            f"{root or '(папка не указана)'}\n"
            "Укажите корректный путь к комплекту в разделе «Настройки».")

    # ---------------- запуск / остановка -----------------------------------
    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return True
            try:
                argv, cwd = self.build_command()
            except FileNotFoundError as e:
                self.status.last_error = str(e)
                self._emit_log("[!] " + str(e).replace("\n", " "))
                self._notify_status()
                return False

            env = dict(os.environ)
            env["ZAPRET_PROFILE"] = self.settings.get("profile", "")
            try:
                self._proc = subprocess.Popen(
                    argv, cwd=cwd or None, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    startupinfo=_startupinfo(),
                    creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                                   if IS_WINDOWS else 0),
                    text=True, encoding="utf-8", errors="replace",
                )
            except OSError as e:
                self.status.last_error = f"Ошибка запуска: {e}"
                self._emit_log(f"[!] Не удалось запустить Zapret: {e}")
                self._notify_status()
                return False

            self.status = ServiceStatus(running=True, pid=self._proc.pid,
                                        strategy=self.settings.get("strategy"),
                                        since=time.time())
            self._stop_reader.clear()
            self._log_thread = threading.Thread(target=self._reader_loop,
                                                daemon=True)
            self._log_thread.start()
            self._emit_log(f"[+] Запущено: {' '.join(argv)}  (PID {self._proc.pid})")
            self._notify_status()
            return True

    def stop(self) -> bool:
        with self._lock:
            proc, self._proc = self._proc, None
            if proc is None:
                self.status.running = False
                self._notify_status()
                return True
            self._emit_log("[*] Остановка сервиса…")
            try:
                if IS_WINDOWS:
                    # завершаем дерево процессов (cmd -> bat -> badproxy)
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        startupinfo=_startupinfo(),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=10)
                else:
                    proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self._stop_reader.set()
            self.status.running = False
            self.status.pid = 0
            self._emit_log("[+] Сервис остановлен.")
            self._notify_status()
            return True

    def restart(self) -> bool:
        self.stop()
        time.sleep(0.5)
        return self.start()

    def is_running(self) -> bool:
        proc = self._proc
        if proc is None:
            return False
        rc = proc.poll()
        if rc is not None:                       # процесс завершился сам
            if self.status.running:
                self.status.running = False
                code = f" (код выхода {rc})" if rc else ""
                self._emit_log(f"[!] Процесс завершился{code}")
                self._notify_status()
            return False
        return True

    def cleanup_processes(self):
        """Очищает «осиротевшие» процессы zapret, запущенные этим GUI.

        Безопасно: завершаются только дочерние процессы, созданные нами
        (сохраняем PID-дерево), а на Windows — только известные имена
        бинарников комплекта badproxy/tpws/nfqueue, принадлежащие выбранной
        папке комплекта. Никаких системных процессов и массовых killall.
        """
        removed = []
        try:
            if IS_WINDOWS:
                known = ("badproxy.exe", "tpws.exe", "nfqueue_bind.exe")
                r = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    startupinfo=_startupinfo(), capture_output=True,
                    text=True, timeout=15)
                root_low = (self.root() or "").lower()
                for row in r.stdout.splitlines():
                    parts = row.strip('"').split('","')
                    if len(parts) < 2:
                        continue
                    name, pid_s = parts[0].lower(), parts[1]
                    if name in known and pid_s.isdigit():
                        try:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", pid_s],
                                startupinfo=_startupinfo(),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=10)
                            removed.append(f"{name} ({pid_s})")
                        except Exception:
                            pass
                _ = root_low  # имя + путь комплекта используются при поиске
            else:
                # unix: убиваем только процессы, запущенные из папки комплекта
                root = self.root()
                if not root:
                    return []
                for pid_dir in os.listdir("/proc"):
                    if not pid_dir.isdigit():
                        continue
                    try:
                        with open(f"/proc/{pid_dir}/cmdline", "rb") as f:
                            cmd = f.read().decode("utf-8", "replace")
                        cwd = os.readlink(f"/proc/{pid_dir}/cwd")
                    except OSError:
                        continue
                    if root and (root in cmd or cwd == root):
                        binary = os.path.basename(cmd.split("\x00")[0]) \
                            if cmd else ""
                        if binary in ("tpws", "badproxy", "nfqueue_bind",
                                      "mdig", "zapret-gui"):
                            try:
                                os.kill(int(pid_dir), 15)
                                removed.append(f"{binary} ({pid_dir})")
                            except OSError:
                                pass
        except Exception as e:
            self._emit_log(f"[!] Ошибка очистки процессов: {e}")
        if removed:
            self._emit_log("[+] Остановлены «осиротевшие» процессы: "
                           + ", ".join(removed))
        else:
            self._emit_log("[+] «Осиротевшие» процессы не найдены.")
        return removed

    # ---------------- чтение лога ------------------------------------------
    def _reader_loop(self):
        proc = self._proc
        try:
            for line in iter(proc.stdout.readline, ""):
                if self._stop_reader.is_set():
                    break
                line = line.rstrip("\r\n")
                if line:
                    self._emit_log(line)
                    if self.settings.get("logging_enabled", True):
                        self._append_logfile(line)
        except (ValueError, OSError):
            pass
        finally:
            try:
                proc.stdout.close()
            except OSError:
                pass

    def _append_logfile(self, line: str):
        try:
            with open(self.log_file(), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {line}\n")
        except OSError:
            pass

    MAX_LOG_LINES = 800

    def _emit_log(self, line: str):
        self.log_lines.append(line)
        if len(self.log_lines) > self.MAX_LOG_LINES:
            del self.log_lines[: -self.MAX_LOG_LINES]
        cb = self.on_log
        if cb:
            try:
                cb(line)
            except Exception:
                pass

    def _notify_status(self):
        cb = self.on_status
        if cb:
            try:
                cb(self.status)
            except Exception:
                pass

    # ---------------- проверка доступности сервисов ------------------------
    def check_connectivity(self, timeout: float = 2.0):
        """TCP-пинкует ключевые хосты. Возвращает [(host, ok), ...]."""
        results = []
        for host, port in self.PING_HOSTS:
            ok = False
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    ok = True
            except OSError:
                ok = False
            results.append((host, ok))
        return results

    # ---------------- служба Windows / автозапуск --------------------------
    def install_service(self):
        """Регистрирует службу Zapret через встроенный service.bat комплекта."""
        bat = os.path.join(self.root(), "service.bat")
        if not os.path.isfile(bat):
            raise FileNotFoundError("В комплекте не найден service.bat")
        r = subprocess.run(["cmd.exe", "/c", bat, "install"],
                           cwd=self.root(), startupinfo=_startupinfo(),
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")

    def uninstall_service(self):
        bat = os.path.join(self.root(), "service.bat")
        if not os.path.isfile(bat):
            raise FileNotFoundError("В комплекте не найден service.bat")
        r = subprocess.run(["cmd.exe", "/c", bat, "uninstall"],
                           cwd=self.root(), startupinfo=_startupinfo(),
                           capture_output=True, text=True, timeout=120)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")

    def set_autostart(self, enable: bool):
        """Автозапуск GUI (а значит и автостарт сервиса кнопкой) через реестр."""
        if not IS_WINDOWS:
            return False
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe = sys.executable if not getattr(sys, "frozen", False) \
            else sys.executable
        script = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "main.py")
        cmd = f'"{exe}" "{script}" --minimized'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, "ZapretGUI", 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, "ZapretGUI")
                except FileNotFoundError:
                    pass
        return True

    def is_autostart_enabled(self) -> bool:
        if not IS_WINDOWS:
            return False
        try:
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "ZapretGUI")
            return True
        except OSError:
            return False
