# Bot de Biwenger

Sistema con LLM que juegue por mí en Biwenger (fantasy de fútbol).

## Objetivo

Que el sistema tome o proponga decisiones de juego: fichajes, ventas,
alineación y pujas, con criterio propio y datos actualizados.

## Piezas del sistema

Son tres bloques bastante independientes. El scraping es la base: sin
datos, los otros dos no existen.

### 1. Scraping de la liga — ✅ hecho

- API de Biwenger reversada e implementada en `biwenger_bot/client.py`:
  login, plantilla, liga, mercado, histórico, y acciones de escritura
  (pujar, vender, alinear — estas últimas sin probar todavía en real).
- Persistencia entre ejecuciones: todavía no implementada (de momento
  cada script vuelve a pedir los datos a la API).

### 2. Estimación del dinero de los rivales — ✅ hecho

- Implementado en `biwenger_bot/money.py`, validado al céntimo contra
  el saldo real propio (`scripts/money_report.py`).
- Fórmula: presupuesto inicial del reset de temporada (20M, confirmado
  por texto de la propia liga) + ventas − compras + primas (jornada,
  racha diaria) + préstamos netos − subidas de cláusula.
- Limitación conocida: solo hay verdad-terreno para el equipo propio;
  un mecanismo de dinero que nadie en la liga haya usado nunca podría
  pasar desapercibido (ya pasó una vez con los préstamos).

### 3. Recomendaciones con LLM

- Entrada: estado de mi plantilla + mercado + dinero estimado de rivales.
- Acceso a web para noticias: lesiones, alineaciones probables,
  sanciones, rotaciones.
- Salida: qué pujar y cuánto, a quién vender, cómo alinear.

## Decisiones pendientes

- **Dónde corre**: Raspberry Pi, con ejecución diaria programada
  (cron). Pendiente de montar.
- **Vigilancia del mercado**: el mercado rota a diario, así que algo
  tiene que ejecutarse solo si quiero no perderme nada.
- **Nivel de autonomía**: ¿decide y ejecuta, o solo propone y yo
  confirmo? Empezar por proponer es más seguro.

## Requisitos descubiertos

- **Login diario obligatorio**: Biwenger da 250.000€ de prima por
  conectarse 5 días seguidos (movimiento `bonus`/`dailyStreak` en el
  histórico). La ejecución diaria en la Raspberry debe hacer login
  siempre, aunque ese día no haya ninguna otra acción que tomar, para
  no romper la racha.

## Por dónde empezar

Bloques 1 y 2 (scraping y dinero de rivales) hechos. Lo que queda:

- Bloque 3 (recomendaciones con LLM) — sin empezar.
- Validar en real las acciones de escritura (pujar, vender, alinear)
  antes de fiarse de ellas.
- Montar la ejecución diaria en la Raspberry (incluyendo el login
  diario para no perder la prima por racha).

## Notas

- Entorno: MacBook Pro 13" 2017, Intel i5, 8 GB. Suficiente para
  scraping y llamadas a API; nada de modelos en local.
- El LLM iría por API pagada de mi bolsillo (el presupuesto de
  formación de la empresa no cubre APIs).
