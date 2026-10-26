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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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


    dist, padre = {}, {}
    out = {"generado": datetime.now().strftime("%Y-%m-%d %H:%M"), "fecha_corte": a.fecha, "tipo_corte": a.tipo,
           "moneda": "USD", "compras": {}, "ventas": {}, "errores": []}

    for rep in ("compras", "ventas"):
        for per in ("MTD", "YTD"):
            d = cargar(a.dir, f"{rep}_{per}")
            f = d["filas"]
            root = next(x for x in f if x["EntityCode"] == "13588")
            filas = []
            for x in f:
                i = x["EntityCode"]
                padre[i] = x.get("ParentEntityCode") or ""
                dist.setdefault(i, {"n": x["EntityName"], "p": padre[i], "lv": x.get("EntityLevel") or ""})
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

    # Meses cerrados del año (hycite_<rep>_meses.json): mismas columnas que MTD
    for rep in ("compras", "ventas"):
        p = os.path.join(a.dir, f"hycite_{rep}_meses.json")
        if not os.path.exists(p):
            continue
        meses = {}
        for m, rows in sorted(json.load(open(p))["meses"].items()):
            fil = []
            for r in rows:
                i = r[0]
                dist.setdefault(i, {"n": r[-1], "p": r[-2] or "", "lv": ""})
                padre.setdefault(i, r[-2] or "")
                fil.append([i] + [R2(x) for x in (r[1:7] if rep == "compras" else r[1:3])])
            meses[m] = fil
        out[rep]["meses"] = meses
        # validación: meses + mes en curso = año a la fecha (solo si el YTD es CURRENT y cubre los mismos meses)
        k = (1, 2) if rep == "compras" else (1,)
        s = sum(sum(r[j] for j in k) for f in meses.values() for r in f) + sum(sum(r[j] for j in k) for r in out[rep]["MTD"]["filas"])
        y = sum(sum(r[j] for j in k) for r in out[rep]["YTD"]["filas"])
        if out[rep]["YTD"].get("periodo") == "CURRENT" and abs(s - y) > 5:
            out["errores"].append(f"{rep}: la suma de los meses (${s:,.2f}) no cuadra con el año a la fecha (${y:,.2f})")
        print(f"OK {rep} meses: {list(meses)}  suma+mes {s:,.2f} vs YTD {y:,.2f}")

    # Estructura comercial: hoja oficial de Alejandro (scripts/estructura.py) + árbol del portal
    import estructura
    E = estructura.construir()
    H = E["distribuidores"]
    mtd_act = set()
    for rep, k in (("compras", (1, 2)), ("ventas", (1,))):
        for r in out[rep]["MTD"]["filas"]:
            if sum(r[j] for j in k) > 0:
                mtd_act.add(r[0])

    def ancestro_activo(i, prof=0):
        p = padre.get(i)
        if not p or prof > 30:
            return None
        if p in H and H[p]["est"] == "activo":
            return p
        return ancestro_activo(p, prof + 1)

    for i, v in dist.items():
        v["pn"] = v.pop("n")                       # nombre en el portal
        if i in H:
            h = H[i]
            v.update(n=h["n"] or v["pn"], s=h["s"], c=h["c"], pr=h["pr"], nv=h["nv"], suc=h["suc"], est=h["est"], fb=h["fb"])
        else:
            anc = ancestro_activo(i)
            h = H.get(anc, {})
            v.update(n=v["pn"], s=h.get("s", ""), c=h.get("c", anc or ""), pr=h.get("pr", ""), nv="", suc=h.get("suc", ""),
                     est="nuevo" if i in mtd_act else "baja", fb="", via=anc or "")
    sin_hoja = sorted(i for i, v in dist.items() if v["est"] == "nuevo")
    if sin_hoja:
        out["errores"].append("Compraron este mes y no están en tu hoja: " + ", ".join(f"{i} {dist[i]['n']}" for i in sin_hoja))
    falt = [f"{i} {h['n']}" for i, h in H.items() if h["est"] == "activo" and i not in dist]
    out["sin_movimiento_2026"] = falt
    out["distribuidores"] = dist
    out["companias"] = E["companias"]
    out["subterritorios"] = E["subterritorios"]
    out["fuente_estructura"] = E["fuente"]
    out["errores"] += E["avisos"]

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

    mv = os.path.join(a.dir, "hycite_fondo_movimientos.json")
    if os.path.exists(mv):
        movs = json.load(open(mv))["filas"]
        out["fondo_reembolsos"] = sorted([{"fecha": (x.get("VoucherDate") or "")[:10], "periodo": x["Period"], "monto": R2(x["Amount"]),
                                            "desc": x.get("Description", ""), "recibos": bool(x.get("HasReceipts"))}
                                           for x in movs if "Reemb" in (x.get("Description") or "")], key=lambda x: x["fecha"], reverse=True)
        canc = {}
        for x in movs:
            if "Reemb" not in (x.get("Description") or ""):
                canc[x["Period"]] = R2(canc.get(x["Period"], 0) + x["Amount"])
        out["fondo_cancelaciones"] = canc
    os.makedirs(os.path.join(ROOT, "data", "historial"), exist_ok=True)
    dst = os.path.join(ROOT, "data", "latest.json")
    json.dump(out, open(dst, "w"), ensure_ascii=False, separators=(",", ":"))
    shutil.copy(dst, os.path.join(ROOT, "data", "historial", f"{a.fecha}.json"))
    idx_p = os.path.join(ROOT, "data", "historial", "index.json")
    idx = json.load(open(idx_p)) if os.path.exists(idx_p) else []
    idx = [x for x in idx if x["fecha"] != a.fecha] + [{"fecha": a.fecha, "tipo": a.tipo}]
    json.dump(sorted(idx, key=lambda x: x["fecha"], reverse=True), open(idx_p, "w"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("Estados:", Counter(v["est"] for v in dist.values()), "| sin subterritorio:", [i for i, v in dist.items() if not v["s"]])
    print("Avisos:", out["errores"] or "ninguno")
    print("Escrito", dst)


if __name__ == "__main__":
    sys.exit(main())
