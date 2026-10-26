# Proceso de actualización — Reportes Hycite CHASEP 13588

Dashboard: https://rp13588-eng.github.io/hycite-reportes/

## Cuándo corre
- **Semanal**: domingo ~9 pm (CDMX). Periodo `CURRENT` (mes y año a la fecha). `--tipo semanal`.
- **Cierre de mes**: día 1 de cada mes ~11 am. Periodo = mes recién cerrado `AAAAMM` (ej. 202610). `--tipo cierre`.

## Requisitos
- Mac mini encendida, Chrome abierto con la extensión Claude in Chrome y una pestaña de distributors.hycite.com con sesión iniciada.
- LaunchAgent `com.chasep.hycite-keepalive` recarga la pestaña cada 9 min (~/Claude/hycite-keepalive).
- Chrome: "Descargas automáticas" permitidas para distributors.hycite.com.
- Si el portal pide login (auth.hycite.com): NO escribir credenciales. Avisar a Alejandro y detenerse.

## Pasos
1. Chrome: abrir pestaña nueva en https://distributors.hycite.com (cerrar el modal de mensajes con "No").
2. En cada página pegar `scripts/extract.js` (define `IR`, `R`, `D`); tras cada `IR(...)` esperar ~7 s y volver a pegarlo.

| Paso | Página (`IR`) | Acción | Archivo |
|---|---|---|---|
| a | `Territory Purchases` | `R('MTD',P)` → esperar 8 s → `D('compras_MTD')`; `R('YTD',P)` → 10 s → `D('compras_YTD')` | compras |
| b | `Territory Volume` | igual → `D('ventas_MTD')`, `D('ventas_YTD')` | ventas |
| c | `Monthly Overrides` | `D('bonos')` (50 registros/página) | bonos |
| d | `Estimated Monthly Overrides` | `D('bono_estimado')` | bono estimado |
| e | `Network Leader Meeting Fund` | `D('fondo_nl')` | fondo |

`P` = `'CURRENT'` (semanal) o `'AAAAMM'` (cierre). Verificar que `meta.filas` > 0 y rango/periodo correctos.

3. Mac (osascript): `mkdir -p ~/Downloads/Hycite/<fecha> && mv ~/Downloads/hycite_*.json ~/Downloads/Hycite/<fecha>/`
4. Subir los 7 JSON al contenedor (device_stage_files) y correr:
   `python3 -I scripts/build_data.py --dir <carpeta> --fecha <AAAA-MM-DD> --tipo semanal|cierre`
   El script valida que la suma de distribuidores cuadre con el total del territorio (tolerancia $1) y que el saldo del fondo cuadre mes a mes; los avisos salen en el dashboard.
5. Commit + push a `main` (GitHub Pages publica solo).

## Datos
- Compras: mercancía (Merch), premiums (Prem) y misc, USD, actual y año anterior, propias del distribuidor. Dashboard: "Mercancía + premiums" (default) o "Solo mercancía".
- Ventas: volumen USD.
- Bonos y fondo: MXN (con USD al TC del portal).
- Subterritorio: `data/organigrama.json`; distribuidores nuevos heredan el de su patrocinador (árbol del portal, `ParentEntityCode`).
