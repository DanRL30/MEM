"""Pruebas de la máquina de estados y de la bitácora de auditoría."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from minsur_domain.auditoria import (
    COBERTURA,
    Accion as AccionAuditoria,
    Bitacora,
    BitacoraCorrupta,
    Origen,
)
from minsur_domain.estados import (
    Accion,
    Estado,
    Perfil,
    PerfilNoAutorizado,
    TransicionInvalida,
    acciones_disponibles,
    es_irreversible,
    verificar,
)

MOMENTO = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


# --- Máquina de estados ------------------------------------------------------


class TestTransiciones:
    def test_el_camino_completo(self):
        assert verificar(Estado.BORRADOR, Accion.EJECUTAR, Perfil.INGENIERO_DE_PROYECTO) is Estado.CALCULADA
        assert verificar(Estado.CALCULADA, Accion.CONGELAR, Perfil.LIDER_DE_ESTUDIO) is Estado.CONGELADA

    def test_editar_devuelve_a_borrador(self):
        assert verificar(Estado.CALCULADA, Accion.EDITAR_INSUMOS, Perfil.LIDER_DE_ESTUDIO) is Estado.BORRADOR

    def test_congelar_es_irreversible(self):
        assert es_irreversible(Estado.CALCULADA, Accion.CONGELAR)

    @pytest.mark.parametrize(
        "accion", [Accion.EJECUTAR, Accion.EDITAR_INSUMOS, Accion.CONGELAR]
    )
    def test_nada_modifica_una_evaluacion_congelada(self, accion: Accion):
        with pytest.raises(TransicionInvalida, match="no admite modificaciones"):
            verificar(Estado.CONGELADA, accion, Perfil.ADMINISTRADOR)

    def test_el_mensaje_orienta_hacia_el_recalculo(self):
        # Que el error explique la salida correcta evita que el usuario
        # concluya que la plataforma se lo impide todo.
        with pytest.raises(TransicionInvalida, match="recalcúlela"):
            verificar(Estado.CONGELADA, Accion.EDITAR_INSUMOS, Perfil.LIDER_DE_ESTUDIO)

    def test_recalcular_no_altera_la_corrida_congelada(self):
        assert verificar(Estado.CONGELADA, Accion.RECALCULAR, Perfil.LIDER_DE_ESTUDIO) is Estado.CONGELADA

    def test_recalcular_no_aplica_a_una_corrida_no_congelada(self):
        with pytest.raises(TransicionInvalida, match="solo aplica"):
            verificar(Estado.BORRADOR, Accion.RECALCULAR, Perfil.LIDER_DE_ESTUDIO)


class TestPermisos:
    def test_el_ingeniero_ejecuta_pero_no_congela(self):
        verificar(Estado.BORRADOR, Accion.EJECUTAR, Perfil.INGENIERO_DE_PROYECTO)
        with pytest.raises(PerfilNoAutorizado, match="no puede congelar"):
            verificar(Estado.CALCULADA, Accion.CONGELAR, Perfil.INGENIERO_DE_PROYECTO)

    def test_finanzas_no_congela_evaluaciones_de_proyectos(self):
        # Finanzas gobierna parámetros maestros y versión del motor; declarar
        # que una evaluación sustenta una decisión corresponde a Proyectos.
        with pytest.raises(PerfilNoAutorizado):
            verificar(Estado.CALCULADA, Accion.CONGELAR, Perfil.FINANZAS)

    @pytest.mark.parametrize("perfil", [Perfil.CONSULTA_EJECUTIVA, Perfil.AUDITOR])
    def test_los_perfiles_de_consulta_no_tienen_acciones(self, perfil: Perfil):
        for estado in Estado:
            assert acciones_disponibles(estado, perfil) == ()

    @pytest.mark.parametrize("perfil", [Perfil.CONSULTA_EJECUTIVA, Perfil.AUDITOR])
    def test_los_perfiles_de_consulta_no_pueden_recalcular(self, perfil: Perfil):
        with pytest.raises(PerfilNoAutorizado, match="consulta"):
            verificar(Estado.CONGELADA, Accion.RECALCULAR, perfil)

    def test_el_error_indica_quien_si_puede(self):
        with pytest.raises(PerfilNoAutorizado, match="Autorizados"):
            verificar(Estado.CALCULADA, Accion.CONGELAR, Perfil.INGENIERO_DE_PROYECTO)


# --- Bitácora ----------------------------------------------------------------


def _bitacora_con_tres_entradas() -> Bitacora:
    b = Bitacora()
    b.registrar("R1", "C1", "hugo.diaz", Perfil.LIDER_DE_ESTUDIO,
                AccionAuditoria.CASO_CREADO, Origen.CAPTURA_WEB, momento=MOMENTO)
    b.registrar("R1", "C1", "hugo.diaz", Perfil.LIDER_DE_ESTUDIO,
                AccionAuditoria.INSUMOS_CARGADOS, Origen.PLANTILLA_EXCEL, momento=MOMENTO)
    b.registrar("R1", "C1", "hugo.diaz", Perfil.LIDER_DE_ESTUDIO,
                AccionAuditoria.EVALUACION_EJECUTADA, Origen.CALCULO, momento=MOMENTO)
    return b


class TestBitacora:
    def test_no_expone_modificacion_ni_borrado(self):
        # La ausencia de estos métodos es la garantía de solo escritura.
        for prohibido in ("modificar", "eliminar", "borrar", "actualizar", "__setitem__"):
            assert not hasattr(Bitacora, prohibido)

    def test_encadena_las_entradas(self):
        b = _bitacora_con_tres_entradas()
        entradas = list(b)
        assert entradas[0].huella_anterior == "0" * 64
        assert entradas[1].huella_anterior == entradas[0].huella
        assert entradas[2].huella_anterior == entradas[1].huella
        b.verificar()

    def test_detecta_la_supresion_de_una_entrada(self):
        b = _bitacora_con_tres_entradas()
        b._entradas.pop(1)
        with pytest.raises(BitacoraCorrupta, match="Cadena rota"):
            b.verificar()

    def test_detecta_la_modificacion_de_una_entrada(self):
        b = _bitacora_con_tres_entradas()
        original = b._entradas[1]
        b._entradas[1] = type(original)(
            **{**original.__dict__, "usuario": "otro.usuario"}
        )
        with pytest.raises(BitacoraCorrupta, match="modificada después"):
            b.verificar()

    def test_detecta_el_reordenamiento(self):
        b = _bitacora_con_tres_entradas()
        b._entradas[0], b._entradas[1] = b._entradas[1], b._entradas[0]
        with pytest.raises(BitacoraCorrupta):
            b.verificar()

    def test_exige_identificar_al_responsable(self):
        b = Bitacora()
        with pytest.raises(ValueError, match="responsable"):
            b.registrar("R1", "C1", "  ", Perfil.LIDER_DE_ESTUDIO,
                        AccionAuditoria.CASO_CREADO, Origen.CAPTURA_WEB)

    def test_una_modificacion_debe_registrar_ambos_valores(self):
        b = Bitacora()
        with pytest.raises(ValueError, match="anterior y posterior"):
            b.registrar("R1", "C1", "hugo.diaz", Perfil.LIDER_DE_ESTUDIO,
                        AccionAuditoria.PARAMETROS_CAMBIADOS, Origen.DATO_MAESTRO)

    def test_registra_el_cambio_con_sus_dos_valores(self):
        b = Bitacora()
        e = b.registrar(
            "R1", "C1", "finanzas.minsur", Perfil.FINANZAS,
            AccionAuditoria.COMITE_SELECCIONADO, Origen.DATO_MAESTRO,
            valor_anterior={"comite": "CP-2026-02"},
            valor_posterior={"comite": "CP-2026-03"},
            momento=MOMENTO,
        )
        assert e.valor_anterior["comite"] == "CP-2026-02"
        assert e.valor_posterior["comite"] == "CP-2026-03"

    def test_el_historial_de_cambios_omite_lo_que_no_modifica(self):
        b = _bitacora_con_tres_entradas()
        b.registrar("R1", "C1", "hugo.diaz", Perfil.LIDER_DE_ESTUDIO,
                    AccionAuditoria.INSUMOS_EDITADOS, Origen.CAPTURA_WEB,
                    valor_anterior={"tms": 1200}, valor_posterior={"tms": 1300},
                    momento=MOMENTO)
        assert len(b.de_caso("C1")) == 4
        assert len(b.historial_de_cambios("C1")) == 1


class TestCoberturaDelAlcance:
    def test_cubre_los_ocho_requisitos_de_gobierno(self):
        assert sorted(COBERTURA) == list(range(1, 9))

    def test_cada_requisito_apunta_a_una_implementacion(self):
        for numero, (requisito, donde) in COBERTURA.items():
            assert requisito.strip(), f"Requisito {numero} sin descripción"
            assert donde.strip(), f"Requisito {numero} sin implementación"
