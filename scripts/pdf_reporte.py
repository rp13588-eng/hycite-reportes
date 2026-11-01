#!/usr/bin/env python3
"""PDF para WhatsApp del corte Hycite (CHASEP 13588) + resumen en texto.

Lee data/latest.json (lo genera build_data.py) y escribe:
  out/Reporte_Hycite_CHASEP_<fecha>.pdf   (carta, 2 páginas)
  out/resumen.txt                          (texto para WhatsApp / notificación)
Imprime un JSON con las rutas.

Uso: python3 -I scripts/pdf_reporte.py
El PDF NO se sube al repo (bonos y fondo son privados): out/ está en .gitignore.
"""
import html, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DASH = "https://rp13588-eng.github.io/hycite-reportes/"


def usd(v):
    return ("-$" if v < 0 else "$") + f"{abs(v):,.0f}"


def mxn(v):
    return ("-$" if v < 0 else "$") + f"{abs(v):,.2f}"


def pct(a, b):
    return None if not b else (a / b - 1) * 100


def fp(p):
    return "nuevo" if p is None else f"{p:+.1f}%"


def luz(p):
    return "nuevo" if p is None else "verde" if p >= 0 else "ambar" if p >= -10 else "rojo"


def periodo_label(d):
    per = d["compras"]["MTD"].get("periodo")
    if per and per != "CURRENT":
        y, m = int(per[:4]), int(per[4:])
    else:
        y, m = int(d["fecha_corte"][:4]), int(d["fecha_corte"][5:7])
    return y, m


def main():
    d = json.load(open(os.path.join(ROOT, "data", "latest.json")))
    y, m = periodo_label(d)
    cierre = d.get("tipo_corte") == "cierre"
    titulo = f"Cierre de {MES[m-1]} {y}" if cierre else f"Corte al {int(d['fecha_corte'][8:])} de {MES[int(d['fecha_corte'][5:7])-1]} {d['fecha_corte'][:4]}"
    mes_txt = f"{MES[m-1]} {y}" if cierre else f"{MES[m-1]} (al día {int(d['fecha_corte'][8:])})"
    C, V, dist = d["compras"], d["ventas"], d["distribuidores"]

    k = {}
    for per in ("MTD", "YTD"):
        t = C[per]["totales"]
        k[per] = dict(mp=t["M"] + t["P"], pmp=t["pM"] + t["pP"], m=t["M"], pm=t["pM"],
                      v=V[per]["totales"]["V"], pv=V[per]["totales"]["pV"])

    # Subterritorios: compras mercancía + premiums
    subs = {}
    for per in ("MTD", "YTD"):
        acc = defaultdict(lambda: [0.0, 0.0, set(), set()])
        for r in C[per]["filas"]:
            s = (dist.get(r[0]) or {}).get("s") or "SIN SUBTERRITORIO"
            a = acc[s]
            a[0] += r[1] + r[2]
            a[1] += r[4] + r[5]
            a[3].add(r[0])
            if r[1] + r[2] > 0:
                a[2].add(r[0])
        subs[per] = acc
    filas_sub = []
    for s, a in subs["MTD"].items():
        y_ = subs["YTD"].get(s, [0, 0, set(), set()])
        nv = (d.get("subterritorios", {}).get(s) or {}).get("nivel", "")
        filas_sub.append(dict(k=s, nv=nv, act=a[0], ant=a[1], p=pct(a[0], a[1]), dv=a[0] - a[1], a=len(a[2]), n=len(a[3]),
                              yact=y_[0], yant=y_[1], yp=pct(y_[0], y_[1])))
    for s, a in subs["YTD"].items():
        if s not in subs["MTD"]:
            nv = (d.get("subterritorios", {}).get(s) or {}).get("nivel", "")
            filas_sub.append(dict(k=s, nv=nv, act=0, ant=0, p=None, dv=0, a=0, n=0, yact=a[0], yant=a[1], yp=pct(a[0], a[1])))
    filas_sub.sort(key=lambda x: -x["act"])
    con_base = [x for x in filas_sub if x["ant"] > 0 or x["act"] > 0]
    suben = sorted([x for x in con_base if x["dv"] > 0], key=lambda x: -x["dv"])[:5]
    bajan = sorted([x for x in con_base if x["dv"] < 0], key=lambda x: x["dv"])[:5]

    bonos = sorted(d.get("bonos", []), key=lambda x: -x["periodo"])
    est = (d.get("bono_estimado") or [{}])[0]
    fondo = sorted(d.get("fondo", []), key=lambda x: -x["periodo"])
    f0 = fondo[0] if fondo else None
    avisos = d.get("errores", [])

    # ---------- HTML ----------
    E = html.escape

    def kpi(lbl, a, b, sub=""):
        p = pct(a, b)
        l = luz(p)
        return (f'<div class="kpi {l}"><div class="kl">{E(lbl)}</div><div class="kv">{usd(a)}</div>'
                f'<div class="kd">{"▲" if l == "verde" else "▼" if l in ("ambar", "rojo") else "●"} {fp(p)} '
                f'<span>vs {usd(b)} año pasado</span></div>{f"<div class=ks>{E(sub)}</div>" if sub else ""}</div>')

    def lista(xs, up):
        if not xs:
            return '<li class="vac">Ninguno</li>'
        return "".join(f'<li><b>{E(x["k"])}</b><span class="{"up" if up else "down"}">{usd(x["dv"])} · {fp(x["p"])}</span></li>' for x in xs)

    trs = "".join(
        f'<tr><td><span class="dot {luz(x["p"])}"></span><b>{E(x["k"])}</b> <span class="tag">{E(x["nv"])}</span></td>'
        f'<td class="n">{usd(x["act"])}</td><td class="n mut">{usd(x["ant"])}</td><td class="n {("up" if (x["p"] or 0) >= 0 else "down")}">{fp(x["p"])}</td>'
        f'<td class="n">{x["a"]}/{x["n"]}</td><td class="n">{usd(x["yact"])}</td><td class="n {("up" if (x["yp"] or 0) >= 0 else "down")}">{fp(x["yp"])}</td></tr>'
        for x in filas_sub)
    tot_tr = (f'<tr class="tot"><td>Total territorio 13588</td><td class="n">{usd(k["MTD"]["mp"])}</td><td class="n">{usd(k["MTD"]["pmp"])}</td>'
              f'<td class="n">{fp(pct(k["MTD"]["mp"], k["MTD"]["pmp"]))}</td><td></td><td class="n">{usd(k["YTD"]["mp"])}</td>'
              f'<td class="n">{fp(pct(k["YTD"]["mp"], k["YTD"]["pmp"]))}</td></tr>')

    bon_tr = "".join(f'<tr><td>{MES[b["periodo"] % 100 - 1].capitalize()} {b["periodo"] // 100}</td><td class="n">{mxn(b["total"])}</td>'
                     f'<td class="n mut">{usd(b["total_usd"])} USD</td></tr>' for b in bonos[:6])
    fon_tr = "".join(f'<tr><td>{MES[f["periodo"] % 100 - 1].capitalize()} {f["periodo"] // 100}</td><td class="n">{mxn(f["cargos"])}</td>'
                     f'<td class="n">{mxn(f["pagos"])}</td><td class="n"><b>{mxn(f["saldo"])}</b></td></tr>' for f in fondo[:6])
    av = "".join(f"<li>{E(a)}</li>" for a in avisos)

    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&display=swap" rel="stylesheet">
