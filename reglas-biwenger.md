# Reglas de Biwenger (Primera División)

Copiadas de la ayuda oficial de Biwenger. Fichero aparte para pasarlo
como contexto fijo al LLM (bloque 3) y tenerlo siempre presente en el
diseño — no son reglas nuestras, son las del juego, y varias de ellas
tienen consecuencias directas sobre cómo debe comportarse el bot.

## Configuración de nuestra liga (Ronnie League 8.0)

Esto no son reglas generales de Biwenger, es cómo está configurada
específicamente nuestra liga (sacado de sus ajustes). Cambia si algún
admin la reconfigura.

- **Tipo**: Liga Ultra (permite subastas, ver más abajo).
- **Fichajes**: Normal (`marketMode: "normal"` en la API).
- **Sistema de puntuación**: **Media AS y SofaScore** (`scoreID: 5`,
  no picas puras de Diario AS) — el apartado "Sistema de puntuación:
  Diario AS" de más abajo en este documento es la fórmula de UN
  proveedor, no el sistema completo que aplica en nuestra liga, que
  promedia AS con SofaScore.
- **Súper Pica activada**: +3 puntos extra por alinear al jugador que
  tenga la Súper Pica de Diario AS esa jornada (el MVP de la jornada
  según AS). Coincide con `settings.superPicaExtraPoints: true` en la
  API. Relevante para el solver de alineación: si un jugador de
  nuestra plantilla o candidato del mercado tiene la Súper Pica,
  sumarle +3 a sus puntos previstos antes de optimizar.
- Solo los administradores pueden publicar en el tablón (no afecta a
  la lógica del bot, es una restricción social de la liga).

### Participantes

- Saldo de otros participantes: **oculto** (por eso hace falta
  `money.py` para estimarlo — confirma la premisa original del
  proyecto).
- Privacidad: liga privada, solo amigos invitados.
- Máximo de participantes: sin límite. Expulsión de inactivos: nunca.
- Última conexión: **visible** para el resto — confirmado
  (`showLastAccess: true`).

### Equipos

- Máximo de jugadores en plantilla: **20**.
- Valor de Equipo: sin límite.
- Máximo de jugadores del mismo club real **por plantilla**: **3**.
  Distinto del máximo **en la alineación titular**, que ya sabíamos
  por la API (`lineupMaxClubPlayers: 2`) — son dos restricciones
  separadas: hasta 3 en plantilla, pero máximo 2 de ese club a la vez
  jugando. Relevante para el solver: la restricción de 2 por club va
  en la alineación, no en qué se puede fichar.
- Máximo por posición (PT/DF/MC/DL/E) en plantilla: sin límite en
  ninguna.
- Reparto inicial (nuevo miembro o nueva temporada): **plantilla
  aleatoria + 20.000.000€** — confirma lo que ya teníamos en
  `money.py` (`INITIAL_BUDGET = 20_000_000`), en ambos casos de alta,
  no solo en reset de temporada.

### Alineaciones — clave para el solver

- Multiposición permitida (`lineupMultiPos: true`): un jugador puede
  contar en más de una posición.
- Alineaciones extra permitidas (`lineupAllowExtra: true`).
- Suplentes permitidos (`lineupReserves: true`).
- Entrenadores permitidos (`lineupCoach: true`).
- Ver alineación y puntos de los rivales: **al comenzar la jornada**
  (no antes).
- Alineaciones no válidas: **nunca** se eliminan automáticamente (si
  una alineación deja de ser válida, p. ej. por lesión tras fijarla,
  el sistema no la resetea solo).
- **Límite de jugadores del mismo club en la alineación titular: 2**
  (confirmado, `lineupMaxClubPlayers: 2` — distinto del límite de 3
  en plantilla, ver arriba).
- Cambios de alineación **entre** jornadas: sin límite.
- Cambios de alineación **durante** la jornada: **1** (⚠️ corrige lo
  que dije antes en "Jornadas divididas" — en modo recálculo SÍ se
  permite un cambio durante la jornada, no cero). Restricción: el
  jugador que sale solo puede ser uno que **no haya jugado todavía**.
- Cambios de estrategia (formación) durante la jornada: permitidos.
- **Capitán**: activado, puntúa doble. **Valor de mercado máximo del
  capitán: 5.000.000€** — no puedes nombrar capitán a cualquiera, solo
  a alguien de tu alineación cuyo valor no supere esa cifra. El solver
  tiene que tratar la elección de capitán como una restricción aparte
  (candidatos ≤5M dentro de los 11 ya seleccionados), no asumir que el
  capitán siempre es el jugador de más puntos previstos si ese supera
  el límite de valor.

