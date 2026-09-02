"""3D asset geometry check — Streamlit Community Cloud.

`PATH_B §2.3` surface 2 (drop-a-file) and surface 1 (the leaderboard), one page.

⭐ THE ENGINE IS INSTALLED, NEVER VENDORED. `requirements.txt` pulls the built
   3dqa 1.1.0 wheel from a GitHub Release. ⛔ No engine source belongs in this
   repo — `LICENSE` names `geometry_linter.py`, `qa_profiles.py` and
   `usd_loader.py`, and putting them in a public repo gives away the
   source-available moat. Running the wheel here is USE, not redistribution:
   §1 grants run-and-use for any purpose, and visitors never receive the wheel.

⚠️ It installs from a Release rather than PyPI because the PyPI account went
   into recovery on 2026-08-22 while 1.1.0 sat gated-green. PyPI still serves
   **1.0.0**, which is pre-FINDING-7 and measures two rates this project has
   retracted. ⛔ Never fall back to it.

DESIGN RULES, all of them load-bearing:

  1. `PATH_B §2.1` — never render a bare percentage. Every rate is "N of M" in
     the same breath, so a copy-pasted fragment cannot become an overstatement.
  2. `CLAUDE.md` — unknown is never clean. An asset the engine cannot measure
     renders as UNVERIFIED, never as a pass.
  3. FINDING-10 is open. `UV_MISSING` can be a swallowed exception rather than a
     defect, so every UV finding carries the caveat inline.
  4. The limitations are on the page, not in a footer. Every stranger who has
     ever engaged with this project did so after a limitation was stated first.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
import threading
import traceback
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st

# ⛔ No sys.path insert. The engine resolves from site-packages, which is the
# only place it should ever come from here. A cwd/dir insert is how
# verify_release.py and scripts/relcheck.sh each shipped a bug that validated
# the source tree instead of the artifact.
try:
    import geometry_linter as gl
except ImportError:  # pragma: no cover - deployment guard
    gl = None

HERE = Path(__file__).resolve().parent
CENSUS_CSV = HERE / "aggregate_by_generator_relint_2026-08-17.csv"
ACCEPTED = [".glb", ".gltf", ".obj", ".ply", ".stl", ".usd", ".usda", ".usdc", ".usdz"]
MAX_MB = 100

# The only contact route on this page, and the only way this surface can move
# `F` in PATHB_LEDGER. `F` counts a file a stranger sent TO A PERSON, and a
# run of the app is not that (see _emit_run). Email rather than a GitHub
# issue on purpose: a person with a broken proprietary asset will not attach
# it to a public issue tracker, and the reply from a human is the thing being
# measured. One constant so the route is one line to change.
# ⛔ It is shown ONLY on READ_FAILURE and UNVERIFIED. Those are the two cases
#    where we actually want the file, and a page whose credibility rests on
#    not selling does not put an ask under a clean result.
CONTACT = "alzastrategy@gmail.com"

# ⛔ THE HEADLINE VERDICT COMES FROM `cert["verdict"]`. DO NOT RE-DERIVE IT.
#
# The engine already emits PASS / FAIL / UNVERIFIED and it is the source of
# truth. The first version of the Gradio page rebuilt the verdict from the
# findings list and got it wrong on the single case that matters most: a
# Gaussian-splat `.ply` renders `verdict: "UNVERIFIED"` in the certificate, and
# the page showed a stranger "FAIL — 1 of 1 checks found a defect". 303 of the
# 2,307 corpus assets are point clouds, so that was the most likely single
# thing anyone would drop here.
#
# Telling someone their asset FAILED when the truth is we could not measure it
# is the exact inversion of CLAUDE.md's first rule, in the shop window.
#
# Findings still drive the BODY. They never drive the headline.

# Checks that mean "we declined to measure", not "we found a defect".
# Matched on `check`, not on `code` — an earlier version guessed the code as
# LOADABLE_GEOMETRY when the engine emits UNMEASURABLE_GEOMETRY.
UNMEASURED_CHECKS = {"loadable_geometry"}
UNMEASURED_CODES = {
    "UNMEASURABLE_GEOMETRY", "NORMALS_NO_FACES",
    "WATERTIGHT_NO_EDGES", "NORMALS_ORIENTATION_UNVERIFIABLE",
}


def _is_unmeasured(f: dict) -> bool:
    return (f.get("check") in UNMEASURED_CHECKS
            or f.get("code") in UNMEASURED_CODES)


# ⛔ DISCLOSURE HOLD — CONCIERGE_LOG §14.7.
# What was promised on 2026-08-04 was to hold off on further PUBLIC writing
# about the Meshy-5/6 comparison "until you've had a chance to look". That
# promise is OPEN-ENDED. The ~2026-08-25 date in some notes is our own
# reminder, not their deadline, and publishing on it would break a promise
# rather than honour a lapsed one.
#
# These rows are withheld from the public leaderboard and the fact of the
# withholding is stated on the page. Removing a row silently would be its own
# dishonesty.
#
# ⛔ Do not delete this list to "complete" the table. It is released when they
#    say so, and by nothing else.
EMBARGOED = {"Meshy-5", "Meshy-6"}

FINDING_10 = (
    "⚠️ **FINDING-10 is open and this code is affected.** `UV_MISSING` is read "
    "from the *concatenated* mesh. When `trimesh` fails to pack a texture atlas "
    "it swallows the exception and returns a mesh with no UVs, which this "
    "engine then reports as a missing-UV defect. On a multi-material asset "
    "this finding may be a false positive. The limitations tab has a "
    "two-line check that settles it."
)


# --------------------------------------------------------------- the census tab

def load_census():
    """Rows from the 2026-08-17 re-lint. Returns (headers, rows, overall)."""
    if not CENSUS_CSV.is_file():
        return [], [], None
    rows = list(csv.DictReader(CENSUS_CSV.open(encoding="utf-8")))
    overall = next((r for r in rows if r["generator"] == "OVERALL"), None)
    return (rows[0].keys() if rows else []), rows, overall


def _frac(cell: str) -> float:
    try:
        a, b = cell.split(" of ")
        return int(a) / max(int(b.split()[0]), 1)
    except Exception:
        return -1.0


def census_table():
    _, rows, _ = load_census()
    out = []
    for r in rows:
        if r["generator"] == "OVERALL" or r["generator"] in EMBARGOED:
            continue
        n = int(r["n_assets"])
        unmeasurable = int(r["n_lint_errors"])
        measured = n - unmeasurable
        if measured == 0:
            # Whole generator is point clouds. Not a zero score — no score.
            out.append([r["generator"], f"{n}", f"0 of {n} measurable",
                        "not measured", "not measured"])
            continue
        passed = round(float(r["pass_rate"] or 0) * measured)
        nm = round(float(r["defect_non_manifold"] or 0) * measured)
        out.append([
            r["generator"], f"{n}",
            f"{measured} of {n} measurable",
            f"{passed} of {measured} pass",
            f"{nm} of {measured} carry ≥1 non-manifold edge",
        ])
    out.sort(key=lambda row: -_frac(row[3]))
    return out


def census_summary() -> str:
    _, _, o = load_census()
    if not o:
        return "Census file not bundled with this app."
    n = int(o["n_assets"])
    measured = int(o["n_ok"])
    unmeasurable = int(o["n_lint_errors"])
    passed = round(float(o["pass_rate"]) * measured)
    nw = round(float(o["defect_not_watertight"]) * measured)
    nm = round(float(o["defect_non_manifold"]) * measured)
    fails = int(o["n_fail"])
    healed = round(float(o["heal_full"]) * fails)
    regr = int(o["n_introduced_regressions"])
    return f"""
