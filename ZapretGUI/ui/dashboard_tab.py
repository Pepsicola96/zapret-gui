# -*- coding: utf-8 -*-
"""Вкладка «Панель управления»: запуск/остановка, статус, проверки, журнал."""

import os
import subprocess
import sys
import threading

import customtkinter as ctk


class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.loc = app.loc
        self.manager = app.manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # ------------------ карточка статуса --------------------------------
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        card.grid_columnconfigure(1, weight=1)

        self.big_status = ctk.CTkLabel(card, text=self.loc.t("status_stopped"),
                                       font=ctk.CTkFont(size=22, weight="bold"),
                                       text_color="gray55")
        self.big_status.grid(row=0, column=0, columnspan=3,
                             padx=24, pady=(18, 6), sticky="w")

        self.info_lbl = ctk.CTkLabel(
            card,
            text=f"{self.loc.t('strategy')}: {self.settings_get('strategy')}   |   "
                 f"{self.loc.t('profile')}: {self.settings_get('profile')}   |   "
                 f"{self.loc.t('uptime')}: —   {self.loc.t('pid')}: —",
            font=ctk.CTkFont(size=13), text_color="gray65")
        self.info_lbl.grid(row=1, column=0, columnspan=3,
                           padx=24, pady=(0, 16), sticky="w")

        # ------------------ кнопки управления -------------------------------
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew", padx=16)
        btns.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.btn_start = ctk.CTkButton(
            btns, text=self.loc.t("btn_start"), height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2fa572", hover_color="#278a5f",
            command=self._start)
        self.btn_start.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.btn_stop = ctk.CTkButton(
            btns, text=self.loc.t("btn_stop"), height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#c0392b", hover_color="#992d22",
            state="disabled", command=self._stop)
        self.btn_stop.grid(row=0, column=1, padx=6, sticky="ew")

        self.btn_restart = ctk.CTkButton(
            btns, text=self.loc.t("btn_restart"), height=48,
            font=ctk.CTkFont(size=15),
            command=self._restart)
        self.btn_restart.grid(row=0, column=2, padx=6, sticky="ew")

        self.btn_check = ctk.CTkButton(
            btns, text=self.loc.t("btn_check"), height=48,
            command=self._check)
        self.btn_check.grid(row=0, column=3, padx=6, sticky="ew")

        self.btn_cleanup = ctk.CTkButton(
            btns, text=self.loc.t("btn_cleanup"), height=48,
            fg_color=("gray75", "gray28"), hover_color=("gray65", "gray22"),
            command=self._cleanup)
        self.btn_cleanup.grid(row=0, column=4, padx=(6, 0), sticky="ew")

        # ------------------ результаты проверки доступности -----------------
        self.conn_frame = ctk.CTkFrame(self, corner_radius=12,
                                       fg_color=("gray88", "gray17"))
        self.conn_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        self.conn_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.conn_frame, text=self.loc.t("connectivity"),
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, padx=16, pady=(8, 0), sticky="w")
        self.conn_lbl = ctk.CTkLabel(self.conn_frame, text="—",
                                     font=ctk.CTkFont(size=13),
                                     justify="left", anchor="w")
        self.conn_lbl.grid(row=1, column=0, padx=16, pady=(2, 10), sticky="w")

        # ------------------ журнал -------------------------------------------
        log_head = ctk.CTkFrame(self, fg_color="transparent")
        log_head.grid(row=3, column=0, sticky="ew", padx=16)
        log_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_head, text=self.loc.t("log_title"),
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, sticky="w", pady=(6, 2))
        ctk.CTkButton(log_head, text=self.loc.t("btn_clear_log"), width=120,
                      command=self.clear_log).grid(row=0, column=1, padx=4)
        ctk.CTkButton(log_head, text=self.loc.t("btn_open_log"), width=130,
                      command=self.open_log_file).grid(row=0, column=2)

        self.log_box = ctk.CTkTextbox(self, font=ctk.CTkFont(
            family="Consolas", size=12), wrap="none")
        self.log_box.grid(row=4, column=0, sticky="nsew", padx=16, pady=(2, 16))
        self.log_box.configure(state="disabled")

        # стартовая запись
        self.append_log("[i] Zapret GUI готов к работе. Путь комплекта: "
                        + (self.manager.root() or "не задан"))

    # ---------------------------------------------------------------- helpers
    def settings_get(self, key):
        return self.app.settings.get(key)

    # ------------------------------------------------------------- действия
    def _start(self):
        if not self.manager.root():
            self.append_log("[!] " + self.loc.t("msg_need_path"))
            self.app._select("settings")
            return
        self.btn_start.configure(state="disabled")
        threading.Thread(target=self.manager.start, daemon=True).start()

    def _stop(self):
        self.btn_stop.configure(state="disabled")
        threading.Thread(target=self.manager.stop, daemon=True).start()

    def _restart(self):
        if not self.manager.is_running():
            self._start()
            return
        threading.Thread(target=self.manager.restart, daemon=True).start()

    def _check(self):
        self.conn_lbl.configure(text=self.loc.t("msg_checking"))

        def worker():
            results = self.manager.check_connectivity()
            lines = []
            for host, ok in results:
                mark = "✅" if ok else "❌"
                lines.append(f"{mark}  {host}:443 — "
                             + ("доступен" if ok else "НЕДОСТУПЕН"))
            self.after(0, lambda: self.conn_lbl.configure(text="\n".join(lines)))
        threading.Thread(target=worker, daemon=True).start()

    def _cleanup(self):
        self.btn_cleanup.configure(state="disabled")

        def worker():
            try:
                self.manager.cleanup_processes()
            finally:
                self.after(0, lambda: self.btn_cleanup.configure(
                    state="normal"))
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------- статус UI
    def update_status(self, status):
        running = status.running
        self.big_status.configure(
            text=self.loc.t("status_running") if running
            else self.loc.t("status_stopped"),
            text_color="#2fa572" if running else "gray55")
        self.btn_start.configure(
            state="disabled" if running else "normal")
        self.btn_stop.configure(
            state="normal" if running else "disabled")
        self._status = status
        self.tick()

    def tick(self):
        st = getattr(self, "_status", None)
        if st is None:
            return
        strategy = self.settings_get("strategy")
        profile = self.settings_get("profile")
        pid = str(st.pid) if st.running else "—"
        up = st.uptime()
        self.info_lbl.configure(
            text=f"{self.loc.t('strategy')}: {strategy}   |   "
                 f"{self.loc.t('profile')}: {profile}   |   "
                 f"{self.loc.t('uptime')}: {up}   {self.loc.t('pid')}: {pid}")

    # ------------------------------------------------------------------- log
    def append_log(self, line: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        # ограничиваем буфер виджета
        try:
            total = int(self.log_box.index("end-1c").split(".")[0])
            if total > 600:
                self.log_box.delete("1.0", f"{total - 500}.0")
        except ValueError:
            pass
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def open_log_file(self):
        path = self.manager.log_file()
        if not os.path.isfile(path):
            self.append_log("[i] Файл журнала ещё не создан.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)                      # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError:
            self.append_log("[!] Не удалось открыть файл лога.")

    def on_show(self):
        pass
