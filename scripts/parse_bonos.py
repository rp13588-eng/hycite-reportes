#!/usr/bin/env python3
"""Lee los estados de cuenta de bonos mensuales (PDF del portal, /Reports/Overrides, currency=true)
y genera data/bonos_detalle.json: resumen por concepto (MXN con IVA) y aportación por distribuidor (USD con IVA).
Uso: python3 -I scripts/parse_bonos.py <carpeta con bono_AAAAMM.pdf>
"""
import glob, json, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MON = r'\(?-?\$[\d,]+\.\d\d\)?'
num = lambda s: float(s.replace('$', '').replace(',', '').replace('(', '-').replace(')', '').replace('--', '-'))
SECC = {'Purchase Discount': 'Purchase Discount', 'Subtract Child Distributor Purchase Discounts': 'PD_resta',
        'Recruiter Bonus': 'Recruiter Bonus', 'Price Level Rebate': 'Price Level Rebate', 'Elite Bonus': 'Elite Bonus',
        'Territory Director Premium Rebate': 'Territory Director Premium Rebate', 'Finance Charge Rebate': 'Finance Charge Rebate',
        'Leadership Bonus': 'Leadership Bonus'}
LINEA = re.compile(r'^\s*(\d{5})-(.*?)\s{2,}(\d+)?\s*(.*)$')


def resumen(t):
    s = t[t.index('Monthly Override Summary'):]
    r = {'conceptos': {}, 'reserva': {}, 'ajustes': {}}
    sec = None
    for l in [l for l in s.splitlines() if l.strip()]:
        ls = l.strip(); v = re.findall(MON, l)
        if ls.startswith('Monthly Overrides (Factura)'): sec = 'c'; continue
        if ls.startswith('TOTAL:'): r['subtotal'], r['iva'], r['total_factura'] = num(v[0]), num(v[1]), num(v[2]); sec = None; continue
        if ls.startswith('Reserve Adjustment') and not v: sec = 'r'; continue
        if ls.startswith('Total Reserve Adjustment'): r['reserva_total'] = num(v[-1]); sec = None; continue
        if ls.startswith('TOTAL PAYOUTS FOR MONTH'): r['total_pagado'] = num(v[-1]); continue
        if ls.startswith('Adjustments to Override'): sec = 'a'; continue
        if ls.startswith('Total Adjustments'): r['ajustes_total'] = num(v[-1]); sec = None; continue
        if ls.startswith('Total Override Remaining'): r['neto'] = num(v[-1]); continue
        if not v: continue
        desc = re.split(r'\s{2,}', ls)[0]
        {'c': r['conceptos'], 'r': r['reserva'], 'a': r['ajustes']}.get(sec, {})[desc] = num(v[-1])
    if abs(sum(r['conceptos'].values()) - r['total_factura']) > 0.05:
        raise SystemExit(f'conceptos {sum(r["conceptos"].values())} != total factura {r["total_factura"]}')
    m = re.search(r'NOT IN GOOD STANDING[^\n]*', t)
    r['aviso'] = m.group(0).strip() if m else ''
    return r


def detalle(t):
    """Aportación por distribuidor y concepto, en USD con IVA (como viene en el PDF)."""
    cuerpo = t[:t.index('Reserve Adjustment - ')] if 'Reserve Adjustment - ' in t else t[:t.index('Monthly Override Summary')]
    sec, pct, pend = None, None, []
    out = {}
    def add(i, c, v):
        out.setdefault(i, {}); out[i][c] = round(out[i].get(c, 0) + v, 2)
    for l in cuerpo.splitlines():
        ls = l.strip()
        if ls in SECC: sec = SECC[ls]; continue
        if sec == 'Purchase Discount':
            m = re.search(r'\*\s*([\d.]+)%\s*=', l)
            if m and not LINEA.match(l):
                pct = float(m.group(1)) / 100
                for i, v in pend: add(i, 'Purchase Discount', v * pct)
                pend = []; continue
        m = LINEA.match(l)
        if not m or not sec: continue
        i = m.group(1); v = re.findall(MON, l)
        if not v: continue
        if sec == 'Purchase Discount' and '=' not in l:
            pend.append((i, num(v[0])))
        elif sec in ('PD_resta',):
            add(i, 'Purchase Discount', num(v[-1]))
        elif sec == 'Purchase Discount':
            add(i, 'Purchase Discount', num(v[-1]))
        else:
            add(i, sec, num(v[-1]))
    return out


def main():
    d = sys.argv[1]
    dst = os.path.join(ROOT, 'data', 'bonos_detalle.json')
    out = json.load(open(dst)) if os.path.exists(dst) else {}
    lt = json.load(open(os.path.join(ROOT, 'data', 'latest.json')))
    tc = {str(x['periodo']): x.get('tc') for x in lt.get('bonos', [])}
    for f in sorted(glob.glob(os.path.join(d, 'bono_*.pdf'))):
        p = re.search(r'bono_(\d{6})', f).group(1)
        t = subprocess.run(['pdftotext', '-layout', f, '-'], capture_output=True, text=True).stdout
        r = resumen(t); r['tc'] = tc.get(p)
        det = detalle(t)
        # validación: suma por concepto (USD) * TC ≈ resumen MXN
        chk = {}
        for c, mx in r['conceptos'].items():
            usd = sum(v.get(c, 0) for v in det.values())
            if r['tc'] and mx:
                dif = abs(usd * r['tc'] - mx) / mx
                chk[c] = round(dif * 100, 2)
        r['detalle_usd'] = det
        r['validacion_pct'] = chk
        out[p] = r
        malos = {c: x for c, x in chk.items() if x > 1.5}
        print(p, 'pagado', r['total_pagado'], 'distribuidores', len(det), 'difs%', malos or 'OK')
    json.dump(dict(sorted(out.items())), open(dst, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('Escrito', dst, len(out), 'meses')


if __name__ == '__main__':
    main()
