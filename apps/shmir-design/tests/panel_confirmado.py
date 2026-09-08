"""EL PANEL CONFIRMADO del ratón, declarado UNA vez.

**Por qué existe.** El panel estaba transcrito en seis ficheros de test. El 2026-09-07
cambió —al medir el homopolímero sobre la molécula y no sobre la ventana, errata nº 144—
y hubo que tocarlo en los seis: seis sitios que hay que acordarse de mover, que es la
forma exacta de la errata nº 28. Aquí se declara una vez y los tests lo importan.

No debilita nada: los seis no eran seis comprobaciones independientes del panel, eran el
MISMO dato escrito seis veces. Lo que cada test comprueba —que el CLI y la página
coinciden, que la cuota se cumple, que la retirada deja rastro— sigue siendo suyo.

**Si este panel cambia, cambia por una decisión.** No se toca para que la suite pase: se
toca cuando alguien decide moverlo, y entonces se apunta aquí abajo con su fecha y su
motivo, como está la de hoy.

## Historia

- **hasta 2026-09-07** — `(60, 143, 200, 359, 449, 553, 652, 735, 819, 1018, 1071)`.
- **desde 2026-09-07** — el de abajo. El homopolímero pasa a medirse sobre la guía y la
  pasajera —lo que se sintetiza— en vez de sobre la ventana diana (errata nº 144), y con
  eso caen cuatro: `3utr:143`, `3utr:652`, `3utr:735` y `3utr:819`.

  Entran **sus vecinos de al lado** —`3utr:144`, `3utr:673`, `3utr:736`, `3utr:818`—, y
  eso no es casualidad: el tramo de 4 lo crea una sustitución de la POSICIÓN 1, así que
  correr la ventana un nucleótido lo deshace.

  `3utr:144` entra por la **cuota de inmunes**, no por asimetría: el orden voraz cogía
  `3utr:187` (+4,06), que deja a `3utr:144` a 43 nt y a `3utr:200` a 13 —los dos por
  debajo del espaciado— y la cuota se quedaba en dos de tres. El conjunto que sí la
  cumple es `{60, 144, 200}`.

  Elegido por el responsable del proyecto entre tres paneles posibles: *«es el único que
  no toca ninguna decisión anterior: conserva la cuota de inmunes, mantiene la retirada
  de 3utr:10 y no cede en el espaciado»*. Coste aceptado: −0,72 de asimetría total y un
  distal menos.
"""

#: El panel, en el marco del 3'UTR. ONCE candidatos.
PANEL_UTR3 = (60, 144, 200, 359, 449, 553, 673, 736, 818, 1018, 1071)

#: Los tres inmunes al truncamiento por APA, en el marco del 3'UTR. Son los que están
#: por delante del corte DERIVADO del informe — no de un número tecleado.
INMUNES_UTR3 = (60, 144, 200)

#: Desfase del marco: `tx = 3utr + OFFSET`. Sale del CDS del fixture murino y se
#: comprueba en `tests/test_la_cuota_de_inmunes_es_un_REQUISITO.py`.
OFFSET_TX = 949

#: El panel en el marco de LO TILADO (transcrito). Se DERIVA, no se transcribe: una
#: posición sin marco es válida en dos sitios y sólo en uno es la ventana que se quiso
#: (errata nº 133).
PANEL_TX = tuple(p + OFFSET_TX for p in PANEL_UTR3)
