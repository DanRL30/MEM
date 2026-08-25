# Registro de decisiones de arquitectura (ADR)

Una decisión con costo de reversión alto se registra aquí **antes** de implementarse.
Los ADR son inmutables: si una decisión cambia, se crea uno nuevo que supersede al anterior.

Nombre: `NNNN-titulo-en-kebab-case.md`

## Plantilla

```markdown
# NNNN. Título de la decisión

- Estado: propuesta | aceptada | supersedida por NNNN
- Fecha: DD/MM/AAAA
- Decide: quién tiene la A en la matriz RACI para esta decisión
- Restricción relacionada: R-xx (si aplica)

## Contexto
Qué situación obliga a decidir. Qué restricciones del cliente aplican.

## Decisión
Qué se hace, en una frase.

## Alternativas consideradas
Qué más se evaluó y por qué se descartó.

## Consecuencias
Qué se vuelve fácil, qué se vuelve difícil, qué queda bloqueado.
```

## Decisiones registradas

| # | Decisión | Estado | Fecha |
|---|---|---|---|
| [0008](0008-versionado-de-claude-md.md) | Versionar `CLAUDE.md` con su encabezado de origen | aceptada | 24/08/2026 |

La numeración no sigue el orden de redacción. Los números de la tabla siguiente están reservados
para decisiones ya identificadas, así que un ADR nuevo toma el primero libre por encima de ellas.

## Decisiones pendientes de registrar

| # | Decisión | Disparador |
|---|---|---|
| 0001 | Python como lenguaje del motor, pese al estándar .NET/C# de MINSUR | KOM 24/08 · `R-14` |
| 0002 | Patrón de persistencia: Azure SQL para transaccional, Blob/Table para evidencias | Estándar MINSUR |
| 0003 | API Management como única puerta al backend | Estándar MINSUR |
| 0004 | Congelamiento por imagen sellada con SHA-256 e inmutabilidad de contenedor | Alcance |
| 0005 | Tres ejes de versionado independientes (motor, datos maestros, inputs) | Alcance |
| 0006 | Patrón de publicación: Front Door vs. Application Gateway | Pendiente de TI |
| 0007 | Estrategia de datos para el contraste según el resultado de `R-12` | Pendiente de TI |
