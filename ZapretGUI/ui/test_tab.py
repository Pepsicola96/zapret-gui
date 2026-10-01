# -*- coding: utf-8 -*-
"""Вкладка «Тест стратегий»: автоматический подбор лучшей стратегии обхода.

Для каждой выбранной стратегии сервис кратко запускается, проверяются
доступность Discord/YouTube и замеряется задержка; по итогам строится
рейтинг, победителя можно применить одной кнопкой.
"""

import tkinter.messagebox as mb

import customtkinter as ctk

from config.profiles import STRATEGIES, STRATEGY_MAP
from core.strategy_tester import StrategyTester
from ui.scroll import scrollable_frame_wheel


PHASE_KEYS = {
    "stop": "test_phase_stop",
    "start": "test_phase_start",
    "test": "test_phase_test",
    "cleanup": "test_phase_cleanup",
}


class TestTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.loc = app.loc
        self.settings = app.settings
        self.manager = app.manager
        self.tester = StrategyTester(self.manager, self.settings)

        # колбэки из рабочего потока -> маршалинг в UI-поток
        self.tester.on_progress = lambda sid, ph: self.after(
            0, lambda: self._on_progress(sid, ph))
        # Результаты кэшируются синхронно в потоке тестера (без обращения к
        # Tk-виджетам) и дополнительно сохраняются на диск — это страховка от
        # потери итогов при закрытии окна во время теста. Отрисовка таблицы —
        # только через after() в UI-поток.
        def _result_cb(res):
            self._results[res.strategy_id] = res
            self._save_cache()
            try:
                self.after(0, lambda r=res: self._on_result(r))
            except Exception:          # окно уже закрывается — кэш сохранён
                pass
        self.tester.on_result = _result_cb

        def _done_cb(results):
            for r in results:
                self._results[r.strategy_id] = r
            self._save_cache()
            try:
                self.after(0, lambda rs=list(results): self._on_done(rs))
            except Exception:
                pass
        self.tester.on_done = _done_cb

        self.row_widgets = {}       # strategy_id -> dict of labels
        self._results = {}          # strategy_id -> StrategyResult (для рейтинга)
        self.check_vars = {}        # strategy_id -> BooleanVar
        self.best_sid = ""

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ---------------- карточка с описанием и параметрами -----------------
        intro = ctk.CTkFrame(self, corner_radius=12)
        intro.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        intro.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(intro, text=self.loc.t("test_title"),
                     font=ctk.CTkFont(size=17, weight="bold")
                     ).grid(row=0, column=0, padx=18, pady=(12, 4), sticky="w")
        ctk.CTkLabel(intro, text=self.loc.t("test_intro"),
                     font=ctk.CTkFont(size=12), text_color="gray65",
                     wraplength=940, justify="left"
                     ).grid(row=1, column=0, padx=18, pady=(0, 4), sticky="w")
        ctk.CTkLabel(intro, text="⚠  " + self.loc.t("test_warning"),
                     font=ctk.CTkFont(size=12), text_color="#d4a017",
                     wraplength=940, justify="left"
                     ).grid(row=2, column=0, padx=18, pady=(0, 10), sticky="w")

        # параметры
        opts = ctk.CTkFrame(intro, fg_color="transparent")
        opts.grid(row=3, column=0, padx=18, pady=(0, 14), sticky="w")
        ctk.CTkLabel(opts, text=self.loc.t("test_rounds") + ":").grid(
            row=0, column=0, padx=(0, 6))
        self.rounds_var = ctk.IntVar(value=3)
        ctk.CTkOptionMenu(opts, values=["1", "2", "3", "5", "8"],
                          variable=self.rounds_var, width=70).grid(row=0, column=1)
        ctk.CTkLabel(opts, text=self.loc.t("test_settle") + ":").grid(
            row=0, column=2, padx=(24, 6))
        self.settle_var = ctk.IntVar(value=3)
        ctk.CTkOptionMenu(opts, values=["2", "3", "5", "8"],
                          variable=self.settle_var, width=70).grid(row=0, column=3)

        # ---------------- выбор стратегий ------------------------------------
        sel_card = ctk.CTkFrame(self, corner_radius=12)
        sel_card.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        sel_card.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(sel_card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text=self.loc.t("strategy_title"),
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(head, text=self.loc.t("test_select_all"), width=120,
                      height=26, fg_color="gray45", hover_color="gray35",
                      command=lambda: self._set_all(True)).grid(row=0, column=1,
                                                                padx=4)
        ctk.CTkButton(head, text=self.loc.t("test_select_none"), width=120,
                      height=26, fg_color="gray45", hover_color="gray35",
                      command=lambda: self._set_all(False)).grid(row=0, column=2)

        self.strat_frame = ctk.CTkScrollableFrame(sel_card, height=200,
                                                  fg_color="transparent")
        self.strat_frame.grid(row=1, column=0, sticky="ew", padx=10,
                              pady=(2, 6))
        self.strat_frame.grid_columnconfigure(0, weight=1)
        scrollable_frame_wheel(self.strat_frame)
        self._build_strategy_checks()

        # ---------------- кнопки запуска теста -------------------------------
        runrow = ctk.CTkFrame(self, fg_color="transparent")
        runrow.grid(row=2, column=0, sticky="ew", padx=16, pady=(2, 6))
        runrow.grid_columnconfigure(2, weight=1)
        self.btn_run = ctk.CTkButton(
            runrow, text=self.loc.t("btn_test_start"), height=44, width=230,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#5b9bd5", hover_color="#4a83b3", command=self._run)
        self.btn_run.grid(row=0, column=0, padx=(0, 8))
        self.btn_cancel = ctk.CTkButton(
            runrow, text=self.loc.t("btn_test_stop"), height=44, width=150,
            fg_color="#c0392b", hover_color="#992d22",
            state="disabled", command=self._cancel)
        self.btn_cancel.grid(row=0, column=1)
        self.progress_lbl = ctk.CTkLabel(runrow, text="", text_color="gray60",
                                         anchor="w")
        self.progress_lbl.grid(row=0, column=2, sticky="ew", padx=8)

        # ---------------- таблица результатов --------------------------------
        res_card = ctk.CTkFrame(self, corner_radius=12)
        res_card.grid(row=3, column=0, sticky="nsew", padx=16, pady=(6, 8))
        res_card.grid_columnconfigure(0, weight=1)
        res_card.grid_rowconfigure(1, weight=1)

        # шапка таблицы: 6 колонок (стратегия | отступ | статус | успех | ms | вердикт)
        header = ctk.CTkFrame(res_card, fg_color=("gray80", "gray25"))
        header.grid(row=0, column=0, sticky="ew")
        headers = [self.loc.t("test_col_strategy"), "",
                   self.loc.t("test_col_status"), self.loc.t("test_col_success"),
                   self.loc.t("test_col_latency"), self.loc.t("test_col_verdict")]
        for col, txt in enumerate(headers):
            ctk.CTkLabel(header, text=txt,
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).grid(row=0, column=col, padx=10, pady=6, sticky="w")
        header.grid_columnconfigure(0, weight=2)
        header.grid_columnconfigure(2, weight=2)
        header.grid_columnconfigure(3, weight=1)
        header.grid_columnconfigure(4, weight=1)
        header.grid_columnconfigure(5, weight=1)

        self.rows_frame = ctk.CTkScrollableFrame(res_card, fg_color="transparent")
        self.rows_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self.rows_frame.grid_columnconfigure(0, weight=2)
        self.rows_frame.grid_columnconfigure(2, weight=2)
        self.rows_frame.grid_columnconfigure(3, weight=1)
        self.rows_frame.grid_columnconfigure(4, weight=1)
        self.rows_frame.grid_columnconfigure(5, weight=1)
        scrollable_frame_wheel(self.rows_frame)

        # ---------------- итог / применение ----------------------------------
        bottom = ctk.CTkFrame(self, corner_radius=12,
                              fg_color=("gray88", "gray17"))
        bottom.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 16))
        bottom.grid_columnconfigure(0, weight=1)
        self.best_lbl = ctk.CTkLabel(bottom, text="",
                                     font=ctk.CTkFont(size=14, weight="bold"),
                                     anchor="w")
        self.best_lbl.grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self.btn_apply_best = ctk.CTkButton(
            bottom, text=self.loc.t("btn_apply_best"), width=230, height=38,
            fg_color="#2fa572", hover_color="#278a5f",
            state="disabled", command=self._apply_best)
        self.btn_apply_best.grid(row=0, column=1, padx=(0, 16), pady=10)

    # ------------------------------------------------------ кэш результатов
    def _cache_path(self):
        import os
        from config.settings import SETTINGS_DIR
        return os.path.join(SETTINGS_DIR, "last_strategy_test.json")

    def _save_cache(self):
        """Сохраняет последние результаты теста на диск (страховка)."""
        try:
            import json, os, time
            data = {"saved_at": time.time(),
                    "results": [{"strategy_id": r.strategy_id,
                                 "launched": r.launched,
                                 "attempts": r.attempts,
                                 "successes": r.successes,
                                 "latencies": r.latencies}
                                for r in self._results.values()]}
            os.makedirs(os.path.dirname(self._cache_path()), exist_ok=True)
            with open(self._cache_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def load_last_results(self):
        """Возвращает последний сохранённый рейтинг (или [])."""
        try:
            import json
            from core.strategy_tester import StrategyResult
            with open(self._cache_path(), encoding="utf-8") as f:
                data = json.load(f)
            out = []
            for d in data.get("results", []):
                r = StrategyResult(d["strategy_id"], launched=d["launched"],
                                   attempts=d["attempts"],
                                   successes=d["successes"],
                                   latencies=list(d["latencies"]))
                r.tested = r.attempts > 0
                out.append(r)
            return out
        except (OSError, ValueError, KeyError):
            return []

    # ------------------------------------------------------------- построение
    def _build_strategy_checks(self):
        default_sid = self.settings.get("strategy", "alt2")
        gamer_default = {"main_gamer", "alt1_gamer", "alt2_gamer",
                         "alt3_gamer", "alt4_proton_gamer"}
        row = 0
        for st in STRATEGIES:
            var = ctk.BooleanVar(value=(st.id == default_sid or
                                        st.id in gamer_default or
                                        st.recommended))
            badge = ("  🎮" if st.gamer else "") + \
                    ("  ⭐" if st.recommended else "")
            cb = ctk.CTkCheckBox(self.strat_frame, text=st.name + badge,
                                 variable=var, font=ctk.CTkFont(size=13))
            cb.grid(row=row, column=0, padx=14, pady=3, sticky="w")
            self.check_vars[st.id] = var
            row += 1

    def _set_all(self, val: bool):
        for var in self.check_vars.values():
            var.set(val)

    # ------------------------------------------------------------------- run
    def _selected_ids(self):
        return [st.id for st in STRATEGIES if self.check_vars[st.id].get()]

    def _run(self):
        if not self.manager.root():
            mb.showwarning("Zapret GUI", self.loc.t("msg_need_path"))
            self.app._select("settings")
            return
        ids = self._selected_ids()
        if not ids:
            mb.showwarning("Zapret GUI", self.loc.t("test_need_strategies"))
            return
        # очищаем таблицу
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self.row_widgets.clear()
        for sid in ids:
            self._add_row(sid, "…")
        self._results.clear()
        self.best_lbl.configure(text="")
        self.btn_apply_best.configure(state="disabled")
        self.best_sid = ""

        self.btn_run.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        try:
            self.tester.start(ids, rounds=int(self.rounds_var.get()),
                              settle_sec=float(self.settle_var.get()))
        except RuntimeError as e:
            mb.showerror("Zapret GUI", str(e))
            self.btn_run.configure(state="normal")
            self.btn_cancel.configure(state="disabled")

    def _cancel(self):
        self.tester.cancel()
        self.progress_lbl.configure(text=self.loc.t("test_cancelled"))
        self.btn_cancel.configure(state="disabled")

    # ------------------------------------------------------------- callbacks
    def _on_progress(self, sid, phase):
        key = PHASE_KEYS.get(phase)
        if not key:
            return
        txt = self.loc.t(key)
        if sid and sid in self.row_widgets:
            self.row_widgets[sid]["status"].configure(text=txt)
            self.progress_lbl.configure(
                text=f"{self.loc.t('test_running')}: {STRATEGY_MAP[sid].name} — {txt}")
        elif phase == "cleanup":
            self.progress_lbl.configure(text=txt)

    def _add_row(self, sid, status_txt):
        st = STRATEGY_MAP.get(sid)
        name = st.name + ("  🎮" if st and st.gamer else "")
        row = len(self.row_widgets)
        odd = row % 2
        bg = ("gray86", "gray20") if odd else ("gray90", "gray16")
        holder = ctk.CTkFrame(self.rows_frame, fg_color=bg, corner_radius=6)
        holder.grid(row=row, column=0, sticky="ew", pady=1)
        for col, w in ((0, 2), (2, 2), (3, 1), (4, 1), (5, 1)):
            holder.grid_columnconfigure(col, weight=w)
        lbl_name = ctk.CTkLabel(holder, text=name, anchor="w",
                                font=ctk.CTkFont(size=13, weight="bold"))
        lbl_name.grid(row=0, column=0, padx=10, pady=6, sticky="w")
        lbl_status = ctk.CTkLabel(holder, text=status_txt, anchor="w",
                                  text_color="gray60",
                                  font=ctk.CTkFont(size=12))
        lbl_status.grid(row=0, column=2, padx=10, pady=6, sticky="w")
        lbl_succ = ctk.CTkLabel(holder, text="—", anchor="w")
        lbl_succ.grid(row=0, column=3, padx=10, pady=6, sticky="w")
        lbl_lat = ctk.CTkLabel(holder, text="—", anchor="w")
        lbl_lat.grid(row=0, column=4, padx=10, pady=6, sticky="w")
        lbl_verdict = ctk.CTkLabel(holder, text="—", anchor="w")
        lbl_verdict.grid(row=0, column=5, padx=10, pady=6, sticky="w")
        self.row_widgets[sid] = {"holder": holder, "status": lbl_status,
                                 "succ": lbl_succ, "lat": lbl_lat,
                                 "verdict": lbl_verdict}

    def _on_result(self, res):
        ru = self.loc.lang == "ru"
        self._results[res.strategy_id] = res
        # гарантируем существование строки (например, при тесте стратегии,
        # добавленной в комплект позже этой версии GUI)
        if res.strategy_id not in self.row_widgets:
            self._add_row(res.strategy_id, "")
        w = self.row_widgets.get(res.strategy_id)
        if not w:
            return
        pct = round(res.success_rate * 100)
        w["succ"].configure(text=f"{res.successes}/{res.attempts} ({pct}%)",
                            text_color=("#2fa572" if pct >= 75 else
                                        "#d4a017" if pct >= 40 else "#c0392b"))
        w["lat"].configure(text=(f"{res.avg_latency:.0f} ms"
                                 if res.latencies else "—"))
        verdict = res.verdict(ru)
        colors = {"отлично": "#2fa572", "хорошо": "#2fa572",
                  "частично": "#d4a017", "плохо": "#c0392b",
                  "excellent": "#2fa572", "good": "#2fa572",
                  "partial": "#d4a017", "bad": "#c0392b"}
        w["verdict"].configure(text=verdict,
                               text_color=colors.get(verdict, "gray60"))
        w["status"].configure(text="✔" if res.launched else "✘")

    def _on_done(self, results):
        self.btn_run.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        # объединяем присланный список с кэшем колбэков — гарантия, что
        # ни один результат не потерян при досрочной остановке теста
        merged = dict(self._results)
        for r in results:
            merged[r.strategy_id] = r
        results = list(merged.values())
        # «протестированной» считаем стратегию с состоявшимся хотя бы одним
        # замером (tested=True выставляется в потоке тестера; при ручном/
        # внешнем формировании результатов поле может не заполняться)
        tested = [r for r in results if r.attempts > 0]
        if not tested:
            self.progress_lbl.configure(text=self.loc.t("test_cancelled"))
            return
        best = max(tested, key=lambda r: r.score())
        if best.successes > 0:
            self.best_sid = best.strategy_id
            st = STRATEGY_MAP.get(best.strategy_id)
            self.best_lbl.configure(
                text=f"🏆 {self.loc.t('test_best')}: "
                     f"{st.name if st else best.strategy_id} "
                     f"({round(best.success_rate * 100)}%, "
                     f"{best.avg_latency:.0f} ms)",
                text_color="#2fa572")
            self.btn_apply_best.configure(state="normal")
            # подсветка строки победителя
            w = self.row_widgets.get(best.strategy_id)
            if w:
                w["holder"].configure(fg_color=("#dff0e4", "gray25"))
        else:
            self.best_lbl.configure(
                text=("Ни одна стратегия не обеспечила доступ — проверьте путь "
                      "к комплекту, права администратора и попробуйте больше "
                      "раундов") if self.loc.lang == "ru" else
                ("No strategy succeeded — check kit path, admin rights, "
                 "or increase rounds"),
                text_color="#c0392b")
        self.progress_lbl.configure(text=self.loc.t("test_done"))
        # запись итогов в общий журнал
        for r in sorted(tested, key=lambda x: -x.score()):
            self.app.tabs["dashboard"].append_log(
                f"[test] {r.strategy_id}: {r.successes}/{r.attempts} "
                f"({round(r.success_rate * 100)}%), "
                f"avg {r.avg_latency:.0f} ms — {r.verdict(self.loc.lang == 'ru')}")

    # --------------------------------------------------------------- apply
    def _apply_best(self):
        if not self.best_sid:
            return
        self.settings.set("strategy", self.best_sid)
        self.settings.save()
        self.app.tabs["profiles"].strategy_var.set(self.best_sid)
        hint = STRATEGY_MAP[self.best_sid].description
        self.app.tabs["profiles"].hint_lbl.configure(text=hint)
        self.progress_lbl.configure(
            text=f"✔ {self.loc.t('strategy')}: {self.best_sid}")
        if self.manager.is_running():
            import threading
            threading.Thread(target=self.manager.restart, daemon=True).start()

    def on_show(self):
        # если есть результаты прошлого теста и текущий список пуст —
        # показываем напоминание о победителе
        if not self._results and self.row_widgets:
            return
