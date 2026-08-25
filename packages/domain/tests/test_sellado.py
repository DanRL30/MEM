"""Pruebas del sellado de evaluaciones congeladas.

El grupo que importa es el de canonicalización. La promesa del alcance —que
una evaluación congelada pueda reproducirse dentro de cinco años— descansa en
que el mismo contenido produzca siempre el mismo resumen. Si eso falla, la
verificación programada reportará incidentes que no son incidentes y el
mecanismo perderá credibilidad justo cuando haga falta.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from minsur_domain.sellado import (
    Contenido,
    ErrorSellado,
    Respaldo,
    canonicalizar,
    sellar,
    sha256,
    verificar_integridad,
    verificar_reproducibilidad,
)
from minsur_domain.versionado import (
    TernaVersion,
    VersionDatosMaestros,
    VersionInputs,
    VersionMotor,
)

MOMENTO = datetime(2026, 9, 30, 14, 30, 0, tzinfo=UTC)
HUELLA = "a" * 64


@pytest.fixture
def terna() -> TernaVersion:
    return TernaVersion(
        motor=VersionMotor(1, 2, 0),
        datos_maestros=VersionDatosMaestros("CP-2026-03", date(2026, 3, 15)),
        inputs=VersionInputs(revision=4, huella=HUELLA),
    )


@pytest.fixture
def contenido(terna: TernaVersion) -> Contenido:
    return Contenido(
        id_caso="CASO-SR-2026-014",
        terna=terna,
        inputs={"produccion_tms": [1200.5, 1310.0], "capex_musd": [45.2, 12.0]},
        parametros={"tasa_descuento": 0.10, "impuesto_renta": 0.295},
        resultados={"npv_musd": 128.4567891234, "tir": 0.2237, "payback_anios": 3.4},
    )


# --- Canonicalización --------------------------------------------------------


class TestCanonicalizacion:
    def test_el_orden_de_las_claves_no_altera_el_resumen(self):
        a = {"zeta": 1, "alfa": 2, "media": {"y": 3, "x": 4}}
        b = {"alfa": 2, "media": {"x": 4, "y": 3}, "zeta": 1}
        assert sha256(a) == sha256(b)

    def test_cero_negativo_y_cero_positivo_coinciden(self):
        # Una resta que da cero puede producir -0.0 en un servidor y 0.0 en
        # otro. Sin normalizar, el recálculo divergiría por eso solo.
        assert sha256({"flujo": -0.0}) == sha256({"flujo": 0.0})

    def test_las_marcas_de_tiempo_se_normalizan_a_utc(self):
        utc = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)
        lima = datetime(2026, 9, 30, 9, 0, tzinfo=timezone(timedelta(hours=-5)))
        assert sha256({"t": utc}) == sha256({"t": lima})

    def test_rechaza_marca_de_tiempo_sin_zona(self):
        with pytest.raises(ErrorSellado, match="sin zona horaria"):
            canonicalizar({"t": datetime(2026, 9, 30, 14, 0)})

    def test_rechaza_valores_indefinidos(self):
        with pytest.raises(ErrorSellado, match="NaN"):
            canonicalizar({"npv": float("nan")})
        with pytest.raises(ErrorSellado, match="infinito"):
            canonicalizar({"tir": float("inf")})

    def test_rechaza_tipos_no_serializables(self):
        with pytest.raises(ErrorSellado, match="no serializable"):
            canonicalizar({"objeto": object()})

    def test_es_estable_entre_invocaciones(self, contenido: Contenido):
        assert len({sha256(contenido.a_dict()) for _ in range(50)}) == 1

    def test_diferencias_por_debajo_de_la_precision_no_alteran_el_resumen(self):
        # Doce decimales exceden la precisión significativa de una evaluación
        # económica: el ruido de coma flotante por debajo de ese umbral no
        # debe leerse como divergencia. Estos dos son floats distintos que
        # difieren a partir del decimal trece.
        a, b = 128.4567891234561, 128.4567891234564
        assert a != b
        assert sha256({"npv": a}) == sha256({"npv": b})

    def test_una_diferencia_en_el_ultimo_decimal_conservado_si_altera(self):
        # El umbral está en doce decimales: por encima se conserva.
        assert sha256({"npv": 128.456789123456}) != sha256({"npv": 128.456789123457})

    def test_diferencias_significativas_si_alteran_el_resumen(self):
        assert sha256({"npv": 128.45}) != sha256({"npv": 128.46})

    def test_no_escapa_caracteres_no_ascii(self):
        assert "ó".encode() in canonicalizar({"linea": "Producción"})


# --- Sellado -----------------------------------------------------------------


class TestSellado:
    def test_produce_dos_resumenes_distintos(self, contenido: Contenido):
        imagen = sellar(
            contenido, "hugo.diaz", "Sustento del Comité de Inversiones", momento=MOMENTO
        )
        assert len(imagen.huella_contenido) == 64
        assert len(imagen.huella_sello) == 64
        assert imagen.huella_contenido != imagen.huella_sello

    def test_exige_responsable(self, contenido: Contenido):
        with pytest.raises(ErrorSellado, match="responsable"):
            sellar(contenido, "   ", "motivo", momento=MOMENTO)

    def test_exige_motivo(self, contenido: Contenido):
        with pytest.raises(ErrorSellado, match="motivo"):
            sellar(contenido, "hugo.diaz", "", momento=MOMENTO)

    def test_el_orden_de_los_respaldos_no_altera_el_sello(self, contenido: Contenido):
        a = Respaldo("acta", "Acta.pdf", "resp/acta.pdf", "b" * 64)
        b = Respaldo("correo", "Aprobacion.msg", "resp/correo.msg", "c" * 64)
        uno = sellar(contenido, "hugo.diaz", "m", (a, b), momento=MOMENTO)
        otro = sellar(contenido, "hugo.diaz", "m", (b, a), momento=MOMENTO)
        assert uno.huella_sello == otro.huella_sello

    def test_serializa_a_bytes_deterministas(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "m", momento=MOMENTO)
        assert imagen.serializar() == imagen.serializar()


# --- Integridad --------------------------------------------------------------


class TestIntegridad:
    def test_una_imagen_recien_sellada_verifica(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "m", momento=MOMENTO)
        assert verificar_integridad(imagen).integra

    def test_detecta_alteracion_del_contenido(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "m", momento=MOMENTO)
        alterada = Contenido(
            id_caso=contenido.id_caso,
            terna=contenido.terna,
            inputs=contenido.inputs,
            parametros=contenido.parametros,
            resultados={**contenido.resultados, "npv_musd": 999.0},
        )
        manipulada = type(imagen)(
            contenido=alterada,
            congelada_por=imagen.congelada_por,
            congelada_en=imagen.congelada_en,
            motivo=imagen.motivo,
            respaldos=imagen.respaldos,
            huella_contenido=imagen.huella_contenido,
            huella_sello=imagen.huella_sello,
        )
        veredicto = verificar_integridad(manipulada)
        assert not veredicto.integra
        assert veredicto.es_incidente
        assert "alterada" in veredicto.detalle

    def test_detecta_alteracion_de_los_metadatos(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "Sustento original", momento=MOMENTO)
        manipulada = type(imagen)(
            contenido=imagen.contenido,
            congelada_por="otro.usuario",
            congelada_en=imagen.congelada_en,
            motivo=imagen.motivo,
            respaldos=imagen.respaldos,
            huella_contenido=imagen.huella_contenido,
            huella_sello=imagen.huella_sello,
        )
        veredicto = verificar_integridad(manipulada)
        assert not veredicto.integra
        assert "contenido está intacto" in veredicto.detalle


# --- Reproducibilidad --------------------------------------------------------


class TestReproducibilidad:
    def test_el_mismo_resultado_reproduce(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "m", momento=MOMENTO)
        veredicto = verificar_reproducibilidad(imagen, dict(contenido.resultados))
        assert veredicto.reproducible
        assert not veredicto.es_incidente

    def test_el_orden_de_las_lineas_no_afecta(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "m", momento=MOMENTO)
        invertido = dict(reversed(list(contenido.resultados.items())))
        assert verificar_reproducibilidad(imagen, invertido).reproducible

    def test_una_divergencia_se_reporta_con_su_linea(self, contenido: Contenido):
        imagen = sellar(contenido, "hugo.diaz", "m", momento=MOMENTO)
        veredicto = verificar_reproducibilidad(imagen, {**contenido.resultados, "tir": 0.2240})
        assert veredicto.reproducible is False
        assert veredicto.es_incidente
        assert "tir" in veredicto.detalle

    def test_localiza_divergencias_anidadas(self, terna: TernaVersion):
        c = Contenido(
            id_caso="C1",
            terna=terna,
            inputs={},
            parametros={},
            resultados={"flujos": {"2027": 10.0, "2028": 20.0}},
        )
        imagen = sellar(c, "hugo.diaz", "m", momento=MOMENTO)
        veredicto = verificar_reproducibilidad(imagen, {"flujos": {"2027": 10.0, "2028": 21.0}})
        assert veredicto.reproducible is False
        assert "flujos.2028" in veredicto.detalle