### Mercado

- **Jugadores libres simultáneos en el mercado: 10** (`marketSize`).
  Aclara algo que asumíamos en `biwenger-bot.md` (bloque 3) como "el
  mercado nunca tiene más de ~15" — ese ~15 que vimos en pruebas
  reales mezclaba jugadores libres (tope de 10) con jugadores puestos
  en venta por mánagers de la liga (sin este tope, se suman aparte).
- Mercado rota **a diario** (`marketSpeed: "daily"`).
- Venta directa (`sales`) caduca a los **7 días** (`daysForSale: 7`)
  — corrige el "48 horas" que sacamos antes de una guía web genérica,
  ver aviso en `biwenger-bot.md`.
- **`maximumBid: "disabled"`** — la "Puja Máxima" que menciona la
  regla general de Fichajes (más abajo) parece estar **desactivada**
  en nuestra liga. No fiarse de un límite de puja máxima automático;
  el único límite real es el saldo disponible.
- Ofertas entre usuarios siempre permitidas (`userOffers: "always"`),
  intercambios de jugadores permitidos (`exchanges: true`).
- Sin límite de ventas simultáneas por usuario (`marketMaxUserSales: -1`).
- Subastas: duración base **12h**, incremento mínimo de puja **5%**
  (`auctionsIncrement: 5`), públicas (`auctionsPublic: true`).

### Cláusulas

- Tipo de cláusula: **"steal"** (el clásico — pagar la cláusula de un
  jugador de otro mánager te lo lleva directamente).
- Importe de la cláusula: **200% del valor de mercado** (`clauseRanges:
  [["inf", 200, "%"]]`) — encaja con lo visto en datos reales (ej.
  Yamal: precio ~26,1M, cláusula 52,24M = exactamente 2x).
- Puedes subir tu propia cláusula (`clauseIncrement: 1`), no bajarla
  (`clauseDecrement: 0`).
- Retraso de activación tras fichar: **7 días** antes de que otros
  puedan ejecutar la cláusula de un jugador que acabas de fichar
  (`clauseActivationDelay`).
- Cláusulas bloqueadas **48h alrededor de cada jornada**
  (`clauseRoundDisabledHours: 48`).
- ⚠️ **Límite por temporada**: puedes ejecutar (robar) cláusulas hasta
  **27 veces** esta temporada (`clauseExecutedLimit`), y a ti te
  pueden ejecutar la cláusula hasta **17 veces** (`clauseReceivedLimit`).
  Relevante si el bot alguna vez recomienda usar cláusulas como
  estrategia — hay un tope real, no es ilimitado.

### Primas por jornada — de dónde sale el número que ya usamos

`money.py` ya suma correctamente el total `bonus` que da la propia API
por jornada (validado, diff 0€), sin reconstruirlo a mano. Esto es
solo para entender de dónde sale ese total, por si hace falta
desglosarlo en el futuro (ej. para explicarle al usuario el porqué de
un ingreso, o para el LLM):

- Por punto conseguido: **35.000€** (`bonusPoint`).
- Fijo por jornada (jugada, con alineación válida): **250.000€**
  (`bonusFixed`).
- Alineación ideal de la jornada: **100.000€** (`bonusIdealLineup`).
- MVP de un partido: **100.000€** (`bonusGameMVP`). MVP de la
  jornada: **200.000€** (`bonusRoundMVP`).
- Por gol: **100.000€** (`bonusGoal`). Por portería a cero:
  **100.000€** (`bonusCleanSheet`) — esto es dinero aparte de los
  puntos de fantasy que da el gol/portería a cero.
- Racha diaria (login 5 días seguidos): **250.000€**
  (`bonusDailyStreak: true`, ya lo teníamos).
- Alineación más rentable / peor alineación: **desactivadas** en
  nuestra liga (`bonusProfitableLineup: 0`, `bonusWorstLineup: 0`).
- ⚠️ Hay también una tabla `bonusRoundPosition` que da bonus por
  posición en la clasificación DE LA JORNADA (no de la liga), de
  100.000€ (posición 2) hasta 1.000.000€ (posición 11) — a primera
  vista parece dar MÁS dinero cuanto PEOR quedas esa jornada, lo cual
  sería un mecanismo de consuelo para el último. No estoy seguro al
  100% de esta lectura (podría estar invertida) — pendiente de
  verificar contra resultados reales antes de asumirlo como cierto.

### Retos y salarios

- Retos: **permitidos** — confirmado (`challengesAllow: true`).
- Salarios: **desactivado** — confirmado, no cobra salarios de la
  plantilla. No hay hueco pendiente en `money.py` por este motivo.

