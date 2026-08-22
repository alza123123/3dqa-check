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
import traceback
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
    "this finding may be a false positive."
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
### The census — {n:,} assets, 23 generators, one instrument

Re-linted 2026-08-17. Every figure below is a count over a stated denominator,
on purpose: a fragment of this text cannot be quoted into something stronger
than it says.

- **{measured:,} of {n:,}** assets were measurable. The other **{unmeasurable}** are
  point clouds with no faces — they are reported UNVERIFIED, **not** as passes.
- **{passed:,} of {measured:,}** measured assets pass every check.
- **{nw:,} of {measured:,}** are not watertight.
- **{nm:,} of {measured:,}** carry at least one non-manifold edge. ⚠️ *At least
  one.* The median affected model carries **4**, on meshes that often exceed a
  million faces. A percentage quoted without that magnitude reads as "a third of
  this generator's output is unusable", which this data does not say.
- Of the **{fails:,}** that failed, **{healed:,}** heal fully — and repair
  introduced a regression on **{regr}** of them. We publish that number because
  a repair tool that cannot tell you when it made things worse is not a QA tool.

⛔ **No UV rate is published.** FINDING-10 is open — see the limitations tab.
"""


# ------------------------------------------------------------------ the linter

def _findings(cert: dict) -> list[dict]:
    return cert.get("findings", cert.get("checks", [])) or []


def check_bytes(name: str, data: bytes) -> tuple[str, str | None]:
    """Lint uploaded bytes. Returns (markdown report, certificate JSON or None)."""
    if gl is None:
        return ("### Engine not installed\n\n`geometry_linter` did not import. "
                "`requirements.txt` should install the 3dqa wheel from the "
                "GitHub Release — check the app logs."), None

    suffix = Path(name).suffix.lower()
    if suffix not in ACCEPTED:
        return (f"### Unsupported file type `{suffix}`\n\n"
                f"Accepted: {', '.join(ACCEPTED)}"), None

    size_mb = len(data) / 1e6
    if size_mb > MAX_MB:
        return (f"### File too large\n\n{size_mb:.1f} MB, limit {MAX_MB} MB "
                f"here. The CLI has no limit."), None

    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    t0 = time.perf_counter()
    try:
        cert = gl.lint_file(tmp_path)
    except Exception:
        return ("### The engine could not read this file\n\n"
                "That is a real answer and we would like to know about it.\n\n"
                "```\n" + traceback.format_exc(limit=3) + "```\n\n"
                "⚠️ This is a failure to measure, **not** a clean result."), None
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    wall = (time.perf_counter() - t0) * 1000

    fs = _findings(cert)
    failed = [f for f in fs if not f.get("passed")]
    unmeasured = [f for f in failed if _is_unmeasured(f)]
    defects = [f for f in failed if not _is_unmeasured(f)]

    # Authoritative. See the comment on UNMEASURED_CHECKS above.
    raw = str(cert.get("verdict", "")).upper()
    if raw == "UNVERIFIED":
        verdict = ("⚠️ UNVERIFIED — the engine could not measure this, "
                   "which is not the same as clean")
    elif raw == "PASS":
        verdict = f"PASS — {len(fs)} of {len(fs)} checks clean"
    elif raw == "FAIL":
        verdict = f"FAIL — {len(defects)} of {len(fs)} checks found a defect"
    else:
        verdict = (f"⚠️ UNVERIFIED — the engine returned an unrecognised "
                   f"verdict ({raw or 'none'}), so nothing is claimed here")

    lines = [f"## {verdict}", "",
             f"`{name}` · {size_mb:.2f} MB · {wall:,.0f} ms wall clock", ""]

    if unmeasured:
        lines += ["### Not measured", "",
                  "⛔ **Unknown is never clean.** These checks did not run or "
                  "could not produce an answer, and are reported as absent "
                  "measurements rather than passes.", ""]
        for f in unmeasured:
            lines.append(f"- **{f.get('code')}** — {f.get('message','')}")
        lines.append("")

    if defects:
        lines += ["### Defects found", ""]
        for f in defects:
            lines.append(f"- **{f.get('code')}** ({f.get('severity')}) — "
                         f"{f.get('message','')}")
            if f.get("code") == "UV_MISSING":
                lines += ["", f"  {FINDING_10}", ""]
        lines.append("")

    clean = [f for f in fs if f.get("passed")]
    if clean:
        lines += [f"**Checks that passed ({len(clean)}):** "
                  + ", ".join(str(f.get("code")) for f in clean), ""]

    lines += ["---", "",
              "**What this does not tell you.** It has no opinion on whether "
              "the topology is *good* — only on whether it is *valid*. "
              "Retopology quality, UV layout quality, whether the model looks "
              "right, and every texture-class defect are all invisible to it. "
              "And if you are 3D printing, your STL export erases most of what "
              "is flagged here: our checker and PrusaSlicer disagreed on 82 of "
              "120 identical files after the same export.", "",
              "Full certificate below. No account, nothing retained beyond this "
              "request, and nothing is sent anywhere."]

    return "\n".join(lines), json.dumps(cert, indent=2)


LIMITS = """
## What this gets wrong

