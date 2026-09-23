import json
import os
from datetime import datetime

DEFAULT_SNAPSHOT_PATH = "data/rival_cash.jsonl"

# Regla de reparto inicial de la liga: en cada reset ("Nueva temporada" o alta de
# nuevo miembro) se entrega una plantilla aleatoria (gratis, no sale de este dinero)
# más esta cantidad en efectivo.
INITIAL_BUDGET = 20_000_000


def to_yymmdd(unix_ts):
    return int(datetime.fromtimestamp(unix_ts).strftime("%y%m%d"))


def last_reset_date(board):
    """Unix timestamp of the most recent season reset, or None if the board doesn't cover one."""
    resets = [m["date"] for m in board if m["type"] == "leagueReset"]
    return max(resets) if resets else None


def _movement_contents(board, types):
    for movement in board:
        if movement["type"] in types and isinstance(movement["content"], list):
            for content in movement["content"]:
                yield movement, content


def sold_amount(board, team_id, since):
    return sum(
        content["amount"]
        for movement, content in _movement_contents(board, ("transfer", "adminTransfer"))
        if movement["date"] >= since and content.get("from", {}).get("id") == team_id
    )


def bought_amount(board, team_id, since):
    return sum(
        content["amount"]
        for movement, content in _movement_contents(board, ("transfer", "market"))
        if movement["date"] >= since and content.get("to", {}).get("id") == team_id
    )


def loan_net_amount(board, team_id, since):
    """Net cash from lending/borrowing players: lending out earns a fee, borrowing costs one."""
    lent = sum(
        content["amount"]
        for movement, content in _movement_contents(board, ("loan",))
        if movement["date"] >= since and content.get("from", {}).get("id") == team_id
    )
    borrowed = sum(
        content["amount"]
        for movement, content in _movement_contents(board, ("loan",))
        if movement["date"] >= since and content.get("to", {}).get("id") == team_id
    )
    return lent - borrowed


def clause_increment_amount(board, team_id, since):
    """Money spent voluntarily raising a player's own release clause."""
    return sum(
        content["amount"]
        for movement, content in _movement_contents(board, ("clauseIncrement",))
        if movement["date"] >= since and content.get("user", {}).get("id") == team_id
    )


def _latest_round_finished_movements(board, since):
    """One roundFinished movement per jornada, keeping only the latest recalculation.

    A jornada with postponed matches ("splitRound": "recalculation" in league settings)
    gets a second roundFinished event once those matches are played, whose bonus figures
    are a full recalculation of the round -- not an addition on top of the first one.
    Keying by the jornada name with any "(aplazada...)" suffix stripped, and keeping the
    highest `part`, avoids double-counting that round's prize money.
    """
    latest_by_round = {}
    for movement in board:
        if movement["type"] != "roundFinished" or movement["date"] < since:
            continue
        round_info = movement["content"]["round"]
        key = round_info["name"].split(" (")[0]
        part = round_info.get("part", 1)
        if key not in latest_by_round or part > latest_by_round[key][0]:
            latest_by_round[key] = (part, movement)
    return [movement for _, movement in latest_by_round.values()]


def awards_amount(board, team_id, since):
    round_bonus = sum(
        result["bonus"]
        for movement in _latest_round_finished_movements(board, since)
        for result in movement["content"]["results"]
        if result.get("user", {}).get("id") == team_id and "bonus" in result
    )
    other_bonus = sum(
        content["amount"]
        for movement, content in _movement_contents(board, ("bonus",))
        if movement["date"] >= since and content.get("user", {}).get("id") == team_id
    )
    return round_bonus + other_bonus


def estimate_cash(team_id, board, since, initial_budget=INITIAL_BUDGET):
    """Estimate a team's current cash balance from its public transaction history.

    cash = initial_budget + sold - bought + awards + loan fees (net) - clause increments,
    counting only movements since the team's last squad/balance reset (new season, or
    the team joining the league).
    """
    return (
        initial_budget
        + sold_amount(board, team_id, since)
        - bought_amount(board, team_id, since)
        + awards_amount(board, team_id, since)
        + loan_net_amount(board, team_id, since)
        - clause_increment_amount(board, team_id, since)
    )


def record_snapshot(client, board, league, path=DEFAULT_SNAPSHOT_PATH, date=None):
    """Append today's estimated cash for every team in the league to
    data/rival_cash.jsonl -- one row per team per day, deduped by (date,
    team_id) so this is safe to call more than once on the same day (e.g. if
    the cron runs twice). Shown as context in the Telegram message, not fed
    to the LLM.
    """
    reset = last_reset_date(board) or 0
    today = date or datetime.now().strftime("%Y-%m-%d")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    seen = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                seen.add((row["date"], row["team_id"]))

    new_rows = []
    for standing in league["standings"]:
        if (today, standing["id"]) in seen:
            continue
        team = client.team(standing["id"])["data"]
        since = max(reset, team["joinDate"])
        cash = estimate_cash(standing["id"], board, since)
        new_rows.append(
            {
                "date": today,
                "team_id": standing["id"],
                "team_name": standing["name"],
                "cash": cash,
                "team_value": standing.get("teamValue", 0),
            }
        )

    if new_rows:
        with open(path, "a") as f:
            for row in new_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return new_rows
