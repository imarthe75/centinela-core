# Lecciones operativas (errores que cualquier proyecto repite)

1. **Recorridos de árbol con tope y exclusiones.** Un recorrido sin límites sobre un directorio con cachés (Gradle, Maven, `node_modules`, `data/`) puede tardar horas. Excluye directorios generados y pon un tope de archivos/tiempo.
2. **Código viejo que sigue ejecutándose.** Tras mover o renombrar módulos, limpia `__pycache__` y reinicia; verifica lo cargado con `inspect.getsource`, no con la fecha del archivo.
3. **Variables de entorno de contenedor.** Un cambio en el `environment:` exige recrear el contenedor; reiniciar no basta.
4. **`py_compile` escribe un archivo.** Para solo validar sintaxis usa `compile(texto, nombre, "exec")`.
5. **Nunca `chmod -R`/`setfacl -R` sobre el proyecto entero.** Deja las llaves SSH con permisos laxos y SSH las rechaza (`0600`).
6. **Un índice se pierde al reemplazar una columna** (`DROP`+`RENAME`); recréalos. Un agregado (`MAX`) puede no existir para un tipo (uuid).
7. **Un cambio de versión se prueba, no se supone.** Tras subir una dependencia mayor, construye y ejecuta; compilar el manifiesto no basta.
8. **Dependencias de pago o ajenas** no se llaman en pruebas: usa un doble, y decláralo (`honesty.md` §3).
9. **La existencia de una fila reciente no prueba que algo ocurrió.** Verifica la evidencia cruda (salida, hash, archivo), no solo el registro.
10. **Un cambio que se hizo en el código no es evidencia de que los datos lo reflejen.** Vuelve a ejecutar y comprueba contra la fuente.
