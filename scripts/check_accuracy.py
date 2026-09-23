import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from biwenger_bot.accuracy import check_predictions
from biwenger_bot.client import BiwengerClient

load_dotenv()

client = BiwengerClient()
client.login(os.environ["BIWENGER_EMAIL"], os.environ["BIWENGER_PASSWORD"])
account = client.account()["data"]
league_info = account["leagues"][0]
client.league_id = league_info["id"]
client.team_id = league_info["user"]["id"]
client.version = account["version"]

new_rows = check_predictions(client)
if not new_rows:
    print("Nada nuevo que comprobar (o la jornada de la última recomendación aún no ha terminado).")
for row in new_rows:
    print(f"\n{row['date']} — error medio: {row['mean_absolute_error']:.2f} pts, sesgo: {row['bias']:+.2f}")
    for p in sorted(row["players"], key=lambda x: -abs(x["error"])):
        print(f"  {p['name']:<20} previsto={p['predicted']:>5} real={p['actual']:>5} error={p['error']:+.1f}")
