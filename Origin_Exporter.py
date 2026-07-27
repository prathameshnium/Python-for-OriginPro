#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
origin_extract_gui.py — get everything out of Origin projects as plain files.
=============================================================================

A general-purpose extractor. Pick any .opju / .opj files in a GUI, pick where to
save, and every worksheet, column formula, fit/report table, matrix and graph is
written out as CSV / PNG / JSON, with a manifest and a log.

Not tied to any one project: the search root, the save location and the options
are all chosen in the GUI and remembered between runs.

HOW TO RUN
----------
Inside Origin — the reliable way, no COM involved:
    Connectivity > Python Console   (or open this file in Code Builder and Run)
    exec(open(r'<path to this file>').read())
Origin ships its own Python with originpro already installed.

From external Python:
    pip install originpro pandas
    python origin_extract_gui.py
It attaches to a running Origin first and only launches its own instance if that
fails. Start Origin before running and you avoid the whole class of COM
"Invalid pointer" errors. If it still cannot connect it prints what to check.

WHAT IT EXTRACTS
----------------
Per worksheet
    <Book>__<Sheet>.csv          the data
    <Book>__<Sheet>.meta.json    per column: short name, long name, units,
                                 comments, plotting designation (X/Y/Z/yErr...),
                                 column FORMULA (Fx), and any user-defined
                                 parameter label rows; plus sheet and book names,
                                 long names, comments and Project Explorer path
Fit / analysis reports
    reports/<Book>__<Sheet>__<Table>.csv
                                 fitted parameters, statistics, ANOVA and
                                 summary tables pulled with report_table()
Matrices
    matrices/<Book>__<Sheet>__m<N>.csv
Graphs
    graphs/<Graph>.png           (optionally .pdf as well)
    graphs/<Graph>.info.json     layers, axis titles, ranges, scale types, and
                                 for every curve its lt_range() source
                                 book/sheet/columns
    graphs/curves/<Graph>__L<n>__P<n>.csv    the plotted XY(Z) arrays
Whole run
    MANIFEST.csv / MANIFEST.json     one row per extracted object
    EXTRACTION_LOG.txt               everything, including every fallback
    <Project>/_project_summary.json  pages, PE folders, counts

SAFETY
------
* Nothing is ever written next to the source projects — only into the save
  folder you choose.
* Projects open with readonly=True where the build supports it, and the script
  never saves. It does *replace* the project currently open in Origin, so save
  your work first; the GUI makes you confirm.
* Every step is individually wrapped. A bad sheet or graph is logged and
  skipped, never fatal.

RELIABLE vs BEST-EFFORT
-----------------------
Documented API, used as documented:
    op.open · op.attach · op.project.pages · WSheet.to_df / to_list /
    get_label(s) / lt_range / report_table · WBook iteration ·
    GLayer.plot_list · Plot.lt_range · GPage.save_fig · op.pe.search
Best-effort, each with a fallback that logs when it fires:
    - column formula: colobj.GetStrProp('formula') (Origin 9.85+), else the
      LabTalk col(n)[O]$ form. NOTE get_label(col,'F') does NOT return a
      formula — only L/C/U/G are real label rows — so anything relying on that
      would silently report every formula as empty.
    - curve arrays off a DataPlot: PyOrigin getter names vary by build; falls
      back to recording lt_range() so the curve can be traced to the exported
      worksheet CSV.
    - save_fig keyword form -> positional -> LabTalk expGraph.
    - matrices: to_np2d -> to_df -> skipped.
    - report tables are found by probing known table names; a report using an
      unusual table name will be missed. Names probed are in REPORT_TABLES.
Read EXTRACTION_LOG.txt before trusting a silent success.

KNOWN NON-COVERAGE (stated, not hidden)
---------------------------------------
* The analysis *operation* behind a fit (its recalculate mode, input ranges and
  the live tree) is not decoded — only the report tables it produced.
* Graph templates, annotations, drawn objects and colour/style settings are not
  exported; the PNG is the record of appearance.
* Notes windows, Layout pages and embedded images are not exported.
* Sheet-level import metadata trees (the "user tree" from imported files) are
  not exported.

Reference style borrowed from prathameshnium/Python-for-OriginPro
https://github.com/prathameshnium/Python-for-OriginPro                MIT.
"""

import csv
import json
import os
import re
import sys
import traceback
from datetime import datetime

# --------------------------------------------------------------------------
# defaults — only used the first time; after that the GUI remembers your choices
# --------------------------------------------------------------------------
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".origin_extract_gui.json")
DEFAULT_SEARCH_ROOT = os.path.expanduser("~")
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Origin_Export")

PROJECT_EXTS = (".opju", ".opj")
PNG_WIDTH = 1600          # px, when save_fig accepts the keyword form
PNG_DPI = 300

# Report tables probed on sheets that look like analysis output. Origin returns
# nothing for a name a sheet does not have, so over-probing is harmless.
REPORT_TABLES = [
    "Parameters", "Fit Parameters", "Statistics", "Fit Statistics",
    "FitStatistics", "Summary", "Fit Summary", "ANOVA", "Coefficients",
    "Regression Statistics", "Descriptive Statistics", "Peak Properties",
    "Peak Analysis", "Integration Results", "Notes", "Input Data",
]
# Sheets whose name suggests analysis output; probed unless you tick "probe all"
REPORT_HINT = re.compile(r"fit|report|result|stat|anova|nlfit|peak|analys|summar",
                         re.I)

# --------------------------------------------------------------------------
# originpro
# --------------------------------------------------------------------------
try:
    import originpro as op
except ImportError:
    print("FATAL: originpro is not importable.\n"
          "  Inside Origin: it ships with Origin 2021+ (Connectivity > Python).\n"
          "  Outside Origin: pip install originpro")
    raise

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

RUNNING_EXTERNAL = bool(getattr(op, "oext", False))

# How we got hold of Origin: 'embedded', 'attached' (an existing GUI instance)
# or 'launched' (we started one). Decides how we let go of it at the end.
CONNECTION = {"mode": "embedded" if not RUNNING_EXTERNAL else None, "version": None}


def _origin_shutdown_exception_hook(exctype, value, tb):
    """Release an external Origin on a crash — but never mask the crash.

    op.exit() on a half-dead COM pointer raises its own exception, which is how
    the real error got buried the first time this ran externally.
    """
    try:
        if CONNECTION["mode"] == "launched":
            op.exit()
        elif CONNECTION["mode"] == "attached":
            op.detach()
    except Exception:                       # noqa: BLE001 - never mask the real error
        pass
    sys.__excepthook__(exctype, value, tb)


if RUNNING_EXTERNAL:
    sys.excepthook = _origin_shutdown_exception_hook


CONNECT_HELP = """\
Could not talk to Origin over COM.

