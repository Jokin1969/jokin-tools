# Anexo — los 95 sitios elegibles, uno a uno

Complemento de `resultados-medidos.md` §3, que sólo da el panel. Aquí está **la piscina
entera**: un sitio que no está en el panel sigue teniendo veredictos, y esconderlo deja al
lector sin poder discutir la selección.

`[DERIVADO 2026-09-08]` **Todo lo de este anexo se ha vuelto a calcular** corriendo el
pipeline sobre los ficheros versionados del repositorio — el mismo camino que la página
(`presentation.page_run`), sobre `NM_011170.3` con la anatomía de su GenBank.

## Lo que hay detrás de las cifras

- **2170** ventanas tiladas sobre el transcrito entero (2191 nt).
- **95** sitios elegibles: bloques de ventanas contiguas que superan todos los
  filtros. El representante de cada sitio es `Site.best` — el de mejor asimetría—, que es el
  mismo criterio con el que la selección ordena.
- **11** en el panel; espaciado mínimo **50 nt** entre elegidos.
- **Frontera de inmunidad al APA: `3utr:251`** (derivada del informe, no
  tecleada). Por delante de ahí la ventana se conserva en las dos isoformas.
- **17** sitios inmunes, y **todos** en el tercio proximal.
- **Colisión de seed**: `mmu-`, ventana **2-8**, nivel **ambos**, contra `mature.fa` del
  depósito (1988 maduros, 1593 seeds distintas, espacio 16384 → **tasa base 9,7 %**).
  Ninguna colisión es del **núcleo** de abundantes ni de la familia **miR-30**.
- **Autositios**: apariciones del núcleo de 6 nt de la guía **en el propio 3'UTR**. **1 es lo
  esperado** (el suyo); **2 significa un segundo sitio en su propio mensajero**, y eso cambia
  la cinética de su knockdown.

## Lo que este anexo NO trae, y por qué

- **Carga de off-targets con percentil**: necesita `transcriptoma_3utr.fa`, que **no está en
  el repositorio**. `NOT_RUN`, y `NOT_RUN` no es `PASS`.
- **Especificidad por BLAST**: la corrida es externa. La registrada `[REGISTRO 2026-09-05]`
  cubrió 88 candidatos y tumbó **uno** (`tx:1746`, contra variantes de *Adar*), que **no está
  en el panel**.
- **Empalme (SpliceAI)**: su unidad es el par candidato × intrón, no cabe como columna por
  candidato. La corrida versionada es del panel **anterior** (ver §2 de este anexo).

Por tanto **ningún candidato de esta tabla está aprobado**: con frentes en `NOT_RUN` el
veredicto de todos es `INCOMPLETE` y la selección es **provisional**.

---

## 1. El panel de once, con todo lo derivado

| 3'UTR | tx | asim. neta | GC | APA | heptámero (2-8) | núcleo | autositios | colisión de seed |
|---|---|---|---|---|---|---|---|---|
| `3utr:60` | `tx:1009` | +5.15 | 0.45 | **INMUNE** | `AATTGAA` | `TCAATT` | 1 (`3utr:75`) | — |
| `3utr:144` | `tx:1093` | +3.69 | 0.50 | **INMUNE** | `TCTACTG` | `AGTAGA` | 1 (`3utr:159`) | pasajera: miR-3474-5p, pasajera: miR-6945-5p |
| `3utr:200` | `tx:1149` | +3.80 | 0.50 | **INMUNE** | `TTAGCAC` | `TGCTAA` | 1 (`3utr:215`) | pasajera: miR-215-3p |
| `3utr:359` | `tx:1308` | +4.82 | 0.45 | techo | `TTGGTTG` | `AACCAA` | 1 (`3utr:374`) | guía: miR-5615-5p |
| `3utr:449` | `tx:1398` | +5.32 | 0.32 | techo | `TTAGTAA` | `TACTAA` | 2 (`3utr:464`, `3utr:1033`) | — |
| `3utr:553` | `tx:1502` | +5.86 | 0.41 | techo | `TAAAGAT` | `TCTTTA` | 2 (`3utr:460`, `3utr:568`) | — |
| `3utr:673` | `tx:1622` | +4.42 | 0.41 | techo | `AAGAAAC` | `TTTCTT` | 2 (`3utr:458`, `3utr:688`) | — |
| `3utr:736` | `tx:1685` | +4.26 | 0.36 | techo | `TAGAAGT` | `CTTCTA` | 1 (`3utr:751`) | — |
| `3utr:818` | `tx:1767` | +4.55 | 0.50 | techo | `TTCCCAC` | `TGGGAA` | 2 (`3utr:147`, `3utr:833`) | — |
| `3utr:1018` | `tx:1967` | +6.65 | 0.50 | techo + estérico penalizado | `TTAGTAC` | `TACTAA` | 2 (`3utr:464`, `3utr:1033`) | — |
| `3utr:1071` | `tx:2020` | +4.28 | 0.50 | techo | `AATCCTA` | `AGGATT` | 1 (`3utr:1086`) | — |

**Núcleos de seed compartidos DENTRO DEL PANEL:** `TACTAA` → `3utr:449` y `3utr:1018`.

Sobre **los 95 sitios** son 8 núcleos compartidos, que afectan a 17 sitios: `AGGAGA` (`3utr:578`, `3utr:595`), `AGGCAA` (`3utr:343`, `3utr:473`, `3utr:851`), `CCAAAG` (`3utr:812`, `3utr:1077`), `GTACAA` (`3utr:309`, `3utr:651`), `GTGACA` (`3utr:316`, `3utr:322`), `TACTAA` (`3utr:449`, `3utr:1018`), `TGGATT` (`3utr:567`, `3utr:922`), `TTCCAA` (`3utr:810`, `3utr:1075`).

