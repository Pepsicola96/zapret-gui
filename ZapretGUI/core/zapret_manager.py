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


# Флаг создания процесса: дочерний процесс создаётся БЕЗ окна консоли вовсе
# (STARTF_USESHOWWINDOW+SWHide лишь «скрывает» окно, и cmd.exe иногда всё
# равно мелькает на экране; CREATE_NO_WINDOW не создаёт его вообще).
NO_WINDOW_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0


def _startupinfo():
    """Скрывать консольное окно при запуске дочерних процессов на Windows."""
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def _win_spawn_kwargs(new_group: bool = False) -> dict:
    """Единые параметры скрытого спавна для Windows."""
    if not IS_WINDOWS:
        return {}
    flags = NO_WINDOW_FLAGS
    if new_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return {"startupinfo": _startupinfo(), "creationflags": flags}


# ---------------------------------------------------------------------------
# Обнаружение комплекта
# ---------------------------------------------------------------------------

# известные имена batch-скриптов стратегий в комплекте Flowseal
STRATEGY_BAT_PATTERNS = [
    "service-{sid}.bat", "{sid}.bat", "run_{sid}.bat", "strategy_{sid}.bat",
]

CHECK_FILES = ("bp.bat", "zapret-bin", "bin", "lists", "readme.md",
               "info.txt", "windivert.dll", "windivert")

# признаки того, что папка вообще как-то связана с zapret (для подсказок)
ZAPRET_NAME_HINTS = ("zapret", "discord-youtube", "flowseal")


def _norm(p: str) -> str:
    """Нормализация пути: убираем кавычки, завершающие слеши, пробелы."""
    if not p:
        return ""
    p = p.strip().strip('"').strip("'")
    while len(p) > 3 and (p.endswith(os.sep) or p.endswith("/")):
        p = p[:-1]
    # нормализуем разделители и «лишние» фрагменты вида //, \.\, C:/...
    if IS_WINDOWS:
        p = p.replace("/", "\\")
    else:
        p = os.path.expanduser(p.replace("\\", "/"))
        p = "/" + p.lstrip("/")
    return os.path.normpath(p)


def list_bat_scripts(root: str) -> list:
    """Все .bat/.cmd файлы в корне комплекта (без вложенных папок)."""
    result = []
    try:
        for name in sorted(os.listdir(root)):
            if name.lower().endswith((".bat", ".cmd")):
                p = os.path.join(root, name)
                if os.path.isfile(p):
                    result.append(name)
    except OSError:
        pass
    return result


def looks_executable_capable(root: str) -> bool:
    """Есть ли в комплекте хоть какой-то исполняемый скрипт/бинарник."""
    if not root or not os.path.isdir(root):
        return False
    if list_bat_scripts(root):
        return True
    bin_dir = os.path.join(root, "bin")
    if os.path.isdir(bin_dir):
        try:
            for f in os.listdir(bin_dir):
                if f.lower().endswith((".exe", ".dll", ".sh")):
                    return True
        except OSError:
            pass
    return False


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
    has_bat = any(e.endswith((".bat", ".cmd")) for e in entries)
    return score >= 2 or (has_bat and ("lists" in entries or "bin" in entries))


