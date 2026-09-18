# Bot de Biwenger

Sistema con LLM que juegue por mí en Biwenger (fantasy de fútbol).

## Objetivo

Que el sistema tome o proponga decisiones de juego: fichajes, ventas,
alineación y pujas, con criterio propio y datos actualizados.

## Piezas del sistema

Son tres bloques bastante independientes. El scraping es la base: sin
datos, los otros dos no existen.

### 1. Scraping de la liga

- Extraer estado de mi liga: plantillas, saldos, movimientos de mercado.
- Los endpoints de la API de Biwenger no están identificados. Hay que
  investigarlos desde cero (DevTools del navegador, ver qué llamadas
  hace la web).
- Decidir cómo autenticar y cómo persistir los datos entre ejecuciones.

### 2. Estimación del dinero de los rivales

- Biwenger no muestra el saldo de los demás.
- Se deduce a partir del histórico: presupuesto inicial, compras,
  ventas, primas por puntos.
- Requiere guardar el histórico de movimientos desde el principio; es
  un cálculo acumulativo, no una foto puntual.

### 3. Recomendaciones con LLM

- Entrada: estado de mi plantilla + mercado + dinero estimado de rivales.
- Acceso a web para noticias: lesiones, alineaciones probables,
  sanciones, rotaciones.
- Salida: qué pujar y cuánto, a quién vender, cómo alinear.

## Decisiones pendientes

- **Dónde corre**: script local que lanzo a mano, tarea programada, o
  servicio 24/7. Sin decidir.
- **Vigilancia del mercado**: el mercado rota a diario, así que algo
  tiene que ejecutarse solo si quiero no perderme nada.
- **Nivel de autonomía**: ¿decide y ejecuta, o solo propone y yo
  confirmo? Empezar por proponer es más seguro.

## Por dónde empezar

Scraping. Concretamente: abrir Biwenger en el navegador con DevTools,
mirar qué peticiones lanza, y conseguir sacar por consola la lista de
jugadores de mi plantilla. Ese es el primer hito real.

## Notas

- Entorno: MacBook Pro 13" 2017, Intel i5, 8 GB. Suficiente para
  scraping y llamadas a API; nada de modelos en local.
- El LLM iría por API pagada de mi bolsillo (el presupuesto de
  formación de la empresa no cubre APIs).