> Los dos que comparten núcleo **no son dos apuestas independientes en el eje de
> off-targets**, aunque el espaciado los dé por buenos: el espaciado mide nucleótidos, no
> seeds. Y sus autositios son **los mismos dos**, o sea que cada uno es el segundo sitio del
> otro.

---

## 2. Los 95 sitios elegibles

`esp. N nt de tx:X` = ese sitio **cabe por filtros** y queda fuera del panel porque está a
menos de 50 nt de un elegido. `cabe, no elegido` = pasa el espaciado con todo el panel y
no entró por ranking o por cuota.

| # | 3'UTR | tx | ventanas | tercio | cruda | penal | neta | GC | APA | autosit. | colisión de seed | estado |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `3utr:10` | `tx:959` | 5 | proximal | +4.33 | 0.00 | +4.33 | 0.50 | INMUNE | 1 | — | cabe, no elegido |
| 2 | `3utr:20` | `tx:969` | 1 | proximal | +1.93 | 0.00 | +1.93 | 0.50 | INMUNE | 3 | — | esp. 40 nt de `tx:1009` |
| 3 | `3utr:53` | `tx:1002` | 3 | proximal | +3.45 | 0.00 | +3.45 | 0.50 | INMUNE | 1 | — | esp. 7 nt de `tx:1009` |
| 4 | `3utr:60` | `tx:1009` | 6 | proximal | +5.15 | 0.00 | +5.15 | 0.45 | INMUNE | 1 | — | **PANEL** |
| 5 | `3utr:69` | `tx:1018` | 2 | proximal | +3.80 | 0.00 | +3.80 | 0.45 | INMUNE | 1 | pasajera: miR-130b-5p, pasajera: miR-7014-3p | esp. 9 nt de `tx:1009` |
| 6 | `3utr:75` | `tx:1024` | 1 | proximal | +2.03 | 0.00 | +2.03 | 0.41 | INMUNE | 1 | — | esp. 15 nt de `tx:1009` |
| 7 | `3utr:83` | `tx:1032` | 6 | proximal | +3.12 | 0.00 | +3.12 | 0.45 | INMUNE | 2 | pasajera: miR-203-5p | esp. 23 nt de `tx:1009` |
| 8 | `3utr:90` | `tx:1039` | 1 | proximal | +1.31 | 0.00 | +1.31 | 0.45 | INMUNE | 1 | guía: miR-7229-3p | esp. 30 nt de `tx:1009` |
| 9 | `3utr:144` | `tx:1093` | 6 | proximal | +3.69 | 0.00 | +3.69 | 0.50 | INMUNE | 1 | pasajera: miR-3474-5p, pasajera: miR-6945-5p | **PANEL** |
| 10 | `3utr:157` | `tx:1106` | 4 | proximal | +3.69 | 0.00 | +3.69 | 0.45 | INMUNE | 2 | — | esp. 13 nt de `tx:1093` |
| 11 | `3utr:163` | `tx:1112` | 5 | proximal | +3.36 | 0.00 | +3.36 | 0.50 | INMUNE | 2 | — | esp. 19 nt de `tx:1093` |
| 12 | `3utr:171` | `tx:1120` | 2 | proximal | +3.96 | 0.00 | +3.96 | 0.50 | INMUNE | 1 | — | esp. 27 nt de `tx:1093` |
| 13 | `3utr:176` | `tx:1125` | 1 | proximal | +1.35 | 0.00 | +1.35 | 0.50 | INMUNE | 1 | — | esp. 24 nt de `tx:1149` |
| 14 | `3utr:183` | `tx:1132` | 1 | proximal | +0.59 | 0.00 | +0.59 | 0.50 | INMUNE | 1 | guía: miR-12198-3p | esp. 17 nt de `tx:1149` |
| 15 | `3utr:185` | `tx:1134` | 1 | proximal | +1.60 | 0.00 | +1.60 | 0.50 | INMUNE | 2 | pasajera: miR-204-5p, pasajera: miR-211-5p | esp. 15 nt de `tx:1149` |
| 16 | `3utr:187` | `tx:1136` | 2 | proximal | +4.06 | 0.00 | +4.06 | 0.50 | INMUNE | 2 | — | esp. 13 nt de `tx:1149` |
| 17 | `3utr:200` | `tx:1149` | 4 | proximal | +3.80 | 0.00 | +3.80 | 0.50 | INMUNE | 1 | pasajera: miR-215-3p | **PANEL** |
| 18 | `3utr:309` | `tx:1258` | 4 | proximal | +2.73 | 0.00 | +2.73 | 0.45 | techo | 2 | — | cabe, no elegido |
| 19 | `3utr:316` | `tx:1265` | 1 | proximal | +2.00 | 0.00 | +2.00 | 0.50 | techo | 2 | — | esp. 43 nt de `tx:1308` |
| 20 | `3utr:320` | `tx:1269` | 2 | proximal | +1.60 | 0.00 | +1.60 | 0.50 | techo | 1 | — | esp. 39 nt de `tx:1308` |
| 21 | `3utr:322` | `tx:1271` | 1 | proximal | +1.84 | 0.00 | +1.84 | 0.50 | techo | 2 | — | esp. 37 nt de `tx:1308` |
| 22 | `3utr:324` | `tx:1273` | 2 | proximal | +1.43 | 0.00 | +1.43 | 0.45 | techo | 1 | guía: miR-599-3p, pasajera: miR-7678-5p | esp. 35 nt de `tx:1308` |
| 23 | `3utr:329` | `tx:1278` | 7 | proximal | +4.39 | 0.00 | +4.39 | 0.45 | techo | 1 | — | esp. 30 nt de `tx:1308` |
| 24 | `3utr:338` | `tx:1287` | 3 | proximal | +3.79 | 0.00 | +3.79 | 0.36 | techo | 1 | — | esp. 21 nt de `tx:1308` |
| 25 | `3utr:343` | `tx:1292` | 1 | proximal | +1.80 | 0.00 | +1.80 | 0.36 | techo | 3 | pasajera: miR-379-3p, pasajera: miR-411-3p | esp. 16 nt de `tx:1308` |
| 26 | `3utr:352` | `tx:1301` | 4 | proximal | +2.49 | 0.00 | +2.49 | 0.45 | techo | 1 | — | esp. 7 nt de `tx:1308` |
| 27 | `3utr:359` | `tx:1308` | 2 | proximal | +4.82 | 0.00 | +4.82 | 0.45 | techo | 1 | guía: miR-5615-5p | **PANEL** |
| 28 | `3utr:364` | `tx:1313` | 3 | proximal | +3.69 | 0.00 | +3.69 | 0.45 | techo | 1 | — | esp. 5 nt de `tx:1308` |
| 29 | `3utr:373` | `tx:1322` | 2 | proximal | +2.99 | 0.00 | +2.99 | 0.45 | techo | 1 | — | esp. 14 nt de `tx:1308` |
| 30 | `3utr:426` | `tx:1375` | 1 | medio | +2.17 | 0.00 | +2.17 | 0.50 | techo | 2 | — | esp. 23 nt de `tx:1398` |
| 31 | `3utr:449` | `tx:1398` | 16 | medio | +5.32 | 0.00 | +5.32 | 0.32 | techo | 2 | — | **PANEL** |
| 32 | `3utr:465` | `tx:1414` | 1 | medio | +2.29 | 0.00 | +2.29 | 0.36 | techo | 1 | — | esp. 16 nt de `tx:1398` |
| 33 | `3utr:468` | `tx:1417` | 1 | medio | +0.62 | 0.00 | +0.62 | 0.36 | techo | 2 | — | esp. 19 nt de `tx:1398` |
| 34 | `3utr:473` | `tx:1422` | 2 | medio | +2.53 | 0.00 | +2.53 | 0.45 | techo | 3 | — | esp. 24 nt de `tx:1398` |
| 35 | `3utr:479` | `tx:1428` | 2 | medio | +3.85 | 0.00 | +3.85 | 0.45 | techo | 1 | — | esp. 30 nt de `tx:1398` |
| 36 | `3utr:516` | `tx:1465` | 2 | medio | +3.27 | 0.00 | +3.27 | 0.41 | techo | 1 | — | esp. 37 nt de `tx:1502` |
| 37 | `3utr:518` | `tx:1467` | 1 | medio | +1.27 | 0.00 | +1.27 | 0.45 | techo | 1 | guía: miR-7059-3p | esp. 35 nt de `tx:1502` |
| 38 | `3utr:522` | `tx:1471` | 6 | medio | +3.96 | 0.00 | +3.96 | 0.41 | techo | 1 | — | esp. 31 nt de `tx:1502` |
| 39 | `3utr:529` | `tx:1478` | 1 | medio | +1.30 | 0.00 | +1.30 | 0.36 | techo | 2 | — | esp. 24 nt de `tx:1502` |
| 40 | `3utr:545` | `tx:1494` | 3 | medio | +2.20 | 0.00 | +2.20 | 0.50 | techo | 3 | — | esp. 8 nt de `tx:1502` |
| 41 | `3utr:548` | `tx:1497` | 1 | medio | +1.76 | 0.00 | +1.76 | 0.50 | techo | 1 | — | esp. 5 nt de `tx:1502` |
| 42 | `3utr:553` | `tx:1502` | 6 | medio | +5.86 | 0.00 | +5.86 | 0.41 | techo | 2 | — | **PANEL** |
| 43 | `3utr:559` | `tx:1508` | 2 | medio | +1.00 | 0.00 | +1.00 | 0.41 | techo | 1 | — | esp. 6 nt de `tx:1502` |
| 44 | `3utr:567` | `tx:1516` | 2 | medio | +2.17 | 0.00 | +2.17 | 0.41 | techo | 2 | — | esp. 14 nt de `tx:1502` |
| 45 | `3utr:573` | `tx:1522` | 3 | medio | +4.42 | 0.00 | +4.42 | 0.45 | techo | 1 | — | esp. 20 nt de `tx:1502` |
| 46 | `3utr:578` | `tx:1527` | 2 | medio | +2.25 | 0.00 | +2.25 | 0.41 | techo | 2 | — | esp. 25 nt de `tx:1502` |
| 47 | `3utr:582` | `tx:1531` | 3 | medio | +2.93 | 0.00 | +2.93 | 0.41 | techo | 2 | — | esp. 29 nt de `tx:1502` |
| 48 | `3utr:588` | `tx:1537` | 1 | medio | +0.66 | 0.00 | +0.66 | 0.45 | techo | 1 | — | esp. 35 nt de `tx:1502` |
| 49 | `3utr:595` | `tx:1544` | 3 | medio | +1.87 | 0.00 | +1.87 | 0.50 | techo | 2 | — | esp. 42 nt de `tx:1502` |
| 50 | `3utr:651` | `tx:1600` | 2 | medio | +4.17 | 0.00 | +4.17 | 0.45 | techo | 2 | pasajera: miR-7039-5p | esp. 22 nt de `tx:1622` |
| 51 | `3utr:653` | `tx:1602` | 2 | medio | +3.69 | 0.00 | +3.69 | 0.45 | techo | 1 | pasajera: miR-7020-5p | esp. 20 nt de `tx:1622` |
| 52 | `3utr:657` | `tx:1606` | 3 | medio | +2.13 | 0.00 | +2.13 | 0.41 | techo | 2 | guía: miR-6365-3p, guía: miR-7073-3p | esp. 16 nt de `tx:1622` |
| 53 | `3utr:664` | `tx:1613` | 4 | medio | +2.79 | 0.00 | +2.79 | 0.41 | techo | 1 | — | esp. 9 nt de `tx:1622` |
| 54 | `3utr:673` | `tx:1622` | 6 | medio | +4.42 | 0.00 | +4.42 | 0.41 | techo | 2 | — | **PANEL** |
| 55 | `3utr:678` | `tx:1627` | 1 | medio | +1.47 | 0.00 | +1.47 | 0.32 | techo | 1 | — | esp. 5 nt de `tx:1622` |
| 56 | `3utr:684` | `tx:1633` | 1 | medio | +1.23 | 0.00 | +1.23 | 0.36 | techo | 1 | — | esp. 11 nt de `tx:1622` |
| 57 | `3utr:691` | `tx:1640` | 3 | medio | +2.90 | 0.00 | +2.90 | 0.32 | techo | 1 | — | esp. 18 nt de `tx:1622` |
| 58 | `3utr:693` | `tx:1642` | 1 | medio | +1.80 | 0.00 | +1.80 | 0.32 | techo | 1 | — | esp. 20 nt de `tx:1622` |
| 59 | `3utr:721` | `tx:1670` | 2 | medio | +2.00 | 0.00 | +2.00 | 0.41 | techo | 1 | — | esp. 15 nt de `tx:1685` |
| 60 | `3utr:727` | `tx:1676` | 4 | medio | +1.52 | 0.00 | +1.52 | 0.45 | techo | 2 | — | esp. 9 nt de `tx:1685` |
| 61 | `3utr:734` | `tx:1683` | 3 | medio | +3.85 | 0.00 | +3.85 | 0.41 | techo | 2 | — | esp. 2 nt de `tx:1685` |
| 62 | `3utr:736` | `tx:1685` | 2 | medio | +4.26 | 0.00 | +4.26 | 0.36 | techo | 1 | — | **PANEL** |
| 63 | `3utr:748` | `tx:1697` | 1 | medio | +1.48 | 0.00 | +1.48 | 0.32 | techo | 1 | guía: miR-6947-5p | esp. 12 nt de `tx:1685` |
| 64 | `3utr:750` | `tx:1699` | 2 | medio | +2.06 | 0.00 | +2.06 | 0.32 | techo | 1 | — | esp. 14 nt de `tx:1685` |
| 65 | `3utr:762` | `tx:1711` | 7 | medio | +3.52 | 0.00 | +3.52 | 0.41 | techo | 1 | guía: miR-7233-3p | esp. 26 nt de `tx:1685` |
| 66 | `3utr:771` | `tx:1720` | 4 | medio | +3.63 | 0.00 | +3.63 | 0.36 | techo | 1 | guía: miR-33-3p, pasajera: miR-881-5p | esp. 35 nt de `tx:1685` |
| 67 | `3utr:775` | `tx:1724` | 1 | medio | +1.47 | 0.00 | +1.47 | 0.32 | techo | 2 | — | esp. 39 nt de `tx:1685` |
| 68 | `3utr:777` | `tx:1726` | 1 | medio | +3.96 | 0.00 | +3.96 | 0.32 | techo | 1 | — | esp. 41 nt de `tx:1685` |
| 69 | `3utr:789` | `tx:1738` | 2 | medio | +1.64 | 0.00 | +1.64 | 0.41 | techo | 1 | pasajera: miR-7041-3p | esp. 29 nt de `tx:1767` |
| 70 | `3utr:791` | `tx:1740` | 1 | medio | +1.87 | 0.00 | +1.87 | 0.45 | techo | 2 | pasajera: miR-7664-3p | esp. 27 nt de `tx:1767` |
| 71 | `3utr:797` | `tx:1746` | 4 | medio | +4.26 | 0.00 | +4.26 | 0.45 | techo | 2 | pasajera: miR-3552-5p | esp. 21 nt de `tx:1767` |
| 72 | `3utr:802` | `tx:1751` | 1 | medio | +1.52 | 0.00 | +1.52 | 0.50 | techo | 1 | — | esp. 16 nt de `tx:1767` |
| 73 | `3utr:810` | `tx:1759` | 1 | medio | +2.81 | 0.00 | +2.81 | 0.45 | techo | 2 | — | esp. 8 nt de `tx:1767` |
| 74 | `3utr:812` | `tx:1761` | 1 | medio | +0.90 | 0.00 | +0.90 | 0.45 | techo | 3 | — | esp. 6 nt de `tx:1767` |
| 75 | `3utr:818` | `tx:1767` | 2 | medio | +4.55 | 0.00 | +4.55 | 0.50 | techo | 2 | — | **PANEL** |
| 76 | `3utr:820` | `tx:1769` | 3 | distal | +3.23 | 0.00 | +3.23 | 0.45 | techo | 1 | guía: miR-7211-5p | esp. 2 nt de `tx:1767` |
| 77 | `3utr:825` | `tx:1774` | 4 | distal | +3.63 | 0.00 | +3.63 | 0.36 | techo | 1 | — | esp. 7 nt de `tx:1767` |
| 78 | `3utr:832` | `tx:1781` | 6 | distal | +2.75 | 0.00 | +2.75 | 0.45 | techo | 1 | pasajera: miR-6903-5p | esp. 14 nt de `tx:1767` |
| 79 | `3utr:840` | `tx:1789` | 1 | distal | +1.47 | 0.00 | +1.47 | 0.32 | techo | 3 | — | esp. 22 nt de `tx:1767` |
| 80 | `3utr:846` | `tx:1795` | 4 | distal | +3.12 | 0.00 | +3.12 | 0.36 | techo | 2 | — | esp. 28 nt de `tx:1767` |
| 81 | `3utr:851` | `tx:1800` | 1 | distal | +3.19 | 0.00 | +3.19 | 0.32 | techo | 3 | guía: miR-216c-3p, pasajera: miR-669g-5p | esp. 33 nt de `tx:1767` |
| 82 | `3utr:900` | `tx:1849` | 5 | distal | +5.15 | 1.00 | +4.15 | 0.45 | techo+p | 1 | — | cabe, no elegido |
| 83 | `3utr:904` | `tx:1853` | 2 | distal | +2.33 | 1.00 | +1.33 | 0.41 | techo+p | 2 | — | cabe, no elegido |
| 84 | `3utr:914` | `tx:1863` | 1 | distal | +1.43 | 1.00 | +0.43 | 0.50 | techo+p | 1 | — | cabe, no elegido |
| 85 | `3utr:922` | `tx:1871` | 3 | distal | +2.90 | 1.00 | +1.90 | 0.45 | techo+p | 2 | pasajera: miR-6999-3p | cabe, no elegido |
| 86 | `3utr:1018` | `tx:1967` | 2 | distal | +7.65 | 1.00 | +6.65 | 0.50 | techo+p | 2 | — | **PANEL** |
| 87 | `3utr:1020` | `tx:1969` | 1 | distal | +4.95 | 1.00 | +3.95 | 0.45 | techo+p | 1 | — | esp. 2 nt de `tx:1967` |
| 88 | `3utr:1025` | `tx:1974` | 3 | distal | +3.73 | 1.00 | +2.73 | 0.41 | techo+p | 1 | — | esp. 7 nt de `tx:1967` |
| 89 | `3utr:1029` | `tx:1978` | 1 | distal | +1.97 | 1.00 | +0.97 | 0.45 | techo+p | 1 | pasajera: miR-101c-3p | esp. 11 nt de `tx:1967` |
| 90 | `3utr:1071` | `tx:2020` | 2 | distal | +4.28 | 0.00 | +4.28 | 0.50 | techo | 1 | — | **PANEL** |
| 91 | `3utr:1075` | `tx:2024` | 1 | distal | +2.57 | 0.00 | +2.57 | 0.45 | techo | 2 | — | esp. 4 nt de `tx:2020` |
| 92 | `3utr:1077` | `tx:2026` | 1 | distal | +1.52 | 0.00 | +1.52 | 0.50 | techo | 3 | — | esp. 6 nt de `tx:2020` |
| 93 | `3utr:1081` | `tx:2030` | 1 | distal | +3.06 | 0.00 | +3.06 | 0.50 | techo | 2 | — | esp. 10 nt de `tx:2020` |
| 94 | `3utr:1103` | `tx:2052` | 1 | distal | +3.29 | 0.00 | +3.29 | 0.50 | techo | 1 | — | esp. 32 nt de `tx:2020` |
| 95 | `3utr:1111` | `tx:2060` | 7 | distal | +3.07 | 0.00 | +3.07 | 0.41 | techo | 2 | — | esp. 40 nt de `tx:2020` |