def resolve_root(path: str) -> tuple:
    """Превращает путь, указанный пользователем, в корень комплекта.

    Пользователь часто указывает папку архива/обёртку (например
    \\...\\zapret-discord-youtube-1.10.1), тогда как сам комплект лежит
    на уровень глубже (\\...\\zapret-discord-youtube-1.10.1\\zapret-discord-youtube-1.10.1).
    Эта функция спускается в подпапки и поднимается наверх, если пользователь
    указал внутренности комплекта.

    Возвращает (корень_комплекта, пояснение_или_пустая_строка).
    Если найти не удалось — возвращает (нормализованный исходный путь, "")
    либо ("", сообщение_об_ошибке), если папки вообще нет.
    """
    p = _norm(path)
    if not p:
        return "", ""
    if not os.path.isdir(p):
        return "", f"Папка не существует:\n{p}"

    # 1) это и есть корень комплекта
    if _looks_like_zapret(p):
        return p, ""

    # 2) комплект на уровень ниже (типично для распакованных zip)
    try:
        subs = sorted(os.listdir(p))
    except OSError as e:
        return "", f"Не удалось прочитать папку ({e}):\n{p}"
    for name in subs:
        sub = os.path.join(p, name)
        try:
            if os.path.isdir(sub) and _looks_like_zapret(sub):
                return sub, ""
        except OSError:
            continue

    # 3) пользователь указал внутреннюю папку комплекта (bin / lists / windiv)
    parent = os.path.dirname(p)
    base_low = os.path.basename(p).lower()
    if base_low in ("bin", "lists", "windiv", "docs", "badproxy") \
            and parent and _looks_like_zapret(parent):
        return parent, ""

    # 4) имя папки похоже на zapret и внутри есть .bat — считаем комплектом
    if any(h in os.path.basename(p).lower() for h in ZAPRET_NAME_HINTS) \
            and looks_executable_capable(p):
        return p, ""

    return p, ""


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
        """Корень комплекта с учётом вложенных папок после распаковки."""
        raw = self.settings.zapret_dir()
        if not raw:
            return ""
        resolved, _note = resolve_root(raw)
        return resolved or raw

    def lists_dir(self) -> str:
        return os.path.join(self.root(), "lists")

    def log_file(self) -> str:
        return os.path.join(self.root() or os.getcwd(), "zapret_gui.log")

    # ---------------- обнаружение bat-скриптов -----------------------------
    @staticmethod
    def _bat_matches(bat_name: str, sid: str, gamer: bool) -> bool:
        """Имя .bat соответствует запрошенной стратегии (в т.ч. геймерской).

        Совпадение по «ядру» имени: из обоих имён вырезаются все цифры и
        служебные слова — например alt3_gamer ↔ alt_3_proton_gamer дают ядро
        {'alt','gamer'} ↔ {'alt','proton','gamer'}, где первое ⊆ второго.
        """
        noise = {"service", "run", "strategy", "bat", "cmd"}

        def core(name):
            parts = [p for p in re.split(r"[_\-. ]+", name.lower()) if p]
            is_gamer = ("gamer" in parts or "gmr" in parts
                        or name.lower().endswith("gmr"))
            cleaned = {re.sub(r"\d+", "", p) for p in parts}
            cleaned -= {"", "gamer", "gmr"} | noise
            return is_gamer, cleaned

        bat_gamer, bat_core = core(bat_name.rsplit(".", 1)[0])
        if bat_gamer != gamer:
            return False
        sid_gamer, sid_core = core(sid)
        if not sid_core or not bat_core:
            return False
        # ядро стратегии должно содержаться в имени bat (или наоборот),
        # при этом оба должны относиться к одному семейству (первое слово)
        if sid_core <= bat_core or bat_core <= sid_core:
            # сравниваем «первое значимое слово» имён (семейство alt/main/...)
            skip = {"gamer", "gmr"} | noise

            def first_token(name):
                for p in re.split(r"[_\-. ]+", name.lower()):
                    c = re.sub(r"\d+", "", p)
                    if c and c not in skip:
                        return c
                return ""
            return first_token(sid) == first_token(bat_name)
        return False

    def find_strategy_bat(self, sid: str, gamer: bool) -> str:
        """Ищет .bat стратегии в корне комплекта; '' если не найдено."""
        root = self.root()
        if not root:
            return ""
        # -1) точное имя файла по id стратегии (поддержка «обнаруженных»
        #     стратегий вида alt5_proton / custom__ext из реального комплекта)
        base_sid = re.sub(r"__ext$", "", sid)
        for cand_name in (base_sid, f"service-{base_sid}", f"run_{base_sid}"):
            for ext in (".bat", ".cmd"):
                p = os.path.join(root, cand_name + ext)
                if os.path.isfile(p):
                    return p
        # 1) штатные шаблоны имён
        for pat in STRATEGY_BAT_PATTERNS:
            cand = pat.format(sid=sid)
            for ext in (".bat", ".cmd"):
                p = os.path.join(root, cand + ext) if not cand.endswith(ext) \
                    else os.path.join(root, cand)
                if os.path.isfile(p):
                    return p
        # 2) неформатированные варианты с суффиксом gamer
        variants = [f"{sid}_gamer.bat", f"service-{sid}_gamer.bat"] if gamer \
            else []
        for v in variants:
            p = os.path.join(root, v)
            if os.path.isfile(p):
                return p
        # 3) эвристический поиск по всем bat-файлам
        try:
            bats = list_bat_scripts(root)
        except OSError:
            bats = []

        def score(b):
            """Чем меньше, тем точнее совпадение имени bat со стратегией."""
            low = b.lower().rsplit(".", 1)[0]
            sid_low = sid.lower()
            if low == sid_low:
                return 0
            if low.replace("_", "").replace("-", "") == \
               sid_low.replace("_", "").replace("-", "").replace("gamer", "") + \
               ("gamer" if gamer else ""):
                return 1
            parts = [p for p in re.split(r"[_\-. ]+", low) if p]
            # точное совпадение с учётом цифр: alt_3 ~ alt3
            digits_sid = "".join(re.findall(r"\d+", sid_low))
            digits_bat = "".join(re.findall(r"\d+", low))
            fam_sid = re.match(r"[a-z]+", sid_low).group() if \
                re.match(r"[a-z]+", sid_low) else ""
            fam_bat = re.match(r"[a-z]+", low).group() if \
                re.match(r"[a-z]+", low) else ""
            if fam_sid and fam_sid == fam_bat and digits_sid == digits_bat \
                    and digits_sid:
                return 2
            return 5

        exact = [(score(b), len(b), b.lower(), b) for b in bats
                 if self._bat_matches(b, sid, gamer)]
        # совпадения с цифрами (уровень <=2) не перекрываются «голым» семейством
        strong = [t for t in exact if t[0] <= 2]
        pool = strong if strong else exact
        if pool:
            pool.sort(key=lambda t: (not t[3].lower().startswith("service"),
                                     t[0], t[1], t[2]))
            return os.path.join(root, pool[0][3])
        return ""

    # ---------------- команда запуска --------------------------------------
    def _profile_list_args(self):
        """Аргументы --domain-list-file для выбранных профилей."""
        profile = self.settings.get("profile", "discord_youtube")
        # геймерские стратегии комплекта работают со своим списком игровых
        # доменов (games.txt / list_game_domain.txt); если его нет — берём
        # обычный профиль пользователя
        from config.profiles import STRATEGY_MAP
        strat = STRATEGY_MAP.get(self.settings.get("strategy", ""))
        if strat and getattr(strat, "gamer", False):
            for gname in ("games.txt", "game_domains.txt",
                          "list_game_domain.txt"):
                gpath = os.path.join(self.lists_dir(), gname)
                if os.path.isfile(gpath):
                    return [f"--domain-list-file={gpath}"]
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
        gamer = bool(getattr(strat, "gamer", False))
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

        # 1) штатный .bat стратегии из комплекта (в т.ч. *_gamer.bat)
        bat = self.find_strategy_bat(sid, gamer)
        if bat:
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
                return [p] + args, root

        # 4) fallback: любой bat стратегии, чтобы не оставлять пользователя
        #    без рабочего запуска (например выбрана alt3, а в комплекте только alt2)
        for b in list_bat_scripts(root):
            low = b.lower()
            if low in ("service.bat", "uninstall_service.bat",
                       "delete_service.bat", "mips64el.bat"):
                continue
            if low.startswith(("cmd_", "check", "update")):
                continue
            if gamer != ("gamer" in low or "_gmr" in low):
                continue
            return ["cmd.exe", "/c", os.path.join(root, b)], root

        raise FileNotFoundError(self._no_executable_message(root))

    def _no_executable_message(self, root: str) -> str:
        """Подробная подсказка: почему ничего не найдено и что делать."""
        ru = self.settings.get("language", "ru") == "ru"
        lines = []
        if ru:
            lines.append("Не найден ни один исполняемый скрипт Zapret.")
            lines.append(f"Проверяемая папка: {root or '(путь не указан)'}")
            if not root or not os.path.isdir(root):
                lines.append("Папка не существует — проверьте путь в «Настройках».")
            elif any(h in os.path.basename(root).lower()
                     for h in ZAPRET_NAME_HINTS):
                bats = list_bat_scripts(root)
                if bats:
                    lines.append("В папке есть bat-файлы, но ни один не подходит "
                                 "под стратегию: " + ", ".join(bats[:12]))
                    lines.append("Попробуйте выбрать другую стратегию на вкладке "
                                 "«Профили» или запустите комплект через его родной "
                                 "ярлык.")
                else:
                    lines.append("Похоже, комплект распакован не полностью "
                                 "(нет .bat-скриптов и папки bin с exe). "
                                 "Распакуйте архив целиком (например 7-Zip'ом) "
                                 "или скачайте полный релиз заново.")
            else:
                lines.append("Эта папка не похожа на комплект "
                             "zapret-discord-youtube. Укажите корневую папку "
                             "комплекта (где лежат *.bat и папка bin/lists) "
                             "в разделе «Настройки», либо нажмите «Определить "
                             "автоматически».")
        else:
            lines.append("No executable Zapret script found.")
            lines.append(f"Checked folder: {root or '(path not set)'}")
            if not root or not os.path.isdir(root):
                lines.append("Folder does not exist - fix the path in Settings.")
            else:
                lines.append("This folder doesn't look like a complete "
                             "zapret-discord-youtube kit. Point to its root "
                             "(where *.bat and bin/lists live) in Settings.")
        return "\n".join(lines) + \
            ("\nУкажите корректный путь к комплекту в разделе «Настройки»."
             if ru else "\nSet the correct kit path in the Settings tab.")

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
                    text=True, encoding="utf-8", errors="replace",
                    **_win_spawn_kwargs(new_group=True),
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
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        timeout=10, **_win_spawn_kwargs())
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
                    capture_output=True, text=True, timeout=15,
                    **_win_spawn_kwargs())
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
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=10,
                                **_win_spawn_kwargs())
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
                           cwd=self.root(),
                           capture_output=True, text=True, timeout=120,
                           **_win_spawn_kwargs())
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")

    def uninstall_service(self):
        bat = os.path.join(self.root(), "service.bat")
        if not os.path.isfile(bat):
            raise FileNotFoundError("В комплекте не найден service.bat")
        r = subprocess.run(["cmd.exe", "/c", bat, "uninstall"],
                           cwd=self.root(),
                           capture_output=True, text=True, timeout=120,
                           **_win_spawn_kwargs())
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
