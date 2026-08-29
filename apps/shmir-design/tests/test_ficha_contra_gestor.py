"""La ficha de obtención dice los MISMOS ficheros que el gestor pide. Principio nº 11.

La ficha es PROSA sobre un hecho que el código sabe: qué ficheros cierran un frente. Y
cuando código y prosa hablan del mismo hecho sin nada que los ate, la prosa se queda
atrás — y es la que alguien lee, porque es la que le dice qué descargar.

EL CASO QUE LO OBLIGA. `fraccion_isoforma_larga.toml` describía PolyA_DB de arriba abajo
—su URL, sus dos tablas, sus columnas por nombre, el aviso de las coordenadas genómicas—
y el ÚNICO fichero que listaba era `apa_medido_{slug}.tsv`, cuyo cargador lee otro
formato: tres columnas `posicion/fraccion/nombre`, con la posición ya convertida. O sea
que **lo que el texto mandaba preparar y lo que el cargador sabe leer eran cosas
distintas**, y no había forma de enterarse: la ficha se lee, el cargador se ejecuta, y
nadie los pone uno al lado del otro.

Consecuencia real, no teórica: eso es lo que hizo creer que la tabla de PolyA_DB ya tenía
hueco en el gestor. Tenía la FICHA, no el cargador.

Estos tests cruzan las dos listas en las dos direcciones, por especie.
"""

import unittest

from shmir_design.obtencion import load_all, resolve_ficha
from shmir_design.species import SPECIES, required_files, resolve


def _por_ficha(especie) -> dict[str, set[str]]:
    """Ficha → los ficheros que el GESTOR pide para ella, ya resueltos a esa especie.

    Con los HERMANOS obligatorios dentro (`filenames`): el `.tbl` de un `.out` no es un
    fichero de adorno — sin el, el `.out` no se puede validar.
    """
    mapa: dict[str, set[str]] = {}
    for requerido in required_files(resolve(especie)):
        mapa.setdefault(requerido.ficha, set()).update(requerido.filenames)
    return mapa


class TestLosDosListadosCuadran(unittest.TestCase):

    #: Fichas de frentes que NO se cierran con ningún fichero. Declaradas por su nombre:
    #: una excepción que crece sin que nadie la mire deja de ser una excepción. Hoy son
    #: dos, y las dos se cierran en el BANCO: conseguir más datos no las cierra.
    SIN_FICHERO = {"empalme_intron", "intron_sin_criptico"}

    def test_toda_ficha_con_ficheros_los_declara_TODOS_los_que_pide_el_gestor(self):
        fichas = load_all()
        for especie in SPECIES:
            gestor = _por_ficha(especie)
            for nombre, pedidos in gestor.items():
                resueltos = {
                    f.name for f in resolve_ficha(nombre, species=resolve(especie)).files
                }
                with self.subTest(especie=especie, ficha=nombre):
                    faltan = pedidos - resueltos
                    self.assertEqual(
                        faltan, set(),
                        f"La ficha {nombre!r} no nombra {sorted(faltan)}, que es lo que "
                        f"el gestor pide para {especie}. Quien la lea preparará otra "
                        f"cosa — y el cargador la rechazará sin poder decir por qué.",
                    )

    def test_y_todo_NOMBRE_DE_FICHERO_de_la_ficha_lo_pide_el_gestor(self):
        """La otra dirección, acotada a lo que ES un nombre de fichero.

        Una entrada de la ficha puede ser una FRASE —«refseq_rna (base de BLAST) + el
        resultado en `-outfmt 6`»— y eso es legítimo: describe qué hay que conseguir
        cuando no es un fichero con nombre fijo. Lo que no puede pasar es que la ficha
        nombre un fichero CONCRETO que ningún cargador va a pedir: eso es una descarga
        en balde que además parece cerrar algo.
        """
        for especie in SPECIES:
            gestor = _por_ficha(especie)
            for nombre, pedidos in gestor.items():
                ficha = resolve_ficha(nombre, species=resolve(especie))
                for fichero in ficha.files:
                    resuelto = fichero.name
                    if " " in resuelto:      # es una frase, no un nombre
                        continue
                    with self.subTest(especie=especie, ficha=nombre, f=resuelto):
                        self.assertIn(resuelto, pedidos)

    def test_las_fichas_SIN_fichero_son_las_declaradas_y_no_otras(self):
        vacias = {n for n, f in load_all().items() if not f.files}
        self.assertEqual(vacias, self.SIN_FICHERO)


class TestElCasoQueLoObligo(unittest.TestCase):
    """`fraccion_isoforma_larga` cierra su frente con DOS ficheros y DOS formatos."""

    @classmethod
    def setUpClass(cls):
        cls.ficha = load_all()["fraccion_isoforma_larga"]

    def test_nombra_los_dos(self):
        nombres = {f.name for f in self.ficha.files}
        self.assertEqual(nombres, {"{fichero_polyadb}", "{fichero_apa}"})

    def test_y_los_NOMBRES_los_pone_el_gestor_no_la_ficha(self):
        # Resueltos contra el raton salen los del manifiesto que ya existe, sin sufijo
        # donde el gestor no lo pone. Si la ficha los transcribiera, esta linea seria
        # la que se quedaria atras.
        resuelta = resolve_ficha("fraccion_isoforma_larga", species=resolve("raton"))
        self.assertEqual(
            {f.name for f in resuelta.files}, {"polya_db_mouse.tsv", "apa_medido.tsv"}
        )

    def test_el_de_PolyA_DB_es_el_OBLIGATORIO_y_el_que_producen_los_pasos(self):
        polyadb = next(f for f in self.ficha.files if "polyadb" in f.name)
        self.assertTrue(polyadb.required)
        self.assertIn("PolyA_DB", polyadb.why)

    def test_el_OTRO_declara_su_formato_y_dice_que_NO_es_PolyA_DB(self):
        # Es la mitad que faltaba: sin decir el formato, «apa medido» y «PolyA_DB»
        # se leen como lo mismo, que es exactamente lo que pasó.
        simple = next(
            f for f in self.ficha.files if f.name == "{fichero_apa}"
        )
        self.assertFalse(simple.required)
        self.assertIn("posicion<TAB>fraccion<TAB>nombre", simple.why)
        self.assertIn("NO es la de PolyA_DB", simple.why)

    def test_y_hay_un_AVISO_que_nombra_la_confusion(self):
        texto = " ".join(self.ficha.warnings)
        self.assertIn("SON DOS FICHEROS Y DOS FORMATOS", texto)


if __name__ == "__main__":
    unittest.main()
