"""La tabla de PolyA_DB murina, PARA LOS TESTS, leída del fichero del gestor.

Hasta 2026-08-27 esto era `apa.POLYA_DB_PRNP`, una constante del código, y los tests la
importaban de ahí. La tabla es DATO —15 PAS con su PSE y su AvgRPM— y su sitio es
`data/reference/polya_db_mouse.tsv`, con su línea en el manifiesto y su md5.

Se carga UNA vez y se reparte, por dos razones que no son la velocidad:

  - si cada test la cargara a su manera, la suite dejaría de comprobar el camino que
    corre la app y pasaría a comprobar el que se escribió en el test;
  - y el fichero es lo que la app lee, así que un fichero mal registrado tiene que
    hacer fallar la suite, no dejarla verde contra una copia en memoria.

Un test que se quede sin fichero se SALTA de forma visible (`skipUnless(HAY_TABLA)`), no
se inventa una tabla: sería la regla 1 por la puerta de los datos medidos.
"""

from shmir_design.apa import find_polyadb

#: La tabla del ratón, o `None` si el fichero no está. `None` NO es una tabla vacía.
TABLA = find_polyadb(species="raton")

#: Para `@unittest.skipUnless`.
HAY_TABLA = TABLA is not None

FALTA = "NOT_RUN: falta data/reference/polya_db_mouse.tsv"
