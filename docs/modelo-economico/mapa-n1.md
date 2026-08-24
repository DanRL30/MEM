# Mapa N1 — correspondencia bloque de contraste a módulo del motor

El contraste de nivel N1 verifica los bloques intermedios año a año. Cada bloque tiene **un solo**
módulo responsable, de modo que una discrepancia se localiza en un archivo.

| Bloque del contraste N1 | Módulo | Prueba |
|---|---|---|
| Producción y toneladas finas | `produccion.py` | `test_n1_bloques.py::test_produccion` |
| Ventas por metal | `ventas.py` | `::test_ventas` |
| Cash cost | `cash_cost.py` | `::test_cash_cost` |
| EBITDA ajustado | `flujos.py` | `::test_ebitda` |
| Depreciación tributaria y financiera | `depreciacion.py` | `::test_depreciacion` |
| Base imponible | `tributos.py` | `::test_base_imponible` |
| Impuestos | `tributos.py` | `::test_impuestos` |
| Regalías y aportes | `tributos.py` | `::test_regalias_aportes` |
| Capital de trabajo | `capital_trabajo.py` | `::test_working_capital` |

Tolerancia N1: diferencia relativa hasta 0,1 % o absoluta hasta US$ 10 000 por línea y año.
Valor provisional hasta que Finanzas cierre `R-31`.