The reliable way is to run this INSIDE Origin, which skips COM entirely:
    1. open Origin
    2. Connectivity > Python Console  (or open this file in Code Builder, Run)
    3. exec(open(r'<path to this file>').read())
Origin ships its own Python with originpro already installed.

Staying in external Python? The usual causes:
  * Origin is not running. Start it first — this script attaches to a running
    instance before it tries to launch its own.
  * Bitness mismatch: the OriginExt wheel is win_amd64 and needs 64-bit Origin.
  * COM server never registered. Launch Origin once as administrator, or use
    its repair / "register as COM server" option.
  * An orphaned Origin.exe from a crashed run. Kill it in Task Manager.
"""


def connect_origin():
    """Get a usable Origin. Returns (ok, message)."""
    if not RUNNING_EXTERNAL:
        try:
            CONNECTION["version"] = op.lt_float("@V")
        except Exception:                   # noqa: BLE001
            pass
        return True, "embedded in Origin (no COM)"

    try:                                    # 1) attach to a running Origin
        op.attach()
        v = op.lt_float("@V")               # first real call; fails loudly if dead
        CONNECTION.update(mode="attached", version=v)
        return True, "attached to the running Origin instance (version %.2f)" % v
    except Exception as exc:                # noqa: BLE001
        first = "%s: %s" % (type(exc).__name__, exc)

    try:                                    # 2) let originpro launch its own
        v = op.lt_float("@V")               # lazy: any call constructs the app
        CONNECTION.update(mode="launched", version=v)
        try:
            op.set_show(True)               # cosmetic only, never fatal
        except Exception:                   # noqa: BLE001
            pass
        return True, "launched a new Origin instance (version %.2f)" % v
    except Exception as exc:                # noqa: BLE001
        return False, ("attach failed (%s)\nlaunch failed (%s: %s)\n\n%s"
                       % (first, type(exc).__name__, exc, CONNECT_HELP))


def release_origin():
    """Let go of Origin without killing a session you were working in."""
    try:
        if CONNECTION["mode"] == "launched":
            op.exit()
        elif CONNECTION["mode"] == "attached":
            op.detach()
    except Exception as exc:                # noqa: BLE001
        LOG.warn("releasing Origin: %s: %s" % (type(exc).__name__, exc))


# --------------------------------------------------------------------------
# logging / small helpers
# --------------------------------------------------------------------------
class Log:
    """Console + file. Everything the run did, including every failure."""

    def __init__(self):
        self.lines = []
        self.path = None
        self.n_warn = 0
        self.n_fail = 0

    def open(self, outdir):
        self.path = os.path.join(outdir, "EXTRACTION_LOG.txt")

    def _w(self, tag, msg):
        line = "%-5s %s" % (tag, msg)
        self.lines.append(line)
        print(line)
        if self.path:                       # append as we go, so even a hard
            try:                            # crash leaves a usable log
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError:
                pass

    def info(self, msg):
        self._w("", msg)

    def warn(self, msg):
        self.n_warn += 1
        self._w("WARN", msg)

    def fail(self, msg, exc=None):
        self.n_fail += 1
        if exc is not None:
            msg = "%s  ::  %s: %s" % (msg, type(exc).__name__, exc)
        self._w("FAIL", msg)

    def trace(self):
        txt = traceback.format_exc()
        self.lines.append(txt)
        if self.path:
            try:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(txt + "\n")
            except OSError:
                pass


LOG = Log()
MANIFEST_ROOT = [""]        # set in run(); used for relative paths in the manifest

_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(s, fallback="unnamed"):
    """Filesystem-safe and short enough for Windows' 260-char path limit."""
    s = _BAD.sub("_", str(s)).strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    return (s[:80] or fallback)


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p


def try_call(desc, fn, *args, **kwargs):
    """Run fn; log and swallow anything it throws. Returns (ok, value)."""
    try:
        return True, fn(*args, **kwargs)
    except Exception as exc:                # noqa: BLE001 - deliberate catch-all
        LOG.fail(desc, exc)
        LOG.trace()
        return False, None


def quiet(fn, *args, **kwargs):
    """Best-effort value or None, no logging. For optional metadata."""
    try:
        return fn(*args, **kwargs)
    except Exception:                       # noqa: BLE001
        return None


def add_manifest(manifest, **row):
    f = row.get("file", "")
    if f:
        row["file"] = os.path.relpath(f, MANIFEST_ROOT[0])
    manifest.append(row)