### The census: {n:,} assets, 23 generators, one instrument

Re-linted 2026-08-17. Every figure below is a count over a stated denominator,
on purpose: a fragment of this text cannot be quoted into something stronger
than it says.

- **{measured:,} of {n:,}** assets were measurable. The other **{unmeasurable}** are
  point clouds with no faces. They are reported UNVERIFIED, **not** as passes.
- **{passed:,} of {measured:,}** measured assets pass every check.
- **{nw:,} of {measured:,}** are not watertight.
- **{nm:,} of {measured:,}** carry at least one non-manifold edge. ⚠️ *At least
  one.* The median affected model carries **4**, on meshes that often exceed a
  million faces. A percentage quoted without that magnitude reads as "a third of
  this generator's output is unusable", which this data does not say.
- Of the **{fails:,}** that failed, **{healed:,}** heal fully, and repair
  introduced a regression on **{regr}** of them. We publish that number because
  a repair tool that cannot tell you when it made things worse is not a QA tool.

⛔ **No UV rate is published.** FINDING-10 is open. See the limitations tab.
"""


# ------------------------------------------------------------------ the counter

# THE RUN COUNTER. `SESSION_HANDOFF_2026-08-22b` section 15.
#
# The surface went live on 2026-08-22 and could not move the metric it was
# built for: `PATHB_LEDGER` grades this project on files received from
# strangers, and a page that retains nothing produces no record at all. A
# hundred people could run broken meshes through it in a week and the ledger
# would still read 0.
#
# This is the whole fix: one line to stdout per completed run. Streamlit
# Community Cloud keeps app logs, so it is a counter with zero storage.
#
# WHAT THIS LINE MAY NEVER CARRY, and the reason is the product, not the law:
#    the filename, any file bytes, the sha256, the byte size, an IP, a session
#    id, or anything else that could identify a visitor or their asset. Verdict,
#    file extension, face count and wall time. Nothing else, ever. If you are
#    tempted to add a field here, change the page copy in the same commit or do
#    not add it.
#
# A RUN IS NOT AN `F`. `F` is a file a stranger SENT TO A PERSON; this counts
#    anonymous engagement. Do not let these lines be totalled into the `F`
#    column, which is precisely the metric drift `PATH_B` section 3 built the
#    throttle to prevent.
#
# AND IT UNDERCOUNTS, BY DESIGN. `check_bytes` is `@st.cache_data`, so a second
#    run of identical bytes is a cache hit and prints nothing. One line is one
#    distinct asset linted by one server process, not one upload click. The
#    cache holds 8 entries and dies with the process, so the undercount is
#    small and always in the conservative direction. Read the total as a floor.
def _is_self_test() -> bool:
    """True when the operator appended ?self=1 to the URL.

    ⛔ This exists because the log had NO way to tell an operator test from a
    stranger's run, so every self-test silently inflated R. It is a query
    parameter the operator types, NOT anything read from the visitor: no IP, no
    session id, no fingerprint. The footer promises "nothing that identifies
    you" and a counter is not a reason to weaken that.
    """
    try:
        return str(st.query_params.get("self", "")) in ("1", "true", "yes")
    except Exception:
        return False


# ⛔ WHY A SECOND DESTINATION EXISTS, and it is not redundancy.
# The RUN line above goes to this container's stdout. Streamlit Cloud CLEARS
# that buffer every time the container restarts, and the container restarts on
# every hibernation - which is every 12 hours without traffic. So with low
# traffic the buffer resets faster than runs accumulate, and `R` read
# approximately zero forever no matter how many people used the demo. It was
# never an unread number. It was an unmeasurable one, for four weeks, and
# nobody noticed because "go read R" kept being written down as a task.
#
# This posts the SAME event to the counter already proven on topoheal.com:
# functions/e/[label].js, allow-listed, writing to Workers Analytics Engine.
# It survives restarts. No new service, no new account, no new dependency.
#
# ⛔ THE PAYLOAD IS THE LABEL AND NOTHING ELSE - no filename, no bytes, no hash,
# no size, no verdict, no IP, no session id. Less than the log line carries.
# The request is made by the SERVER, so the visitor's address never touches it.
# ⛔ If you are ever tempted to add a field, change the page copy in the SAME
# commit or do not add it. That rule is what the whole footer rests on.
_COUNT_ENDPOINT = "https://topoheal.com/e/"


def _count_run(self_test: bool) -> None:
    """Fire-and-forget tick so a completed run outlives this container.

    ⛔ Daemon thread with a short timeout, and every failure swallowed. A
    counter must never add latency to a lint and must never break one. If
    topoheal.com is down, the run still completes and the log line still
    prints - counting is worth less than the thing being counted.
    """
    label = "app-selftest" if self_test else "app-run"

    def _send() -> None:
        try:
            req = urllib.request.Request(
                _COUNT_ENDPOINT + label, data=b"", method="POST"
            )
            req.add_header("User-Agent", "topoheal-app/1 (+https://topoheal.com)")
            urllib.request.urlopen(req, timeout=3).close()
        except Exception:
            pass

    try:
        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass


def _emit_run(verdict: str, suffix: str, faces, ms) -> None:
    """One line per completed run, to the app log AND to the durable counter.

    ⛔ Every field here is named in the app footer. Add one and the footer
    changes in the SAME commit, or the change does not ship.
    """
    self_test = _is_self_test()
    _count_run(self_test)
    print(
        f"RUN ts={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"verdict={verdict} suffix={suffix or 'none'} "
        f"faces={'na' if faces is None else faces} "
        f"ms={'na' if ms is None else round(ms)}"
        f"{' self=1' if self_test else ''}",
        flush=True,
    )


# ------------------------------------------------------------------ the linter

def _findings(cert: dict) -> list[dict]:
    return cert.get("findings", cert.get("checks", [])) or []


# The engine writes its own defect messages and 76 lines of geometry_linter.py
# plus 50 of repair_engine.py contain an em dash. No em dash is wanted in any
# text this app renders, so displayed messages are normalised here.
# ⛔ PUNCTUATION ONLY, and the certificate is never touched: the JSON a visitor
# downloads keeps the engine's exact bytes, so nothing that carries meaning can
# drift between the page and the artifact. Fix it at the source in 1.1.2 and
# this function becomes a no-op.
def _plain(text: str) -> str:
    return (str(text or "")
            .replace(" — ", ", ")
            .replace("—", ",")
            .replace(" – ", ", ")
            .replace("–", "-"))


# ⛔ Cached on the file's bytes. Streamlit re-runs the whole script on EVERY
# widget interaction, so without this the asset is re-linted when the visitor
# expands the raw certificate or clicks download. Found 2026-08-22 on the live
# app: the page displayed 302 ms while the downloaded certificate recorded
# 507.82 ms, because they were two separate lints of the same bytes. Two
# different numbers for one upload is exactly the kind of thing this product
# cannot afford to show a stranger.
@st.cache_data(show_spinner=False, max_entries=8)
def check_bytes(name: str, data: bytes) -> tuple[str, str | None]:
    """Lint uploaded bytes. Returns (markdown report, certificate JSON or None)."""
    suffix = Path(name).suffix.lower()

    if gl is None:
        _emit_run("ENGINE_MISSING", suffix, None, None)
        return ("### Engine not installed\n\n`geometry_linter` did not import. "
                "`requirements.txt` should install the 3dqa wheel from the "
                "GitHub Release. Check the app logs."), None

    if suffix not in ACCEPTED:
        _emit_run("UNSUPPORTED", suffix, None, None)
        return (f"### Unsupported file type `{suffix}`\n\n"
                f"Accepted: {', '.join(ACCEPTED)}"), None

    size_mb = len(data) / 1e6
    if size_mb > MAX_MB:
        _emit_run("TOO_LARGE", suffix, None, None)
        return (f"### File too large\n\n{size_mb:.1f} MB, limit {MAX_MB} MB "
                f"here. The CLI has no limit."), None

    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    t0 = time.perf_counter()
    try:
        cert = gl.lint_file(tmp_path)
    except Exception:
        _emit_run("READ_FAILURE", suffix, None,
                  (time.perf_counter() - t0) * 1000)
        return ("### The engine could not read this file\n\n"
                "That is a real answer and we would like to know about it.\n\n"
                "```\n" + _plain(traceback.format_exc(limit=3)) + "```\n\n"
                "⚠️ This is a failure to measure, **not** a clean result.\n\n"
                "A file this engine cannot read is worth more to us than one "
                "it can. Send it to " + CONTACT + " and it becomes a "
                "regression test, and you get back whatever we learn from "
                "it."), None
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    wall = (time.perf_counter() - t0) * 1000

    # From the certificate, never re-derived. Same rule as the verdict
    # below: the engine is the source of truth, and `faces` is None on a
    # point cloud, which is why _emit_run prints `na` rather than 0.
    _emit_run(str(cert.get("verdict", "")).upper() or "UNRECOGNISED",
              suffix, (cert.get("geometry") or {}).get("faces"), wall)

    fs = _findings(cert)
    failed = [f for f in fs if not f.get("passed")]
    unmeasured = [f for f in failed if _is_unmeasured(f)]
    defects = [f for f in failed if not _is_unmeasured(f)]

    # Authoritative. See the comment on UNMEASURED_CHECKS above.
    raw = str(cert.get("verdict", "")).upper()
    if raw == "UNVERIFIED":
        verdict = ("⚠️ UNVERIFIED: the engine could not measure this, "
                   "which is not the same as clean")
    elif raw == "PASS":
        verdict = f"PASS: {len(fs)} of {len(fs)} checks clean"
    elif raw == "FAIL":
        verdict = f"FAIL: {len(defects)} of {len(fs)} checks found a defect"
    else:
        verdict = (f"⚠️ UNVERIFIED: the engine returned an unrecognised "
                   f"verdict ({raw or 'none'}), so nothing is claimed here")

    lines = [f"## {verdict}", "",
             f"`{name}` · {size_mb:.2f} MB · {wall:,.0f} ms wall clock", ""]

    if unmeasured:
        lines += ["### Not measured", "",
                  "⛔ **Unknown is never clean.** These checks did not run or "
                  "could not produce an answer, and are reported as absent "
                  "measurements rather than passes.", ""]
        for f in unmeasured:
            lines.append(f"- **{f.get('code')}**: {_plain(f.get('message'))}")
        lines.append("")

    if defects:
        lines += ["### Defects found", ""]
        for f in defects:
            lines.append(f"- **{f.get('code')}** ({f.get('severity')}): "
                         f"{_plain(f.get('message'))}")
            if f.get("code") == "UV_MISSING":
                lines += ["", f"  {FINDING_10}", ""]
        lines.append("")

    clean = [f for f in fs if f.get("passed")]
    if clean:
        lines += [f"**Checks that passed ({len(clean)}):** "
                  + ", ".join(str(f.get("code")) for f in clean), ""]

    if raw == "UNVERIFIED":
        lines += ["⛔ **This is not a pass and it is not a fail.** The "
                  "engine declined to measure this asset, which is a "
                  "result about our instrument, not about your file. If "
                  "you think it should have been measurable, send it to "
                  + CONTACT + ". An asset that defeats the linter is the "
                  "single most useful thing anyone can give us.", ""]

    lines += ["---", "",
              "**What this does not tell you.** It has no opinion on whether "
              "the topology is *good*, only on whether it is *valid*. "
              "Retopology quality, UV layout quality, whether the model looks "
              "right, and every texture-class defect are all invisible to it. "
              "And if you are 3D printing, your STL export erases most of what "
              "is flagged here: our checker and PrusaSlicer disagreed on 82 of "
              "120 identical files after the same export.", "",
              "Full certificate below. No account, and your file is never "
              "stored: the bytes live in a temporary file for the length "
              "of this lint and are deleted before you see this page. One "
              "line per run goes to our server log, so we can tell the "
              "tool is being used: the verdict, the file extension, the "
              "face count and the milliseconds. No filename, no file "
              "contents, no checksum, nothing that identifies you."]

    return "\n".join(lines), json.dumps(cert, indent=2)


LIMITS = """
## What it gets wrong and leaves out

