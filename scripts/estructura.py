#!/usr/bin/env python3
"""Estructura comercial desde la hoja "DISTRUBUCIONES CHASEP & MEJAB" (Google Sheets, fuente oficial de Alejandro).

Reglas (confirmadas con Alejandro, 26-oct-2026):
- Subterritorio, nivel, sponsor y sucursal: tal cual la hoja.
- Compañía: la columna COMPAÑÍA dice a quién le cuenta; si ese nombre a su vez cuenta a otro, se sube
  hasta el que se cuenta a sí mismo (ej. Sebastián Saldaña -> Samuel Díaz -> Luis Oñate -> Zarazua).
- Premier: por subterritorio (CHASEP: ARLISSA, DAMARO, FORZA, HEALTHY, HENKEM, HL AVANTRA, HL IMPACT,
  HL VENTURE, HLC; MEJAB: MEJAB, CYCLICO, JONPHILIP). Abdul (29365) cuenta en MEJAB.
- Pestaña BAJAS = bajas. Quien está en el portal pero no en la hoja = baja (su historial suma al
  subterritorio/compañía de su patrocinador en el portal). Si compró en el mes en curso = "nuevo, falta en la hoja".
"""
import csv, io, json, re, subprocess, unicodedata

SHEET_ID = "1Z0X2oGDuehvK660O_l5Y9CwYYbbWQmEIY-fi3GOQE6I"
GIDS = {"CHASEP": "0", "MEJAB": "242031749", "BAJAS": "557672347"}
# Nombres de COMPAÑÍA que ya no están en la hoja -> a quién cuentan (confirmado por Alejandro)
OVERRIDES = {"ANGELA CONSTAZA COLCHADO DE ANDA": "86205"}
RANGO = {"PNL": 7, "ROYAL": 6, "BLUE": 5, "N1": 4, "N2": 3, "N3": 2, "N4": 1, "DJ": 0}


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z ]", " ", s).split()


def bajar(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    out = subprocess.run(["curl", "-sfL", "--max-time", "30", url], capture_output=True, check=True).stdout
    return list(csv.DictReader(io.StringIO(out.decode("utf-8-sig"))))


def limpiar(r):
    return {(k or "").strip(): (v or "").strip() for k, v in r.items()}


def cargar():
    activos, bajas = {}, {}
    for hoja in ("CHASEP", "MEJAB"):
        for r in map(limpiar, bajar(GIDS[hoja])):
            if r.get("ID_Distribuidor"):
                activos[r["ID_Distribuidor"]] = r
    for r in map(limpiar, bajar(GIDS["BAJAS"])):
        i = r.get("ID Distribuidor") or r.get("ID_Distribuidor")
        if i:
            bajas[i] = r
    return activos, bajas


def construir():
    activos, bajas = cargar()
    todos = {**bajas, **activos}
    avisos = []

    def resolver(nombre):
        key = nombre.upper().strip()
        if key in OVERRIDES:
            return OVERRIDES[key]
        t = set(norm(nombre))
        cand = []
        for i, r in todos.items():
            u = set(norm(r.get("Nombre")))
            cand.append((len(t & u) / max(1, len(t)), i in activos, i))
        cand.sort(reverse=True)
        if not cand or cand[0][0] < 0.6:
            return None
        return cand[0][2]

    cache = {}
    def comp_directa(i):
        if i not in cache:
            cache[i] = resolver(todos[i].get("COMPAÑÍA", "")) or i
        return cache[i]

    def lider(i):
        vistos = [i]
        while True:
            c = comp_directa(vistos[-1])
            if c == vistos[-1] or c in vistos or c not in todos:
                return vistos[-1]
            vistos.append(c)

    subs = {}
    for i, r in activos.items():
        subs.setdefault(r["Subterritorio"], []).append(i)
    premier_sub = {}
    for s, ids in subs.items():
        votos = {}
        for i in ids:
            p = activos[i]["PREMIER"].upper()
            votos[p] = votos.get(p, 0) + 1
        premier_sub[s] = max(votos, key=votos.get)
    premier_sub["FORZA"] = "CHASEP"
    lider_sub = {s: max(ids, key=lambda i: RANGO.get(activos[i]["NIVEL"], -1)) for s, ids in subs.items()}

    dist = {}
    for i, r in todos.items():
        c = lider(i)
        sub = r.get("Subterritorio", "")
        dist[i] = {
            "n": r.get("Nombre", ""), "s": sub, "pr": premier_sub.get(sub, r.get("PREMIER", "").upper()),
            "c": c, "cd": comp_directa(i), "nv": r.get("NIVEL", ""), "sp": r.get("SPONSOR", ""),
            "suc": r.get("SUCURSAL", "") if i in activos else "", "est": "activo" if i in activos else "baja",
            "fb": r.get("FECHA BAJA", "") if i in bajas else "",
        }
        if resolver(r.get("COMPAÑÍA", "")) is None and r.get("COMPAÑÍA"):
            avisos.append(f"{i} {r.get('Nombre')}: no encontré la compañía '{r.get('COMPAÑÍA')}' en la hoja")
    companias = {}
    for i, d in dist.items():
        if d["est"] != "activo":
            continue
        c = d["c"]
        companias.setdefault(c, {"lider": c, "nombre": todos[c]["Nombre"] if c in todos else c,
                                 "s": dist[c]["s"] if c in dist else d["s"], "miembros": []})
        companias[c]["miembros"].append(i)
    subterritorios = {s: {"premier": premier_sub[s], "lider": lider_sub[s], "lider_nombre": activos[lider_sub[s]]["Nombre"],
                          "nivel": activos[lider_sub[s]]["NIVEL"]} for s in subs}
    return {"distribuidores": dist, "companias": companias, "subterritorios": subterritorios,
            "fuente": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}", "avisos": avisos}


if __name__ == "__main__":
    e = construir()
    print(len(e["distribuidores"]), "en hoja,", len(e["companias"]), "compañías,", len(e["subterritorios"]), "subterritorios")
    for s, v in sorted(e["subterritorios"].items()):
        cs = [c for c in e["companias"].values() if c["s"] == s]
        print(f"{s:11} {v['premier']:6} {v['nivel']:5} líder {v['lider']} | {len(cs)} compañías")
    print("avisos:", e["avisos"])
