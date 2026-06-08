#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ScroBot GitHub worker — rownolegly skaner KRS na IP GitHub Actions.
Wspolpracuje z cronem Hostingera przez wspolny panel str24 (inv_lease / inv_ingest).
Sekrety (GitHub Secrets): PANEL_BASE, CRON_TOKEN. Brak sekretow w kodzie."""
import os, sys, time, json, urllib.request, urllib.error, ssl
PANEL_BASE = os.environ.get("PANEL_BASE", "").rstrip("/")
TOKEN      = os.environ.get("CRON_TOKEN", "")
BATCH      = int(os.environ.get("BATCH", "400"))
MAX_FIRMS  = int(os.environ.get("MAX_FIRMS", "1500"))
DELAY      = float(os.environ.get("DELAY", "0.8"))
KRS_API    = "https://api-krs.ms.gov.pl/api/krs/OdpisPelny/{krs}?rejestr=P&format=json"
if not PANEL_BASE or not TOKEN:
    print("BRAK PANEL_BASE / CRON_TOKEN w env"); sys.exit(2)
CTX = ssl.create_default_context()
def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "ScroBot-GH/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")
def http_post(url, payload, timeout=40):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "ScroBot-GH/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")
def lease(n):
    url = f"{PANEL_BASE}/skrobot_api.php?action=inv_lease&n={n}&src=gh&token={TOKEN}"
    try:
        d = json.loads(http_get(url)); return d.get("krs", []) if d.get("ok") else []
    except Exception as e:
        print("LEASE ERR:", str(e)[:120]); return []
def ingest(krs, odpis):
    url = f"{PANEL_BASE}/skrobot_api.php?action=inv_ingest&token={TOKEN}"
    try:
        return json.loads(http_post(url, {"krs": krs, "odpis": odpis}))
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
def main():
    done = hot = errs = 0; t0 = time.time()
    while done < MAX_FIRMS:
        batch = lease(min(BATCH, MAX_FIRMS - done))
        if not batch:
            print("Brak wiecej firm do leasowania - koniec."); break
        for item in batch:
            krs = item["krs"]
            try:
                raw = http_get(KRS_API.format(krs=krs)); i = raw.find("{")
                odpis_full = json.loads(raw[i:]); odpis = odpis_full.get("odpis", odpis_full)
                r = ingest(krs, odpis); done += 1; hot += int(r.get("kwalifikuje", 0) or 0)
                if done % 50 == 0:
                    print(f"[{done}] {krs} wyjsc={r.get('wyjsc')} hot+={r.get('kwalifikuje')} {time.time()-t0:.0f}s")
            except urllib.error.HTTPError as e:
                errs += 1
                if e.code in (429, 503):
                    print(f"RATE-LIMIT {e.code} na {krs} - pauza 60s"); time.sleep(60)
            except Exception as e:
                errs += 1; print(f"ERR {krs}: {str(e)[:80]}")
            time.sleep(DELAY)
    print(f"KONIEC: przetworzono {done}, hot~{hot}, bledow {errs}, czas {time.time()-t0:.0f}s")
if __name__ == "__main__":
    main()
