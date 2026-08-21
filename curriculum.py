"""PyKode — Loader kurikulum dari file YAML di curriculum/levels/."""
import os
import re
import yaml

CURRICULUM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curriculum", "levels")

MARKDOWN_TEMPLATE = re.compile(r"^[\w\s-]+$")

_babs = None
_by_lesson = None
_by_problem = None
_drills = None


def _load_all():
    global _babs, _by_lesson, _by_problem, _drills
    if _babs is not None:
        return
    babs = []
    by_lesson, by_problem = {}, {}
    drills = []
    for fn in sorted(os.listdir(CURRICULUM_DIR)):
        if not fn.endswith(".yaml"):
            continue
        with open(os.path.join(CURRICULUM_DIR, fn), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "bab" in data:
            babs.append(data)
            for p in (data.get("pelajaran") or []):
                by_lesson[p["id"]] = {"bab": data, "data": p}
            for s in (data.get("soal") or []):
                by_problem[s["id"]] = {"bab": data, "data": s}
        elif "drill" in data:
            drills = data["drill"] or []
    babs.sort(key=lambda b: b.get("bab", 999))
    _babs, _by_lesson, _by_problem, _drills = babs, by_lesson, by_problem, drills


def get_babs():
    _load_all()
    return _babs


def get_bab(n):
    _load_all()
    for b in _babs:
        if b["bab"] == n:
            return b
    return None


def get_lesson(lesson_id):
    _load_all()
    return _by_lesson.get(lesson_id)


def get_problem(problem_id):
    _load_all()
    return _by_problem.get(problem_id)


def get_drills():
    _load_all()
    return _drills


def get_drill(drill_id):
    _load_all()
    for d in _drills:
        if d["id"] == drill_id:
            return d
    return None


def get_problems_by_bab(bab_num):
    _load_all()
    if 0 < bab_num <= len(_babs):
        return list(_babs[bab_num - 1].get("soal") or [])
    return []


def stats():
    _load_all()
    total_lessons = sum(len(b.get("pelajaran", [])) for b in _babs)
    total_problems = sum(len(b.get("soal", [])) for b in _babs)
    return {"babs": len(_babs), "pelajaran": total_lessons,
            "soal": total_problems, "drill": len(_drills)}


def render_markdown(md: str) -> str:
    """Markdown mini (cukup untuk materi pelajaran): heading, bold, inline code, list, paragraf."""
    md = (md or "").strip()
    lines = md.split("\n")
    out = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("### "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h4>{_inline(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h3>{_inline(stripped[3:])}</h3>")
        elif stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p class='lead'>{_inline(stripped)}</p>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{_inline(stripped)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _inline(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # `kode`
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    # **tebal**
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s
