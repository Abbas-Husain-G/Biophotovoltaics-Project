"""Download every external input of the study into one zip (agripv_data.zip) - run on any internet-connected PC.

    python fetch_all_data.py

Needs only Python 3 (standard library). Takes 2-5 minutes. Downloads:
  - PVGIS 5.3 typical meteorological year (TMY) + PVcalc cross-checks for the six proxy points (42 files)
  - Laub & Pataczek crop-shade dataset, Zenodo record 5716091 (2 workbooks, CC BY 4.0)
"""
import io, json, time, urllib.request, zipfile

API = "https://re.jrc.ec.europa.eu/api/v5_3"
SITES = {"Rajasthan": (26.26, 73.02), "Gujarat": (21.52, 70.46), "Maharashtra": (19.99, 73.79),
         "Madhya_Pradesh": (23.52, 77.81), "Karnataka": (13.14, 78.13), "Uttar_Pradesh": (27.18, 78.01)}
ZENODO = ["https://zenodo.org/records/5716091/files/Data_Meta_Analysis_updated.xlsx?download=1",
          "https://zenodo.org/records/5716091/files/Data-Meta_Analysis.xlsx?download=1"]


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "agripv-study"}), timeout=180) as r:
                return r.read()
        except Exception as e:
            print(f"   retry {k + 1} ({e})"); time.sleep(5 * (k + 1))
    raise RuntimeError(f"failed: {url}")


buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for name, (lat, lon) in SITES.items():
        print("PVGIS", name)
        z.writestr(f"pvgis/tmy_{name}.json", get(f"{API}/tmy?lat={lat}&lon={lon}&outputformat=json"))
        base = f"{API}/PVcalc?lat={lat}&lon={lon}&peakpower=1&loss=14&mountingplace=free&aspect=0&outputformat=json"
        z.writestr(f"pvgis/pvcalc_opt_{name}.json", get(base + "&optimalinclination=1"))
        for a in (10, 15, 20, 25, 30):
            z.writestr(f"pvgis/pvcalc_{a}_{name}.json", get(base + f"&angle={a}"))
            time.sleep(0.5)
    for u in ZENODO:
        fn = u.split("/files/")[1].split("?")[0]
        print("Zenodo", fn)
        z.writestr(f"zenodo/{fn}", get(u))
    z.writestr("MANIFEST.json", json.dumps({"downloaded": time.strftime("%Y-%m-%d %H:%M:%S"), "pvgis_api": API,
                                            "zenodo_record": "10.5281/zenodo.5716091"}, indent=1))
open("agripv_data.zip", "wb").write(buf.getvalue())
print(f"\nDone: agripv_data.zip ({len(buf.getvalue()) / 1e6:.1f} MB). Attach this file in the chat.")
