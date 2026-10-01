# -*- coding: utf-8 -*-
"""Вкладка «Редактор списков»: просмотр и правка файлов lists/*.txt."""

import os
import tkinter.messagebox as mb
import tkinter.simpledialog as sd

import customtkinter as ctk

from core.lists_model import ListsEditorModel


class ListsTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.loc = app.loc
        self.model = ListsEditorModel(app.manager)
        self.current_path = ""
        self.dirty = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- левая колонка: список файлов ----------------------
        left = ctk.CTkFrame(self, corner_radius=12)
        left.grid(row=0, column=0, sticky="ns", padx=(16, 8), pady=16)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text=self.loc.t("lists_files"),
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self.files_list = ctk.CTkScrollableFrame(left, width=230, height=430,
                                                 fg_color="transparent")
        self.files_list.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        self.files_list.grid_columnconfigure(0, weight=1)
        self.file_buttons = {}

        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.grid(row=2, column=0, padx=8, pady=(4, 10))
        ctk.CTkButton(btns, text=self.loc.t("btn_new_file"), width=105,
                      command=self._new_file).grid(row=0, column=0, padx=2)
        ctk.CTkButton(btns, text=self.loc.t("btn_reload"), width=105,
                      command=self.refresh_files).grid(row=0, column=1, padx=2)

        # ---------------- правая колонка: редактор --------------------------
        right = ctk.CTkFrame(self, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(right, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        head.grid_columnconfigure(0, weight=1)
        self.title_lbl = ctk.CTkLabel(head, text="—",
                                      font=ctk.CTkFont(size=14, weight="bold"))
        self.title_lbl.grid(row=0, column=0, sticky="w")
        self.count_lbl = ctk.CTkLabel(head, text="", text_color="gray60")
        self.count_lbl.grid(row=0, column=1, sticky="e")

        tools = ctk.CTkFrame(right, fg_color="transparent")
        tools.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
        ctk.CTkButton(tools, text=self.loc.t("btn_add_domain"), width=160,
                      command=self._add_dialog).grid(row=0, column=0, padx=2)
        ctk.CTkButton(tools, text=self.loc.t("btn_del_domain"), width=160,
                      command=self._remove_selected).grid(row=0, column=1,
                                                          padx=2)
        ctk.CTkButton(tools, text=self.loc.t("btn_save"), width=110,
                      fg_color="#2fa572", hover_color="#278a5f",
                      command=self._save).grid(row=0, column=2, padx=2)

        self.editor = ctk.CTkTextbox(
            right, font=ctk.CTkFont(family="Consolas", size=13))
        self.editor.grid(row=2, column=0, sticky="nsew", padx=12,
                         pady=(2, 8))
        self.editor.bind("<<Modified>>", lambda e: self._mark_dirty())
        self.editor.bind("<Control-s>", lambda e: self._save())

        hint = ctk.CTkLabel(right, text="Ctrl+S — сохранить  •  "
                                        "строки с # — комментарии",
                            font=ctk.CTkFont(size=11), text_color="gray55")
        hint.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 10))

        self.refresh_files()

    # ------------------------------------------------------------- файлы UI
    def refresh_files(self):
        for w in self.files_list.winfo_children():
            w.destroy()
        self.file_buttons.clear()
        files = self.model.list_files()
        if not files:
            txt = ("Папка lists не найдена.\nПроверьте путь к комплекту\nв «Настройках»."
                   if self.loc.lang == "ru" else
                   "lists folder not found.\nCheck the path in Settings.")
            ctk.CTkLabel(self.files_list, text=txt,
                         text_color="gray55").grid(row=0, column=0, pady=20)
            return
        for i, (name, path) in enumerate(files):
            count = self.model.count_domains(path)
            b = ctk.CTkButton(self.files_list,
                              text=f"{name}  ({count})", anchor="w",
                              height=32, corner_radius=6,
                              fg_color="transparent",
                              hover_color=("gray80", "gray25"),
                              command=lambda p=path, n=name: self._open(p, n))
            b.grid(row=i, column=0, sticky="ew", pady=1)
            self.file_buttons[path] = b

    def _open(self, path, name):
        if self.dirty and not mb.askyesno(
                self.loc.t("btn_save"),
                "Есть несохранённые изменения. Сохранить перед переходом?"):
            pass  # продолжаем без сохранения
        self.current_path = path
        self.title_lbl.configure(text=name)
        self.count_lbl.configure(
            text=f"{self.loc.t('domains_count')}: "
                 f"{self.model.count_domains(path)}")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.model.read_file(path))
        self.dirty = False
        for p, btn in self.file_buttons.items():
            btn.configure(fg_color=("gray75", "gray28") if p == path
                          else "transparent")

    def _mark_dirty(self):
        if self.editor.edit_modified():
            self.dirty = True
            self.editor.edit_modified(False)

    def _save(self):
        if not self.current_path:
            return
        text = self.editor.get("1.0", "end-1c")
        if self.model.save_file(self.current_path, text + "\n"):
            self.dirty = False
            self.count_lbl.configure(
                text=f"{self.loc.t('domains_count')}: "
                     f"{self.model.count_domains(self.current_path)}")
            self.refresh_files()
        else:
            mb.showerror("Zapret GUI", "Не удалось сохранить файл (права доступа?).")

    def _new_file(self):
        if not self.model.root_ok():
            mb.showwarning("Zapret GUI", self.loc.t("msg_need_path"))
            return
        name = sd.askstring(self.loc.t("btn_new_file"),
                            self.loc.t("new_file_prompt"), parent=self)
        if not name:
            return
        path = self.model.create_file(name,
                                      initial="# список создан через Zapret GUI\n")
        self.refresh_files()
        self._open(path, os.path.basename(path))

    # ------------------------------------------------------------ домены
    def _add_dialog(self):
        if not self.current_path:
            mb.showwarning("Zapret GUI", "Сначала откройте файл списка.")
            return
        dlg = AddDomainsDialog(self, self.loc)
        self.wait_window(dlg)
        if dlg.result:
            added, dupes, errors = self.model.add_domains(self.current_path,
                                                          dlg.result)
            msg = (f"Добавлено: {added}, пропущено дублей: {dupes}."
                   if self.loc.lang == "ru" else
                   f"Added: {added}, duplicates skipped: {dupes}.")
            if errors:
                msg += "\n" + ("Пропущенные некорректные строки:"
                               if self.loc.lang == "ru"
                               else "Invalid lines skipped:")
                for line, err in errors[:10]:
                    msg += f"\n  ✗ {line} — {err}"
            mb.showinfo(self.loc.t("btn_add_domain"), msg)
            # перечитать файл в редактор
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", self.model.read_file(self.current_path))
            self.dirty = False
            self.count_lbl.configure(
                text=f"{self.loc.t('domains_count')}: "
                     f"{self.model.count_domains(self.current_path)}")
            self.refresh_files()

    def _remove_selected(self):
        if not self.current_path:
            return
        try:
            sel = self.editor.get("sel.first", "sel.end").strip()
        except Exception:
            sel = ""
        if not sel:
            # берём строку под курсором
            idx = self.editor.index("insert")
            sel = self.editor.get(f"{idx} linestart", f"{idx} lineend").strip()
        if not sel or sel.startswith("#"):
            mb.showwarning("Zapret GUI",
                           "Выделите домен или поставьте курсор на его строку.")
            return
        lines = [ln for ln in sel.splitlines() if ln.strip()]
        removed = 0
        for ln in lines:
            if self.model.remove_domain(self.current_path, ln):
                removed += 1
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.model.read_file(self.current_path))
        self.dirty = False
        self.count_lbl.configure(
            text=f"{self.loc.t('domains_count')}: "
                 f"{self.model.count_domains(self.current_path)}")
        self.refresh_files()

    def on_show(self):
        self.refresh_files()


# ---------------------------------------------------------------------------
class AddDomainsDialog(ctk.CTkToplevel):
    def __init__(self, master, loc):
        super().__init__(master)
        self.result = ""
        self.title(loc.t("add_dialog_title"))
        self.geometry("460x360")
        self.transient(master.winfo_toplevel())
        self.grab_set()

        ctk.CTkLabel(self, text=loc.t("add_dialog_info"),
                     wraplength=420, justify="left").pack(padx=16, pady=(14, 6),
                                                          anchor="w")
        self.box = ctk.CTkTextbox(self)
        self.box.pack(fill="both", expand=True, padx=16, pady=6)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 14))
        ctk.CTkButton(row, text=loc.t("btn_add_domain"),
                      command=self._ok).pack(side="right", padx=(8, 0))
        ctk.CTkButton(row, text="Отмена" if loc.lang == "ru" else "Cancel",
                      fg_color="gray45", hover_color="gray35",
                      command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())

    def _ok(self):
        self.result = self.box.get("1.0", "end-1c")
        self.destroy()
