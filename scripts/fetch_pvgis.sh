#!/usr/bin/env bash
# Phase 1 (weather part): download PVGIS 5.3 typical-year hourly weather and PVcalc cross-check values
# for the six proxy points. Run on a machine that can reach re.jrc.ec.europa.eu.
# Usage: bash fetch_pvgis.sh <output_dir>
set -euo pipefail
OUT="${1:-pvgis_data}"; mkdir -p "$OUT"
API="https://re.jrc.ec.europa.eu/api/v5_3"
SITES=("Rajasthan 26.26 73.02" "Gujarat 21.52 70.46" "Maharashtra 19.99 73.79"
       "Madhya_Pradesh 23.52 77.81" "Karnataka 13.14 78.13" "Uttar_Pradesh 27.18 78.01")
for s in "${SITES[@]}"; do
  read -r name lat lon <<< "$s"
  curl -sS --fail -m 120 "$API/tmy?lat=$lat&lon=$lon&outputformat=json" -o "$OUT/tmy_$name.json"
  curl -sS --fail -m 120 "$API/PVcalc?lat=$lat&lon=$lon&peakpower=1&loss=14&mountingplace=free&optimalinclination=1&aspect=0&outputformat=json" -o "$OUT/pvcalc_opt_$name.json"
  for a in 10 15 20 25 30; do
    curl -sS --fail -m 120 "$API/PVcalc?lat=$lat&lon=$lon&peakpower=1&loss=14&mountingplace=free&angle=$a&aspect=0&outputformat=json" -o "$OUT/pvcalc_${a}_$name.json"
  done
  echo "done $name"; sleep 1
done
ls -la "$OUT"
