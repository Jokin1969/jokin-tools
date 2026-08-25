# Endpoints externos verificados

Regla 4: ninguna URL externa se escribe en el código de Batchwork sin estar en esta
tabla. Verificar significa haber lanzado la petición y haber comprobado que responde y
que el formato es el esperado — no que la URL "parezca correcta" ni que aparezca en una
documentación.

Una entrada solo se añade después de la verificación, con la petición exacta que se
lanzó y la forma real de la respuesta obtenida.

| Endpoint | Petición verificada | Fecha | Formato observado | Verificado por |
|---|---|---|---|---|
| _(vacío)_ | | | | |

**Estado: ningún endpoint verificado.** Mientras esta tabla siga vacía, Batchwork no
hace llamadas de red. Si un paso las necesita, se pregunta antes de escribir la URL.
