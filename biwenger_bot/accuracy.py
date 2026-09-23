import json
import os

DEFAULT_PATH = "data/prediction_accuracy.jsonl"


def check_predictions(client, recommendations_path="data/recommendations.jsonl", out_path=DEFAULT_PATH):
    """Compare each not-yet-checked recommendation's predicted_points against
    what each player actually scored, and append the result to
    data/prediction_accuracy.jsonl (one row per recommendation date).

    Biwenger doesn't expose "points this specific round" by player id directly
    -- fitness[-1] (the most recent entry in a player's fitness array) is used
    as a stand-in, since it appears to literally be the points scored in the
    most recently finished round (matches season totals when cross-checked).

    ⚠️ Only call this once you know the round that recommendation was made for
    has actually finished -- this always reads the CURRENT fitness[-1], so
    calling it too early compares against a round that hasn't been played yet
    (or the wrong one) instead of failing loudly. Not yet validated end-to-end
    against a real finished round (written during a 2-week international
    break with nothing to check against).
    """
    if not os.path.exists(recommendations_path):
        return []

    recs = [json.loads(line) for line in open(recommendations_path)]
    already_checked = set()
    if os.path.exists(out_path):
        already_checked = {json.loads(line)["date"] for line in open(out_path)}

    all_players = client.competition_players()
    new_rows = []
    for rec in recs:
        if rec["date"] in already_checked:
            continue
        predicted_points = rec["lineup"].get("predicted_points", {})
        if not predicted_points:
            continue

        errors = []
        per_player = []
        for player_id_str, predicted in predicted_points.items():
            info = all_players.get(player_id_str)
            fitness = info.get("fitness") if info else None
            actual = fitness[-1] if fitness else None
            if actual is None or not isinstance(actual, (int, float)):
                continue
            error = predicted - actual
            errors.append(error)
            per_player.append(
                {"player_id": int(player_id_str), "name": info["name"], "predicted": predicted, "actual": actual, "error": error}
            )

        if not errors:
            continue

        row = {
            "date": rec["date"],
            "mean_absolute_error": sum(abs(e) for e in errors) / len(errors),
            "bias": sum(errors) / len(errors),  # positivo = sobreestima, negativo = infraestima
            "players": per_player,
        }
        new_rows.append(row)

    if new_rows:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "a") as f:
            for row in new_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return new_rows