---

## 3. Guías y dianas de los 95

**La posición 1 de la guía es CONVENIO**, no dato: se fuerza una U para que AGO2 cargue esa
hebra. Por eso todas empiezan por U, y esa base **no entra en ninguna comparación de
identidad**. La diana va en ADN, tal como está en el transcrito.

| 3'UTR | guía (5'→3', ARN) | diana (ADN) |
|---|---|---|
| `3utr:10` | `UAAUGCGAAGGAACAAGCAGGA` | `TCCTGCTTGTTCCTTCGCATTC` |
| `3utr:20` | `UAGACCACGAGAAUGCGAAGGA` | `TCCTTCGCATTCTCGTGGTCTA` |
| `3utr:53` | `UAGAGCUACAGGUGGAUAACCC` | `GGGTTATCCACCTGTAGCTCTT` |
| `3utr:60` ★ | `UAAUUGAAAGAGCUACAGGUGG` | `CCACCTGTAGCTCTTTCAATTG` |
| `3utr:69` | `UAACCACCUCAAUUGAAAGAGC` | `GCTCTTTCAATTGAGGTGGTTC` |
| `3utr:75` | `UAAUGAGAACCACCUCAAUUGA` | `TCAATTGAGGTGGTTCTCATTC` |
| `3utr:83` | `UGAAGCAAGAAUGAGAACCACC` | `GGTGGTTCTCATTCTTGCTTCT` |
| `3utr:90` | `UACACAGAGAAGCAAGAAUGAG` | `CTCATTCTTGCTTCTCTGTGTC` |
| `3utr:144` ★ | `UUCUACUGUACAUUUCCCAGGG` | `CCCTGGGAAATGTACAGTAGAC` |
| `3utr:157` | `UAAAGAGCAACUGGUCUACUGU` | `ACAGTAGACCAGTTGCTCTTTG` |
| `3utr:163` | `UUGAAGCAAAGAGCAACUGGUC` | `GACCAGTTGCTCTTTGCTTCAG` |
| `3utr:171` | `UAAGGGACCUGAAGCAAAGAGC` | `GCTCTTTGCTTCAGGTCCCTTT` |
| `3utr:176` | `UCAUCAAAGGGACCUGAAGCAA` | `TTGCTTCAGGTCCCTTTGATGG` |
| `3utr:183` | `UCAGACUCCAUCAAAGGGACCU` | `AGGTCCCTTTGATGGAGTCTGT` |
| `3utr:185` | `UGACAGACUCCAUCAAAGGGAC` | `GTCCCTTTGATGGAGTCTGTCA` |
| `3utr:187` | `UAUGACAGACUCCAUCAAAGGG` | `CCCTTTGATGGAGTCTGTCATC` |
| `3utr:200` ★ | `UUUAGCACUGGCUGAUGACAGA` | `TCTGTCATCAGCCAGTGCTAAC` |
| `3utr:309` | `UUUGUACUCUGGGUACAAGUCA` | `TGACTTGTACCCAGAGTACAAG` |
| `3utr:316` | `UUGUCACCUUGUACUCUGGGUA` | `TACCCAGAGTACAAGGTGACAG` |
| `3utr:320` | `UUCACUGUCACCUUGUACUCUG` | `CAGAGTACAAGGTGACAGTGAC` |
| `3utr:322` | `UUGUCACUGUCACCUUGUACUC` | `GAGTACAAGGTGACAGTGACAC` |
| `3utr:324` | `UUGUGUCACUGUCACCUUGUAC` | `GTACAAGGTGACAGTGACACAT` |
| `3utr:329` | `UUUACAUGUGUCACUGUCACCU` | `AGGTGACAGTGACACATGTAAC` |
| `3utr:338` | `UUAUGCUAAGUUACAUGUGUCA` | `TGACACATGTAACTTAGCATAG` |
| `3utr:343` | `UUUGCCUAUGCUAAGUUACAUG` | `CATGTAACTTAGCATAGGCAAA` |
| `3utr:352` | `UUAGAACCCUUUGCCUAUGCUA` | `TAGCATAGGCAAAGGGTTCTAC` |
| `3utr:359` ★ | `UUUGGUUGUAGAACCCUUUGCC` | `GGCAAAGGGTTCTACAACCAAA` |
| `3utr:364` | `UCUUCUUUGGUUGUAGAACCCU` | `AGGGTTCTACAACCAAAGAAGC` |
| `3utr:373` | `UAAACAGUGGCUUCUUUGGUUG` | `CAACCAAAGAAGCCACTGTTTG` |
| `3utr:426` | `UGUGGAUGCUCUAGCUAUCCCA` | `TGGGATAGCTAGAGCATCCACA` |
| `3utr:449` ★ | `UUUAGUAAAGAAAGAAUUCCAC` | `GTGGAATTCTTTCTTTACTAAC` |
| `3utr:465` | `UAAUCAGCUAUCGUUUGUUAGU` | `ACTAACAAACGATAGCTGATTG` |
| `3utr:468` | `UUUCAAUCAGCUAUCGUUUGUU` | `AACAAACGATAGCTGATTGAAG` |
| `3utr:473` | `UUUGCCUUCAAUCAGCUAUCGU` | `ACGATAGCTGATTGAAGGCAAC` |
| `3utr:479` | `UUUCCUGUUGCCUUCAAUCAGC` | `GCTGATTGAAGGCAACAGGAAA` |
| `3utr:516` | `UUUGCUUUCAACGUCAGUAGGA` | `TCCTACTGACGTTGAAAGCAAA` |
| `3utr:518` | `UGUUUGCUUUCAACGUCAGUAG` | `CTACTGACGTTGAAAGCAAACC` |
| `3utr:522` | `UAAAGGUUUGCUUUCAACGUCA` | `TGACGTTGAAAGCAAACCTTTG` |
| `3utr:529` | `UAAUGAACAAAGGUUUGCUUUC` | `GAAAGCAAACCTTTGTTCATTC` |
| `3utr:545` | `UAUUCUAGUGCCCUGGGAAUGA` | `TCATTCCCAGGGCACTAGAATG` |
| `3utr:548` | `UAUCAUUCUAGUGCCCUGGGAA` | `TTCCCAGGGCACTAGAATGATC` |
| `3utr:553` ★ | `UUAAAGAUCAUUCUAGUGCCCU` | `AGGGCACTAGAATGATCTTTAG` |
| `3utr:559` | `UCAAGGCUAAAGAUCAUUCUAG` | `CTAGAATGATCTTTAGCCTTGC` |
| `3utr:567` | `UAAUCCAAGCAAGGCUAAAGAU` | `ATCTTTAGCCTTGCTTGGATTG` |
| `3utr:573` | `UUAGUUCAAUCCAAGCAAGGCU` | `AGCCTTGCTTGGATTGAACTAG` |
| `3utr:578` | `UUCUCCUAGUUCAAUCCAAGCA` | `TGCTTGGATTGAACTAGGAGAT` |
| `3utr:582` | `UAAGAUCUCCUAGUUCAAUCCA` | `TGGATTGAACTAGGAGATCTTG` |
| `3utr:588` | `UAGAGUCAAGAUCUCCUAGUUC` | `GAACTAGGAGATCTTGACTCTG` |
| `3utr:595` | `UUCUCCUCAGAGUCAAGAUCUC` | `GAGATCTTGACTCTGAGGAGAG` |
| `3utr:651` | `UUUGUACCUUAACCAUCCCUCC` | `GGAGGGATGGTTAAGGTACAAA` |
| `3utr:653` | `UCUUUGUACCUUAACCAUCCCU` | `AGGGATGGTTAAGGTACAAAGG` |
| `3utr:657` | `UUAGCCUUUGUACCUUAACCAU` | `ATGGTTAAGGTACAAAGGCTAG` |
| `3utr:664` | `UAAGUUUCUAGCCUUUGUACCU` | `AGGTACAAAGGCTAGAAACTTG` |
| `3utr:673` ★ | `UAAGAAACUCAAGUUUCUAGCC` | `GGCTAGAAACTTGAGTTTCTTC` |
| `3utr:678` | `UAAAUGAAGAAACUCAAGUUUC` | `GAAACTTGAGTTTCTTCATTTC` |
| `3utr:684` | `UAGACAGAAAUGAAGAAACUCA` | `TGAGTTTCTTCATTTCTGTCTC` |
| `3utr:691` | `UAAUUGUGAGACAGAAAUGAAG` | `CTTCATTTCTGTCTCACAATTA` |
| `3utr:693` | `UAUAAUUGUGAGACAGAAAUGA` | `TCATTTCTGTCTCACAATTATC` |
| `3utr:721` | `UAUAGGGCAGAAGCUAAUUCUA` | `TAGAATTAGCTTCTGCCCTATG` |
| `3utr:727` | `UAGAAACAUAGGGCAGAAGCUA` | `TAGCTTCTGCCCTATGTTTCTG` |
| `3utr:734` | `UGAAGUACAGAAACAUAGGGCA` | `TGCCCTATGTTTCTGTACTTCT` |
| `3utr:736` ★ | `UUAGAAGUACAGAAACAUAGGG` | `CCCTATGTTTCTGTACTTCTAT` |
| `3utr:748` | `UAUCCAGUUCAAAUAGAAGUAC` | `GTACTTCTATTTGAACTGGATA` |
| `3utr:750` | `UUUAUCCAGUUCAAAUAGAAGU` | `ACTTCTATTTGAACTGGATAAC` |
| `3utr:762` | `UAUUGUCUCUCUGUUAUCCAGU` | `ACTGGATAACAGAGAGACAATC` |
| `3utr:771` | `UAAUGUUUAGAUUGUCUCUCUG` | `CAGAGAGACAATCTAAACATTC` |
| `3utr:775` | `UAGAGAAUGUUUAGAUUGUCUC` | `GAGACAATCTAAACATTCTCTT` |
| `3utr:777` | `UUAAGAGAAUGUUUAGAUUGUC` | `GACAATCTAAACATTCTCTTAG` |
| `3utr:789` | `UUUAUCUGCAGCCUAAGAGAAU` | `ATTCTCTTAGGCTGCAGATAAG` |
| `3utr:791` | `UUCUUAUCUGCAGCCUAAGAGA` | `TCTCTTAGGCTGCAGATAAGAG` |
| `3utr:797` | `UUACUUCUCUUAUCUGCAGCCU` | `AGGCTGCAGATAAGAGAAGTAG` |
| `3utr:802` | `UGAGCCUACUUCUCUUAUCUGC` | `GCAGATAAGAGAAGTAGGCTCC` |
| `3utr:810` | `UUUGGAAUGGAGCCUACUUCUC` | `GAGAAGTAGGCTCCATTCCAAA` |
| `3utr:812` | `UCUUUGGAAUGGAGCCUACUUC` | `GAAGTAGGCTCCATTCCAAAGT` |
| `3utr:818` ★ | `UUUCCCACUUUGGAAUGGAGCC` | `GGCTCCATTCCAAAGTGGGAAA` |
| `3utr:820` | `UCUUUCCCACUUUGGAAUGGAG` | `CTCCATTCCAAAGTGGGAAAGA` |
| `3utr:825` | `UAAUUUCUUUCCCACUUUGGAA` | `TTCCAAAGTGGGAAAGAAATTC` |
| `3utr:832` | `UCUAGCAGAAUUUCUUUCCCAC` | `GTGGGAAAGAAATTCTGCTAGC` |
| `3utr:840` | `UAAACAAUGCUAGCAGAAUUUC` | `GAAATTCTGCTAGCATTGTTTA` |
| `3utr:846` | `UUGAUUUAAACAAUGCUAGCAG` | `CTGCTAGCATTGTTTAAATCAG` |
| `3utr:851` | `UUUGCCUGAUUUAAACAAUGCU` | `AGCATTGTTTAAATCAGGCAAA` |
| `3utr:900` | `UUAUCGCAGUUUAUGUCUGCUG` | `CAGCAGACATAAACTGCGATAG` |
| `3utr:904` | `UAAGCUAUCGCAGUUUAUGUCU` | `AGACATAAACTGCGATAGCTTC` |
| `3utr:914` | `UGUGCAAGCUGAAGCUAUCGCA` | `TGCGATAGCTTCAGCTTGCACT` |
| `3utr:922` | `UAAUCCACAGUGCAAGCUGAAG` | `CTTCAGCTTGCACTGTGGATTT` |
| `3utr:1018` ★ | `UUUAGUACUGGAUGGAACGGCC` | `GGCCGTTCCATCCAGTACTAAA` |
| `3utr:1020` | `UAUUUAGUACUGGAUGGAACGG` | `CCGTTCCATCCAGTACTAAATG` |
| `3utr:1025` | `UUAAGCAUUUAGUACUGGAUGG` | `CCATCCAGTACTAAATGCTTAC` |
| `3utr:1029` | `UACGGUAAGCAUUUAGUACUGG` | `CCAGTACTAAATGCTTACCGTG` |
| `3utr:1071` ★ | `UAAUCCUACGGAACUGAGUGCA` | `TGCACTCAGTTCCGTAGGATTC` |
| `3utr:1075` | `UUUGGAAUCCUACGGAACUGAG` | `CTCAGTTCCGTAGGATTCCAAA` |
| `3utr:1077` | `UCUUUGGAAUCCUACGGAACUG` | `CAGTTCCGTAGGATTCCAAAGC` |
| `3utr:1081` | `UUCUGCUUUGGAAUCCUACGGA` | `TCCGTAGGATTCCAAAGCAGAC` |
| `3utr:1103` | `UAGAUUCAAAGACCAGCUAGGG` | `CCCTAGCTGGTCTTTGAATCTG` |
| `3utr:1111` | `UGUACAUGCAGAUUCAAAGACC` | `GGTCTTTGAATCTGCATGTACT` |

