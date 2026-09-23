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
(cuántos partidos ha disputado), y posición (PT/DF/MC/DL, cada una puntúa de \
forma distinta). No tengas en cuenta el precio ni la cláusula del jugador, solo \
su rendimiento esperado.

Jugadores (JSON):
{players_json}

Devuelve una predicción para cada player_id de la lista, ni uno más ni uno menos.
"""


def _players_prompt_json(players):
    fields = ["id", "name", "position", "status", "statusInfo", "fitness", "points", "playedHome", "playedAway"]
    return json.dumps([{k: p.get(k) for k in fields if k in p} for p in players], ensure_ascii=False)


def predict_points(players, repo_root=".", timeout=180):
    """Ask headless Claude Code for predicted fantasy points per player.

    players: list of dicts (raw competition_players() entries work directly).
    Returns (predictions, cost_usd) where predictions is
    {player_id: {"predicted_points": float, "reason": str}} and cost_usd is the
    client-side estimate of subscription usage consumed by the call (not a
    separate charge -- see biwenger-bot.md). Uses the caller's Claude
    subscription (no --bare, no API key).
    """
    prompt = PROMPT_TEMPLATE.format(players_json=_players_prompt_json(players))

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
