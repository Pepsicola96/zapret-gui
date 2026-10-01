# -*- coding: utf-8 -*-
"""
Автоматический тестер стратегий обхода DPI.

Механика (по аналогии с test_*.bat / goodcheck из комплекта
zapret-discord-youtube и оригинального zapret bol-van):

  для каждой стратегии из списка:
    1) останавливает текущий сервис;
    2) запускает Zapret с аргументами этой стратегии
       (штатный bat-скрипт комплекта, bp.bat или tpws напрямую);
    3) ждёт поднятия сервиса;
    4) выполняет N замеров HTTPS-доступности целевых хостов
       (discord.com, youtube.com, googlevideo.com …) с оценкой
       времени отклика (latency TTFB);
    5) вычисляет долю успеха, среднюю/минимальную задержку;
    6) заносит результат в таблицу.

В конце все результаты сортируются — «лучшая стратегия» это та,
у которой максимальная доля успешных подключений и минимальная
задержка. Тест ничего не меняет в настройках автоматически —
применение победителя выполняется отдельной кнопкой по решению
пользователя.

Модуль не зависит от GUI и может использоваться автономно.
"""

import os
import ssl
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field

IS_WINDOWS = sys.platform.startswith("win")


def _startupinfo():
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


# ---------------------------------------------------------------------------
# Модель результата
# ---------------------------------------------------------------------------

@dataclass
class StrategyResult:
    strategy_id: str
    name: str = ""
    tested: bool = False
    launched: bool = False          # удалось ли поднять сервис
    attempts: int = 0
    successes: int = 0
    latencies: list = field(default_factory=list)   # мс, только успешные
    errors: list = field(default_factory=list)      # краткие тексты ошибок
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    @property
    def min_latency(self) -> float:
        return min(self.latencies) if self.latencies else 0.0

    def score(self) -> float:
        """Сводный балл: сначала надёжность, затем скорость."""
        if not self.attempts or not self.successes:
            return -1.0
        avg = self.avg_latency or 99999
        return self.success_rate * 1000 - min(avg, 9999)

    def verdict(self, ru: bool = True) -> str:
        if not self.launched:
            return ("не удалось запустить сервис" if ru else "service failed to start")
        pct = round(self.success_rate * 100)
        if pct == 100 and self.avg_latency < 700:
            return ("отлично" if ru else "excellent")
        if pct >= 75:
            return ("хорошо" if ru else "good")
        if pct >= 40:
            return ("частично" if ru else "partial")
        return ("плохо" if ru else "bad")


# ---------------------------------------------------------------------------
# Сетевые зонды
# ---------------------------------------------------------------------------

class Probes:
    """HTTPS/TCP-зонды к целевым сервисам."""

    #: (домен, порт, путь HEAD/GET, таймаут сек)
    DEFAULT_TARGETS = [
        ("discord.com",         443, "/",              5.0),
        ("gateway.discord.gg",  443, "/",              5.0),
        ("media-discordapp.cdnvideos.com", 443, "/",  6.0),
        ("www.youtube.com",     443, "/",              5.0),
        ("googlevideo.com",     443, "/",              6.0),
    ]

    def __init__(self, targets=None):
        self.targets = list(targets or self.DEFAULT_TARGETS)

    def probe_https(self, host: str, port: int, path: str = "/",
                    timeout: float = 5.0):
        """Возвращает (ok, latency_ms, error). Оценивает TTFB HEAD-запроса."""
        url = f"https://{host}{path}"
        req = urllib.request.Request(
            url, method="HEAD",
            headers={"User-Agent": "Mozilla/5.0 (ZapretGUI strategy-test)",
                     "Host": host})
        ctx = ssl.create_default_context()
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=ctx) as resp:
                code = getattr(resp, "status", 200)
                ms = (time.perf_counter() - t0) * 1000.0
                return (code < 500), ms, ""
        except Exception as e:                      # noqa: BLE001
            return False, 0.0, f"{type(e).__name__}: {e}"[:120]

    def probe_tcp(self, host: str, port: int, timeout: float = 4.0):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, (time.perf_counter() - t0) * 1000.0, ""
        except OSError as e:
            return False, 0.0, f"{type(e).__name__}"

    def one_round(self):
        """Один прогон по всем целям. Возвращает [(ok, ms, err), ...]."""
        out = []
        for host, port, path, tmo in self.targets:
            ok, ms, err = self.probe_https(host, port, path, tmo)
            if not ok:                              # fallback — хотя бы TCP
                ok2, ms2, _ = self.probe_tcp(host, port, min(tmo, 4))
                if ok2:
                    ok, ms = True, ms2
                    err = ""
            out.append((ok, ms, err))
        return out


# ---------------------------------------------------------------------------
# Тестер
# ---------------------------------------------------------------------------

