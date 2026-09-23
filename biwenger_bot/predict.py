import json
import os
import subprocess

RULES_FILES = ["biwenger-bot.md", "reglas-biwenger.md"]

SCHEMA = {
    "type": "object",
    "properties": {
        "predictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "player_id": {"type": "integer"},
                    "predicted_points": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["player_id", "predicted_points"],
            },
        }
    },
    "required": ["predictions"],
}

PROMPT_TEMPLATE = """\
Eres un analista de fantasy football para Biwenger (La Liga). Para cada jugador \
de la lista de abajo, estima cuántos puntos fantasy va a hacer en la PRÓXIMA \
jornada.

Ten en cuenta: forma reciente (fitness, últimos partidos, null = no jugó), \
estado (lesión/sanción/duda, con statusInfo si lo hay), fiabilidad de jugar \
(cuántos partidos ha disputado), posición (PT/DF/MC/DL, cada una puntúa de \
forma distinta), y si viene incluido, la dificultad del próximo rival \
(next_match: home/away + estadísticas del equipo contrario -- un rival \
más fuerte o jugar fuera de casa reduce la puntuación esperada). No tengas \
en cuenta el precio ni la cláusula del jugador, solo su rendimiento esperado.

Jugadores (JSON):
{players_json}

Devuelve una predicción para cada player_id de la lista, ni uno más ni uno menos.
"""


def next_match_difficulty(season):
    """club_id -> {"home": bool, "opponent_difficulty": {...}} for the next
    round that hasn't finished yet (competition_season()'s "rounds" list --
    covers pending rounds too, unlike activeEvents which is empty outside the
    lineup-setting window, e.g. during an international break).
    """
    rounds = season.get("rounds", []) if season else []
    next_round = next((r for r in rounds if r.get("status") != "finished"), None)
    if not next_round:
        return {}

    by_club = {}
    for game in next_round.get("games", []):
        home, away = game.get("home"), game.get("away")
        if home and away and "difficulty" in away:
            by_club[home["id"]] = {"home": True, "opponent_difficulty": away["difficulty"]}
        if home and away and "difficulty" in home:
            by_club[away["id"]] = {"home": False, "opponent_difficulty": home["difficulty"]}
    return by_club


def _players_prompt_json(players, difficulty_by_club=None):
    fields = ["id", "name", "position", "status", "statusInfo", "fitness", "points", "playedHome", "playedAway"]
    difficulty_by_club = difficulty_by_club or {}
    rows = []
    for p in players:
        row = {k: p.get(k) for k in fields if k in p}
        next_match = difficulty_by_club.get(p.get("club_id") or p.get("teamID"))
        if next_match:
            row["next_match"] = next_match
        rows.append(row)
    return json.dumps(rows, ensure_ascii=False)


def predict_points(players, repo_root=".", timeout=180, season=None):
    """Ask headless Claude Code for predicted fantasy points per player.

    players: list of dicts (raw competition_players() entries work directly --
             needs a "club_id" or "teamID" key for next_match_difficulty to attach).
    season: client.competition_season()'s return value, for next-opponent
            difficulty -- optional, omitted gracefully if not passed.
    Returns (predictions, cost_usd) where predictions is
    {player_id: {"predicted_points": float, "reason": str}} and cost_usd is the
    client-side estimate of subscription usage consumed by the call (not a
    separate charge -- see biwenger-bot.md). Uses the caller's Claude
    subscription (no --bare, no API key).
    """
    difficulty_by_club = next_match_difficulty(season)
    prompt = PROMPT_TEMPLATE.format(players_json=_players_prompt_json(players, difficulty_by_club))

    cmd = ["claude", "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(SCHEMA), "--permission-prompts", "none"]
    for rules_file in RULES_FILES:
        path = os.path.join(repo_root, rules_file)
        if os.path.exists(path):
            cmd += ["--append-system-prompt-file", path]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=repo_root)
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:2000]}")

    response = json.loads(result.stdout)
    predictions = response["structured_output"]["predictions"]
    by_id = {p["player_id"]: {"predicted_points": p["predicted_points"], "reason": p.get("reason", "")} for p in predictions}
    return by_id, response.get("total_cost_usd")
