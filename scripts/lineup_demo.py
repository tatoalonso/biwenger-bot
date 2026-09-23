import os
import sys

from dotenv import load_dotenv

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, REPO_ROOT)

from biwenger_bot.client import BiwengerClient
from biwenger_bot.lineup import POSITIONS, best_lineup
from biwenger_bot.predict import predict_points

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

squad_info = []
for p in team["players"]:
    info = all_players.get(str(p["id"])) or all_players.get(p["id"])
    if info:
        squad_info.append(info)

print(f"Pidiendo predicción de puntos al LLM para {len(squad_info)} jugadores...")
predicted, cost_usd = predict_points(squad_info, repo_root=REPO_ROOT)

players = [
    {
        "id": info["id"],
        "name": info["name"],
        "position": POSITIONS[info["position"]],
        "predicted_points": predicted.get(info["id"], {}).get("predicted_points", 0),
        "reason": predicted.get(info["id"], {}).get("reason", ""),
        "price": info["price"],
        "club_id": info["teamID"],
    }
    for info in squad_info
]

print(f"(coste estimado de la llamada, consumido de tu cupo de Pro: ${cost_usd:.4f})\n")
print("Plantilla (nombre, posición, puntos previstos, motivo del LLM):")
for p in sorted(players, key=lambda x: -x["predicted_points"]):
    print(f"  {p['name']:<22} {p['position']}  {p['predicted_points']:>5}  -- {p['reason']}")

formation, result = best_lineup(players)
print(f"\n=== Mejor formación: {formation} (total previsto: {result['total_points']:.2f}) ===")
for p in result["starters"]:
    marca = " (C)" if result["captain"] and p["id"] == result["captain"]["id"] else ""
    print(f"  {p['position']}  {p['name']}{marca}  ({p['predicted_points']} pts)")
