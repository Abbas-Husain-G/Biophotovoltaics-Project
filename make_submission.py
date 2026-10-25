"""Build the complete submission: tests -> pipeline -> figures -> report + defence brief (DOCX + PDF) -> zip.
Usage: python -I make_submission.py <data_dir> <build_dir> [cover.json]
<data_dir> must contain pvgis/, zenodo/ and zenodo_columns.json."""
import pathlib, shutil, subprocess, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parent
DATA, BUILD = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve()
COVER = sys.argv[3] if len(sys.argv) > 3 else None
OUT, FIG, DOC = BUILD / "outputs", BUILD / "figures", BUILD / "docs"
for d in (OUT, FIG, DOC):
    d.mkdir(parents=True, exist_ok=True)
SOFFICE = "/root/.claude/skills/synced/f81dc59f-2391-412c-bc88-2fd298a83689_fec28d36-3e54-4c3a-a69c-3dcf686aeb46/docx/scripts/office/soffice.py"


def run(*args, cwd=ROOT):
    print("$", " ".join(map(str, args)))
    subprocess.run([str(a) for a in args], cwd=cwd, check=True)


py = [sys.executable, "-I"]
for t in ("test_validation.py", "test_cropfit.py", "test_econ.py"):
    run(*py, ROOT / "tests" / t)
shutil.copy(ROOT / "outputs" / "validation_checks.csv", OUT / "validation_checks.csv")
run(*py, ROOT / "run_phase23.py", DATA / "pvgis", OUT)
run(*py, ROOT / "run_phase45.py", DATA, OUT)
run(*py, ROOT / "run_phase6.py", OUT)
run(*py, ROOT / "make_figures.py", OUT, FIG)
cov = [COVER] if COVER else []
run(*py, ROOT / "report" / "build_report.py", OUT, FIG, BUILD / "report_spec.json", *cov)
run(*py, ROOT / "report" / "build_defence.py", OUT, BUILD / "defence_spec.json", *cov)
run("node", ROOT / "report" / "render_docx.js", BUILD / "report_spec.json", DOC / "Agrivoltaics_India_Report.docx", cwd="/tmp")
run("node", ROOT / "report" / "render_docx.js", BUILD / "defence_spec.json", DOC / "Defence_Brief.docx", cwd="/tmp")
for f in ("Agrivoltaics_India_Report.docx", "Defence_Brief.docx"):
    run(sys.executable, SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", DOC, DOC / f, cwd=DOC)

zpath = BUILD / "Agrivoltaics_India_Submission.zip"
top = "Agrivoltaics_India_Submission"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(DOC.glob("*")):
        z.write(f, f"{top}/{f.name}")
    for sub in ("agripv", "tests", "scripts", "report"):
        for f in sorted((ROOT / sub).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f"{top}/code/{f.relative_to(ROOT)}")
    for f in ("run_phase23.py", "run_phase45.py", "run_phase6.py", "make_figures.py", "make_submission.py",
              "README.md", "requirements.txt", "CHANGELOG.md"):
        z.write(ROOT / f, f"{top}/code/{f}")
    for f in sorted(OUT.glob("*")):
        z.write(f, f"{top}/outputs/{f.name}")
    for f in sorted(FIG.glob("*.png")):
        z.write(f, f"{top}/figures/{f.name}")
    for f in sorted(DATA.rglob("*")):
        if f.is_file():
            z.write(f, f"{top}/data/{f.relative_to(DATA)}")
    z.write(ROOT / "README.md", f"{top}/README.md")
print("submission:", zpath, f"{zpath.stat().st_size / 1e6:.1f} MB")
