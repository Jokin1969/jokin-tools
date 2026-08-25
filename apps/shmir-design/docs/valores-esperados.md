# Valores esperados (verificados por el responsable del proyecto)

Son las cifras contra las que deben escribirse los tests de cada paso, antes de
implementarlo (regla 5). Están aquí para que no se pierdan, no porque estén cubiertas:
la columna de estado dice qué se comprueba ya.

## Anatomía del transcrito

| | ratón `NM_011170.3` | humano `NM_000311.5` | Estado |
|---|---:|---:|---|
| Total | 2191 | 2435 | en `reference.py`, con test |
| 5'UTR | 1–184 (184 nt) | 1–67 (67 nt) | en `reference.py`, con test |
| CDS | 185–949 (765 nt) | 68–829 (762 nt) | en `reference.py`, con test |
| Proteína | 254 aa + TGA | 253 aa + TGA | comprobado como `cds/3 - 1` |
| 3'UTR | 950–2191 (**1242 nt**) | 830–2435 (**1606 nt**) | en `reference.py`, con test |
| GC 3'UTR | 43.2% | 37.4% | pendiente (paso 4) |

## Tiling y filtros duros

Ventanas de 22 nt sobre el 3'UTR, con umbrales GC 0.30–0.52, homopolímero máx 3,
asimetría ≥ +0.5 kcal/mol, sin motivo G4, U forzada en posición 1 de la guía:

| | ventanas | PASS | sitios independientes |
|---|---:|---:|---:|
| ratón | 1221 | **302** | 96 |
| humano | 1585 | **322** | 96 |

"Sitios independientes" = bloques de posiciones contiguas entre las que pasan.
Estado: pendiente (pasos 3 y 15; los filtros 4–8 ya están).

> Cifras **corregidas** tras el error de signo en la especificación de la asimetría.
> Las anteriores (181 / 231, 93 / 90 sitios) correspondían al signo invertido y no
> valen para nada: no las uses como comparación histórica.

## Señales de poliadenilación — **cubierto**

Ratón (3'UTR de 1242 nt):
- `AATAAA` en 288, a 949 nt del extremo → posible APA proximal
- `ATTAAA` en 1214, a 23 nt del extremo → señal terminal

Humano (3'UTR de 1606 nt):
- ninguna `AATAAA` canónica en todo el 3'UTR
- `ATTAAA` en 1582, a 19 nt del extremo → señal terminal
- la ventana en 1581 (`AATTAAACGAGCGAAGATGAGC`) queda excluida por solapar esa señal

Estado: implementado y con tests. Los tests que necesitan el 3'UTR completo (que la
única `AATAAA` del ratón sea la de 288, y que en el humano no haya ninguna) están
escritos y **se saltan** hasta que existan los FASTA.

## Bloque conservado ratón/humano

Existe **exactamente uno** de ≥22 nt:

```
TTTTCTATATTTGTAACTTTGCATGT          (26 nt, GC 23.1%)
  humano  1507–1532   (a 74 nt del extremo 3')
  ratón   1138–1163   (a 79 nt del extremo 3')
```

De sus 5 ventanas de 22 nt, la del offset 1 (`TTTCTATATTTGTAACTTTGCA`) debe fallar
**únicamente** por GC (0.227), con asimetría 2.98. Las otras cuatro fallan además por
homopolímero o asimetría negativa.

El bloque se reporta **siempre**, aunque ninguna ventana pase: la decisión de usarlo es
del usuario.

Estado: **implementado y con tests** (`conservation.py`). Cubierto sobre un andamio de
`N` con el bloque real en sus coordenadas reales: 26 nt, GC 23.1%, humano 1507–1532 (74
nt del extremo), ratón 1138–1163 (79 nt), 5 ventanas de 22 nt, y la del offset 1
fallando por GC 0.227 con homopolímero y G4 en `PASS`. El test sobre los 3'UTR completos
—que ese bloque sea el **único** de ≥22 nt— está escrito y se salta hasta que existan
los FASTA.

### Asimetría de las 5 ventanas (signo corregido)

| offset | asimetría | veredicto |
|---:|---:|---|
| 0 | −2.60 | FAIL (GC 0.227, homopolímero 4, asimetría) |
| 1 | −2.98 | FAIL (GC 0.227, asimetría) |
| 2 | −1.55 | FAIL (GC 0.227, asimetría) |
| 3 | **+0.77** | FAIL **solo** por GC (0.273) |
| 4 | −0.60 | FAIL (GC 0.273, asimetría) |

Los cinco valores están cubiertos por tests (`test_thermo.py`), igual que las dos guías
de cordura biológica que detectarían una inversión de signo.