## Generales

- Cada miembro recibe al comienzo del juego o de una nueva temporada
  un equipo completo y/o saldo, según la configuración de la liga.
- El estado de los jugadores, alineaciones posibles o consejos fantasy
  de proveedores externos es meramente orientativo, no determinante.
- Durante el mercado de fichajes, los jugadores pueden cambiar de
  posición o de equipo real según el proveedor de datos.

## Jornadas divididas (partidos aplazados)

Cada liga elige cómo gestionar jornadas con partidos aplazados, entre
varias modalidades disponibles. **La nuestra usa "Jornada única,
entregar puntos y abonos tras cada fase (recálculo)"** — coincide con
`settings.splitRound: "recalculation"`, que ya nos hizo falta corregir
en `money.py` para no contar doble las primas de jornadas aplazadas
(ver bloque 2 en `biwenger-bot.md`).

Cómo funciona este modo:

- Todos los partidos (originales + aplazados) se tratan como **una
  única jornada con una única alineación base** — no hay una
  alineación distinta para la parte aplazada. Matiz (ver ajustes de
  la liga más abajo): sí se permite **1 cambio** durante la jornada,
  y solo con un jugador que no haya jugado todavía — no es tan rígido
  como "cero cambios en toda la jornada".
- Al disputarse la jornada original se calcula y se entregan puntos y
  abonos (excepto primas de posición, alineación ideal/rentable, MVP
  y retos).
- Al disputarse los partidos aplazados (semanas o meses después), la
  jornada se **recalcula** teniendo en cuenta todos los partidos,
  ajustando lo que faltaba sumar o restar — no es un pago aparte, es
  un ajuste del mismo total (confirma lo que ya asumimos en `money.py`).
- Las primas de alineación ideal/rentable y MVP se abonan solo en el
  recálculo final, cuando ya se jugaron todos los partidos.

Ventaja de este modo: una sola alineación por jornada evita que
plantillas grandes opten a más puntos alineando según qué partidos se
van a jugar cada fase.

⚠️ **Inconvenientes relevantes para el bot**:
- Los jugadores de los partidos aplazados hay que alinearlos con
  semanas o meses de antelación (en la alineación única de la
  jornada) — riesgo de que se lesionen, sancionen, o cambien de
  equipo real antes de que se dispute su partido aplazado.
- Un cambio en la configuración de abonos o un reset de liga entre la
  jornada original y el partido aplazado se refleja al recalcular.
- Un jugador puede llegar a puntuar doble si ficha por un equipo de
  los partidos aplazados: juega la primera parte de la jornada con su
  equipo anterior, y el partido aplazado con el nuevo.

### Las otras modalidades que existen (NO son la nuestra)

Por completitud — nuestra liga usa "recálculo" (arriba), no esta. Si
algún día cambiara la configuración de la liga, esto es lo que habría
que rediseñar:

**"Jornada única con bloqueo progresivo de alineaciones"**: también
trata todos los partidos como una jornada única, pero permite
modificar la alineación entre fases (bloques de partidos) en vez de
fijarla toda de golpe.

- Al inicio de la jornada hay que presentar una alineación completa;
  al empezar cada fase, los jugadores de esos partidos quedan
  bloqueados (no sustituibles), pero los no bloqueados sí se pueden
  cambiar para las fases restantes (si encajan con los ya bloqueados).
- El saldo se comprueba **al inicio de cada fase**, no solo al
  principio de la jornada — un saldo negativo puntual solo anula los
  puntos de esa fase, no de toda la jornada.
- Si vendes/pierdes un jugador durante la jornada, puedes rellenar su
  hueco con alguien sin jugar aún cuyo equipo ya haya terminado —
  suma 0 pero evita la penalización de -4 por hueco vacío.
- Huecos vacíos al inicio del primer partido quedan inutilizados para
  siempre (no rellenables después, a diferencia de los que deja un
  jugador vendido/perdido).
- Permite una picaresca real: alinear una estrella, venderla en
  cuanto se bloquea (puntos asegurados), y usar ese dinero para
  fichar y alinear a otra estrella en una fase posterior — duplicando
  efectivamente el rendimiento del presupuesto esa jornada.
- Capitán y Ariete solo se pueden cambiar mientras no estén bloqueados.

**"Dividir en varias jornadas"**: trata cada fase como jornadas
completamente independientes, con puntos y abonos entregados por
separado (las primas de alineación ideal/rentable y MVP sí se abonan
en el último recálculo, como en las otras modalidades).

