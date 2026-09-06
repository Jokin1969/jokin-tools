// Adelanta el reloj del proceso ANTES de que se cargue nada más.
//
// Se precarga con `node --require` desde `test/calendario.test.js`. Vive aquí y no
// dentro de ese test porque tiene que estar en marcha antes del primer `require` de la
// aplicación: un módulo que capture `Date` al cargarse ya no vería el parche.
//
// `SALTO_DIAS` es el desplazamiento. Todo lo demás —zona horaria, resolución, formato—
// queda igual: lo que se mueve es CUÁNDO se está corriendo, nada más.
const DIAS = Number(process.env.SALTO_DIAS || 0);
const SALTO = DIAS * 24 * 60 * 60 * 1000;
const Real = Date;

class Adelantada extends Real {
  constructor(...args) {
    if (args.length === 0) super(Real.now() + SALTO);
    else super(...args);
  }
  static now() { return Real.now() + SALTO; }
}
// El nombre y el prototipo se conservan: hay código que hace `x instanceof Date`.
Object.defineProperty(Adelantada, 'name', { value: 'Date' });
globalThis.Date = Adelantada;