# --------------------------------------------------------------------------
# worksheet metadata
# --------------------------------------------------------------------------
# Only these are genuine label rows in originpro's _getlabel: L=long name,
# C=comments, U=units, G=short name. 'F' is NOT one of them.
LABEL_ROWS = [("L", "long_name"), ("U", "units"), ("C", "comments"),
              ("G", "short_name")]
N_USER_PARAMS = 8           # user-defined label rows captured, if non-empty


def column_formula(wks, i):
    """Column formula (Fx). Two documented routes, mirroring set_formula()."""
    colobj = quiet(wks._find_col, i)                       # noqa: SLF001
    if colobj is not None:
        v = quiet(colobj.GetStrProp, "formula")            # Origin 9.85+
        if v:
            return str(v)
    # LabTalk route, in the sheet's own context (same form set_formula uses)
    try:
        wks.obj.LT_execute('string __PYFRM$=col(%d)[O]$;' % (i + 1))
        v = op.get_lt_str("__PYFRM$")
        wks.obj.LT_execute("del -vs __PYFRM$")
        return str(v or "")
    except Exception:                                       # noqa: BLE001
        return ""


def sheet_column_meta(wks, ncols):
    meta = [{"index": i} for i in range(ncols)]

    for code, key in LABEL_ROWS:
        vals = quiet(wks.get_labels, code)                  # documented: a list
        if not isinstance(vals, (list, tuple)):
            vals = [quiet(wks.get_label, i, code) for i in range(ncols)]
        for i in range(ncols):
            v = vals[i] if i < len(vals) else ""
            meta[i][key] = "" if v is None else str(v)

    # plotting designation, one letter per column, from the sheet property
    desig = str(quiet(wks.get_str, "desig") or "")
    for i in range(ncols):
        meta[i]["designation"] = desig[i] if i < len(desig) else ""

    # column formula (Fx)
    for i in range(ncols):
        meta[i]["formula"] = column_formula(wks, i)

    # user-defined parameter label rows (integer index => GetUserDefLabel)
    for i in range(ncols):
        ups = {}
        for k in range(N_USER_PARAMS):
            v = quiet(wks.get_label, i, k)
            if v:
                ups["user_param_%d" % (k + 1)] = str(v)
        if ups:
            meta[i]["user_params"] = ups

    return meta


def sheet_book_info(wks, wb):
    return {
        "sheet_name": str(quiet(getattr, wks, "name") or ""),
        "sheet_long_name": str(quiet(getattr, wks, "lname") or ""),
        "sheet_comments": str(quiet(wks.get_str, "comment") or
                              quiet(wks.get_str, "comments") or ""),
        "sheet_lt_range": str(quiet(wks.lt_range) or ""),
        "book_name": str(quiet(getattr, wb, "name") or ""),
        "book_long_name": str(quiet(getattr, wb, "lname") or ""),
        "book_comments": str(quiet(wb.get_str, "label") or ""),
    }


# --------------------------------------------------------------------------
# worksheet + report extraction
# --------------------------------------------------------------------------
def write_csv_from_df(df, path):
    df.to_csv(path, index=False, encoding="utf-8")
    return int(df.shape[0]), int(df.shape[1])


def write_csv_column_wise(wks, ncols, path, meta):
    """Fallback when to_df() fails — mixed text sheets, report sheets."""
    cols = []
    for i in range(ncols):
        try:
            cols.append(list(wks.to_list(i)))
        except Exception:                   # noqa: BLE001
            cols.append([])
    nrows = max((len(c) for c in cols), default=0)
    header = [(meta[i].get("long_name") or meta[i].get("short_name")
               or "Col%d" % (i + 1)) for i in range(ncols)]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in range(nrows):
            w.writerow([cols[i][r] if r < len(cols[i]) else "" for i in range(ncols)])
    return nrows, ncols


def dump_report_tables(wks, book_name, sheet_name, rdir, pe_path, manifest):
    """Fitted parameters / statistics / ANOVA etc. via report_table()."""
    if pd is None:
        return 0
    found = 0
    for tname in REPORT_TABLES:
        df = quiet(wks.report_table, tname)
        if df is None or getattr(df, "empty", True):
            continue
        ensure_dir(rdir)
        p = os.path.join(rdir, "%s__%s__%s.csv" %
                         (safe_name(book_name), safe_name(sheet_name), safe_name(tname)))
        try:
            df.to_csv(p, index=False, encoding="utf-8")
        except OSError as exc:
            LOG.fail("write report table %s" % p, exc)
            continue
        add_manifest(manifest, kind="report_table", book=book_name, sheet=sheet_name,
                     long_name=tname, pe_path=pe_path, rows=int(df.shape[0]),
                     cols=int(df.shape[1]), file=p, note="report_table('%s')" % tname)
        LOG.info("    report [%s]%s -> %s (%d x %d)" %
                 (book_name, sheet_name, tname, df.shape[0], df.shape[1]))
        found += 1
    return found


