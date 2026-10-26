#!/usr/bin/env python3
"""Construye data/latest.json para el dashboard Hycite (CHASEP 13588).

Entrada: carpeta con los JSON extraídos del portal distributors.hycite.com
(ver docs/PROCESO.md):
  hycite_compras_MTD.json  hycite_compras_YTD.json
  hycite_ventas_MTD.json   hycite_ventas_YTD.json
  hycite_bonos.json  hycite_bono_estimado.json  hycite_fondo_nl.json

Uso:
  python3 -I scripts/build_data.py --dir <carpeta> --fecha AAAA-MM-DD [--tipo semanal|cierre]
"""
import argparse, json, os, shutil, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R2 = lambda v: round(float(v or 0), 2)
ETQ = {"M": "mercancía actual", "P": "premiums actual", "pM": "mercancía año ant.", "pP": "premiums año ant.", "V": "ventas actual", "pV": "ventas año ant."}


def cargar(d, n):
    p = os.path.join(d, f"hycite_{n}.json")
    if not os.path.exists(p):
        raise SystemExit(f"Falta {p}")
    return json.load(open(p))


def money(js, campo="USD"):
    try:
        return R2(json.loads(js)[campo])
    except Exception:
        return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--tipo", default="semanal")
    a = ap.parse_args()

    org = json.load(open(os.path.join(ROOT, "data", "organigrama.json")))
    id2sub = org.get("id_to_sub", {})
    bajas = set(org.get("bajas_globales", []))
    subs = {k: {"premier": v["premier"], "nivel": v["nivel"], "lider": v["lider_id"], "lider_nombre": v.get("lider_nombre", "")}
            for k, v in org["subterritorios"].items()}

    dist, padre = {}, {}
    out = {"generado": datetime.now().strftime("%Y-%m-%d %H:%M"), "fecha_corte": a.fecha, "tipo_corte": a.tipo,
           "moneda": "USD", "subterritorios": subs, "compras": {}, "ventas": {}, "errores": []}

    for rep in ("compras", "ventas"):
        for per in ("MTD", "YTD"):
            d = cargar(a.dir, f"{rep}_{per}")
            f = d["filas"]
            root = next(x for x in f if x["EntityCode"] == "13588")
            filas = []
            for x in f:
                i = x["EntityCode"]
                padre[i] = x.get("ParentEntityCode") or ""
                dist.setdefault(i, {"n": x["EntityName"], "p": padre[i], "lv": x.get("EntityLevel") or "",
                                    "c": x.get("EntityCompany") or ""})
                if rep == "compras":
                    filas.append([i, R2(x["MerchUSD"]), R2(x["PremUSD"]), R2(x["MiscUSD"]),
                                  R2(x["PMerchUSD"]), R2(x["PPremUSD"]), R2(x["PMiscUSD"])])
                else:
                    filas.append([i, R2(x["VolumeUSD"]), R2(x["PVolumeUSD"])])
            if rep == "compras":
                tot = {k: R2(sum(r[j] for r in filas)) for j, k in enumerate(["M", "P", "X", "pM", "pP", "pX"], 1)}
                chk = [("M", root["TMerchUSD"]), ("P", root["TPremUSD"]), ("pM", root["TPMerchUSD"]), ("pP", root["TPPremUSD"])]
            else:
                tot = {"V": R2(sum(r[1] for r in filas)), "pV": R2(sum(r[2] for r in filas))}
                chk = [("V", root["TerrVolumeUSD"]), ("pV", root["PTerrVolumeUSD"])]
            for k, v in chk:
                if abs(tot[k] - R2(v)) > 1:
                    out["errores"].append(f"{rep} {per} ({ETQ[k]}): suma de distribuidores ${tot[k]:,.2f} vs total del territorio ${R2(v):,.2f} USD en el portal")
            out[rep][per] = {"rango": d["meta"].get("rango"), "periodo": d["meta"].get("periodo"),
                             "extraido": d["meta"].get("extraido"), "totales": tot, "filas": filas}
            print(f"OK {rep} {per}: {len(filas)} filas, totales {tot}")

    # Subterritorio: organigrama; si no está, hereda del ancestro más cercano mapeado
    def sub_de(i, prof=0):
        if i in id2sub:
            return id2sub[i]
        p = padre.get(i)
        if not p or prof > 30:
            return ""
        return sub_de(p, prof + 1)

    for i, v in dist.items():
        v["s"] = sub_de(i)
        v["org"] = i in id2sub      # True = en organigrama; False = asignado por árbol
        v["b"] = i in bajas
    out["distribuidores"] = dist

    b = cargar(a.dir, "bonos")["filas"]
    out["bonos"] = [{"periodo": x["Period"], "overrides": R2(x["TotalOverrides"]), "ajuste": R2(x["TotalReserveAdjustment"]),
                     "total": R2(x["TotalPayout"]), "total_usd": money(x.get("TotalPayoutJSON")), "tc": x.get("ExchangeRate"),
                     "fecha_proceso": (x.get("ProcessDate") or "")[:10], "procesando": bool(x.get("IsProcessing"))} for x in b]
    e = cargar(a.dir, "bono_estimado")["filas"]
    out["bono_estimado"] = [{"periodo": x["Period"], "reclutador": R2(x.get("RecruiterBonus")), "liderazgo": R2(x.get("LeadershipBonus")),
                             "nivel_precio": R2(x.get("PriceLevelIncentive")), "total": R2(x.get("TotalOverride")),
                             "total_usd": money(x.get("TotalOverrideJSON"))} for x in e]
    fo = cargar(a.dir, "fondo_nl")["filas"]
    out["fondo"] = [{"periodo": x["Period"], "cargos": R2(x["TotalCharges"]), "pagos": R2(x["TotalPayouts"]),
                     "saldo": R2(x["EndingBalance"]), "saldo_usd": money(x.get("EndingBalanceJSON"))} for x in fo]
    fo_s = sorted(out["fondo"], key=lambda x: x["periodo"])
    for p, c in zip(fo_s, fo_s[1:]):
        if abs(p["saldo"] + c["cargos"] + c["pagos"] - c["saldo"]) > 0.05:
            out["errores"].append(f"fondo {c['periodo']}: saldo no cuadra")

    os.makedirs(os.path.join(ROOT, "data", "historial"), exist_ok=True)
    dst = os.path.join(ROOT, "data", "latest.json")
    json.dump(out, open(dst, "w"), ensure_ascii=False, separators=(",", ":"))
    shutil.copy(dst, os.path.join(ROOT, "data", "historial", f"{a.fecha}.json"))
    idx_p = os.path.join(ROOT, "data", "historial", "index.json")
    idx = json.load(open(idx_p)) if os.path.exists(idx_p) else []
    idx = [x for x in idx if x["fecha"] != a.fecha] + [{"fecha": a.fecha, "tipo": a.tipo}]
    json.dump(sorted(idx, key=lambda x: x["fecha"], reverse=True), open(idx_p, "w"), ensure_ascii=False, indent=1)
    print("Por árbol (no en organigrama):", sum(1 for v in dist.values() if not v["org"]),
          "| sin subterritorio:", sum(1 for v in dist.values() if not v["s"]))
    print("Avisos:", out["errores"] or "ninguno")
    print("Escrito", dst)


if __name__ == "__main__":
    sys.exit(main())
