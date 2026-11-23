"""
Modulo de inferencia de SaludOral-IA.

Componente PURO de inferencia, desacoplado de Django, Supabase y cualquier
capa de aplicacion (aprobado en la etapa 9):

- Entrada: bytes de una imagen.
- Salida: dict JSON-serializable (contrato en predict.py y docs/etapa9_inferencia.md).
- Errores: excepciones de dominio propias; las traduce la capa que llame.

Convencion fija del proyecto: indice 0 = "cancer" (clase positiva),
indice 1 = "non-cancer".
"""
