# Casos certificados — manifiestos

Aquí **no hay datos**. Solo manifiestos que apuntan a la evidencia custodiada en el tenant de MINSUR.

Los tres casos de la batería de contraste son evaluaciones económicas reales, cerradas y
confidenciales. No se versionan, no se copian, no se anonimizan "temporalmente".

## Formato del manifiesto

```json
{
  "caso_id": "CASO-BASE-SIN-PROYECTO",
  "descripcion": "Plan de vida de mina sin proyecto, aprobado por Operaciones",
  "tipo": "base | monometalico | polimetalico",
  "origen": "Finanzas MINSUR",
  "uri_inputs": "https://<storage>.blob.core.windows.net/contraste/<id>/inputs",
  "uri_resultados": "https://<storage>.blob.core.windows.net/contraste/<id>/resultados",
  "sha256_inputs": "",
  "sha256_resultados": "",
  "version_motor_certificada": "",
  "fecha_certificacion": "",
  "certificado_por": "Finanzas MINSUR"
}
```

Las pruebas que consumen estos manifiestos se marcan `@pytest.mark.tenant_minsur` y solo se
ejecutan dentro del tenant del cliente.
