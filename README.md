# 3D asset geometry check — Streamlit deploy

Public surface for `PATH_B §2.3`: drop a mesh, get the defect list. Deployed on
**Streamlit Community Cloud** (free, public apps only).

## Why not a Hugging Face Space

⛔ **Gradio and Docker Spaces became PRO-only.** Verified from the create form
on 2026-08-22, personal account `alza123123`: *"Gradio and Docker Spaces require
a paid plan. Static Spaces stay free for everyone."* Static cannot run Python,
and there is no client-side linter to fall back on — `web/engine/qaRunner.js`
POSTs to `/v1/audit/full`, which is `api.py`, deliberately withheld. HF PRO is
$9/mo and is a recurring spend on an account in the operator's name, so it is a
guardian item. Streamlit Community Cloud costs nothing and needs no card.

## Deploy

1. Push these three files to a **public** GitHub repo:

   ```
   app.py
   requirements.txt
   aggregate_by_generator_relint_2026-08-17.csv
   ```

   ⛔ **No engine source.** `LICENSE` names `geometry_linter.py`,
   `qa_profiles.py` and `usd_loader.py`; a public repo would give away the
   source-available moat. `requirements.txt` installs the built wheel instead —
   running it here is **use**, not redistribution (`LICENSE §1`).

2. `share.streamlit.io` → sign in with GitHub → **New app** → pick the repo,
   branch and `app.py` → Deploy. Every `git push` redeploys.

## Verified before deploy, by running it

- ✅ `requirements.txt` installs clean in **27 s** — 3dqa 1.1.0, streamlit
  1.62.0, and every engine pin held exactly (trimesh 4.5.3 · numpy 2.1.3 ·
  networkx 3.4.2 · pillow 12.3.0 · scipy 1.13.1). `pip check`: no broken
  requirements.
- ✅ The app boots headless and serves **HTTP 200**; `/_stcore/health` returns
  `ok`; no errors in the log.
- ⭐ **The point-cloud case passes.** A Gaussian-splat `.ply` renders
  *"⚠️ UNVERIFIED — the engine could not measure this, which is not the same as
  clean"*. That is the regression that once told a stranger their point cloud
  FAILED, and 303 of the 2,307 corpus assets are point clouds. The headline is
  read from `cert["verdict"]` and never re-derived.
- ✅ A normal mesh renders `FAIL — 1 of 8 checks found a defect`, with the
  FINDING-10 caveat attached inline to `UV_MISSING`.
- ✅ Census tab renders **21** generator rows: `OVERALL` excluded, both
  embargoed rows excluded, and `404_GEN` / `LGM` / `SAM-3D-Objects-3DGS` show
  **not measured** rather than a zero.
- ✅ All three rejection paths: unsupported type, over `MAX_MB`, unreadable
  file — the last reported as *a failure to measure, not a clean result*.

## ⚠️ Still to do after it is live

The **eight file cases** have still only ever run against vendored source:
`.glb` small, `.glb` **4 MB**, `.obj`, tiny `.obj`, `.ply` point cloud,
truncated `.glb`, empty `.glb`, wrong extension. ⛔ Run the 4 MB case **first** —
Community Cloud's memory ceiling is not published and that is the case most
likely to hit it.
