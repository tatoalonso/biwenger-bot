import json
import os
from datetime import datetime

from biwenger_bot.money import last_reset_date

DEFAULT_HISTORY_PATH = "data/bid_history.jsonl"


def to_yymmdd(unix_ts):
    return int(datetime.fromtimestamp(unix_ts).strftime("%y%m%d"))


def _price_at(prices, date_yymmdd):
    candidates = [price for date, price in prices if date <= date_yymmdd]
    return candidates[-1] if candidates else prices[0][1]


def _is_free_agent(board, player_id, market_date, window_seconds=3600 * 24 * 3):
    """A market resolution is for an owned player if a paired `transfer` (with
    `from`, no `to`) shows up close in time for the same player -- the seller
    getting paid. No pairing found this season so far (everyone who trades an
    owned player uses a clause or a direct transfer instead), but the check
    stays in case that ever happens."""
    for m in board:
        if m["type"] != "transfer" or abs(m["date"] - market_date) > window_seconds:
            continue
        for c in m["content"]:
            if c.get("player") == player_id and "from" in c and "to" not in c:
                return False
    return True


def record_market_resolutions(client, board, history_path=DEFAULT_HISTORY_PATH, since=None):
    """Append newly-seen `market` board movements to the bid history file.

    Computes bidder_count and overbid_pct (vs. the player's market value that
    day) for each resolution, and skips ones already recorded (by date+player)
    so this is safe to call repeatedly (e.g. daily from cron) as the season
    progresses. Player price history only covers ~1 year, so once a
    resolution ages out of that window it can never be recomputed -- this is
    the only place that data survives long-term.

    `since` defaults to this season's reset date (via last_reset_date(board))
    so old seasons never leak in just because a caller forgot to pass it --
    pass an explicit value only to deliberately widen or narrow the window.
    """
    if since is None:
        since = last_reset_date(board) or 0

    os.makedirs(os.path.dirname(history_path) or ".", exist_ok=True)

    seen = set()
    if os.path.exists(history_path):
        with open(history_path) as f:
            for line in f:
                row = json.loads(line)
                seen.add((row["date"], row["player_id"]))

    player_cache = {}

    def get_player(player_id):
        if player_id not in player_cache:
            player_cache[player_id] = client.player(player_id)
        return player_cache[player_id]

    new_rows = []
    for m in board:
        if m["type"] != "market" or m["date"] < since:
            continue
        for c in m["content"]:
            player_id = c["player"]
            if (m["date"], player_id) in seen:
                continue
            value = _price_at(get_player(player_id)["prices"], to_yymmdd(m["date"]))
            if not value:
                continue
            bidder_count = 1 + len(c.get("bids", []))
            new_rows.append(
                {
                    "date": m["date"],
                    "player_id": player_id,
                    "player_name": get_player(player_id)["name"],
                    "bidder_count": bidder_count,
                    "winning_amount": c["amount"],
                    "value_that_day": value,
                    "overbid_pct": round((c["amount"] - value) / value * 100, 2),
                    "free_agent": _is_free_agent(board, player_id, m["date"]),
                }
            )
            seen.add((m["date"], player_id))

    if new_rows:
        with open(history_path, "a") as f:
            for row in new_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return new_rows


def _load_history(history_path=DEFAULT_HISTORY_PATH, free_agent_only=True):
    if not os.path.exists(history_path):
        return []
    rows = []
    with open(history_path) as f:
        for line in f:
            row = json.loads(line)
            if not free_agent_only or row.get("free_agent", True):
                rows.append(row)
    return rows


def required_overbid_pct(bidder_count, history_path=DEFAULT_HISTORY_PATH, cap_pct=100, min_samples=3):
    """Median historical overbid % needed to win against `bidder_count` rivals.

    Falls back to the closest bidder_count with enough samples if this exact
    count is too sparse (small samples are noisy -- one outlier can swing the
    median a lot). Applies `cap_pct` as a hard ceiling regardless of what the
    data suggests, since it's a policy choice (how much you're willing to
    overpay), not something to infer from history.
    """
    rows = _load_history(history_path)
    by_count = {}
    for row in rows:
        by_count.setdefault(row["bidder_count"], []).append(row["overbid_pct"])

    candidates = sorted(by_count, key=lambda n: (len(by_count[n]) < min_samples, abs(n - bidder_count)))
    if not candidates:
        return None, 0

    chosen = candidates[0]
    values = sorted(by_count[chosen])
    median = values[len(values) // 2]
    return min(median, cap_pct), len(values)
