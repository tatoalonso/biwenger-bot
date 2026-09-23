import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from biwenger_bot.client import BiwengerClient
from biwenger_bot.lineup import POSITIONS, best_lineup

load_dotenv()

client = BiwengerClient()
client.login(os.environ["BIWENGER_EMAIL"], os.environ["BIWENGER_PASSWORD"])
account = client.account()["data"]
league_info = account["leagues"][0]
client.league_id = league_info["id"]
client.team_id = league_info["user"]["id"]
client.version = account["version"]

team = client.team()["data"]
all_players = client.competition_players()

players = []
for p in team["players"]:
    info = all_players.get(str(p["id"])) or all_players.get(p["id"])
    if not info:
        continue
    played = info.get("playedHome", 0) + info.get("playedAway", 0)
    average = info["points"] / played if played else 0
    # fiabilidad: de las últimas 5 jornadas, en cuántas jugó de verdad (fitness=None si no jugó)
    fitness = info.get("fitness") or []
    reliability = sum(1 for f in fitness if f is not None) / len(fitness) if fitness else 0
    # placeholder "predicted points" -- media histórica * fiabilidad, hasta que esto lo calcule el LLM
    predicted_points = average * reliability
    players.append(
        {
            "id": p["id"],
            "name": info["name"],
            "position": POSITIONS[info["position"]],
            "predicted_points": round(predicted_points, 2),
            "price": info["price"],
            "club_id": info["teamID"],
        }
    )

print("Plantilla usada (id, nombre, posición, puntos previstos*, precio):")
for p in sorted(players, key=lambda x: -x["predicted_points"]):
    print(f"  {p['name']:<22} {p['position']}  {p['predicted_points']:>5}  {p['price']:>10,}")
print("* media histórica * fiabilidad (partidos jugados de las últimas 5 jornadas) como placeholder, aún sin LLM\n")

formation, result = best_lineup(players)
print(f"=== Mejor formación: {formation} (total previsto: {result['total_points']:.2f}) ===")
for p in result["starters"]:
    marca = " (C)" if result["captain"] and p["id"] == result["captain"]["id"] else ""
    print(f"  {p['position']}  {p['name']}{marca}  ({p['predicted_points']} pts)")