A benchmark that only publishes its wins is marketing. This is the list we
would rather you read first.

### FINDING-10 — open, 2026-08-21
`UV_MISSING` is read from the **concatenated** mesh. `trimesh.util.concatenate`
wraps its visual merge in `except BaseException` and logs at DEBUG, so when a
texture-atlas pack fails it silently returns a mesh with no UVs — which this
engine reports as a *measured defect*. One asset in a 149-asset contrast group
flipped between two runs with identical bytes because of this.

**No UV rate is published anywhere while this is open**, and every per-file
UV finding carries the caveat inline.

### The instrument disagrees with slicers
Our checker and PrusaSlicer disagree on **82 of 120** identical files after the
same export. If your pipeline ends in a slicer, most of what this flags is
erased by your own STL export before it reaches the printer. **Non-manifold
geometry is a real defect for anyone consuming glTF directly and close to a
non-issue for 3D printing.** Same file, opposite verdict, depending on where it
is going.

### Repair can make things worse
Across the **1,461** assets that failed lint, repair introduced a regression on
**312** of them. The engine reverts a repair that would introduce a defect
rather than shipping it, and the report names every one.

### It has no opinion on quality
Valid is not good. Edge flow, topology suitable for deformation, sensible UV
layout, whether the asset looks like what it claims to be — none of it is
measured here.

### Numbers we retired
Two headline figures were published and are now withdrawn: the check that
produced them counted holes as something other than boundary edges (FINDING-7).
The corrected figures are 33.7% and 70.5%. Both retired strings are blocked by
an automated gate in the repo so they cannot reappear by accident.

### Scope
2,307 assets from 23 generators, sourced from the 3D Arena dataset on Hugging
Face. It is one corpus, one instrument, one point in time. It is not a claim
about any generator's current release.
"""


# ------------------------------------------------------------------- the page

st.set_page_config(page_title="3D asset geometry check", page_icon="🔍",
                   layout="wide")

st.title("3D asset geometry check")
st.markdown(
    "Drop a mesh. Get the defect list, the checks that could not run, and the "
    "raw certificate. Free, no account, nothing kept.\n\n"
    "*Same engine, same thresholds, as the census in the second tab.*")

tab_check, tab_census, tab_limits = st.tabs(
    ["Check a file", "The census", "What this gets wrong"])

with tab_check:
    left, right = st.columns([1, 2])
    with left:
        up = st.file_uploader(
            "Mesh",
            type=[s.lstrip(".") for s in ACCEPTED],
            accept_multiple_files=False)
        st.caption(
            f"Accepted: {', '.join(ACCEPTED)} · up to {MAX_MB} MB. "
            "Large or unusual files are the interesting ones — if it breaks, "
            "that is a finding and we want it.")
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
        "`SAM-3D-Objects-3DGS` ship point clouds with no faces — 101 each. "
        "There is nothing to measure, so they get no score. They are **not** a "
        "zero.\n\n"
        f"⛔ **{len(EMBARGOED)} generator rows are measured but withheld.** We "
        "told that vendor we would hold off on publishing the comparison until "
        "they had a chance to look at it, and they have not said they are done. "
        "The commitment has no expiry date, so neither does the hold. Their "
        "assets are still counted in the totals above. We would rather show you "
        "a gap than break a promise — and you should weigh what that implies "
        "about the rows we *do* show.\n\n"
        "Want your generator measured, or think a row is wrong? Send a batch "
        "and it gets run. A corrected row is worth more to us than a "
        "flattering one.")

with tab_limits:
    st.markdown(LIMITS)