★ = en el panel de once.

---

## 4. Las dos arquitecturas de intrón, re-derivadas

`[DERIVADO 2026-09-08]` **Plegado** (ViennaRNA 2.7.2, función de partición) de las
**22** construcciones del panel de HOY — once candidatos × dos intrones,
0 fallidas. Fracción media **sin aparear** de cada elemento:

| elemento | `mvm_actual` | `intron_quimerico` | gana |
|---|---|---|---|
| donante | 0.889 | 0.533 | `mvm_actual` |
| punto de ramificacion | 0.257 | 0.355 | `intron_quimerico` |
| tracto polipirimidinas | 0.594 | 0.547 | `mvm_actual` |
| aceptor | 0.836 | 0.994 | `intron_quimerico` |

**El contraste queda 2-2 y no se redondea a un ganador.**

- **El menos accesible de los cuatro es el mismo en las dos arquitecturas: el
  `punto_de_ramificacion`.** Se DERIVA, no está escrito en el código: con un
  tercer intrón puede ser otro. Que coincida lo convierte en propiedad del **elemento**,
  no del intrón.
- La cifra del punto de ramificación es el **peor** de sus candidatos, y no tienen los
  mismos: el MVM tiene **1** y el quimérico **2**
  (mejor 0.585). Con el mejor de cada uno el quimérico gana más holgado.
