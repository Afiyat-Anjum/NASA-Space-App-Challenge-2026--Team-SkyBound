# Copyright 2026 Space Apps Challenge Team
# Licensed under the Apache License, Version 2.0
"""
ACQUISITION LAYER: Offline/pre-event downloader for NASA FIRMS country archives.
Stores raw CSVs in cache/ (gitignored). Never imported by src/api/ or web/.
"""

import os
import urllib.request

SOUTH_ASIA_COUNTRIES = [
    "Afghanistan", "Bangladesh", "Bhutan", "India",
    "Maldives", "Nepal", "Pakistan", "Sri_Lanka",
]

FIRMS_ENDPOINTS = {
    "MODIS":        ("modis",      range(2000, 2026)),
    "VIIRS_SNPP":   ("viirs-snpp", range(2012, 2026)),
    "VIIRS_NOAA20": ("viirs-j1",   range(2018, 2026)),
    "VIIRS_NOAA21": ("viirs-j2",   range(2023, 2026)),
}


def download_country_archives(cache_dir: str = "cache") -> int:
    os.makedirs(cache_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    saved = 0

    for country in SOUTH_ASIA_COUNTRIES:
        for sensor, (folder, years) in FIRMS_ENDPOINTS.items():
            for year in years:
                url = f"https://firms.modaps.eosdis.nasa.gov/data/country/{folder}/{year}/{folder}_{year}_{country}.csv"
                dest = os.path.join(cache_dir, f"{sensor}_{year}_{country}.csv")
                if os.path.exists(dest):
                    continue
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        payload = resp.read()
                        if b"latitude,longitude" in payload[:200]:
                            with open(dest, "wb") as f:
                                f.write(payload)
                            saved += 1
                except Exception:
                    pass
    return saved


if __name__ == "__main__":
    count = download_country_archives()
    print(f"Acquisition complete: {count} new CSV files cached in cache/.")
