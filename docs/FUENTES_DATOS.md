# Fuentes de datos del sistema

## Estado actual

- **Fuente principal de mercado:** API pública de IQ Options (solo lectura).
  - Cuatro activos: dos spot y dos OTC.
  - El colector persistente guarda ticks y velas M1/M15, además de puntos de
    `charts` para calentamiento.
  - No requiere credenciales ni sesión de cuenta; el endpoint expuesto es de
    lectura y no envía órdenes.
- **Deriv:** ya no es fuente en vivo. Sus CSV históricos M15 se usan únicamente
  como *warm-up* del motor, alineados a los últimos bloques de 15 minutos.
- **Alertas:** se entregan por el servidor ntfy local. El envío en vivo se
  habilita de forma explícita con `PIVOT_ALERTAS_LIVE=1`.

## Consideraciones

- Las velas OTC son sintéticas del bróker: sirven para investigación y señales,
  no como precio interbancario.
- El esquema del GraphQL público puede cambiar sin aviso; el colector está
  aislado y no toca la cuenta de corretaje.
- Este documento describe arquitectura, no credenciales. No incluye hosts,
  tokens, contraseñas ni identificadores de cuenta.