class StrategyTester:
    """Последовательно перебирает стратегии, оценивает качество обхода.

    Параметры колбэков вызываются из рабочего потока — UI сам
    маршалингует события в главный поток (через widget.after).
    """

    def __init__(self, manager, settings):
        self.manager = manager
        self.settings = settings
        self.probes = Probes()
        self.on_progress = None     # callback(strategy_id, phase:str)
        self.on_result = None       # callback(StrategyResult)
        self.on_done = None         # callback(list[StrategyResult])
        self._cancel = threading.Event()
        self._thread = None
        self.results = []

    # ------------------------------------------------------------------ run
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, strategy_ids, rounds: int = 3,
              settle_sec: float = 3.0, between_sec: float = 1.0):
        """Запускает тестирование в фоновом потоке."""
        if self.is_running():
            raise RuntimeError("Тестирование уже выполняется.")
        self._cancel.clear()
        self.results = []
        self._thread = threading.Thread(
            target=self._run, args=(list(strategy_ids), rounds,
                                    settle_sec, between_sec),
            daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    # ------------------------------------------------------------- internal
    def _emit_progress(self, sid, phase):
        cb = self.on_progress
        if cb:
            try:
                cb(sid, phase)
            except Exception:
                pass

    def _emit_result(self, res):
        cb = self.on_result
        if cb:
            try:
                cb(res)
            except Exception:
                pass

    def _run(self, strategy_ids, rounds, settle_sec, between_sec):
        was_running = self.manager.is_running()
        try:
            for sid in strategy_ids:
                if self._cancel.is_set():
                    break
                res = StrategyResult(strategy_id=sid, name=sid,
                                     started_at=time.time())
                self._emit_progress(sid, "stop")
                self.manager.stop()
                time.sleep(0.6)

                self._emit_progress(sid, "start")
                launched = self._launch_strategy(sid)
                res.launched = launched
                if launched:
                    # ждём поднятия сервиса + прогрев DNS
                    deadline = time.time() + max(settle_sec, 2.0)
                    while time.time() < deadline:
                        if self._cancel.is_set():
                            break
                        time.sleep(0.3)
                if self._cancel.is_set():
                    res.finished_at = time.time()
                    self._emit_result(res)
                    break

                self._emit_progress(sid, "test")
                for r in range(rounds):
                    if self._cancel.is_set():
                        break
                    for ok, ms, err in self.probes.one_round():
                        res.attempts += 1
                        res.tested = True
                        if ok:
                            res.successes += 1
                            res.latencies.append(ms)
                        elif err:
                            res.errors.append(err)
                    time.sleep(0.35)
                res.finished_at = time.time()
                self._emit_result(res)
                time.sleep(between_sec)
        finally:
            self._emit_progress("", "cleanup")
            self.manager.stop()
            time.sleep(0.5)
            if was_running:                          # возвращаем исходный режим
                self.manager.start()
            cb = self.on_done
            if cb:
                try:
                    cb(list(self.results))
                except Exception:
                    pass

    # --------------------------------------------------------- запуск страт.
    def _launch_strategy(self, sid: str) -> bool:
        """Запускает Zapret именно с этой стратегией, не трогая настройки.

        Порядок: bat комплекта -> bp.bat+args -> прямой tpws/badproxy.
        Возвращает True, если процесс жив через 1.5 секунды после старта.
        """
        from config.profiles import STRATEGY_MAP
        root = self.manager.root()
        if not root:
            return False
        strat = STRATEGY_MAP.get(sid)
        base_args = list(strat.args) if strat else []
        list_args = self.manager._profile_list_args()

        candidates = []
        if IS_WINDOWS:
            for pat in ("service-{sid}.bat", "{sid}.bat",
                        "run_{sid}.bat", "strategy_{sid}.bat"):
                p = os.path.join(root, pat.format(sid=sid))
                if os.path.isfile(p):
                    candidates.append(["cmd.exe", "/c", p])
            bp = os.path.join(root, "bp.bat")
            if os.path.isfile(bp):
                candidates.append(["cmd.exe", "/c", bp] + base_args + list_args)
            for exe in ("bin/tpws.exe", "bin/badproxy.exe"):
                p = os.path.join(root, exe.replace("/", os.sep))
                if os.path.isfile(p):
                    candidates.append([p] + base_args + list_args)
        else:
            for sh in ("zapret.sh", "init.d/run_zapret.sh"):
                p = os.path.join(root, sh.replace("/", os.sep))
                if os.path.isfile(p):
                    candidates.append(["/bin/sh", p] + base_args + list_args)
            for exe in ("bin/tpws", "tpws/tpws"):
                p = os.path.join(root, exe.replace("/", os.sep))
                if os.path.isfile(p):
                    candidates.append([p] + base_args + list_args)

        for argv in candidates:
            try:
                proc = subprocess.Popen(
                    argv, cwd=root, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                    startupinfo=_startupinfo(),
                    creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                                   if IS_WINDOWS else 0))
            except OSError:
                continue
            # регистрируем процесс в менеджере, чтобы stop()/is_running()
            # работали штатно и лог-читатель не мешал
            with self.manager._lock:
                old = self.manager._proc
                self.manager._proc = proc
                self.manager.status.running = True
                self.manager.status.pid = proc.pid
                self.manager.status.strategy = sid
                self.manager.status.since = time.time()
            if old is not None:
                try:
                    old.terminate()
                except OSError:
                    pass
            time.sleep(1.5)
            if proc.poll() is None:
                return True
            # процесс сразу умер — пробуем следующий кандидат
        return False
