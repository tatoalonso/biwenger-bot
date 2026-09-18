import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from biwenger_bot.client import BiwengerClient
from biwenger_bot.money import estimate_cash, last_reset_date

load_dotenv()

client = BiwengerClient()
client.login(os.environ["BIWENGER_EMAIL"], os.environ["BIWENGER_PASSWORD"])

account = client.account()["data"]
league_info = account["leagues"][0]
client.league_id = league_info["id"]
client.team_id = league_info["user"]["id"]
client.version = account["version"]

board = client.full_board()
reset = last_reset_date(board)

league = client.league()["data"]

my_team_id = league_info["user"]["id"]
my_team = client.team(my_team_id)["data"]
my_since = max(reset or 0, my_team["joinDate"])
my_estimate = estimate_cash(my_team_id, board, my_since)
my_real = league_info["user"]["balance"]

print(f"Validación (tu equipo) -> estimado: {my_estimate:,}  real: {my_real:,}  diff: {my_estimate - my_real:,}\n")

rows = []
for standing in league["standings"]:
    team = client.team(standing["id"])["data"]
    since = max(reset or 0, team["joinDate"])
    cash = estimate_cash(standing["id"], board, since)
    rows.append((standing["name"], cash, standing.get("teamValue", 0)))

rows.sort(key=lambda r: r[1] + r[2], reverse=True)

print(f"{'Equipo':<28}{'Caja estimada':>16}{'Valor plantilla':>18}{'Total':>16}")
for name, cash, value in rows:
    print(f"{name:<28}{cash:>16,}{value:>18,}{cash + value:>16,}")