A benchmark that only publishes its wins is marketing. This is the list we
would rather you read first.

Two different things are below and they are not the same. **Wrong** is where
this reports something untrue: a check that fires when it should not, or a
number we published and withdrew. **Blind** is where it never looks at all, and
never claims to. A false positive and an absent opinion are different failures,
and you should know which one you are reading.

### Wrong: FINDING-10, open since 2026-08-21
`UV_MISSING` is read from the **concatenated** mesh. `trimesh.util.concatenate`
wraps its visual merge in `except BaseException` and logs at DEBUG, so when a
texture-atlas pack fails it silently returns a mesh with no UVs, which this
engine reports as a *measured defect*. One asset in a 149-asset contrast group
flipped between two runs with identical bytes because of this.

**No UV rate is published anywhere while this is open**, and every per-file
UV finding carries the caveat inline.

**What to do about it.** The mechanism only fires when more than one primitive
has to be merged, and it does not fire every time: a two-primitive test asset
with UVs on both reports `UV_OK` correctly. So a single-primitive file is not
affected, and a multi-primitive one is worth checking rather than assuming. This
settles it in ten seconds, because it reads each primitive *before* the merge
that loses them:

```python
import trimesh
s = trimesh.load("yourfile.glb")
geoms = s.geometry if hasattr(s, "geometry") else {"mesh": s}
for name, g in geoms.items():
    uv = getattr(g.visual, "uv", None)
    print(name, "has UVs:", uv is not None and len(uv) > 0)
```