<style>
@page{{size:letter;margin:0}}
:root{{--navy:#064180;--blue:#006BB5;--tint:#EEF4FB;--ink:#16202C;--ink2:#5B6675;--line:#E2E7EE;--line2:#F0F3F7;
--verde:#1E7D45;--verdebg:#E7F4EC;--ambar:#8A6100;--ambarbg:#FFF4D6;--rojo:#B3261E;--rojobg:#FCE9E7}}
*{{box-sizing:border-box}}
body{{margin:0;font:11px/1.4 'Archivo',system-ui,sans-serif;color:var(--ink);font-variant-numeric:tabular-nums;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.pg{{width:8.5in;height:11in;padding:.45in .5in .4in;position:relative;page-break-after:always;overflow:hidden}}
.pg:last-child{{page-break-after:auto}}
header{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid var(--navy);padding-bottom:8px;margin-bottom:14px}}
.mark{{color:var(--navy);font-stretch:72%;font-weight:800;font-size:24px;line-height:1}}
.mark small{{display:block;font-stretch:100%;font-weight:500;font-size:11px;color:var(--ink2);margin-top:5px}}
.cut{{text-align:right;font-size:10px;color:var(--ink2)}} .cut b{{display:block;font-size:15px;color:var(--ink)}}
h2{{font-size:12.5px;margin:16px 0 7px;color:var(--navy);text-transform:uppercase;letter-spacing:.6px}}
h2 small{{text-transform:none;letter-spacing:0;color:var(--ink2);font-weight:500;font-size:10px;margin-left:6px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.kpi{{border:1px solid var(--line);border-left:5px solid var(--line);border-radius:8px;padding:9px 11px}}
.kpi.verde{{border-left-color:var(--verde)}} .kpi.ambar{{border-left-color:#E0A800}} .kpi.rojo{{border-left-color:var(--rojo)}}
.kl{{font-size:10px;color:var(--ink2);font-weight:600}} .kv{{font-size:21px;font-weight:800;margin:2px 0}}
.kd{{font-weight:700;font-size:11px}} .kd span{{font-weight:400;color:var(--ink2)}} .ks{{font-size:9.5px;color:var(--ink2);margin-top:2px}}
.verde .kd{{color:var(--verde)}} .ambar .kd{{color:var(--ambar)}} .rojo .kd{{color:var(--rojo)}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.box{{border:1px solid var(--line);border-radius:8px;padding:9px 12px}}
.box h3{{margin:0 0 6px;font-size:11px}} .box.up h3{{color:var(--verde)}} .box.dn h3{{color:var(--rojo)}}
ul.rk{{list-style:none;margin:0;padding:0}} ul.rk li{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--line2)}}
ul.rk li:last-child{{border-bottom:0}} .vac{{color:var(--ink2)}}
.up{{color:var(--verde)}} .down{{color:var(--rojo)}} .mut{{color:var(--ink2)}}
table{{width:100%;border-collapse:collapse;font-size:10px}}
th{{text-align:left;font-weight:600;color:var(--ink2);border-bottom:1.5px solid var(--line);padding:4px 5px;font-size:9.5px}}
td{{padding:3.4px 5px;border-bottom:1px solid var(--line2)}} .n{{text-align:right;white-space:nowrap}} th.n{{text-align:right}}
tr.tot td{{font-weight:800;border-top:1.5px solid var(--ink);border-bottom:0;background:var(--tint)}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:0}}
.dot.verde{{background:var(--verde)}} .dot.ambar{{background:#E0A800}} .dot.rojo{{background:var(--rojo)}} .dot.nuevo{{background:#9AA5B4}}
.tag{{font-size:8.5px;color:var(--ink2);font-weight:600}}
.money{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.big{{display:flex;gap:16px;margin-bottom:6px}} .big div{{flex:1;background:var(--tint);border-radius:7px;padding:7px 10px}}
.big span{{display:block;font-size:9.5px;color:var(--ink2);font-weight:600}} .big b{{font-size:16px}}
.aviso{{background:var(--ambarbg);border-radius:8px;padding:8px 12px;margin-top:12px;font-size:10px}} .aviso b{{color:var(--ambar)}}
.aviso ul{{margin:4px 0 0;padding-left:16px}}
footer{{position:absolute;left:.5in;right:.5in;bottom:.3in;display:flex;justify-content:space-between;font-size:9px;color:var(--ink2);border-top:1px solid var(--line);padding-top:5px}}
.ley{{font-size:9px;color:var(--ink2);margin-top:5px}}
</style></head><body>
<section class="pg">
<header><div class="mark">REPORTE HYCITE · CHASEP<small>Territorio 13588 · Alejandro Sepúlveda</small></div>
<div class="cut"><b>{E(titulo)}</b>Compras y ventas en USD · bonos y fondo en MXN</div></header>
<h2>Compras<small>mercancía + premiums, propias de cada distribuidor</small></h2>
<div class="grid">{kpi("Mes · " + mes_txt, k["MTD"]["mp"], k["MTD"]["pmp"], f"Solo mercancía: {usd(k['MTD']['m'])} ({fp(pct(k['MTD']['m'], k['MTD']['pm']))})")}
{kpi(f"Año · ene–{MES[m-1][:3]} {y}", k["YTD"]["mp"], k["YTD"]["pmp"], f"Solo mercancía: {usd(k['YTD']['m'])} ({fp(pct(k['YTD']['m'], k['YTD']['pm']))})")}
{kpi("Ventas del mes", k["MTD"]["v"], k["MTD"]["pv"], f"Año: {usd(k['YTD']['v'])} ({fp(pct(k['YTD']['v'], k['YTD']['pv']))})")}</div>
<h2>Subterritorios<small>compras del mes vs mismo mes del año pasado</small></h2>
<div class="two"><div class="box up"><h3>▲ Top 5 que crecen</h3><ul class="rk">{lista(suben, True)}</ul></div>
<div class="box dn"><h3>▼ Top 5 que caen</h3><ul class="rk">{lista(bajan, False)}</ul></div></div>
<table style="margin-top:10px"><thead><tr><th>Subterritorio</th><th class="n">Mes</th><th class="n">Año pasado</th><th class="n">Var.</th><th class="n">Activos</th><th class="n">Año a la fecha</th><th class="n">Var. año</th></tr></thead>
<tbody>{trs}{tot_tr}</tbody></table>
<div class="ley">● verde: arriba del año pasado · ● ámbar: hasta 10% abajo · ● rojo: más de 10% abajo · Activos: distribuidores con compra en el mes / con registro.</div>
<footer><span>Fuente: distributors.hycite.com · extraído {E(d.get('generado', ''))}</span><span>{DASH}</span></footer>
</section>
<section class="pg">
<header><div class="mark">BONOS Y FONDO NL<small>Territorio 13588 · Alejandro Sepúlveda</small></div><div class="cut"><b>{E(titulo)}</b>Montos en MXN</div></header>
<div class="money"><div>
<h2>Bonos mensuales</h2>
<div class="big"><div><span>Último pagado · {MES[bonos[0]['periodo'] % 100 - 1] if bonos else ''}</span><b>{mxn(bonos[0]['total']) if bonos else '—'}</b></div>
<div><span>Estimado · {MES[est.get('periodo', 0) % 100 - 1] if est else ''}</span><b>{mxn(est.get('total', 0))}</b></div></div>
<table><thead><tr><th>Mes</th><th class="n">Total MXN</th><th class="n">USD</th></tr></thead><tbody>{bon_tr}</tbody></table>
<div class="ley">El estimado del mes se ajusta hasta que Hycite procesa el bono (alrededor del día 14).</div>
</div><div>
<h2>Fondo Network Leader</h2>
<div class="big"><div><span>Saldo · {MES[f0['periodo'] % 100 - 1] if f0 else ''}</span><b>{mxn(f0['saldo']) if f0 else '—'}</b></div>
<div><span>Entró este mes</span><b>{mxn(f0['cargos']) if f0 else '—'}</b></div></div>
<table><thead><tr><th>Mes</th><th class="n">Entradas</th><th class="n">Salidas</th><th class="n">Saldo</th></tr></thead><tbody>{fon_tr}</tbody></table>
<div class="ley">Entra 1.75% de cada orden del territorio; salen reembolsos y cancelaciones.</div>
</div></div>
{f'<div class="aviso"><b>Avisos de validación</b><ul>{av}</ul></div>' if av else ''}
<footer><span>Documento privado · no reenviar fuera del equipo directivo</span><span>{DASH}</span></footer>
</section></body></html>"""

    out_dir = os.path.join(ROOT, "out")
    os.makedirs(out_dir, exist_ok=True)
    nombre = f"Reporte_Hycite_CHASEP_{d['fecha_corte']}{'_cierre' if cierre else ''}.pdf"
    pdf = os.path.join(out_dir, nombre)
    hp = os.path.join(out_dir, "reporte.html")
    open(hp, "w").write(doc)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto("file://" + hp)
        pg.wait_for_timeout(1500)
        pg.pdf(path=pdf, format="Letter", print_background=True, prefer_css_page_size=True)
        b.close()

    def linea(x):
        return f"{x['k']} {usd(x['dv'])} ({fp(x['p'])})"
    t = [f"📊 *Reporte Hycite CHASEP · {titulo}*",
         f"Compras {mes_txt}: {usd(k['MTD']['mp'])} USD ({fp(pct(k['MTD']['mp'], k['MTD']['pmp']))}) · solo mercancía {usd(k['MTD']['m'])} ({fp(pct(k['MTD']['m'], k['MTD']['pm']))})",
         f"Compras año: {usd(k['YTD']['mp'])} ({fp(pct(k['YTD']['mp'], k['YTD']['pmp']))}) · solo mercancía {usd(k['YTD']['m'])} ({fp(pct(k['YTD']['m'], k['YTD']['pm']))})",
         f"Ventas mes: {usd(k['MTD']['v'])} ({fp(pct(k['MTD']['v'], k['MTD']['pv']))}) · año {usd(k['YTD']['v'])} ({fp(pct(k['YTD']['v'], k['YTD']['pv']))})",
         "▲ Crecen: " + ("; ".join(linea(x) for x in suben) or "ninguno"),
         "▼ Caen: " + ("; ".join(linea(x) for x in bajan) or "ninguno"),
         (f"Bono {MES[bonos[0]['periodo'] % 100 - 1]}: {mxn(bonos[0]['total'])} MXN · estimado {MES[est.get('periodo', 0) % 100 - 1]}: {mxn(est.get('total', 0))}" if bonos else ""),
         (f"Fondo NL: {mxn(f0['saldo'])} MXN" if f0 else ""),
         (f"⚠️ Avisos: {len(avisos)} (ver PDF)" if avisos else "Sin avisos de validación"),
         DASH]
    txt = "\n".join(x for x in t if x)
    open(os.path.join(out_dir, "resumen.txt"), "w").write(txt)
    print(json.dumps({"pdf": pdf, "file": nombre, "resumen": os.path.join(out_dir, "resumen.txt")}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
