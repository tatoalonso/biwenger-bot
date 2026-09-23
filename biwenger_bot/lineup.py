import pulp

POSITIONS = {1: "PT", 2: "DF", 3: "MC", 4: "DL"}

# Las 14 formaciones reales que admite Biwenger (sacadas del código fuente de
# la web, no de una lista genérica de internet -- esa nos había fallado, no
# incluía "4-2-4" que sí es real). Todas suman 10 de campo + 1 portero = 11.
FORMATIONS = {
    "3-4-3": {"PT": 1, "DF": 3, "MC": 4, "DL": 3},
    "4-3-3": {"PT": 1, "DF": 4, "MC": 3, "DL": 3},
    "4-5-1": {"PT": 1, "DF": 4, "MC": 5, "DL": 1},
    "5-4-1": {"PT": 1, "DF": 5, "MC": 4, "DL": 1},
    "3-3-4": {"PT": 1, "DF": 3, "MC": 3, "DL": 4},
    "4-6-0": {"PT": 1, "DF": 4, "MC": 6, "DL": 0},
    "3-2-5": {"PT": 1, "DF": 3, "MC": 2, "DL": 5},
    "3-5-2": {"PT": 1, "DF": 3, "MC": 5, "DL": 2},
    "4-4-2": {"PT": 1, "DF": 4, "MC": 4, "DL": 2},
    "5-3-2": {"PT": 1, "DF": 5, "MC": 3, "DL": 2},
    "3-6-1": {"PT": 1, "DF": 3, "MC": 6, "DL": 1},
    "4-2-4": {"PT": 1, "DF": 4, "MC": 2, "DL": 4},
    "5-2-3": {"PT": 1, "DF": 5, "MC": 2, "DL": 3},
    "5-1-4": {"PT": 1, "DF": 5, "MC": 1, "DL": 4},
}

# Biwenger's set_lineup (PUT /user) rejects playersID unless it's ordered
# goalkeeper first, then by position -- sending it in solver-iteration order
# fails with "Invalid player position" for whoever lands in the wrong slot
# (confirmed against the real API, 2026-09-23).
_POSITION_ORDER = {"PT": 0, "DF": 1, "MC": 2, "DL": 3}


def ordered_player_ids(starters):
    """Starter dicts (with a "position" key) -> ids in the order set_lineup() needs."""
    return [p["id"] for p in sorted(starters, key=lambda p: _POSITION_ORDER[p["position"]])]


_RESERVE_SLOTS = ["PT", "DF", "MC", "DL"]


def pick_reserves(starters, players, max_per_club=2):
    """One reserve per position (PT/DF/MC/DL, None if none fits) from whoever
    isn't starting -- exactly the 4 fixed slots reservesID expects.

    lineupMaxClubPlayers counts starters AND reserves together (confirmed
    against the real API: submitting a 3rd player from the same club, split
    between starters and reserves, was rejected with "Maximum club players
    reached") -- so this has to know who's already starting, not just pick
    the 4 best remaining players independently of them.
    """
    starter_ids = {p["id"] for p in starters}
    club_counts = {}
    for p in starters:
        if p.get("club_id") is not None:
            club_counts[p["club_id"]] = club_counts.get(p["club_id"], 0) + 1

    remaining = [p for p in players if p["id"] not in starter_ids]
    reserves = []
    for position in _RESERVE_SLOTS:
        candidates = sorted(
            (p for p in remaining if p["position"] == position and p["id"] not in {r["id"] for r in reserves if r}),
            key=lambda p: -p["predicted_points"],
        )
        pick = next(
            (p for p in candidates if club_counts.get(p.get("club_id"), 0) < max_per_club),
            None,
        )
        reserves.append(pick)
        if pick and pick.get("club_id") is not None:
            club_counts[pick["club_id"]] = club_counts.get(pick["club_id"], 0) + 1
    return reserves


def reserve_ids(reserves):
    """reserves (from pick_reserves, may contain None) -> the reservesID list set_lineup() needs."""
    return [p["id"] if p else None for p in reserves]


def optimize_lineup(players, formation, max_per_club=2, captain_max_value=5_000_000):
    """Pick the 11 (+ captain) that maximize predicted points under the league's rules.

    players: list of dicts with id, name, position ("PT"/"DF"/"MC"/"DL"),
             predicted_points, price, club_id.
    formation: key into FORMATIONS, or a dict like {"PT": 1, "DF": 4, ...}.
    Returns {"starters": [...], "captain": {...} or None, "reserves": [...]
    (4 entries, None for unfilled slots, PT/DF/MC/DL order), "total_points": float}.
    """
    counts = FORMATIONS[formation] if isinstance(formation, str) else formation
    problem = pulp.LpProblem("alineacion", pulp.LpMaximize)

    starts = {p["id"]: pulp.LpVariable(f"start_{p['id']}", cat="Binary") for p in players}
    captains = {
        p["id"]: pulp.LpVariable(f"cap_{p['id']}", cat="Binary")
        for p in players
        if p["price"] <= captain_max_value
    }

    # objective: normal points for starters, plus another copy for the captain (doubles their score)
    problem += pulp.lpSum(p["predicted_points"] * starts[p["id"]] for p in players) + pulp.lpSum(
        p["predicted_points"] * captains[p["id"]] for p in players if p["id"] in captains
    )

    for position, needed in counts.items():
        problem += pulp.lpSum(starts[p["id"]] for p in players if p["position"] == position) == needed

    clubs = {p.get("club_id") for p in players if p.get("club_id") is not None}
    for club_id in clubs:
        problem += pulp.lpSum(starts[p["id"]] for p in players if p.get("club_id") == club_id) <= max_per_club

    # captain must be one of the starters, exactly one captain
    for p in players:
        if p["id"] in captains:
            problem += captains[p["id"]] <= starts[p["id"]]
    problem += pulp.lpSum(captains.values()) == 1

    problem.solve(pulp.PULP_CBC_CMD(msg=0))

    starters = [p for p in players if starts[p["id"]].value() == 1]
    captain = next((p for p in players if p["id"] in captains and captains[p["id"]].value() == 1), None)

    total_points = sum(p["predicted_points"] for p in starters)
    if captain:
        total_points += captain["predicted_points"]

    reserves = pick_reserves(starters, players, max_per_club)

    return {"starters": starters, "captain": captain, "reserves": reserves, "total_points": total_points}


def best_lineup(players, max_per_club=2, captain_max_value=5_000_000):
    """Try every valid Biwenger formation and return the one with the highest total."""
    results = {
        name: optimize_lineup(players, counts, max_per_club, captain_max_value)
        for name, counts in FORMATIONS.items()
    }
    best_formation = max(results, key=lambda name: results[name]["total_points"])
    return best_formation, results[best_formation]
