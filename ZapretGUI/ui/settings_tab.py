# -*- coding: utf-8 -*-
"""Вкладка «Настройки»: путь к комплекту, тема, язык, автозапуск, служба."""

import os
import threading
import tkinter.messagebox as mb
from tkinter import filedialog

import customtkinter as ctk

from core.zapret_manager import (find_zapret_root, resolve_root, IS_WINDOWS,
                                list_bat_scripts)


class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.loc = app.loc
        self.settings = app.settings
        self.manager = app.manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # ---------------- путь к комплекту ----------------------------------
        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=self.loc.t("zapret_path"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 6), sticky="w")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))
        row.grid_columnconfigure(0, weight=1)
        self.path_var = ctk.StringVar(value=self.settings.get("zapret_path"))
        self.path_entry = ctk.CTkEntry(row, textvariable=self.path_var)
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(row, text=self.loc.t("btn_browse"), width=110,
                      command=self._browse).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(row, text=self.loc.t("btn_autodetect"), width=170,
                      command=self._autodetect).grid(row=0, column=2)

        self.valid_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=12))
        self.valid_lbl.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")
        self._validate()

        # ---------------- внешний вид ---------------------------------------
        look = ctk.CTkFrame(self, corner_radius=12)
        look.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        look.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(look, text=self.loc.t("appearance"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, columnspan=3, padx=18,
                            pady=(12, 6), sticky="w")

        ctk.CTkLabel(look, text=self.loc.t("theme")).grid(row=1, column=0,
                                                          padx=18, sticky="w")
        self.theme_var = ctk.StringVar(value=self.settings.get("theme"))
        ctk.CTkSegmentedButton(
            look, values=["dark", "light", "system"],
            variable=self.theme_var).grid(row=2, column=0, padx=18,
                                          pady=(0, 14), sticky="w")

        ctk.CTkLabel(look, text=self.loc.t("language")).grid(row=1, column=1,
                                                             padx=18, sticky="w")
        self.lang_var = ctk.StringVar(value=self.settings.get("language"))
        ctk.CTkSegmentedButton(
            look, values=["ru", "en"],
            variable=self.lang_var).grid(row=2, column=1, padx=18,
                                         pady=(0, 14), sticky="w")

        # ---------------- поведение -----------------------------------------
        beh = ctk.CTkFrame(self, corner_radius=12)
        beh.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        beh.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(beh, text=self.loc.t("behavior"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 6), sticky="w")

        self.tray_var = ctk.BooleanVar(
            value=self.settings.get("minimize_to_tray"))
        ctk.CTkCheckBox(beh, text=self.loc.t("minimize_to_tray"),
                        variable=self.tray_var).grid(
            row=1, column=0, padx=24, pady=2, sticky="w")

        self.log_var = ctk.BooleanVar(value=self.settings.get("logging_enabled"))
        ctk.CTkCheckBox(beh, text=self.loc.t("logging_enabled"),
                        variable=self.log_var).grid(
            row=2, column=0, padx=24, pady=2, sticky="w")

        self.auto_var = ctk.BooleanVar(value=self.settings.get("autostart"))
        ctk.CTkCheckBox(beh, text=self.loc.t("autostart_service"),
                        variable=self.auto_var).grid(
            row=3, column=0, padx=24, pady=(2, 12), sticky="w")

        # ---------------- служба Windows ------------------------------------
        svc = ctk.CTkFrame(self, corner_radius=12)
        svc.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
        svc.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(svc, text=self.loc.t("install_service"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 6), sticky="w")
        srow = ctk.CTkFrame(svc, fg_color="transparent")
        srow.grid(row=1, column=0, padx=18, pady=(0, 14), sticky="w")
        ctk.CTkButton(srow, text=self.loc.t("install_service"), width=220,
                      command=lambda: self._service(True)).grid(row=0, column=0,
                                                                padx=(0, 8))
        ctk.CTkButton(srow, text=self.loc.t("uninstall_service"), width=220,
                      fg_color="gray45", hover_color="gray35",
                      command=lambda: self._service(False)).grid(row=0,
                                                                 column=1)
        if not IS_WINDOWS:
            for w in srow.winfo_children():
                w.configure(state="disabled")

        # ---------------- сохранить ----------------------------------------
        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.grid(row=4, column=0, sticky="sw", padx=16, pady=(4, 16))
        save_row.grid_rowconfigure(0, weight=1)
        self.save_btn = ctk.CTkButton(save_row, text=self.loc.t("save_settings"),
                                      width=220, height=42,
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      fg_color="#2fa572", hover_color="#278a5f",
                                      command=self._save)
        self.save_btn.grid(row=1, column=0)
        self.saved_lbl = ctk.CTkLabel(save_row, text="", text_color="gray60")
        self.saved_lbl.grid(row=1, column=1, padx=12)

    # -------------------------------------------------------------- handlers
    def _validate(self):
        """Проверяет путь и автоматически спускается вложенную папку комплекта."""
        d = self.path_var.get().strip()
        if not d:
            self.valid_lbl.configure(text="⚠ " + self.loc.t("msg_need_path"),
                                     text_color="#d4a017")
            return False

        resolved, err = resolve_root(d)
        if err:  # папки вообще нет
            self.valid_lbl.configure(text="✘ " + err.replace("\n", " — "),
                                     text_color="#c0392b")
            return False
        if resolved and os.path.normcase(resolved) != os.path.normcase(
                os.path.abspath(d)):
            # пользователь указал обёртку/родительскую папку — исправляем сами
            self.path_var.set(resolved)
            d = resolved

        bats = list_bat_scripts(d)
        ok = bool(d) and os.path.isdir(d) and (
            os.path.isdir(os.path.join(d, "bin"))
            or os.path.isfile(os.path.join(d, "bp.bat"))
            or bool(bats))
        if ok:
            extra = f"  ({len(bats)} bat-скриптов)" if bats else ""
            self.valid_lbl.configure(
                text=("✔ Комплект найден" + extra) if self.loc.lang == "ru"
                else (f"✔ Kit found ({len(bats)} bat scripts)" if bats
                      else "✔ Kit found"),
                text_color="#2fa572")
        else:
            self.valid_lbl.configure(
                text="✘ В этой папке нет скриптов zapret (.bat / bin). "
                     "Укажите корневую папку комплекта."
                if self.loc.lang == "ru" else
                "✘ No zapret scripts (.bat / bin) here. Point to the kit root.",
                text_color="#c0392b")
        return ok

    def _browse(self):
        path = filedialog.askdirectory(title=self.loc.t("zapret_path"))
        if path:
            self.path_var.set(os.path.normpath(path))
            self._validate()

    def _autodetect(self):
        found = find_zapret_root(self.path_var.get() or "")
        if not found:
            # расширенный поиск: из указанного пути, из HOME, рядом с GUI
            found = find_zapret_root("")
        if found:
            self.path_var.set(found)
        else:
            mb.showinfo("Zapret GUI",
                        "Комплект не найден автоматически.\nУкажите папку вручную."
                        if self.loc.lang == "ru" else
                        "Kit not found automatically. Set the folder manually.")
        self._validate()

    def _service(self, install: bool):
        try:
            ok, out = (self.manager.install_service() if install
                       else self.manager.uninstall_service())
        except FileNotFoundError as e:
            mb.showerror("Zapret GUI", str(e))
            return
        except OSError as e:
            mb.showerror("Zapret GUI",
                         ("Требуются права администратора: запустите GUI "
                          "от имени администратора.") if self.loc.lang == "ru"
                         else "Administrator rights required.")
            return
        (mb.showinfo if ok else mb.showwarning)(
            "Zapret GUI", out[-800:] or ("Готово" if ok else "Не удалось"))

    def _save(self):
        path = self.path_var.get().strip()
        # нормализуем и при необходимости спускаемся в реальную папку комплекта
        resolved, err = resolve_root(path) if path else ("", "")
        final_path = resolved or path
        self.settings.set("zapret_path", final_path)
        self.path_var.set(final_path)
        self._validate()
        self.settings.set("theme", self.theme_var.get())
        self.settings.set("language", self.lang_var.get())
        self.settings.set("minimize_to_tray", self.tray_var.get())
        self.settings.set("logging_enabled", self.log_var.get())
        autostart_changed = self.settings.get("autostart") != self.auto_var.get()
        self.settings.set("autostart", self.auto_var.get())
        self.settings.save()

        ctk.set_appearance_mode(self.theme_var.get())
        if autostart_changed:
            try:
                self.manager.set_autostart(self.auto_var.get())
            except OSError:
                pass
        self.saved_lbl.configure(text="✔ " + self.loc.t("settings_saved"))
        self.after(2500, lambda: self.saved_lbl.configure(text=""))
        if self.lang_var.get() != self.loc.lang:
            mb.showinfo("Zapret GUI",
                        "Язык применится после перезапуска приложения."
                        if self.loc.lang == "ru" else
                        "Language applies after restart.")

    def on_show(self):
        self.path_var.set(self.settings.get("zapret_path"))
        self._validate()
