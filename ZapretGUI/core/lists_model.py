# -*- coding: utf-8 -*-
"""Редактор списков доменов (свойства файлов lists/*.txt комплекта)."""

import os


class ListsEditorModel:
    """Работа с файлами списков доменов внутри комплекта Zapret."""

    def __init__(self, manager):
        self.manager = manager

    def root_ok(self) -> bool:
        return bool(self.manager.root()) and os.path.isdir(self.manager.root())

    def list_files(self):
        """Возвращает [(имя, полный путь)] всех .txt в папке lists.
        Если папки нет — возвращает пустой список (UI предложит создать)."""
        d = self.manager.lists_dir()
        out = []
        if os.path.isdir(d):
            try:
                for name in sorted(os.listdir(d)):
                    if name.lower().endswith(".txt"):
                        out.append((name, os.path.join(d, name)))
            except OSError:
                pass
        return out

    def read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def save_file(self, path: str, text: str) -> bool:
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp, path)
            return True
        except OSError:
            return False

    def create_file(self, name: str, initial: str = "") -> str:
        """Создаёт новый список lists/<name>.txt, возвращает путь."""
        name = os.path.basename(name)
        if not name.lower().endswith(".txt"):
            name += ".txt"
        d = self.manager.lists_dir()
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(initial)
        return path

    # ---- валидация строк списка ------------------------------------------
    DOMAIN_RE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_*")

    def validate_line(self, line: str):
        """Возвращает (ok, очищенная_строка, сообщение_об_ошибке)."""
        s = line.strip()
        if not s or s.startswith("#"):
            return True, s, ""
        bad = set(s) - self.DOMAIN_RE_CHARS
        if bad:
            return False, s, f"недопустимые символы: {''.join(sorted(bad))}"
        if s.startswith(".") or s.endswith("."):
            return False, s, "домен не может начинаться/заканчиваться с точки"
        if ".." in s:
            return False, s, "двойная точка в домене"
        if "." not in s and "*" not in s:
            return False, s, "нет точки — похоже, не домен"
        return True, s.lower(), ""

    def add_domains(self, path: str, domains_text: str):
        """Добавляет домены (по одному на строку) без дубликатов.
        Возвращает (добавлено, пропущено_дублей, ошибки[(строка, причина)])."""
        existing = set()
        raw = self.read_file(path)
        for ln in raw.splitlines():
            t = ln.strip().lower()
            if t and not t.startswith("#"):
                existing.add(t)

        added, dupes, errors = 0, 0, []
        new_lines = []
        for line in domains_text.splitlines():
            ok, cleaned, err = self.validate_line(line)
            if not ok:
                errors.append((line.strip(), err))
                continue
            if not cleaned:
                continue
            if cleaned in existing:
                dupes += 1
                continue
            existing.add(cleaned)
            new_lines.append(cleaned)
            added += 1

        if added:
            sep = "" if (not raw or raw.endswith("\n")) else "\n"
            self.save_file(path, raw + sep + "\n".join(new_lines) + "\n")
        return added, dupes, errors

    def remove_domain(self, path: str, domain: str) -> bool:
        domain = domain.strip().lower()
        raw = self.read_file(path)
        kept = [ln for ln in raw.splitlines()
                if ln.strip().lower() != domain]
        if len(kept) == len(raw.splitlines()):
            return False
        return self.save_file(path, "\n".join(kept) + "\n")

    def count_domains(self, path: str) -> int:
        n = 0
        for ln in self.read_file(path).splitlines():
            t = ln.strip()
            if t and not t.startswith("#"):
                n += 1
        return n