- **La guía no mueve ninguno de los cuatro**: entre las once construcciones de una misma
  arquitectura la dispersión máxima es **0.43 %**. Este eje **no discrimina entre
  candidatos** — compara arquitecturas.

`[REGISTRO 2026-09-05]` **SpliceAI**, re-derivado del fichero versionado (20 construcciones,
panel anterior). Puntuación de los sitios **legítimos**:

| | media | rango | **dispersión entre guías** |
|---|---|---|---|
| `mvm_actual` donante | 0.873 | 0.783–0.925 | **18.1 %** |
| `mvm_actual` aceptor | 0.831 | 0.778–0.858 | **10.3 %** |
| `intron_quimerico` donante | 0.966 | 0.956–0.973 | **1.8 %** |
| `intron_quimerico` aceptor | 0.990 | 0.985–0.994 | **0.9 %** |

> **Lo que vale no es que el quimérico puntúe más alto, es que NO SE MUEVE.** La media
> compara dos moléculas; la dispersión dice qué pasa al cambiar de guía.

Excluyendo `3utr:10` —retirado del panel— la dispersión del donante del MVM sigue en
**11.1 %** frente al **1,8 %** del quimérico: el argumento no depende del retirado.

**Crípticos INTRÓNICOS por encima del 5 % del donante legítimo de su propia construcción:**
dos en `mvm_actual` —un aceptor al **11,9 %** y un donante al **6,1 %**—, los dos **sólo en la
construcción de `3utr:10`**, que es el candidato retirado. En `intron_quimerico`, **ninguno**.

