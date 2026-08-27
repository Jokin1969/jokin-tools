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

En cuanto el commit llega a `main`, Railway despliega y, al arrancar, el servidor
**copia automáticamente** lo que hay aquí a su almacenamiento persistente — de ahí
es de donde de verdad se sirven las fotos. Esta carpeta es solo la forma de
**entregarlas** (por GitHub, sin acceso al servidor); no hace falta tocar nada
más, ni aquí ni en el servidor.

Borrar un fichero de aquí también lo borra del servidor en el siguiente
despliegue — la carpeta del repo manda siempre.

Si un medicamento no tiene foto aquí, Pastillero, Data Matrix y Asignación
muestran en su lugar el icono de color/forma que ya usan (nunca un icono de
"imagen rota"); Galénica muestra un hueco vacío con «Sin foto».