If every primitive prints `True` and we said `UV_MISSING`, the finding is ours,
not yours. Send it and it becomes a test case.

### Blind: the instrument does not know where your file is going
Our checker and PrusaSlicer disagree on **82 of 120** identical files after the
same export. If your pipeline ends in a slicer, most of what this flags is
erased by your own STL export before it reaches the printer. **Non-manifold
geometry is a real defect for anyone consuming glTF directly and close to a
non-issue for 3D printing.** Same file, opposite verdict, depending on where it
is going.

**What to do about it.** Check the file your pipeline actually ships, not the
one it starts from. If you export to STL before printing, export first and drop
*that* file here, then judge against the result. If you ship glTF or USD to an
engine or a viewer, check the source file and take non-manifold edges seriously.

### Wrong: repair can make things worse
Across the **1,461** assets that failed lint, repair introduced a regression on
**312** of them. The engine reverts a repair that would introduce a defect
rather than shipping it, and the report names every one.

**What to do about it.** Never let a repair write over anything you have not
read first. `3dqa heal --dry-run` computes the whole repair and writes nothing,
and its `introduced` list is the answer to "would this make my asset worse".
Read that list, then decide. On a batch, dry-run the batch and sort by it.

### Blind: it has no opinion on quality
Valid is not good. Edge flow, topology suitable for deformation, sensible UV
layout, whether the asset looks like what it claims to be. None of it is
measured here.