- Ventaja: más simple, permite alinear con menos antelación (se
  conocen antes lesionados/sancionados de esa fase), y se adapta bien
  a ligas que reinician o cambian configuración entre fases.
- Inconveniente: da ventaja a quien tiene más jugadores de los
  equipos con partidos aplazados o más plantilla en general, al poder
  alinear gente distinta en cada fase y optar a más puntos totales.

**"Jornada única, entregar puntos y abonos tras disputarse TODOS los
partidos"**: como la de recálculo (la nuestra), pero sin entregar
nada — ni puntos ni abonos — hasta que se disputan todos los partidos
de la jornada, evitando así casos como cobrar un abono de colista que
luego haya que devolver al subir en la clasificación tras el partido
aplazado. A cambio, puede no haber ni puntos ni abonos durante
semanas o meses tras el comienzo de la jornada original.

**"Ignorar puntos y abonos de los partidos aplazados"**: solo cuentan
los partidos de la primera fase de la jornada; todo lo disputado en
fechas posteriores (los partidos aplazados en sí) se ignora por
completo, no se recalcula ni se suma nunca.

**"Ignorar puntos y abonos de la primera parte de la jornada"**: al
revés que la anterior — se ignoran los partidos adelantados (el
primer bloque de la jornada dividida), y el resto de partidos
(incluidos los aplazados) se tratan como una única jornada.

**"Ignorar puntos y abonos de todos los partidos de esas jornadas"**:
la más drástica — se ignora completamente toda la jornada dividida
(aplazados y no aplazados), sin puntuar ni abonar nada por ella.

## Puntuación

- Gana quien tenga más puntos a final de temporada. Empate → gana
  quien tenga mayor Valor de Equipo + Saldo.
- Antes de cada jornada se registra la alineación y estrategia fijada.
- **Solo puntúan los jugadores alineados.**
- ⚠️ **Si el saldo es negativo en el momento exacto de comienzo de la
  jornada, no se recibe ningún punto ni abono esa jornada**, aunque
  luego durante la jornada se recupere saldo positivo. Los retos
  activos esa jornada se marcan como perdidos. **Regla crítica para el
  bot: nunca dejar el saldo propio en negativo antes de que arranque
  una jornada.**
- **-4 puntos por cada posición desocupada en la alineación**, salvo
  que esté completamente vacía, en cuyo caso son 0 puntos (no
  acumula -4 por cada una). **Relevante para el solver de alineación**:
  mejor una opción mediocre en una posición que dejarla vacía, salvo
  que llenar todas suponga dejarla completamente vacía (0 siempre
  mejor que muchos -4).
- La puntuación de un jugador en la jornada es la media de sus
  puntos entre partidos disputados (si jugó más de un partido en la
  jornada, ej. por aplazamientos).
- Empate a puntos en la jornada → gana quien tenga mayor valor de
  equipo alineado al comienzo de la jornada (en ligas fantasy, al
  revés: gana el de menor valor).
- Tras cada jornada se recibe saldo según la puntuación conseguida y
  las opciones de la liga.

## Fichajes

- No se puede pujar por encima de la Puja Máxima.
- Pujas por jugadores libres: se procesan cuando expira su tiempo en
  el mercado (configurable por liga), son secretas, gana la más alta;
  empate → gana la primera puja realizada.
- El propio mercado (no otro mánager) puede hacer una oferta de
  compra automática por jugadores puestos a la venta, de +/-5% del
  Valor de Mercado en el momento de la oferta. Se retira si no se
  contesta en 2 días.
- Las ofertas entre usuarios expiran en 7 días si no se contestan.

## Sistema de puntuación: Diario AS

- Se basa en las "picas" (notas) que publica el Diario AS.
- Gol, según posición: PT +6 / DF +5 / MC +4 / DL +3.
- Penalti recibido (independiente de la posición): +3.
- Gol en propia puerta: no resta ni suma puntos por el gol en sí.
- Segunda tarjeta amarilla: -3. Tarjeta roja directa: -6.
- Una sanción penaliza en Biwenger aunque el jugador no haya jugado
  minutos o la sanción no conste en el acta arbitral.
- En caso de duda sobre un evento del partido, prevalece el acta
  arbitral sobre cualquier otra fuente.
- ⚠️ La tabla de "Nota → Puntos" (picas del Diario AS) se pegó desde
  la web y perdió el emparejamiento fila-columna al copiarla —
  valores vistos sueltos: 14, 10, 6, 2, 0, -2, y "SC" (sin calificar)
  → 0. No fiarse de este mapeo hasta verificarlo de nuevo contra la
  fuente original.
