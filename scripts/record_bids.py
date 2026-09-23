import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from biwenger_bot.bidding import record_market_resolutions, required_overbid_pct
from biwenger_bot.client import BiwengerClient

load_dotenv()

client = BiwengerClient()
client.login(os.environ["BIWENGER_EMAIL"], os.environ["BIWENGER_PASSWORD"])
account = client.account()["data"]
league_info = account["leagues"][0]
client.league_id = league_info["id"]
client.team_id = league_info["user"]["id"]
client.version = account["version"]

board = client.full_board()
new_rows = record_market_resolutions(client, board)
print(f"Filas nuevas guardadas: {len(new_rows)}")

print("\nSobreoferta recomendada por nº de pujantes:")
for n in range(1, 7):
    pct, samples = required_overbid_pct(n)
    if pct is not None:
        print(f"  {n} pujantes -> {pct}% (basado en {samples} muestras)")
