# Preguntas abiertas

Regla 4, aplicada más allá de las URLs: lo que no está verificado no se escribe, se
pregunta. Cada entrada dice qué está bloqueado y qué se necesita exactamente para
desbloquearlo.

## 1. Definición de la asimetría (paso 7) — **bloqueante**

`hard_filters.filter_asymmetry` devuelve `NOT_RUN` mientras no llegue la definición. El
valor esperado está anotado (2.98 kcal/mol para `TTTCTATATTTGTAACTTTGCA`, y negativo
para los offsets 2–4 del mismo bloque), pero reproducirlo requiere saber:

1. **Qué se compara.** ¿ΔG del extremo 5' de la guía menos ΔG del extremo 5' de la
   pasajera? ¿Con qué signo, es decir, positivo = extremo 5' de la guía más débil?
2. **Cuántos pares de bases** entran en cada extremo: ¿4 nt, 5 nt, un solo par
   terminal?
3. **Qué tabla de vecino más próximo**: SantaLucia 2004 (ADN), Turner 2004 (ARN), otra;
   y a qué temperatura.
4. **Si se calcula sobre la guía ya transformada** (con la U forzada en la posición 1,
   paso 6) o sobre la secuencia original. Cambia el par terminal, y con él el resultado.

Con esas cuatro respuestas escribo el modelo, lo enchufo como `asymmetry_model` y el
test que hoy comprueba `NOT_RUN` pasa a comprobar 2.98. Intentar deducirlo probando
tablas hasta que salga 2.98 sería fabricar el resultado; por eso no se ha hecho.

## 2. Motivo G-cuádruplex (paso 8) — asunción, confirmar

Implementado con el patrón canónico: cuatro tramos de ≥3 G separados por 1–7 nt
(`G{3,}N{1,7}G{3,}N{1,7}G{3,}N{1,7}G{3,}`), aplicado sobre la ventana diana. Si el
prompt 1 usaba otro criterio (por ejemplo tramos de ≥2 G, o evaluarlo sobre la guía),
dímelo: es un cambio de una línea.

## 3. Guía y U forzada (paso 6) — asunción, confirmar

`guide_from_target` = complementario inverso en notación ARN, y después la posición 1 se
fuerza a U. Queda por confirmar si esa U forzada debe reflejarse también en el sitio
diana que se reporta, o solo en el oligo.

## 4. Endpoints

Ninguno verificado desde este proyecto: la política de red del entorno rechaza el
CONNECT a NCBI, Ensembl, UCSC y miRBase. Ver `endpoints-verificados.md`.