**Geometría y elementos**, derivados de cada intrón:

| | `mvm_actual` | `intron_quimerico` |
|---|---|---|
| intrón vacío | 82 nt | 133 nt |
| intrón montado (módulo de 149 nt) | 296 nt | 282 nt |
| donante | `GTAAGG` | `GTAAGT` (consenso exacto) |
| pirimidinas contiguas del tracto | 9 | 11 |
| candidatos a punto de ramificación | 1 | 2 (uno es `CTGAC`, el canónico de mamífero) |
| donante → ramificación (montado) | 256 nt | 249–253 nt |

**La geometría NO discrimina** —256 frente a 249–253— y lo que se intercala se DERIVA de
cada intrón: el MVM mete módulo **más espaciadores** (214 nt) y el quimérico **sólo el
módulo** (149). Aplicarle al quimérico el 214 del MVM da 314–318 y es la **errata nº 106**,
retirada: una magnitud derivada de dos construcciones distintas no se compara sin
comprobar que las dos se montan igual (principio nº 40).

> **RIESGO COMPARTIDO, y va junto o se lee mal:** el punto de ramificación es el elemento
> menos accesible **en las dos**, y la distancia donante→ramificación queda **fuera del rango
> típico de mamífero (18–100 nt) en las dos**. Es el candidato a **causa común** si el empalme
> falla en las dos arquitecturas, y **no lo arregla cambiar de intrón**: lo movería acortar lo
> que se intercala.