def dump_worksheet(wks, wb, book_name, wdir, rdir, pe_path, manifest, probe_all):
    sheet_name = str(getattr(wks, "name", "Sheet"))
    base = "%s__%s" % (safe_name(book_name), safe_name(sheet_name))
    csv_path = os.path.join(wdir, base + ".csv")

    try:
        ncols = int(wks.cols)
        nrows_declared = int(wks.rows)
    except Exception as exc:                # noqa: BLE001
        LOG.fail("sheet shape [%s]%s" % (book_name, sheet_name), exc)
        return

    meta = sheet_column_meta(wks, ncols)

    nrows = method = None
    if pd is not None:
        df = None
        try:                                # not a hard failure: the column-wise
            df = wks.to_df()                # path below handles text/report sheets
        except Exception as exc:            # noqa: BLE001
            LOG.warn("to_df failed on [%s]%s (%s)" % (book_name, sheet_name, exc))
        if df is not None:
            ok, dims = try_call("write csv %s" % base, write_csv_from_df, df, csv_path)
            if ok:
                nrows, _ = dims
                method = "to_df"
    if method is None:
        LOG.warn("[%s]%s: falling back to column-wise export" % (book_name, sheet_name))
        ok, dims = try_call("column-wise csv %s" % base,
                            write_csv_column_wise, wks, ncols, csv_path, meta)
        if not ok:
            return
        nrows, _ = dims
        method = "to_list"

    payload = dict(sheet_book_info(wks, wb))
    payload.update({
        "project_explorer_path": pe_path,
        "rows_declared": nrows_declared, "rows_written": nrows, "cols": ncols,
        "export_method": method, "columns": meta,
    })
    try:
        with open(os.path.join(wdir, base + ".meta.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        LOG.fail("write meta %s" % base, exc)

    nform = sum(1 for m in meta if m.get("formula"))
    add_manifest(manifest, kind="worksheet", book=book_name, sheet=sheet_name,
                 long_name=payload.get("sheet_long_name", ""), pe_path=pe_path,
                 rows=nrows, cols=ncols, file=csv_path,
                 note="export=%s; formulas=%d" % (method, nform))
    LOG.info("    sheet  [%s]%s  %d x %d%s  -> %s.csv" %
             (book_name, sheet_name, nrows, ncols,
              ("  (%d formulas)" % nform) if nform else "", base))

    if probe_all or REPORT_HINT.search(sheet_name) or \
            REPORT_HINT.search(payload.get("sheet_long_name", "")):
        dump_report_tables(wks, book_name, sheet_name, rdir, pe_path, manifest)


# --------------------------------------------------------------------------
# matrices
# --------------------------------------------------------------------------
def dump_matrixsheet(ms, book_name, mdir, pe_path, manifest):
    sheet_name = str(getattr(ms, "name", "MSheet"))
    base = "%s__%s" % (safe_name(book_name), safe_name(sheet_name))

    arr = None
    for meth in ("to_np2d", "to_np3d"):
        f = getattr(ms, meth, None)
        if f is None:
            continue
        ok, arr = try_call("%s [%s]%s" % (meth, book_name, sheet_name), f)
        if ok and arr is not None:
            break
        arr = None

    if arr is None:
        if pd is not None and hasattr(ms, "to_df"):
            ok, df = try_call("matrix to_df [%s]%s" % (book_name, sheet_name), ms.to_df)
            if ok and df is not None:
                p = os.path.join(mdir, base + ".csv")
                df.to_csv(p, index=False, encoding="utf-8")
                add_manifest(manifest, kind="matrix", book=book_name, sheet=sheet_name,
                             long_name="", pe_path=pe_path, rows=int(df.shape[0]),
                             cols=int(df.shape[1]), file=p, note="export=to_df")
                LOG.info("    matrix [%s]%s -> %s.csv (to_df)" %
                         (book_name, sheet_name, base))
                return
        LOG.warn("matrix [%s]%s not exported" % (book_name, sheet_name))
        return

    if np is None:
        LOG.warn("matrix [%s]%s not exported (numpy missing)" % (book_name, sheet_name))
        return

    a = np.asarray(arr)
    planes = [a] if a.ndim == 2 else [a[..., k] for k in range(a.shape[-1])]
    for k, plane in enumerate(planes):
        p = os.path.join(mdir, "%s__m%d.csv" % (base, k + 1))
        ok, _ = try_call("savetxt %s" % p, np.savetxt, p, plane, delimiter=",")
        if not ok:
            continue
        add_manifest(manifest, kind="matrix", book=book_name, sheet=sheet_name,
                     long_name="matrix object %d" % (k + 1), pe_path=pe_path,
                     rows=int(plane.shape[0]), cols=int(plane.shape[1]), file=p,
                     note="export=numpy")
        LOG.info("    matrix [%s]%s obj%d  %dx%d" %
                 (book_name, sheet_name, k + 1, plane.shape[0], plane.shape[1]))


# --------------------------------------------------------------------------
# graphs
# --------------------------------------------------------------------------
def save_graph_image(gp, path, fmt="png"):
    """Export one graph page. Returns the method that worked, or None.

    The documented signature (originpro/graph.py) is
        save_fig(path='', type='auto', replace=True, width=0, ratio=0)
    — no dpi argument. type='auto' infers png/pdf from the extension, and the
    call returns the full path written, or '' on failure.
    """
    f = getattr(gp, "save_fig", None)
    if f is not None:
        try:
            ret = f(path, width=PNG_WIDTH)
            if (ret and os.path.exists(ret)) or os.path.exists(path):
                return "save_fig"
            LOG.warn("save_fig returned '%s' for %s; trying positional" % (ret, path))
        except Exception as exc:            # noqa: BLE001
            LOG.warn("save_fig(width=) failed (%s); trying positional" % exc)
        try:
            ret = f(path)
            if (ret and os.path.exists(ret)) or os.path.exists(path):
                return "save_fig(positional)"
        except Exception as exc:            # noqa: BLE001
            LOG.warn("save_fig positional failed (%s); trying LabTalk expgraph" % exc)
    try:                                    # LabTalk X-Function, page context
        folder = os.path.dirname(path)
        fname = os.path.splitext(os.path.basename(path))[0]
        gp.obj.LT_execute('expgraph -sw type:=%s filename:="%s" overwrite:=replace '
                          'path:="%s"' % (fmt, fname, folder))
        return "lt expgraph" if os.path.exists(path) else None
    except Exception as exc:                # noqa: BLE001
        LOG.fail("expgraph fallback for %s" % path, exc)
        return None


def layer_axis_info(gl):
    """Axis titles, ranges and scale types. All optional, all best-effort."""
    out = {}
    for ax in ("x", "y"):
        d = {}
        a = quiet(gl.axis, ax)
        if a is not None:
            t = quiet(getattr, a, "title")
            if t:
                d["title"] = str(t)
        for prop, key in ((ax + ".from", "from"), (ax + ".to", "to"),
                          (ax + ".inc", "increment")):
            v = quiet(gl.get_float, prop)
            if v is not None:
                d[key] = v
        s = quiet(getattr, gl, ax + "scale")
        if s is not None:
            d["scale"] = s                  # 0 linear, 2 log10, per Origin
        if d:
            out[ax] = d
    return out


_RANGE_RE = re.compile(r"\[(?P<book>[^\]]+)\](?P<sheet>[^!]+)!")


def plot_curve_arrays(plot):
    """Best-effort XY(Z) arrays for one data plot. Returns (dict, method)."""
    obj = getattr(plot, "obj", None)
    if obj is None:
        return None, None

    for meth in ("GetData", "GetXYData", "GetDataXY"):      # single call
        f = getattr(obj, meth, None)
        if f is None:
            continue
        try:
            got = f()
        except Exception:                   # noqa: BLE001
            continue
        if isinstance(got, (list, tuple)) and len(got) >= 2:
            keys = ["x", "y", "z"][:len(got)]
            return {k: list(v) for k, v in zip(keys, got)}, meth

    out = {}                                                # separate getters
    for key, names in (("x", ("GetXData", "xdata", "X")),
                       ("y", ("GetYData", "ydata", "Y")),
                       ("z", ("GetZData", "zdata", "Z"))):
        for n in names:
            v = getattr(obj, n, None)
            if v is None:
                continue
            try:
                out[key] = list(v() if callable(v) else v)
                break
            except Exception:               # noqa: BLE001
                continue
    return (out, "attribute getters") if "y" in out else (None, None)


def dump_graph(gp, gdir, cdir, pe_path, manifest, opts):
    gname = str(getattr(gp, "name", "Graph"))
    glname = str(getattr(gp, "lname", "") or "")
    base = safe_name(gname)

    for fmt in (["png"] + (["pdf"] if opts["pdf"] else [])):
        path = os.path.join(gdir, "%s.%s" % (base, fmt))
        method = save_graph_image(gp, path, fmt)
        if method and os.path.exists(path):
            add_manifest(manifest, kind="graph_" + fmt, book=gname, sheet="",
                         long_name=glname, pe_path=pe_path, rows="", cols="",
                         file=path, note=method)
            LOG.info("    graph  %s -> %s.%s (%s)" % (gname, base, fmt, method))
        else:
            LOG.fail("no %s produced for graph %s" % (fmt, gname))

    info = {"graph": gname, "long_name": glname,
            "project_explorer_path": pe_path, "layers": []}
    ok, layers = try_call("iterate layers of %s" % gname, lambda: list(gp))
    for li, gl in enumerate(layers or []):
        lay = {"layer_index": li, "axes": layer_axis_info(gl), "plots": []}
        ok, plots = try_call("plot_list on %s layer %d" % (gname, li), gl.plot_list)
        for pi, plot in enumerate(plots or []):
            rec = {"plot_index": pi}
            rng = quiet(plot.lt_range)
            if rng:
                rec["lt_range"] = rng
                m = _RANGE_RE.search(rng)
                if m:
                    rec["source_book"] = m.group("book")
                    rec["source_sheet"] = m.group("sheet")

            if opts["curves"]:
                data, meth = plot_curve_arrays(plot)
                if data and data.get("y"):
                    ensure_dir(cdir)
                    cpath = os.path.join(cdir, "%s__L%d__P%d.csv" % (base, li, pi))
                    keys = [k for k in ("x", "y", "z") if k in data]
                    n = max(len(data[k]) for k in keys)
                    try:
                        with open(cpath, "w", newline="", encoding="utf-8") as fh:
                            w = csv.writer(fh)
                            w.writerow(keys)
                            for r in range(n):
                                w.writerow([data[k][r] if r < len(data[k]) else ""
                                            for k in keys])
                        rec.update(curve_file=os.path.basename(cpath),
                                   curve_method=meth, n_points=n)
                        add_manifest(manifest, kind="graph_curve", book=gname,
                                     sheet="layer%d/plot%d" % (li, pi),
                                     long_name=rec.get("lt_range", ""), pe_path=pe_path,
                                     rows=n, cols=len(keys), file=cpath,
                                     note="curve via %s" % meth)
                    except OSError as exc:
                        LOG.fail("write curve %s" % cpath, exc)
                else:
                    rec["curve_file"] = None
                    rec["curve_note"] = ("arrays not reachable from the DataPlot on "
                                         "this Origin build; use lt_range and the "
                                         "exported worksheet CSV instead")
            lay["plots"].append(rec)
        info["layers"].append(lay)

    try:
        with open(os.path.join(gdir, base + ".info.json"), "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        LOG.fail("write %s.info.json" % base, exc)


# --------------------------------------------------------------------------
# project driver
# --------------------------------------------------------------------------
def pe_path_of(page):
    """Project Explorer folder holding this page. Best effort."""
    try:
        return op.pe.search(page.name, 0)
    except Exception:                       # noqa: BLE001
        return ""


def iter_pages(kind):
    """All pages of one type. op.pages() is the documented generator."""
    for desc, fn in (("op.pages", lambda: op.pages(kind)),
                     ("op.project.pages", lambda: op.project.pages(kind))):
        try:
            return list(fn())
        except Exception as exc:            # noqa: BLE001
            last = (desc, exc)
    LOG.fail("%s('%s')" % (last[0], kind), last[1])
    return []


def extract_current_project(label, outroot, opts, manifest):
    """Dump whatever project is open in Origin right now."""
    pdir = ensure_dir(os.path.join(outroot, safe_name(label)))
    wdir = ensure_dir(os.path.join(pdir, "worksheets"))
    rdir = os.path.join(pdir, "reports")            # created on first hit
    summary = {"project": label,
               "extracted": datetime.now().isoformat(timespec="seconds"),
               "origin_version": CONNECTION.get("version"),
               "workbooks": [], "matrixbooks": [], "graphs": []}

    for wb in iter_pages("w"):
        bname = str(getattr(wb, "name", "Book"))
        pep = pe_path_of(wb)
        ok, sheets = try_call("iterate sheets of [%s]" % bname, lambda w=wb: list(w))
        names = []
        for wks in (sheets or []):
            dump_worksheet(wks, wb, bname, wdir, rdir, pep, manifest,
                           opts["probe_all_reports"])
            names.append(str(getattr(wks, "name", "")))
        summary["workbooks"].append({"name": bname,
                                     "long_name": str(getattr(wb, "lname", "")),
                                     "pe_path": pep, "sheets": names})

    if opts["matrices"]:
        mdir = ensure_dir(os.path.join(pdir, "matrices"))
        for mb in iter_pages("m"):
            bname = str(getattr(mb, "name", "MBook"))
            pep = pe_path_of(mb)
            ok, msheets = try_call("iterate matrix sheets of [%s]" % bname,
                                   lambda b=mb: list(b))
            for ms in (msheets or []):
                dump_matrixsheet(ms, bname, mdir, pep, manifest)
            summary["matrixbooks"].append({"name": bname, "pe_path": pep,
                                           "sheets": len(msheets or [])})

    if opts["graphs"]:
        gdir = ensure_dir(os.path.join(pdir, "graphs"))
        cdir = os.path.join(gdir, "curves")
        for gp in iter_pages("g"):
            dump_graph(gp, gdir, cdir, pe_path_of(gp), manifest, opts)
            summary["graphs"].append(str(getattr(gp, "name", "")))

    try:
        with open(os.path.join(pdir, "_project_summary.json"), "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        LOG.fail("write project summary for %s" % label, exc)

    LOG.info("  done: %d workbooks, %d matrix books, %d graphs" %
             (len(summary["workbooks"]), len(summary["matrixbooks"]),
              len(summary["graphs"])))


def open_project_readonly(path):
    """op.open with readonly if the build supports it, else plain open."""
    try:
        op.open(file=path, readonly=True)
        return "readonly"
    except TypeError:
        pass
    except Exception as exc:                # noqa: BLE001
        LOG.warn("readonly open failed for %s (%s); retrying plain open" %
                 (os.path.basename(path), exc))
    op.open(path)
    return "read-write (readonly unsupported on this build)"


def current_project_label():
    """Name of the open project.

    NOT op.project.path — originpro.project imports utils.path, so that
    attribute is a *function*, and str() of it becomes a junk folder name.
    %G is the LabTalk project name; %X is its folder.
    """
    for getter in (lambda: op.get_lt_str("%G"),
                   lambda: op.get_lt_str("%X")):
        raw = quiet(getter)
        if raw and not callable(raw):
            raw = str(raw).replace("\\", "/").rstrip("/")
            lbl = os.path.splitext(raw.split("/")[-1])[0]
            if lbl:
                return lbl
    return "CURRENT_PROJECT"


def run(files, outroot, opts):
    ensure_dir(outroot)
    MANIFEST_ROOT[0] = outroot
    LOG.open(outroot)
    LOG.info("=" * 78)
    LOG.info("Origin extraction  %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    LOG.info("originpro %s | %s | pandas %s | numpy %s" %
             (getattr(op, "__version__", "?"),
              "external" if RUNNING_EXTERNAL else "embedded in Origin",
              getattr(pd, "__version__", "absent"),
              getattr(np, "__version__", "absent")))
    LOG.info("connection: %s" % CONNECTION)
    LOG.info("save location: %s" % outroot)
    LOG.info("options: %s" % opts)
    LOG.info("=" * 78)

    manifest = []
    if opts["use_open_project"]:
        label = current_project_label()
        LOG.info("[current project] %s" % label)
        extract_current_project(label, outroot, opts, manifest)
    else:
        for i, f in enumerate(files, 1):
            LOG.info("")
            LOG.info("[%d/%d] %s" % (i, len(files), f))
            if not os.path.exists(f):
                LOG.fail("missing file %s" % f)
                continue
            ok, mode = try_call("open %s" % f, open_project_readonly, f)
            if not ok:
                continue
            LOG.info("  opened %s" % mode)
            parent = os.path.basename(os.path.dirname(f))
            stem = os.path.splitext(os.path.basename(f))[0]
            extract_current_project("%s__%s" % (safe_name(parent), safe_name(stem)),
                                    outroot, opts, manifest)

    cols = ["kind", "book", "sheet", "long_name", "pe_path", "rows", "cols",
            "file", "note"]
    try:
        with open(os.path.join(outroot, "MANIFEST.csv"), "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in manifest:
                w.writerow({c: r.get(c, "") for c in cols})
        with open(os.path.join(outroot, "MANIFEST.json"), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        LOG.fail("write manifest", exc)

    kinds = {}
    for r in manifest:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    LOG.info("")
    LOG.info("=" * 78)
    LOG.info("FINISHED: %d objects — %s" %
             (len(manifest), ", ".join("%s %s" % (v, k) for k, v in sorted(kinds.items()))
              or "nothing"))
    LOG.info("%d warnings, %d failures. Saved to %s" % (LOG.n_warn, LOG.n_fail, outroot))
    LOG.info("Read EXTRACTION_LOG.txt before trusting a silent success.")
    LOG.info("=" * 78)
    return manifest


# --------------------------------------------------------------------------
# settings + file discovery
# --------------------------------------------------------------------------
def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                       # noqa: BLE001
        return {}


def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=2)
    except OSError:
        pass


def find_projects(root):
    out = []
    for dirpath, _dirs, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(PROJECT_EXTS):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------
def gui_pick(conn_msg, conn_ok):
    """Returns (files, outdir, opts) or None if cancelled."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    cfg = load_settings()
    state = {"result": None, "files": []}

    root = tk.Tk()
    root.title("Origin project extractor")
    root.geometry("1000x740")
    pad = {"padx": 8, "pady": 4}

    ttk.Label(root, text=("Origin: " + conn_msg) if conn_ok
                          else "Origin: NOT CONNECTED — see console",
              foreground=("#0a0" if conn_ok else "#c00")).pack(anchor="w", padx=10, pady=(8, 0))

    # 1 · find --------------------------------------------------------------
    frm = ttk.LabelFrame(root, text="1 · Find projects")
    frm.pack(fill="x", **pad)
    var_root = tk.StringVar(value=cfg.get("search_root", DEFAULT_SEARCH_ROOT))
    ttk.Entry(frm, textvariable=var_root).pack(side="left", fill="x", expand=True,
                                               padx=6, pady=6)

    def do_scan():
        lb.delete(0, tk.END)
        state["files"] = find_projects(var_root.get())
        for f in state["files"]:
            try:
                lb.insert(tk.END, os.path.relpath(f, var_root.get()))
            except ValueError:
                lb.insert(tk.END, f)
        lbl_count.config(text="%d project files found — select any number "
                              "(Ctrl / Shift click)" % len(state["files"]))

    def browse_root():
        d = filedialog.askdirectory(initialdir=var_root.get() or os.getcwd(),
                                    title="Folder to scan for .opju / .opj")
        if d:
            var_root.set(d)
            do_scan()

    def add_files():
        fs = filedialog.askopenfilenames(
            title="Add Origin project files",
            filetypes=[("Origin projects", "*.opju *.opj"), ("All files", "*.*")])
        for f in fs:
            if f not in state["files"]:
                state["files"].append(f)
                lb.insert(tk.END, f)
        lbl_count.config(text="%d project files listed" % len(state["files"]))

    ttk.Button(frm, text="Browse…", command=browse_root).pack(side="left", padx=4)
    ttk.Button(frm, text="Scan", command=do_scan).pack(side="left", padx=4)
    ttk.Button(frm, text="Add files…", command=add_files).pack(side="left", padx=4)

    # 2 · choose ------------------------------------------------------------
    frm2 = ttk.LabelFrame(root, text="2 · Choose which to extract")
    frm2.pack(fill="both", expand=True, **pad)
    lbl_count = ttk.Label(frm2, text="")
    lbl_count.pack(anchor="w", padx=6)
    inner = ttk.Frame(frm2)
    inner.pack(fill="both", expand=True, padx=6, pady=4)
    sb = ttk.Scrollbar(inner, orient="vertical")
    lb = tk.Listbox(inner, selectmode="extended", yscrollcommand=sb.set, activestyle="none")
    sb.config(command=lb.yview)
    sb.pack(side="right", fill="y")
    lb.pack(side="left", fill="both", expand=True)

    btns = ttk.Frame(frm2)
    btns.pack(fill="x", padx=6, pady=2)
    ttk.Button(btns, text="Select all",
               command=lambda: lb.selection_set(0, tk.END)).pack(side="left")
    ttk.Button(btns, text="Select none",
               command=lambda: lb.selection_clear(0, tk.END)).pack(side="left", padx=4)
    var_filter = tk.StringVar()

    def select_match():
        q = var_filter.get().strip().lower()
        if not q:
            return
        lb.selection_clear(0, tk.END)
        for i in range(lb.size()):
            if q in lb.get(i).lower():
                lb.selection_set(i)

    ttk.Entry(btns, textvariable=var_filter, width=24).pack(side="left", padx=(16, 4))
    ttk.Button(btns, text="Select matching", command=select_match).pack(side="left")

    # 3 · save location + options ------------------------------------------
    frm3 = ttk.LabelFrame(root, text="3 · Save location and options")
    frm3.pack(fill="x", **pad)

    r1 = ttk.Frame(frm3)
    r1.pack(fill="x", padx=6, pady=4)
    ttk.Label(r1, text="Save everything to:").pack(side="left")
    var_out = tk.StringVar(value=cfg.get("output_dir", DEFAULT_OUTPUT_DIR))
    ttk.Entry(r1, textvariable=var_out).pack(side="left", fill="x", expand=True, padx=6)

    def browse_out():
        d = filedialog.askdirectory(initialdir=var_out.get() or os.getcwd(),
                                    title="Where to save the extracted data")
        if d:
            var_out.set(d)

    ttk.Button(r1, text="Choose…", command=browse_out).pack(side="left")

    o = cfg.get("options", {})
    var_graphs = tk.BooleanVar(value=o.get("graphs", True))
    var_curves = tk.BooleanVar(value=o.get("curves", True))
    var_pdf = tk.BooleanVar(value=o.get("pdf", False))
    var_matrix = tk.BooleanVar(value=o.get("matrices", True))
    var_probe = tk.BooleanVar(value=o.get("probe_all_reports", False))
    var_current = tk.BooleanVar(value=False)

    r2 = ttk.Frame(frm3)
    r2.pack(fill="x", padx=6, pady=2)
    ttk.Checkbutton(r2, text="Graph images (PNG)", variable=var_graphs).pack(side="left")
    ttk.Checkbutton(r2, text="also PDF", variable=var_pdf).pack(side="left", padx=8)
    ttk.Checkbutton(r2, text="Curve data + source refs",
                    variable=var_curves).pack(side="left", padx=8)
    ttk.Checkbutton(r2, text="Matrices", variable=var_matrix).pack(side="left", padx=8)

    r3 = ttk.Frame(frm3)
    r3.pack(fill="x", padx=6, pady=2)
    ttk.Checkbutton(r3, text="Probe EVERY sheet for fit/report tables (slower; default "
                             "probes sheets whose name looks like analysis output)",
                    variable=var_probe).pack(side="left")

    r4 = ttk.Frame(frm3)
    r4.pack(fill="x", padx=6, pady=2)
    ttk.Checkbutton(r4, text="Ignore the list — just dump the project already open in Origin",
                    variable=var_current).pack(side="left")

    r5 = ttk.Frame(frm3)
    r5.pack(fill="x", padx=6, pady=4)
    var_ack = tk.BooleanVar(value=False)
    ttk.Checkbutton(r5, variable=var_ack,
                    text=("I have saved my current Origin project. Batch extraction opens each "
                          "file in turn and will close what is open now. (Nothing is written "
                          "to the source folders.)")).pack(side="left")

    # run -------------------------------------------------------------------
    def go():
        outdir = var_out.get().strip()
        if not outdir:
            messagebox.showerror("Save location", "Choose where to save the export.")
            return
        use_current = bool(var_current.get())
        sel = [state["files"][i] if i < len(state["files"]) else lb.get(i)
               for i in lb.curselection()]
        if not use_current and not sel:
            messagebox.showerror("Nothing selected",
                                 "Select at least one project, or tick "
                                 "'dump the project already open'.")
            return
        if not use_current and not var_ack.get():
            messagebox.showerror("Confirm", "Tick the confirmation box — batch mode closes "
                                            "the project you have open.")
            return
        opts = {"graphs": bool(var_graphs.get()),
                "curves": bool(var_curves.get()) and bool(var_graphs.get()),
                "pdf": bool(var_pdf.get()) and bool(var_graphs.get()),
                "matrices": bool(var_matrix.get()),
                "probe_all_reports": bool(var_probe.get()),
                "use_open_project": use_current}
        save_settings({"search_root": var_root.get(), "output_dir": outdir,
                       "options": {k: v for k, v in opts.items()
                                   if k != "use_open_project"}})
        state["result"] = (sel, outdir, opts)
        root.destroy()

    frm4 = ttk.Frame(root)
    frm4.pack(fill="x", **pad)
    ttk.Button(frm4, text="Run extraction", command=go).pack(side="right", padx=6)
    ttk.Button(frm4, text="Cancel", command=root.destroy).pack(side="right")
    ttk.Label(frm4, text="Progress prints to the console and to EXTRACTION_LOG.txt "
                         "in the save folder.").pack(side="left", padx=6)

    do_scan()
    root.mainloop()          # ends before extraction starts, so Tk's event loop
    return state["result"]   # never runs while Origin is being driven


def console_pick():
    """Fallback if tkinter is missing from Origin's embedded Python."""
    cfg = load_settings()
    print("\n(tkinter unavailable — console mode)\n")
    root = input("Folder to scan [%s]: " % cfg.get("search_root", DEFAULT_SEARCH_ROOT)
                 ).strip() or cfg.get("search_root", DEFAULT_SEARCH_ROOT)
    files = find_projects(root)
    for i, f in enumerate(files):
        print("  %3d  %s" % (i, os.path.relpath(f, root)))
    print("\nEnter indices (0,3,5 or 0-4 or 'all'), or 'open' for the project "
          "already open in Origin.")
    raw = input("Selection: ").strip().lower()
    use_current = raw == "open"
    sel = []
    if not use_current:
        if raw == "all":
            sel = files
        else:
            for part in raw.replace(" ", "").split(","):
                if "-" in part:
                    a, b = part.split("-")
                    sel += files[int(a):int(b) + 1]
                elif part:
                    sel.append(files[int(part)])
    outdir = input("Save to [%s]: " % cfg.get("output_dir", DEFAULT_OUTPUT_DIR)
                   ).strip() or cfg.get("output_dir", DEFAULT_OUTPUT_DIR)
    save_settings({"search_root": root, "output_dir": outdir})
    return sel, outdir, {"graphs": True, "curves": True, "pdf": False,
                         "matrices": True, "probe_all_reports": False,
                         "use_open_project": use_current}


# --------------------------------------------------------------------------
def main():
    ok, msg = connect_origin()
    print("Origin connection: %s" % msg)
    if not ok:
        return

    try:
        picked = gui_pick(msg, ok)
    except Exception as exc:                # noqa: BLE001
        print("GUI unavailable (%s: %s) — falling back to console."
              % (type(exc).__name__, exc))
        picked = console_pick()

    if not picked:
        print("Cancelled — nothing extracted, nothing changed.")
    else:
        files, outdir, opts = picked
        run(files, outdir, opts)

    release_origin()


main()
