# Fotos de pastilla

Para añadir la foto de un medicamento, sube aquí (en GitHub, en esta misma carpeta)
un PNG llamado exactamente con su **Código Nacional** (CN), sin ceros extra ni
prefijos:

```
702983.png
699154.png
```

- **Formato**: PNG, con fondo transparente si es posible. No uses JPG (no admite
  transparencia).
- **Tamaño**: cualquiera — la app lo ajusta sola al hueco donde se muestra.
- Sustituir una foto ya existente es tan fácil como subir un fichero nuevo con
  el **mismo nombre**: lo reemplaza.

En cuanto el commit llega a `main`, Railway despliega solo y la foto empieza a
verse en Pastillero, Data Matrix y Asignación — no hace falta tocar nada más.

Si un medicamento no tiene foto aquí, esas tres apps muestran en su lugar el
icono de color/forma que ya usan (nunca un icono de "imagen rota").
