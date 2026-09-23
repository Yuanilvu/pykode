"""PyKode — Loader kurikulum dari file YAML di curriculum/levels/."""
import os
import re
import yaml

CURRICULUM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curriculum", "levels")
JURUSAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "curriculum", "jurusan")

MARKDOWN_TEMPLATE = re.compile(r"^[\w\s-]+$")

_babs = None
_by_lesson = None
_by_problem = None
_drills = None
_project = None
_project2 = None
_bugs = None
_bug_by_id = None
_jurusan_info = None       # [info], termasuk yang belum dibuka (enabled False)
_jurusan_babs = None       # {jid: [modul dict]}
_jurusan_lesson = None     # {lesson_id: jid}
_jurusan_problem = None    # {problem_id: jid}


def _load_all():
    global _babs, _by_lesson, _by_problem, _drills, _project, _project2, _bugs, _bug_by_id
    global _jurusan_info, _jurusan_babs, _jurusan_lesson, _jurusan_problem
    if _babs is not None:
        return
    babs = []
    by_lesson, by_problem = {}, {}
    drills = []
    project = None
    project2 = None
    bugs, bug_by_id = [], {}
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
        elif "proyek" in data:
            project = data["proyek"]
        elif "proyek2" in data:
            project2 = data["proyek2"]
        elif "bug" in data:
            bugs = data["bug"] or []
            for b in bugs:
                bug_by_id[b["id"]] = b
    babs.sort(key=lambda b: b.get("bab", 999))
    if project:
        misi = sorted(project.get("misi") or [], key=lambda m: m.get("bab", 999))
        project["misi"] = misi
    if project2:
        misi2 = sorted(project2.get("misi") or [], key=lambda m: m.get("bab", 999))
        project2["misi"] = misi2
    bugs.sort(key=lambda b: (b.get("bab", 99), b["id"]))

    # ── Jurusan (penjurusan): konten di curriculum/jurusan/<id>/babNN.yaml ──
    # Modul TIDAK masuk jalur utama (_babs) — punya daftar sendiri per jurusan.
    # Pelajaran & soalnya TETAP didaftarkan ke by_lesson/by_problem supaya
    # route /lesson & /problem jalan tanpa perubahan.
    jinfo = []
    meta_p = os.path.join(JURUSAN_DIR, "jurusan.yaml")
    if os.path.isfile(meta_p):
        try:
            with open(meta_p, encoding="utf-8") as f:
                jinfo = (yaml.safe_load(f) or {}).get("jurusan") or []
        except Exception:
            jinfo = []
    jbabs, jles, jpro = {}, {}, {}
    jinfo_by_id = {j.get("id"): j for j in jinfo}
    if os.path.isdir(JURUSAN_DIR):
        for jid in sorted(os.listdir(JURUSAN_DIR)):
            jdir = os.path.join(JURUSAN_DIR, jid)
            if not os.path.isdir(jdir):
                continue
            mods = jbabs.setdefault(jid, [])
            for fn in sorted(os.listdir(jdir)):
                if not fn.endswith(".yaml"):
                    continue
                try:
                    with open(os.path.join(jdir, fn), encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                except Exception:
                    continue
                if not isinstance(data, dict) or "bab" not in data:
                    continue
                data["jurusan"] = jid
                mods.append(data)
            mods.sort(key=lambda b: (b.get("modul", b.get("bab", 999)),
                                     b.get("bab", 999)))
    for jid, mods in jbabs.items():
        ji = jinfo_by_id.get(jid) or {"id": jid, "nama": jid, "emoji": "🎓"}
        for m in mods:
            emo = ji.get("emoji", "🎓")
            m["tingkat"] = m.get("tingkat", 1)
            _tl = " · Tingkat 2" if m["tingkat"] >= 2 else ""
            m["nav_label"] = (f"{emo} {ji.get('nama', jid)} · "
                              f"Modul {m.get('modul', m.get('bab'))}{_tl}")
            m["jurusan_info"] = ji
            for p in (m.get("pelajaran") or []):
                by_lesson[p["id"]] = {"bab": m, "data": p}
                jles[p["id"]] = jid
            for s in (m.get("soal") or []):
                by_problem[s["id"]] = {"bab": m, "data": s}
                jpro[s["id"]] = jid
    _jurusan_info, _jurusan_babs = jinfo, jbabs
    _jurusan_lesson, _jurusan_problem = jles, jpro

    _babs, _by_lesson, _by_problem, _drills, _project = babs, by_lesson, by_problem, drills, project
    _project2 = project2
    _bugs, _bug_by_id = bugs, bug_by_id


def get_project():
    _load_all()
    return _project


def get_milestone(milestone_id):
    _load_all()
    if not _project:
        return None
    for m in _project.get("misi") or []:
        if m["id"] == milestone_id:
            return m
    return None


def get_project2():
    _load_all()
    return _project2


def get_milestone2(milestone_id):
    _load_all()
    if not _project2:
        return None
    for m in _project2.get("misi") or []:
        if m["id"] == milestone_id:
            return m
    return None


def get_bugs():
    _load_all()
    return _bugs


def get_bug(bug_id):
    _load_all()
    return _bug_by_id.get(bug_id)


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


def get_jurusan_list():
    """Daftar info jurusan (termasuk yang belum dibuka / enabled False)."""
    _load_all()
    return list(_jurusan_info or [])


def get_jurusan(jid):
    _load_all()
    for j in (_jurusan_info or []):
        if j.get("id") == jid:
            return j
    return None


def get_jurusan_babs(jid):
    """Modul (bab) milik satu jurusan, terurut."""
    _load_all()
    return list((_jurusan_babs or {}).get(jid) or [])


def jurusan_of_lesson(lesson_id):
    _load_all()
    return (_jurusan_lesson or {}).get(lesson_id)


def jurusan_of_problem(problem_id):
    _load_all()
    return (_jurusan_problem or {}).get(problem_id)


def stats():
    _load_all()
    total_lessons = sum(len(b.get("pelajaran", [])) for b in _babs)
    total_problems = sum(len(b.get("soal", [])) for b in _babs)
    return {"babs": len(_babs), "pelajaran": total_lessons,
            "soal": total_problems, "drill": len(_drills)}


def render_markdown(md: str) -> str:
    """Markdown mini (cukup untuk materi pelajaran): heading, bold, inline code,
    list, paragraf, dan fenced code block ```...```."""
    md = (md or "").strip()
    lines = md.split("\n")
    out = []
    in_list = False
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_list:
                out.append("</ul>")
                in_list = False
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre class='block-code'><code>")
                in_code = True
            continue
        if in_code:
            out.append(_esc(line))
            continue
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
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(s: str) -> str:
    s = _esc(s)
    # `kode`
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    # **tebal**
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s
