"""El plásmido de SGEP #111170 entra por el gestor, y los contextos se DERIVAN de él.

**Pedido el 2026-09-02**: «El plásmido de SGEP #111170 no tiene hueco en el panel de
referencia… Hazlo fichero de primera clase, como los demás: rol propio, hueco en el
gestor, ficha de obtención, validación al subir y md5 en el manifiesto. Formato .gb o
.dna, y que extraiga los contextos por la anotación, no por las coordenadas declaradas».

**Lo segundo es lo que pesa.** `gblock.verify_contexts_against_plasmid` leía el plásmido
en `1739-1758` y `1856-1875` —coordenadas ESCRITAS— y comparaba lo que hubiera ahí con
nuestros contextos. Eso comprueba menos de lo que parece: si las coordenadas estuvieran
corridas, la comprobación fallaría contra un plásmido CORRECTO; y si alguien las
«arreglara» moviéndolas hasta que cuadren, pasaría siempre. Un número escrito no puede
validar el fichero del que salió (principio nº 13).

Ahora el ancla es la ANOTACIÓN del propio fichero —`ncRNA` «miR-30a loop»— y el andamio
se localiza POR SECUENCIA a su alrededor; los contextos son lo que flanquea al 97-mero.
Las coordenadas dejan de ser una entrada y pasan a ser un RESULTADO.

Regla 5: escritos antes.
"""

import unittest
from pathlib import Path

from shmir_design import blocks, gblock, scaffold_registry, species
from shmir_design.errors import ShmirDesignError
from shmir_design.scaffold import SGEP_SCAFFOLD

DATOS = Path(__file__).resolve().parent.parent / "data" / "reference"
SGEP = DATOS / "addgene_111170.gb"
HAY = SGEP.is_file()

#: Lo que el fichero dice de sí mismo, para poder contrastar. NO se usa como entrada de
#: la derivación: si lo fuera, esto volvería a ser una coordenada escrita.
LOOP_ANOTADO = (1801, 1815)


