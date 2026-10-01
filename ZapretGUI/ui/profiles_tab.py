# -*- coding: utf-8 -*-
"""Вкладка «Профили и стратегия»: выбор списков доменов и стратегии запуска."""

import os
import re
import threading

import customtkinter as ctk

from config.profiles import (DOMAIN_PROFILES, STRATEGIES,
                             DOMAIN_PROFILE_MAP, STRATEGY_MAP)
from core.zapret_manager import list_bat_scripts


def _bat_family(bat_name: str) -> str:
    """«Семейство» стратегии по имени bat: alt_3_proton_gamer.bat -> alt3,
    main_gamer.bat -> main, service-alt2.bat -> alt2 и т.п."""
    stem = bat_name.rsplit(".", 1)[0].lower()
    m = re.match(r"^(?:service[-_]?|run[-_]?|strategy[-_]?)?"
                 r"(main|alt|zaproto|goodcheck|test|bp)", stem)
    if not m:
        return ""
    fam = m.group(1)
    if fam == "alt":
        d = re.search(r"alt[-_]?(\d+)", stem)
        fam = f"alt{d.group(1)}" if d else "alt"
    return fam


class ProfilesTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.loc = app.loc
        self.settings = app.settings
        self.manager = app.manager

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ================= Профиль доменов ==================================
        pcard = ctk.CTkFrame(self, corner_radius=12)
        pcard.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        pcard.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pcard, text=self.loc.t("profiles_title"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 6), sticky="w")

        self.profile_var = ctk.StringVar(value=self.settings.get("profile"))
        self.profile_btns = {}
        row = 1
        for prof in DOMAIN_PROFILES + [type("P", (), {
                "id": "custom", "name": "Свой набор…",
                "description": "Отдельно: Discord / YouTube / Reports"})()]:
            rbtn = ctk.CTkRadioButton(
                pcard,
                text=f"{prof.name} — {prof.description}",
                variable=self.profile_var, value=prof.id,
                font=ctk.CTkFont(size=13))
            rbtn.grid(row=row, column=0, padx=24, pady=3, sticky="w")
            self.profile_btns[prof.id] = rbtn
            row += 1

        # тонкие переключатели для профиля custom
        sub = ctk.CTkFrame(pcard, fg_color="transparent")
        sub.grid(row=row, column=0, padx=44, pady=(2, 10), sticky="w")
        self.disc_var = ctk.BooleanVar(value=self.settings.get("enable_discord"))
        self.yt_var = ctk.BooleanVar(value=self.settings.get("enable_youtube"))
        self.rep_var = ctk.BooleanVar(value=self.settings.get("enable_reports"))
        ctk.CTkCheckBox(sub, text="Discord", variable=self.disc_var
                        ).grid(row=0, column=0, padx=(0, 18))
        ctk.CTkCheckBox(sub, text="YouTube", variable=self.yt_var
                        ).grid(row=0, column=1, padx=(0, 18))
        ctk.CTkCheckBox(sub, text="Reports (запрещ. IP)", variable=self.rep_var
                        ).grid(row=0, column=2)
        self.sub_frame = sub

        # ================= Стратегия ========================================
        scard = ctk.CTkFrame(self, corner_radius=12)
        scard.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        scard.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scard, text=self.loc.t("strategy_title"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 6), sticky="w")

        self.strategy_var = ctk.StringVar(value=self.settings.get("strategy"))
        strat_frame = ctk.CTkScrollableFrame(scard, height=230,
                                             fg_color="transparent")
        strat_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        strat_frame.grid_columnconfigure(0, weight=1)

        # --- секция «обнаружено в комплекте» (реальные bat-файлы пользователя)
        self.detected_frame = ctk.CTkFrame(strat_frame, fg_color="transparent")
        self._detected_lbl = ctk.CTkLabel(
            self.detected_frame,
            text="⚡ " + self.loc.t("detected_section"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e8a33d")
        self._detected_lbl.grid(row=0, column=0, padx=16, pady=(2, 2), sticky="w")
        self._detected_note = ctk.CTkLabel(
            self.detected_frame, text=self.loc.t("detected_note"),
            font=ctk.CTkFont(size=11), text_color="gray55",
            wraplength=760, justify="left")
        self._detected_note.grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")
        self.detected_btns = {}
        self._detected_key = None
        self.refresh_detected()

        sep0 = ctk.CTkLabel(
            strat_frame, text=self.loc.t("strategy_title"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray65")
        sep0.grid(row=1, column=0, padx=16, pady=(8, 2), sticky="w")
        self.strategy_btns = {}
        prev_gamer = None
        for i, st in enumerate(STRATEGIES):
            # разделитель секции геймерских режимов
            if st.gamer and prev_gamer is False:
                sep = ctk.CTkLabel(
                    strat_frame, text="🎮  " + self.loc.t("gamer_section"),
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#5b9bd5")
                sep.grid(row=i + 2, column=0, padx=16, pady=(10, 2), sticky="w")
            prev_gamer = st.gamer
            label = f"{st.name}"
            if st.recommended:
                label += f"  ⭐ ({self.loc.t('recommended')})"
            if st.gamer:
                label += f"  [{self.loc.t('gamer_badge')}]"
            rb = ctk.CTkRadioButton(
                strat_frame, text=label,
                variable=self.strategy_var, value=st.id,
                font=ctk.CTkFont(size=13),
                command=lambda s=st: self._strategy_hint(s))
            rb.grid(row=i + 3, column=0, padx=16, pady=3, sticky="w")
            self.strategy_btns[st.id] = rb

        self.hint_lbl = ctk.CTkLabel(
            scard, text=self._hint_for(self.strategy_var.get()),
            font=ctk.CTkFont(size=12), text_color="gray60",
            wraplength=900, justify="left")
        self.hint_lbl.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

        # ================= Доп. аргументы ===================================
        acard = ctk.CTkFrame(self, corner_radius=12)
        acard.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        acard.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(acard, text=self.loc.t("custom_args"),
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 4), sticky="w")
        self.args_entry = ctk.CTkEntry(
            acard, placeholder_text=self.loc.t("custom_args_hint"))
        self.args_entry.grid(row=1, column=0, sticky="ew",
                             padx=18, pady=(0, 4))
        self.args_entry.insert(0, self.settings.get("custom_args", ""))
        ctk.CTkLabel(acard, text=self.loc.t("custom_args_hint"),
                     font=ctk.CTkFont(size=11), text_color="gray55"
                     ).grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

        # ================= Кнопки ===========================================
        self.grid_rowconfigure(3, weight=1)          # пустая растягиваемая строка
        holder = ctk.CTkFrame(self, fg_color="transparent")
        holder.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 16))
        holder.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(holder, text="", text_color="gray60")
        self.status_lbl.grid(row=0, column=1, padx=12)

        ctk.CTkButton(holder, text=self.loc.t("btn_apply"), width=140,
                      command=self._apply).grid(row=0, column=0)
        ctk.CTkButton(holder, text=self.loc.t("apply_restarts"), width=240,
                      fg_color="#2fa572", hover_color="#278a5f",
                      command=self._apply_restart).grid(row=0, column=2,
                                                        padx=(12, 0))

    # ------------------------------------------------------------------ логика
    def _hint_for(self, sid):
        st = STRATEGY_MAP.get(sid)
        if not st:
            return ""
        txt = st.description
        if st.gamer and st.gamer_note:
            txt += "\n🎮 " + st.gamer_note
        return txt

    def _strategy_hint(self, st):
        self.hint_lbl.configure(text=self._hint_for(st.id))

    def _collect(self):
        self.settings.set("profile", self.profile_var.get())
        self.settings.set("strategy", self.strategy_var.get())
        self.settings.set("custom_args", self.args_entry.get().strip())
        self.settings.set("enable_discord", self.disc_var.get())
        self.settings.set("enable_youtube", self.yt_var.get())
        self.settings.set("enable_reports", self.rep_var.get())
        self.settings.save()

    def _apply(self):
        self._collect()
        self.status_lbl.configure(
            text="✔ " + self.loc.t("settings_saved"))
        self.after(2500, lambda: self.status_lbl.configure(text=""))

    def _apply_restart(self):
        self._collect()
        if not self.manager.root():
            self.status_lbl.configure(text="⚠ " + self.loc.t("msg_need_path"))
            return
        self.status_lbl.configure(text="⟳ " + self.loc.t("msg_started"))
        threading.Thread(target=self.manager.restart, daemon=True).start()

    def on_show(self):
        # синхронизировать виджеты с текущими настройками
        self.refresh_detected()
        self.profile_var.set(self.settings.get("profile"))
        self.strategy_var.set(self.settings.get("strategy"))

    # ------------------------------------------------- обнаружение bat-файлов
    def _scan_kit_bats(self) -> dict:
        """Сканирует реальный комплект и возвращает {bat_name: (sid, gamer)}.

        sid — ближайшая известная стратегия GUI; если её нет — генерируется
        новый id на основе имени файла, чтобы показать ВСЕ стратегии комплекта.
        """
        root = self.manager.root()
        if not root:
            return {}
        try:
            bats = list_bat_scripts(root)
        except OSError:
            return {}
        service_bats = [b for b in bats if b.lower().startswith("service")] \
            or bats
        out = {}
        known_sids = set(STRATEGY_MAP)
        for b in service_bats:
            low = b.rsplit(".", 1)[0].lower()
            if not re.match(r"^(?:service[-_]?|run[-_]?|strategy[-_]?)?"
                            r"(main|alt|zaproto)", low):
                continue                      # goodcheck/update и пр. — не стратегии
            gamer = "gamer" in low or low.endswith("_gmr")
            fam = _bat_family(b)
            sid = None
            if fam:
                cand = f"{fam}_gamer" if gamer else fam
                if cand in known_sids:
                    sid = cand
                else:
                    for st in STRATEGIES:
                        core = st.id[:-6] if st.id.endswith("_gamer") else st.id
                        if core.replace("_", "") == fam.replace("_", "") \
                                and st.gamer == gamer:
                            sid = st.id
                            break
            if not sid:
                clean = re.sub(r"^(?:service[-_]?|run[-_]?|strategy[-_]?)", "", low)
                sid = clean + ("__ext" if clean in known_sids else "")
            out[b] = (sid, gamer)
        return out

    def refresh_detected(self):
        """Перестраивает секцию «Обнаружено в комплекте» по фактическим bat."""
        detected = self._scan_kit_bats()
        key = "|".join(sorted(f"{k}:{v[0]}" for k, v in detected.items()))
        if key == self._detected_key:
            return                              # ничего не изменилось
        self._detected_key = key
        for w in list(self.detected_btns.values()):
            w.destroy()
        self.detected_btns = {}
        if not detected:
            self.detected_frame.grid_remove()
            return
        self.detected_frame.grid(row=0, column=0, sticky="ew")
        seen = set()
        rows = sorted(detected.items(),
                      key=lambda kv: (not kv[1][1], kv[1][0]))
        for r, (bat, (sid, gamer)) in enumerate(rows, start=2):
            if sid in seen:
                continue
            seen.add(sid)
            name = os.path.splitext(bat)[0]
            label = f"{name}   ({bat})" + ("  🎮" if gamer else "")
            rb = ctk.CTkRadioButton(
                self.detected_frame, text=label,
                variable=self.strategy_var, value=sid,
                font=ctk.CTkFont(size=13),
                command=lambda s=sid, g=gamer, n=name: self._detected_hint(s, g, n))
            rb.grid(row=r, column=0, padx=16, pady=2, sticky="w")
            self.detected_btns[sid] = rb

    def _detected_hint(self, sid, gamer, name):
        st = STRATEGY_MAP.get(sid)
        if st:
            self._strategy_hint(st)
        else:
            txt = "Стратегия из вашего комплекта: " + name
            if gamer:
                txt += ("\n🎮 Геймерский режим: обходятся только игровые домены "
                        "из списка комплекта, остальной трафик идёт напрямую.")
            self.hint_lbl.configure(text=txt)