**What to do about it: nothing we can offer.** This one has no workaround and we
are not going to invent one. A person who knows your pipeline has to look at the
asset. A clean certificate from this tool means structurally valid, and that is
all it has ever meant.

### Wrong: numbers we published and withdrew
Two headline figures were published and are now withdrawn: the check that
produced them counted holes as something other than boundary edges (FINDING-7).
The corrected figures are 33.7% and 70.5%. Both retired strings are blocked by
an automated gate in the repo so they cannot reappear by accident.

**What to do about it.** If you quoted either of the old figures anywhere,
correct it. And audit the rest of this page while you are here: every number on
it is a count over a stated denominator for exactly that reason, so you can
check any of them without asking us.

### Blind: scope
2,307 assets from 23 generators, sourced from the 3D Arena dataset on Hugging
Face. It is one corpus, one instrument, one point in time. It is not a claim
about any generator's current release.

**What to do about it.** The corpus is whatever 3D Arena happened to contain, so
it says nothing about your files. Send a batch of your own and it gets run, and
you get the per-asset rows back. We are more interested in the files that fail
than the ones that do not.
"""


# ------------------------------------------------------------------- the page

# ⛔ THIS APP IS AN INDEXED PUBLIC SURFACE, not just a demo host. Streamlit's
# own docs: public Community Cloud apps "are automatically indexed by search
# engines like Google and Bing on a weekly basis." Until 2026-09-01 it carried
# NO brand and NO link back to topoheal.com, so it was an orphan: a second
# public page about mesh geometry that a reader — or an answer engine — had no
# way to connect to the site, the census or the package.
#   * page_title carries the wordmark FIRST. It is what shows in the search
#     result and the browser tab.
#   * The brand line sits directly under the title on purpose. Streamlit's
#     indexability docs say engines favour the content of st.header/st.text
#     over st.title when deciding what the page is about.
#   * "Topoheal ... ships as the `3dqa` package" is the entity link. The brand
#     and the installable name never co-occurred anywhere a crawler could read,
#     so nothing could tie the census to the thing you install.
# ⛔ No number here. Every rate on this page is read from the engine at runtime;
# a figure typed into the header would be a figure nobody re-checks.
st.set_page_config(page_title="Topoheal: 3D asset geometry check",
                   page_icon="🔍", layout="wide")

st.title("3D asset geometry check")
st.markdown(
    "Drop a mesh. Get the defect list, the checks that could not run, and the "
    "raw certificate. Free, no account, your file is never stored.\n\n"
    "This is **Topoheal**, geometry inspection and non-destructive repair for "
    "`.glb` `.gltf` `.obj` `.ply` `.stl`, the same engine that ships as the "
    "`3dqa` package. [topoheal.com](https://topoheal.com) · "
    "[the full census](https://topoheal.com/census/)\n\n"
    "*Same engine, same thresholds, as the census in the second tab.*")

tab_check, tab_census, tab_limits = st.tabs(
    ["Check a file", "The census", "What it gets wrong and leaves out"])

with tab_check:
    left, right = st.columns([1, 2])
    with left:
        up = st.file_uploader(
            "Mesh",
            type=[s.lstrip(".") for s in ACCEPTED],
            accept_multiple_files=False)
        st.caption(
            f"Accepted: {', '.join(ACCEPTED)} · up to {MAX_MB} MB. "
            "Large or unusual files are the interesting ones. If it breaks, "
            "that is a finding and we want it.")
        st.caption(
            "**What we keep.** Not your file. One line per run in the "
            "server log: a timestamp, the verdict, the file extension, "
            "the face count, and how many milliseconds it took. Plus one "
            "anonymous tick sent to topoheal.com, so the count survives "
            "this server restarting - that tick carries the single word "
            "\"run\" and nothing else, not even the verdict. That is the "
            "whole record. Nothing identifies you, and it exists so we "
            "know whether anyone is using this.")
    with right:
        if up is None:
            st.markdown("Drop a file to start.")
        else:
            with st.spinner("Linting…"):
                report, cert_json = check_bytes(up.name, up.getvalue())
            st.markdown(report)
            if cert_json:
                st.download_button(
                    "Download certificate.json", cert_json,
                    file_name=f"{Path(up.name).stem}_certificate.json",
                    mime="application/json")
                with st.expander("Raw certificate"):
                    st.code(cert_json, language="json")

with tab_census:
    st.markdown(census_summary())
    rows = census_table()
    st.dataframe(
        rows,
        column_config={
            0: st.column_config.Column("generator"),
            1: st.column_config.Column("assets"),
            2: st.column_config.Column("measurable"),
            3: st.column_config.Column("pass"),
            4: st.column_config.Column("non-manifold"),
        },
        hide_index=True, width='stretch')
    st.markdown(
        "⚠️ **Three generators show `not measured`.** `404_GEN`, `LGM` and "
        "`SAM-3D-Objects-3DGS` ship point clouds with no faces, 101 each. "
        "There is nothing to measure, so they get no score. They are **not** a "
        "zero.\n\n"
        f"⛔ **{len(EMBARGOED)} generator rows are measured but withheld.** We "
        "told that vendor we would hold off on publishing the comparison until "
        "they had a chance to look at it, and they have not said they are done. "
        "The commitment has no expiry date, so neither does the hold. Their "
        "assets are still counted in the totals above. We would rather show you "
        "a gap than break a promise, and you should weigh what that implies "
        "about the rows we *do* show.\n\n"
        "Want your generator measured, or think a row is wrong? Send a batch "
        "and it gets run. A corrected row is worth more to us than a "
        "flattering one.")

with tab_limits:
    st.markdown(LIMITS)

st.divider()
st.caption(
    "Topoheal · [topoheal.com](https://topoheal.com) · "
    "[the census](https://topoheal.com/census/) · "
    "install the CLI: `pip install 3dqa`")
