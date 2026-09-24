# semcial-datos

Datos públicos que usan las herramientas gratuitas de [semcial.com](https://semcial.com).

## rates.json

Cuántas unidades de cada moneda vale 1 USD, actualizado de lunes a viernes por GitHub Actions
con las APIs públicas y gratuitas de cada banco central:

| Moneda | Fuente |
| --- | --- |
| ARS | BCRA, API de estadísticas cambiarias (tipo de cambio mayorista, Com. A 3500) |
| UYU | Banco Central del Uruguay, servicio web de cotizaciones (dólar billete) |
| CLP | Banco Central de Chile, dólar observado, vía [mindicador.cl](https://mindicador.cl) |
| MXN | Banco de Canadá, API Valet (cruce USD/CAD y MXN/CAD) |
| EUR | Banco Central Europeo, API de datos (tipo de referencia) |

Si una fuente falla, se usa la API abierta de [ExchangeRate-API](https://www.exchangerate-api.com)
como respaldo y queda indicado en el campo `source`. Si un valor salta más de 30% de un día a
otro, se conserva el anterior.

Se sirve desde `https://cdn.jsdelivr.net/gh/<usuario>/semcial-datos@main/rates.json`.
