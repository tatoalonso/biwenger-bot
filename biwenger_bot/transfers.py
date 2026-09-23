import pulp

from biwenger_bot.lineup import FORMATIONS


def optimize_transfers(squad, candidates, cash, formation, max_per_club=3, lineup_max_per_club=2, team_max_size=20):
    """Decide which candidates to buy and which squad players to sell -- valuing
    a transfer only if it actually wins a spot in the starting XI. Buying bench
    depth you'd never field is worthless in this model (that was the bug in the
    first version: summing points over the whole squad let it "recommend"
    selling your best player and buying a pile of mediocre ones nobody starts).

    squad/candidates: list of dicts {id, name, position, predicted_points, price, club_id}.
      squad price = what you'd get selling (sell_player() asking price);
      candidates price = cost to acquire (fixed-price market listings only,
      not auctions with an uncertain final price).
    cash: current balance.
    formation: a lineup.FORMATIONS key or an equivalent {"PT":1,...} dict.
    Returns {"sell": [...], "buy": [...], "starting_xi": [...], "captain": None,
    "total_points": float, "cash_after": float}. Doing nothing is always
    feasible, so nothing is recommended unless it beats the current squad.
    """
    counts = FORMATIONS[formation] if isinstance(formation, str) else formation
    pool = squad + candidates
    problem = pulp.LpProblem("fichajes", pulp.LpMaximize)

    start = {p["id"]: pulp.LpVariable(f"start_{p['id']}", cat="Binary") for p in pool}
    sell = {p["id"]: pulp.LpVariable(f"sell_{p['id']}", cat="Binary") for p in squad}
    buy = {c["id"]: pulp.LpVariable(f"buy_{c['id']}", cat="Binary") for c in candidates}

    # objective: points of whoever actually starts, with a tiny nudge against
    # pointless sales so the solver doesn't sell bench players for no reason
    problem += pulp.lpSum(p["predicted_points"] * start[p["id"]] for p in pool) - 0.001 * pulp.lpSum(sell.values())

    for position, needed in counts.items():
        problem += pulp.lpSum(start[p["id"]] for p in pool if p["position"] == position) == needed

    # a candidate can only start if bought; a squad player can't start if sold
    for c in candidates:
        problem += start[c["id"]] <= buy[c["id"]]
    for p in squad:
        problem += start[p["id"]] + sell[p["id"]] <= 1

    # budget: buying costs money, selling raises it
    problem += pulp.lpSum(c["price"] * buy[c["id"]] for c in candidates) <= cash + pulp.lpSum(
        p["price"] * sell[p["id"]] for p in squad
    )

    # squad size after the moves (bench included, not just starters)
    problem += len(squad) - pulp.lpSum(sell.values()) + pulp.lpSum(buy.values()) <= team_max_size

    clubs = {p.get("club_id") for p in pool if p.get("club_id") is not None}
    for club_id in clubs:
        # teamMaxClubPlayers: limit across the whole resulting squad, not just the XI
        current = sum(1 for p in squad if p.get("club_id") == club_id)
        problem += (
            current
            - pulp.lpSum(sell[p["id"]] for p in squad if p.get("club_id") == club_id)
            + pulp.lpSum(buy[c["id"]] for c in candidates if c.get("club_id") == club_id)
            <= max_per_club
        )
        # lineupMaxClubPlayers: limit within the starting XI itself
        problem += pulp.lpSum(start[p["id"]] for p in pool if p.get("club_id") == club_id) <= lineup_max_per_club

    problem.solve(pulp.PULP_CBC_CMD(msg=0))

    sold = [p for p in squad if sell[p["id"]].value() == 1]
    bought = [c for c in candidates if buy[c["id"]].value() == 1]
    starting_xi = [p for p in pool if start[p["id"]].value() == 1]
    total_points = sum(p["predicted_points"] for p in starting_xi)
    cash_after = cash + sum(p["price"] for p in sold) - sum(c["price"] for c in bought)

    return {"sell": sold, "buy": bought, "starting_xi": starting_xi, "total_points": total_points, "cash_after": cash_after}


def best_transfers(squad, candidates, cash, max_per_club=3, lineup_max_per_club=2, team_max_size=20):
    """Try every formation and return the transfer plan with the highest total."""
    results = {
        name: optimize_transfers(squad, candidates, cash, counts, max_per_club, lineup_max_per_club, team_max_size)
        for name, counts in FORMATIONS.items()
    }
    best_formation = max(results, key=lambda name: results[name]["total_points"])
    return best_formation, results[best_formation]