@unittest.skipUnless(HAY, "falta addgene_111170.gb")
class TestElAnclaSaleDeLaANOTACION(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.texto = SGEP.read_text(encoding="utf-8")
        cls.ancla = scaffold_registry.anchor_scaffold(
            scaffold_registry.SCAFFOLDS["mir_e"], cls.texto,
            context_length=len(blocks.PIECES["contexto5"].sequence),
        )

    def test_encuentra_el_loop_ANOTADO_del_fichero(self):
        self.assertEqual(self.ancla.annotated_loop, LOOP_ANOTADO)

    def test_y_el_andamio_por_SECUENCIA_lo_CONTIENE(self):
        # Es lo que ata las dos vías: la anotación dice dónde mirar y la secuencia dice
        # qué hay. Si discreparan, una de las dos está mal y no se elige por nuestra
        # cuenta.
        inicio, fin = self.ancla.scaffold_span
        self.assertLess(inicio, LOOP_ANOTADO[0])
        self.assertGreater(fin, LOOP_ANOTADO[1])

    def test_los_CONTEXTOS_salen_del_fichero_y_son_los_del_modulo(self):
        self.assertEqual(self.ancla.context_5, blocks.PIECES["contexto5"].sequence)
        self.assertEqual(self.ancla.context_3, blocks.PIECES["contexto3"].sequence)

    def test_y_sus_coordenadas_son_un_RESULTADO_no_una_entrada(self):
        # Las que estaban escritas salen ahora MEDIDAS. Que coincidan es el hallazgo;
        # que se deriven es lo que hace que sigan coincidiendo mañana.
        self.assertEqual(self.ancla.context_5_span, (1739, 1758))
        self.assertEqual(self.ancla.context_3_span, (1856, 1875))

    def test_la_derivacion_NO_lleva_ninguna_coordenada_escrita(self):
        import inspect

        fuente = inspect.getsource(scaffold_registry.anchor_scaffold)
        for numero in ("1739", "1758", "1856", "1875", "1801", "1815"):
            with self.subTest(numero):
                self.assertNotIn(numero, fuente)


@unittest.skipUnless(HAY, "falta addgene_111170.gb")
class TestLaCOMPROBACION_del_modulo(unittest.TestCase):
    """`verify_contexts_against_plasmid` deja de leer coordenadas."""

    def test_con_el_plasmido_de_verdad_PASA(self):
        gblock.verify_contexts_against_plasmid(SGEP.read_text(encoding="utf-8"))

    def test_con_UN_CONTEXTO_CAMBIADO_aborta(self):
        # Control adversario: sin él, «pasa» y «no mira nada» dan el mismo verde. Se
        # cambia UNA base del contexto 5' —la 1758, la última— sobre el fichero real.
        with self.assertRaises(ShmirDesignError) as caja:
            gblock.verify_contexts_against_plasmid(_con_una_base_cambiada(1758))
        self.assertIn("PARA", str(caja.exception))

    def test_y_con_la_ANOTACION_movida_tambien(self):
        # La otra mitad: si la anotación del loop deja de caer dentro del andamio
        # localizado por secuencia, una de las dos vías está mal y no se elige por
        # nuestra cuenta. Sin esto, el ancla sería decorativa.
        texto = SGEP.read_text(encoding="utf-8").replace(
            "     ncRNA           1801..1815", "     ncRNA           801..815", 1
        )
        with self.assertRaises(ShmirDesignError) as caja:
            gblock.verify_contexts_against_plasmid(texto)
        self.assertIn("NO cae dentro", str(caja.exception))

    def test_con_un_plasmido_que_NO_lleva_el_andamio_aborta_diciendolo(self):
        # El casete de AAV está en el depósito y NO contiene los contextos: comprobado
        # con test para que nadie apunte ahí creyendo que sirve.
        casete = (DATOS / "aav_casete.fa").read_text(encoding="utf-8")
        with self.assertRaises(ShmirDesignError):
            gblock.verify_contexts_against_plasmid(casete)


def _con_una_base_cambiada(posicion: int) -> str:
    """El GenBank real con UNA base cambiada, reescribiendo su bloque ORIGIN.

    Se reescribe el bloque en vez de tocar el texto a mano porque el ORIGIN va en
    bloques de diez separados por espacios: un `replace` sobre la cadena entera no
    encuentra nada y el «control adversario» pasaría sin haber cambiado nada.
    """
    texto = SGEP.read_text(encoding="utf-8")
    cabecera, origen = texto.split("ORIGIN", 1)
    secuencia = "".join(c for c in origen if c.isalpha()).upper()
    cambiada = "A" if secuencia[posicion - 1] != "A" else "C"
    secuencia = secuencia[: posicion - 1] + cambiada + secuencia[posicion:]
    lineas = []
    for i in range(0, len(secuencia), 60):
        trozo = secuencia[i : i + 60].lower()
        bloques = " ".join(trozo[j : j + 10] for j in range(0, len(trozo), 10))
        lineas.append(f"{i + 1:>9} {bloques}")
    return cabecera + "ORIGIN\n" + "\n".join(lineas) + "\n//\n"


class TestElROL_del_plasmido(unittest.TestCase):
    """Fichero de primera clase: rol, hueco, validador, ficha y md5."""

    def _fila(self, especie="raton"):
        return next(
            f for f in species.required_files(species.resolve(especie))
            if f.role == "plasmido_andamio"
        )

    def test_tiene_ROL_propio_en_el_gestor(self):
        self.assertEqual(self._fila().filename, "addgene_111170.gb")

    def test_y_NO_lleva_sufijo_de_especie(self):
        # SGEP no es de ninguna especie: es el vector del ANDAMIO. Ponerle sufijo diría
        # que hace falta uno por especie, que es falso — al revés que `aav_casete.fa`,
        # que SÍ es pAAV con PrP murino.
        self.assertEqual(self._fila("raton").filename, self._fila("conejo").filename)

    def test_admite_gb_y_dna(self):
        self.assertEqual(set(self._fila().extensions), {"gb", "dna", "gbk"})

    def test_tiene_VALIDADOR_al_subir(self):
        from shmir_design.deposito import VALIDATORS

        self.assertIn("plasmido_andamio", VALIDATORS)

    def test_esta_en_manifest_ROLES(self):
        from shmir_design.manifest import ROLES

        self.assertIn("plasmido_andamio", {r.role for r in ROLES})

    def test_y_su_md5_esta_en_el_manifiesto_versionado(self):
        from shmir_design.manifest import load_manifest

        entrada = load_manifest(DATOS / "manifest.tsv").entry("addgene_111170.gb")
        self.assertEqual(entrada.md5, _md5_del_fichero())

    def test_declara_QUE_pasa_si_se_reemplaza(self):
        from shmir_design.gestor import ROLE_INVALIDATES

        self.assertIn("plasmido_andamio", ROLE_INVALIDATES)


def _md5_del_fichero() -> str:
    from shmir_design.identidad import file_fingerprint

    return file_fingerprint(SGEP.read_bytes())


class TestElFRENTE_de_los_contextos(unittest.TestCase):
    """Un fichero de primera clase cierra un frente, y el frente sale en el panel."""

    def _informe(self, presentes=()):
        return species.fixture_report(species.resolve("raton"), have=tuple(presentes))

    def test_sin_el_plasmido_el_frente_NO_esta_cerrado(self):
        fila = next(
            f for f in self._informe().rows if "contextos" in f.keys[0]
        )
        self.assertFalse(fila.available)
        self.assertIn("addgene_111170.gb", fila.missing)

    def test_con_el_plasmido_SI(self):
        fila = next(
            f for f in self._informe(("addgene_111170.gb",)).rows
            if "contextos" in f.keys[0]
        )
        self.assertTrue(fila.available)

    def test_y_tiene_FICHA_de_obtencion(self):
        from shmir_design.presentation import obtencion_rows

        ficha = obtencion_rows("contextos_del_andamio", species="raton")
        self.assertIn("111170", ficha["texto"])
        self.assertIn("addgene_111170.gb", ficha["texto"])


class TestQUE_MAS_estaba_igual(unittest.TestCase):
    """La auditoría que se pidió «de paso», y sale MEDIDA sobre los ficheros de verdad.

    De las 12 piezas de `blocks.PIECES`, sólo dos declaraban coordenadas en un plásmido
    —los dos contextos de SGEP— y ya se derivan. Lo que apareció al mirar las otras diez
    es de otra clase: **diez dicen de dónde vienen y nadie lo estaba comprobando**.
    """

    def test_las_piezas_del_receptor_ESTAN_en_el_casete_y_son_unicas(self):
        informe = blocks.audit_pieces_against_plasmids()
        confirmadas = {f["pieza"] for f in informe if f["estado"] == "CONFIRMADA"}
        # Las cuatro del receptor —nadie las estaba contrastando— y los dos contextos,
        # que ahora salen del plásmido del andamio por el mismo camino.
        self.assertEqual(
            confirmadas,
            {"MluI", "MVM5", "MVM3", "AgeI", "contexto5", "contexto3"},
        )

    def test_los_exones_de_5_nt_solo_se_pueden_comprobar_EN_POSICION(self):
        # Cinco nucleótidos aparecen por azar: `exon5` sale 3 veces y `exon3` 8. Lo que
        # sí se puede exigir es que estén PEGADOS a su MVM, y eso se comprueba.
        informe = blocks.audit_pieces_against_plasmids()
        for pieza in ("exon5", "exon3"):
            with self.subTest(pieza):
                fila = next(f for f in informe if f["pieza"] == pieza)
                self.assertEqual(fila["estado"], "CONFIRMADA_EN_POSICION")

    def test_NheI_y_SacI_NO_estan_en_el_receptor_depositado(self):
        # HALLAZGO. Su procedencia decía «plásmido receptor» y el receptor que hay NO
        # las contiene: el parental lleva el intrón VACÍO, sin sitio de clonaje. No es
        # que las secuencias estén mal —son las dianas canónicas— es que esa frase
        # afirmaba un origen que ningún fichero sostiene.
        informe = blocks.audit_pieces_against_plasmids()
        for pieza in ("NheI", "SacI"):
            with self.subTest(pieza):
                fila = next(f for f in informe if f["pieza"] == pieza)
                self.assertEqual(fila["estado"], "NO_ESTA")

    def test_y_su_PROCEDENCIA_ya_no_dice_que_vienen_del_receptor(self):
        for pieza in ("NheI", "SacI"):
            with self.subTest(pieza):
                self.assertNotIn(
                    "plásmido receptor", blocks.PIECES[pieza].source
                )

    def test_los_espaciadores_son_de_NOVO_y_no_se_les_busca(self):
        informe = blocks.audit_pieces_against_plasmids()
        for pieza in ("espaciador5", "espaciador3"):
            with self.subTest(pieza):
                fila = next(f for f in informe if f["pieza"] == pieza)
                self.assertEqual(fila["estado"], "NO_APLICA")

    def test_TODAS_las_piezas_salen_en_el_informe(self):
        informe = blocks.audit_pieces_against_plasmids()
        self.assertEqual(
            {f["pieza"] for f in informe}, set(blocks.PIECES)
        )

    def test_y_el_ANDAMIO_de_miR_E_queda_CONTRASTADO_contra_el_plasmido(self):
        # La sospecha era ésta. La diferencia con los contextos: el andamio tiene una
        # PUBLICACIÓN detrás, así que no se DERIVA del plásmido —eso sería elegir
        # coordenadas por nuestra cuenta, lo que `mir30_original` se niega a hacer— sino
        # que se CONTRASTA con él, que es lo que aquí se puede comprobar.
        if not HAY:
            self.skipTest("falta addgene_111170.gb")
        ancla = scaffold_registry.anchor_scaffold(
            scaffold_registry.SCAFFOLDS["mir_e"],
            SGEP.read_text(encoding="utf-8"),
            context_length=len(blocks.PIECES["contexto5"].sequence),
        )
        inicio, fin = ancla.scaffold_span
        entero = ancla.plasmid[inicio - 1:fin]
        self.assertTrue(entero.startswith(SGEP_SCAFFOLD.flank5))
        self.assertTrue(entero.endswith(SGEP_SCAFFOLD.flank3))
        self.assertIn(SGEP_SCAFFOLD.loop, entero)


if __name__ == "__main__":
    unittest.main()
