# Proceso de actualización — Reportes Hycite CHASEP 13588

Dashboard: https://rp13588-eng.github.io/hycite-reportes/

## Cuándo corre
- **Semanal**: domingo ~9 pm (CDMX). Periodo `CURRENT` (mes y año a la fecha). `--tipo semanal`.
- **Cierre de mes**: día 1 de cada mes ~11 am. Periodo = mes recién cerrado `AAAAMM` (ej. 202610). `--tipo cierre`.

## Requisitos
- Chrome de la Mac mini = deviceId `a020add6-d2e4-434e-8d09-8a2a675c88f3` (si hay varios Chrome conectados, select_browser con ese).
- La tarea programada necesita acceso a la carpeta `~/Downloads/Hycite` (permiso de carpeta en la Mac).
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
| f | `Monthly Overrides` | `BONOS(3)` (cierre: 3; semanal: 1) → esperar ~20 s, revisar `window.__st` | `bono_AAAAMM.pdf` (estado de cuenta de bonos, MXN) |
| h | `Territory Purchases` y `Territory Volume` | `SERIE('compras_meses', [meses cerrados del año])` y `SERIE('ventas_meses', [...])` → ~10 s por mes; revisar `window.__se`. El build valida que la suma de meses + mes en curso = año a la fecha | `hycite_compras_meses.json`, `hycite_ventas_meses.json` |
| g | `TD Meeting Fund Payments` | `MOVS()` → esperar ~60 s, revisar `window.__fp` | `hycite_fondo_movimientos.json` (reembolsos y cancelaciones) |

`P` = `'CURRENT'` (semanal) o `'AAAAMM'` (cierre). Verificar que `meta.filas` > 0 y rango/periodo correctos.

3. Mac (osascript): `mkdir -p ~/Downloads/Hycite/<fecha> && mv ~/Downloads/hycite_*.json ~/Downloads/bono_*.pdf ~/Downloads/Hycite/<fecha>/`
4. Subir los 7 JSON al contenedor (device_stage_files) y correr:
   `python3 -I scripts/build_data.py --dir <carpeta> --fecha <AAAA-MM-DD> --tipo semanal|cierre`
   y luego `python3 -I scripts/parse_bonos.py <carpeta>` (lee los PDF de bonos; valida que el detalle por distribuidor cuadre con el resumen).
   El script valida que la suma de distribuidores cuadre con el total del territorio (tolerancia $1) y que el saldo del fondo cuadre mes a mes; los avisos salen en el dashboard.
5. Commit + push a `main` (GitHub Pages publica solo).
6. PDF para WhatsApp: `python3 -I scripts/pdf_reporte.py` → `out/Reporte_Hycite_CHASEP_<fecha>[_cierre].pdf` (carta, 2 páginas: compras/ventas/subterritorios y bonos/fondo) y `out/resumen.txt`. `out/` NO se sube al repo (bonos y fondo son privados).
7. WhatsApp (siempre, semanal y cierre): dos mensajes de texto al grupo "Reporte crecimiento Hycite" (120363431292937289@g.us): (a) compras y ventas USD mes/año vs año anterior + subterritorios >10% abajo + link; (b) bonos (último y estimado) y saldo del fondo NL en MXN. Revisar antes que no se haya enviado ya ese corte.
   Entrega del PDF: device_commit_files a `~/Downloads/Hycite/<carpeta del corte>/`, copiar con osascript a `~/.local/share/whatsapp-mcp/outbox/` y send_file al chat propio de Alejandro (12108151417@s.whatsapp.net) con el resumen como caption. Solo a Alejandro.

## Dashboard
- Descargar (botón arriba): el usuario escoge secciones de la pestaña actual → imagen para WhatsApp (1080 px, una por sección; en el celular abre compartir) o PDF carta. Respeta los filtros puestos.
- Bonos y Fondo: "Comparativo de años" en año total (año completo y mismo tramo ene–mes) o mes por mes (últimos 4 años).

## Datos
- Compras: mercancía (Merch), premiums (Prem) y misc, USD, actual y año anterior, propias del distribuidor. Dashboard: "Mercancía + premiums" (default) o "Solo mercancía".
- Ventas: volumen USD.
- Bonos y fondo: MXN (con USD al TC del portal).
- Subterritorio: `data/organigrama.json`; distribuidores nuevos heredan el de su patrocinador (árbol del portal, `ParentEntityCode`).

## Estructura de la red (fuente oficial)
- Hoja de Google **DISTRUBUCIONES CHASEP & MEJAB** (pestañas CHASEP, MEJAB, BAJAS). `scripts/estructura.py` la baja sola (export CSV).
- Compañía: columna COMPAÑÍA; si ese nombre cuenta a otro, se sube hasta el que se cuenta a sí mismo. Ximena Mejía es compañía propia. Pablo Partida → Alejandro Alcalá.
- Premier por subterritorio (Abdul 29365 cuenta en MEJAB).
- En el portal pero no en la hoja = baja (historial al subterritorio/compañía de su patrocinador). Si compró en el mes = aviso "falta en tu hoja".
- Niveles del portal: TD = Director de Territorio, L1–L4 = Distribuidor por nivel de precio, JV = Junior. Niveles de la hoja: PNL, ROYAL, BLUE, N1–N4, DJ.

## Bonos y fondo (privados, cifrados)
- En el repo público van CIFRADOS: `latest.json` e historial llevan `privado` (bonos, bono_estimado, fondo, reembolsos, cancelaciones) y `data/bonos_detalle.json` es {periodo: bloque cifrado}. El dashboard pide un PIN numérico para abrirlos.
- Esquema híbrido (`scripts/cripto.py`): `data/llave.json` trae la llave pública RSA (los cortes cifran sin PIN) y la privada cifrada con PBKDF2(PIN). Los cortes automáticos NO necesitan el PIN.
- Copia en claro solo en `out/privado.json` (no se sube) para `pdf_reporte.py` y los mensajes de WhatsApp.
- Cambiar PIN: `python3 -I scripts/cripto.py cambiar <PIN_ACTUAL> <PIN_NUEVO>` y commit de data/llave.json. Verificar: `python3 -I scripts/cripto.py probar <PIN>`.
- Nunca escribir el PIN en el repo, en commits ni en mensajes al grupo.
- Estado de cuenta de bonos: POST /Reports/Overrides (sessionid del mes, currency=true, exportformat=pdf|excel). Resumen por concepto en MXN con IVA; detalle por distribuidor en USD con IVA (× tipo de cambio del mes).
- Fondo NL: entra 1.75% de cada orden del territorio; salen reembolsos "Chasep Enterprise/Reemb Gtos PNL ... F.###" y cancelaciones de órdenes.

## Sesión del portal
- La sesión del portal vence aprox. 2 horas después de iniciar, aunque se recargue la página (el keep-alive solo evita el cierre por inactividad).
- Si al correr aparece la pantalla de login: no escribir credenciales; avisar a Alejandro y detenerse.
