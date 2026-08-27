"""La ficha de un candidato: todo lo que sabemos de un sitio, en un sitio.

Los datos de un candidato viven repartidos entre el informe, la tabla comparativa, el
TSV de ventanas y la hoja de pedido. Para decidir sobre UN sitio hay que reunirlos a
mano, y reunirlos a mano es donde se pierde el `NOT_RUN` de alguno.

La ficha los junta: el veredicto de CADA frente con su procedencia y su fecha, la
asimetria en sus tres columnas, el techo de APA con el tramo del que sale, los hexameros
cercanos con clase y distancia, el modulo de 149 nt, el cassette de 318 y el historial de
BLAST.

Y con la misma disciplina que el informe: la ficha se compara **entera** contra una de
referencia (`tests/golden/ficha_raton_200.txt`). Los tests de presencia miran lo que cada
uno espera y **no ven lo que falta**.

Python 3.11+, solo libreria estandar (regla 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ShmirDesignError
from .filters import FilterState

#: Cuando un frente no viene de una corrida fechada, su fecha es esta y se lee como lo
#: que es: no hay dato, no una fecha inventada.
SIN_FECHA = "—"


@dataclass(frozen=True)
class FrontVerdict:
    name: str
    state: FilterState
    reason: str
    source: str
    date: str

    def describe(self, width: int = 24) -> str:
        """`width` lo fija quien imprime la tabla, no esta fila.

        Los nombres de frente crecieron al partirse por hebra y por intron
        (`empalme_sitios:intron_quimerico` son 31 caracteres). Con un ancho fijo,
        los nombres largos se comen la columna de al lado y el estado deja de leerse en
        vertical — que es justo para lo que sirve la tabla: ver de un vistazo cuantos
        `NOT_RUN` quedan.
        """
        return (
            f"{self.name:<{width}} {self.state.value:<9} {self.date:<12} {self.source}"
        )


@dataclass(frozen=True)
class NearbyHexamer:
    motif: str
    position: int
    classification: str
    distance: int

    def describe(self) -> str:
        donde = (
            "SOLAPA la ventana" if self.distance == 0
            else f"a {abs(self.distance)} nt {'por delante' if self.distance > 0 else 'por detras'}"
        )
        return f"{self.motif}  3utr:{self.position}  {self.classification:<12} {donde}"


@dataclass(frozen=True)
class Dossier:
    species: str
    start: int
    end: int
    guide: str
    passenger: str
    verdict: str
    fronts: tuple[FrontVerdict, ...]
    asymmetry_raw: float
    penalty: float
    asymmetry_net: float
    ceiling: float | None
    ceiling_layer: str
    hexamers: tuple[NearbyHexamer, ...]
    module: str
    cassette: str
    blast_history: tuple
    module_note: str = ""
    #: Otros candidatos ELEGIDOS que comparten el nucleo de seed de 6 nt con este. No
    #: es un veredicto del candidato: es una propiedad de la PAREJA, y por eso va en su
    #: propia fila y no mezclada con los frentes.
    core_shared_with: tuple[str, ...] = ()
    #: Sitios de ESTA hebra en su propia diana, con su clase.
    self_sites: tuple = ()

    def render(self) -> str:
        # El ancho de la columna sale del nombre mas largo QUE HAY, no de un numero
        # escrito a mano: cada frente que se parte (por hebra, por intron) alarga los
        # nombres, y un ancho fijo se queda corto sin que nadie lo note.
        ancho = max([len("frente")] + [len(f.name) for f in self.fronts])
        lineas = [
            f"═══ Ficha del candidato — {self.species} 3utr:{self.start} ═══",
            "",
            f"  sitio      3utr:{self.start}-{self.end}",
            f"  guía       {self.guide}",
            f"  pasajera   {self.passenger}",
            f"  veredicto  {self.verdict}",
            "",
            f"── Frentes ({len(self.fronts)}) ──",
            f"  {'frente':<{ancho}} {'estado':<9} {'fecha':<12} procedencia",
        ]
        lineas.extend(f"  {f.describe(ancho)}" for f in self.fronts)
        lineas.extend(
            [
                "",
                "── Asimetría — las TRES cifras, que son magnitudes distintas ──",
                f"  cruda {self.asymmetry_raw:+.2f}   penalizacion {self.penalty:.2f}   "
                f"neta {self.asymmetry_net:+.2f}",
                "",
                "── Techo de APA ──",
            ]
        )
        if self.ceiling is None:
            lineas.append(f"  sin techo — {self.ceiling_layer}")
        else:
            lineas.append(f"  {self.ceiling:.2f} — {self.ceiling_layer}")
        lineas.extend(["", "── Sitios de esta seed en la PROPIA diana (esperado: 1) ──"])
        if not self.self_sites:
            lineas.append(
                "  NO CALCULADO en esta ficha. No es cero: no se ha contado."
            )
        else:
            lineas.extend(f"  {s.describe()}" for s in self.self_sites)
            if len(self.self_sites) > 1:
                lineas.append(
                    "  ⚠  MÁS DE UNO: hay varias dianas en el mismo mensajero, así que "
                    "la cinetica no se lee"
                )
                lineas.append(
                    "     igual. La CLASE decide cuanto importa — un 8mer o un 7mer-m8 "
                    "de más dan cooperatividad"
                )
                lineas.append("     real; un 6mer es marginal.")

        lineas.extend(["", "── Multiplexado: núcleo de seed compartido ──"])
        if self.core_shared_with:
            lineas.extend(f"  ⚠  {c}" for c in self.core_shared_with)
        else:
            lineas.append(
                "  Con ningún otro candidato del panel. En este eje es independiente."
            )

        lineas.extend(["", "── Hexámeros cercanos ──"])
        if self.hexamers:
            lineas.extend(f"  {h.describe()}" for h in self.hexamers)
        else:
            lineas.append("  ninguno a menos de la distancia que se mira.")
        lineas.extend(
            [
                "",
                "── Bloques ──",
                f"  módulo NheI-SacI ({len(self.module)} nt):",
                *(f"    {self.module[i:i + 60]}" for i in range(0, len(self.module), 60)),
                f"  cassette MluI-AgeI ({len(self.cassette)} pb):",
                *(
                    f"    {self.cassette[i:i + 60]}"
                    for i in range(0, len(self.cassette), 60)
                ),
            ]
        )
        if self.module_note:
            lineas.append(f"  ⚠  {self.module_note}")
        lineas.extend(["", "── Historial de BLAST ──"])
        if not self.blast_history:
            lineas.append(
                "  SIN CORRIDAS. El frente de especificidad sigue en NOT_RUN, y NOT_RUN "
                "no es PASS."
            )
        else:
            for corrida in self.blast_history:
                lineas.extend(f"  {l}" for l in corrida.describe())
        return "\n".join(lineas) + "\n"


def _hexamers_near(tiling, start: int, end: int, *, offset: int, window: int = 60):
    from .polya import SignalClass

    salida = []
    for señal in tiling.signals:
        pos = señal.position - offset
        fin = señal.end - offset
        if fin < start - window or pos > end + window:
            continue
        if pos > end:
            distancia = pos - end
        elif fin < start:
            distancia = fin - start
        else:
            distancia = 0
        etiqueta = señal.classification.value
        if señal.classification is SignalClass.APA_POSSIBLE:
            etiqueta += f"/{señal.evidence}"
        salida.append(
            NearbyHexamer(
                motif=señal.motif, position=pos, classification=etiqueta,
                distance=distancia,
            )
        )
    return tuple(sorted(salida, key=lambda h: h.position))


def build_dossier(
    *, species: str, tiling, selection, start: int, store=None, seed_store=None,
    offtarget_store=None, splice_store=None, target: str | None = None,
) -> Dossier:
    """Reune la ficha de UN candidato. Aborta si ese sitio no esta en el panel."""
    from .blocks import build_block
    from .blast_store import BlastStore
    from .scaffold import SGEP_SCAFFOLD
    from .selection import blocking_fronts

    elegido = next(
        (c for c in selection.selection.chosen if c.start == start), None
    )
    if elegido is None:
        raise ShmirDesignError(
            f"3utr:{start} no está entre los candidatos elegidos de esta corrida "
            f"({', '.join(str(c.start) for c in selection.selection.chosen)}); no se "
            f"emite una ficha de un sitio que el panel no tiene. Se aborta."
        )
    ventana = selection.window_of(elegido)
    desfase = 0
    if tiling.anatomy is not None and tiling.anatomy.utr3:
        desfase = tiling.anatomy.utr3[0] - 1

    almacen = store or BlastStore()
    consulta = f"{species}_pos{start}_guia"

    fecha_de = {}
    procedencia_de = {}
    estados = {}
    for frente in blocking_fronts(tiling, selection):
        # Un frente CERRADO no puede salir como NOT_RUN: la ficha diria que falta algo
        # que ya esta resuelto, y eso es tan engañoso como lo contrario.
        abierto = frente.blocking
        estados[frente.name] = (
            FilterState.NOT_RUN if abierto else FilterState.PASS, frente.reason
        )
        procedencia_de[frente.name] = (
            "frente abierto del informe" if abierto else "frente CERRADO del informe"
        )
        fecha_de[frente.name] = SIN_FECHA
    # La especificidad de ESTE candidato sale del almacen, que es quien tiene la fecha
    # y quien sabe si la corrida cierra el frente o no.
    resultado = almacen.verdict_for(consulta)
    ultima = almacen.latest(consulta)
    estados["especificidad"] = (resultado.state, resultado.reason)
    procedencia_de["especificidad"] = (
        f"corrida {ultima.run_id} ({ultima.database.name})" if ultima
        else "sin corrida en el almacen"
    )
    fecha_de["especificidad"] = ultima.date if ultima else SIN_FECHA

    # `seed_colision` se PARTE en dos: guia y pasajera son dos consultas y fundirlas en
    # una sola fila esconderia la mitad. Nunca se suman.
    from .seed_store import SeedStore

    seeds = seed_store or SeedStore()
    estados.pop("seed_colision", None)
    procedencia_de.pop("seed_colision", None)
    fecha_de.pop("seed_colision", None)
    for hebra in ("guia", "pasajera"):
        nombre = f"seed_colision:{hebra}"
        consulta_hebra = f"{species}_pos{start}_{hebra}"
        resultado_hebra = seeds.verdict_for(consulta_hebra)
        corrida = seeds.latest(consulta_hebra)
        estados[nombre] = (resultado_hebra.state, resultado_hebra.reason)
        procedencia_de[nombre] = (
            f"corrida {corrida.run_id} ({corrida.source.split(',')[0]})" if corrida
            else "sin corrida en el almacen"
        )
        fecha_de[nombre] = corrida.date if corrida else SIN_FECHA

    # `offtarget_seed` se PARTE igual, y por el mismo motivo. Ademas es el frente que
    # estuvo invisible: si la ficha lo enseñara como una sola fila por candidato, la
    # mitad de las consultas volveria a no verse.
    from .offtarget_store import OfftargetStore

    cargas = offtarget_store or OfftargetStore()
    estados.pop("offtarget_seed", None)
    procedencia_de.pop("offtarget_seed", None)
    fecha_de.pop("offtarget_seed", None)
    for hebra in ("guia", "pasajera"):
        nombre = f"offtarget_seed:{hebra}"
        consulta_hebra = f"{species}_pos{start}_{hebra}"
        resultado_hebra = cargas.verdict_for(consulta_hebra)
        corrida = cargas.latest(consulta_hebra)
        estados[nombre] = (resultado_hebra.state, resultado_hebra.reason)
        procedencia_de[nombre] = (
            f"corrida {corrida.run_id} ({corrida.scan.provenance.assembly}, "
            f"{corrida.scan.provenance.table_date})" if corrida
            else "sin corrida en el almacen"
        )
        fecha_de[nombre] = corrida.date if corrida else SIN_FECHA

    # El CUARTO modal. Su veredicto va por PAR candidato x intron, asi que la ficha saca
    # una fila por intron consultado — colapsarlo por candidato perderia justo lo que se
    # quiere comparar: el mismo modulo dentro de dos intrones distintos.
    from .introns import INTRONS
    from .splice_store import SpliceStore

    empalmes = splice_store or SpliceStore()
    estados.pop("empalme_sitios", None)
    procedencia_de.pop("empalme_sitios", None)
    fecha_de.pop("empalme_sitios", None)
    ultima = empalmes.latest
    for intron in INTRONS:
        nombre = f"empalme_sitios:{intron}"
        resultado_intron = empalmes.verdict_for(start, intron)
        estados[nombre] = (resultado_intron.state, resultado_intron.reason)
        procedencia_de[nombre] = (
            f"corrida {ultima.run_id} ({ultima.executor})" if ultima is not None
            else "sin corrida en el almacen"
        )
        fecha_de[nombre] = ultima.date if ultima is not None else SIN_FECHA

    frentes = tuple(
        FrontVerdict(
            name=nombre, state=estado, reason=motivo,
            source=procedencia_de[nombre], date=fecha_de[nombre],
        )
        for nombre, (estado, motivo) in sorted(estados.items())
    )

    capa = tiling.measured_apa.layer_for(ventana.window.start) if tiling.measured_apa else None
    bloque = build_block(ventana.evaluation.guide, scaffold=SGEP_SCAFFOLD)

    # Nucleo compartido con otros ELEGIDOS, y sitios de esta seed en la propia diana.
    # Los dos salen del mismo sitio (`offtarget`) y contestan dos preguntas distintas:
    # con quien NO es independiente, y cuantas dianas tiene en su propio mensajero.
    from .offtarget import core_conflicts, self_sites

    from .coords import Frame, frame_of, label as etiqueta

    marco_ficha = (
        frame_of(selection.anatomy) if selection.anatomy is not None else Frame.UTR3
    )
    compartido = tuple(
        c.describe(
            label_a=etiqueta(c.a, marco_ficha), label_b=etiqueta(c.b, marco_ficha)
        )
        for c in core_conflicts(selection)
        if start in (c.a, c.b)
    )
    propios = self_sites(
        ventana.evaluation.guide,
        target=target if target is not None else "",
        window=(ventana.inicio_3utr, ventana.fin_3utr),
    ) if target is not None else ()
    return Dossier(
        species=species, start=start, end=elegido.end - desfase,
        guide=ventana.evaluation.guide.replace("U", "T"),
        passenger=bloque.passenger,
        verdict=ventana.verdict.value,
        fronts=frentes,
        asymmetry_raw=elegido.asymmetry_raw,
        penalty=elegido.penalty,
        asymmetry_net=elegido.asymmetry,
        ceiling=capa.ceiling if capa else None,
        ceiling_layer=(
            capa.describe() if capa
            else "sin tabla de APA medido en esta corrida: techo INDETERMINADO"
        ),
        hexamers=_hexamers_near(
            tiling, ventana.window.start, ventana.window.end, offset=0
        ),
        core_shared_with=compartido,
        self_sites=propios,
        module=bloque.module,
        cassette=bloque.cassette,
        blast_history=almacen.history(consulta),
        module_note=" ".join(
            aviso for aviso in (
                (
                    "" if bloque.module_safe
                    else "MÓDULO NO VERIFICADO: no se ha podido confirmar que la "
                         "horquilla sobreviva dentro del intrón."
                ),
                # La comprobación de contextos CORRE en cada generación de módulo; que
                # corra y no se vea sería la mitad del arreglo. Sale aquí porque ésta es
                # la pantalla desde la que se pide sintetizar.
                bloque.check("contextos_vs_plasmido").reason
                if bloque.check("contextos_vs_plasmido").state is FilterState.NOT_RUN
                else "",
            ) if aviso
        ),
    )
