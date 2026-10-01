# -*- coding: utf-8 -*-
"""
Универсальная поддержка прокрутки колесом мыши.

CustomTkinter 5.x/6.x в CTkTextbox и CTkScrollableFrame не всегда
реагирует на колесо мыши (особенно когда курсор находится над дочерним
виджетом — кнопкой, чекбоксом, рамкой). Модуль добавляет:

  * bind_mousewheel(widget)      — прокрутка CTkTextbox / tkinter.Text
                                   колесом, включая курсор над дочерними
                                   виджетами (через and-bind на <Enter>);
  * scrollable_frame_wheel(fr)   — гарантирует работу колеса над любым
                                   содержимым CTkScrollableFrame;
  * install_global_wheel_router  — глобальный fallback: перенаправляет
                                   события колеса на виджет под курсором.

Реализация кроссплатформенная: Windows/Linux — <MouseWheel>/<Button-4/5>,
macOS — <MouseWheel> с другим множителем delta.
"""

import platform

import customtkinter as ctk
from tkinter import Text as TkText

_IS_MAC = platform.system() == "Darwin"


# ---------------------------------------------------------------------------
# Прокрутка текстовых полей
# ---------------------------------------------------------------------------

def _text_scroll(widget, delta, unit="lines", amount=None):
    """Кроссплатформенная прокрутка Text/CTkTextbox на delta колеса."""
    try:
        if not widget.winfo_exists():
            return
    except Exception:
        return
    if _IS_MAC:
        step = -delta
    else:
        step = -delta // 120
    if step == 0:
        step = -1 if delta > 0 else 1
    if unit == "pixels":
        widget.yview_scroll(int(step * (amount or 3)), "units")
    else:
        widget.yview_scroll(int(step * (amount or 3)), "lines")
    return "break"


def bind_mousewheel(widget, amount: int = 3):
    """Делает CTkTextbox/Text прокручиваемым колесом — в т.ч. над детьми.

    Используется «and-bind»: при наведении курсора на текстовое поле
    временно привязывается обработчик колеса к корневому окну, при
    уходе — снимается. Это стандартный надёжный приём для Tk.
    """
    canvas = getattr(widget, "_textbox", None)      # внутренний Text у CTkTextbox
    target = canvas if isinstance(canvas, TkText) else widget

    def _enter(_e=None):
        try:
            root = widget.winfo_toplevel()
            for seq in _wheel_sequences():
                root.bind_all(seq, _on_wheel, add="+")
        except Exception:
            pass

    def _leave(_e=None):
        try:
            root = widget.winfo_toplevel()
            for seq in _wheel_sequences():
                root.unbind_all(seq)
        except Exception:
            pass

    def _on_wheel(event):
        # прокручиваем только если курсор действительно внутри нашего виджета
        try:
            if not widget.winfo_exists():
                return
            x, y = widget.winfo_pointerxy()
            wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
            inside = (wx <= x < wx + widget.winfo_width() and
                      wy <= y < wy + widget.winfo_height())
            # также считаем «внутри» дочерние канвасы CTkTextbox
            if not inside:
                inside = widget.winfo_containing(x, y) is not None and \
                    _is_descendant(widget, widget.winfo_containing(x, y))
            if not inside:
                return
        except Exception:
            pass
        _text_scroll(target, event.delta, "lines", amount)
        return "break"

    widget.bind("<Enter>", _enter)
    widget.bind("<Leave>", _leave)
    # прямые привязки как запасной вариант
    for seq in _wheel_sequences():
        widget.bind(seq, _on_wheel, add="+")
    return widget


def _wheel_sequences():
    if _IS_MAC:
        return ("<MouseWheel",)
    return ("<MouseWheel>", "<Button-4>", "<Button-5>")


def _is_descendant(root_widget, widget):
    try:
        while widget is not None:
            if widget is root_widget:
                return True
            widget = widget.master
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# Прокрутка CTkScrollableFrame колесом над детьми
# ---------------------------------------------------------------------------

def scrollable_frame_wheel(frame: ctk.CTkScrollableFrame, amount: int = 3):
    """Гарантирует работу колеса над любым содержимым CTkScrollableFrame.

    В CTkScrollableFrame внутренняя прокрутка уже привязана к его canvas,
    но события от дочерних кнопок/фреймов иногда теряются. Добавляем
    and-bind на toplevel, направленный в canvas этого фрейма.
    """
    canvas = getattr(frame, "_canvas", None)
    if canvas is None:                              # совместимость со старыми версиями
        canvas = frame

    def _on_wheel(event):
        try:
            px, py = frame.winfo_pointerxy()
            fx, fy = frame.winfo_rootx(), frame.winfo_rooty()
            inside = (fx <= px < fx + frame.winfo_width() and
                      fy <= py < fy + frame.winfo_height())
            if not inside:
                return
            # не мешаем внутренней обработке, если она уже сработала выше
            if _IS_MAC:
                canvas.yview_scroll(int(-event.delta), "units")
            else:
                steps = -event.delta // 120
                if steps == 0:
                    steps = -1 if event.delta > 0 else 1
                canvas.yview_scroll(int(steps * amount), "units")
            return "break"
        except Exception:
            return

    def _enter(_e=None):
        root = frame.winfo_toplevel()
        for seq in _wheel_sequences():
            root.bind_all(seq, _on_wheel, add="+")

    def _leave(_e=None):
        root = frame.winfo_toplevel()
        for seq in _wheel_sequences():
            root.unbind_all(seq)

    frame.bind("<Enter>", _enter)
    frame.bind("<Leave>", _leave)
    for seq in _wheel_sequences():
        frame.bind(seq, _on_wheel, add="+")
    return frame


# ---------------------------------------------------------------------------
# Глобальный fallback для всего приложения
# ---------------------------------------------------------------------------

def install_global_wheel_router(root: ctk.CTk):
    """Маршрутизирует события колеса виджету под курсором.

    Ставится один раз на главное окно. Если ни один специфический
    обработчик не перехватил событие, оно доставляется ближайшему
    прокручиваемому предку под указателем (Text или canvas
    ScrollableFrame). Это лечит классическую проблему «скролл не
    работает, пока не кликнешь в область».
    """
    if getattr(root, "_zapret_wheel_router", False):
        return root
    root._zapret_wheel_router = True

    def _find_scrollable(widget):
        from tkinter import Canvas
        while widget is not None:
            try:
                if isinstance(widget, TkText):
                    return widget, "text"
                if isinstance(widget, Canvas):
                    return widget, "canvas"
            except Exception:
                return None, None
            widget = getattr(widget, "master", None)
        return None, None

    def _route(event):
        try:
            px, py = root.winfo_pointerxy()
            widget = root.winfo_containing(px, py)
            if widget is None:
                return
            target, kind = _find_scrollable(widget)
            if target is None:
                return
            if kind == "text":
                _text_scroll(target, event.delta, "lines", 3)
            else:
                if _IS_MAC:
                    target.yview_scroll(int(-event.delta), "units")
                else:
                    steps = -event.delta // 120
                    if steps == 0:
                        steps = -1 if event.delta > 0 else 1
                    target.yview_scroll(steps * 3, "units")
        except Exception:
            pass

    for seq in _wheel_sequences():
        root.bind_all(seq, _route, add="+")
    return root
