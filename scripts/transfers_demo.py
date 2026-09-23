import os
import sys

from dotenv import load_dotenv

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, REPO_ROOT)

from biwenger_bot.client import BiwengerClient
from biwenger_bot.lineup import POSITIONS, best_lineup
from biwenger_bot.predict import predict_points
from biwenger_bot.transfers import best_transfers

load_dotenv()

client = BiwengerClient()
client.login(os.environ["BIWENGER_EMAIL"], os.environ["BIWENGER_PASSWORD"])
account = client.account()["data"]
league_info = account["leagues"][0]
client.league_id = league_info["id"]
client.team_id = league_info["user"]["id"]
client.version = account["version"]

team = client.team()["data"]
market = client.market()["data"]
all_players = client.competition_players()

squad_info = [all_players.get(str(p["id"])) or all_players.get(p["id"]) for p in team["players"]]
squad_info = [p for p in squad_info if p]
squad_ids = {p["id"] for p in squad_info}

# solo ventas a precio fijo (sales): el precio de compra es conocido, a diferencia
# de una subasta donde no sabemos qué puja hará falta para ganarla.
# user: null en el listado = jugador libre; user: {...} = lo vende otro mánager
# (confirmado hace tiempo contra GET /market en vivo).
candidate_info = []
for s in market["sales"]:
    info = all_players.get(str(s["player"]["id"])) or all_players.get(s["player"]["id"])
    if info and info["id"] not in squad_ids:
        candidate_info.append({**info, "market_price": s["price"], "free_agent": s["user"] is None})

print(f"Plantilla: {len(squad_info)} jugadores. Candidatos en venta directa: {len(candidate_info)}.")
print("Pidiendo predicción de puntos al LLM para todos a la vez...")
predicted, cost_usd = predict_points(squad_info + candidate_info, repo_root=REPO_ROOT)
print(f"(coste estimado: ${cost_usd:.4f})\n")

squad = [
    {
        "id": p["id"],
        "name": p["name"],
        "position": POSITIONS[p["position"]],
        "predicted_points": predicted.get(p["id"], {}).get("predicted_points", 0),
        "price": p["price"],  # lo que sacarías vendiéndolo ahora
        "club_id": p["teamID"],
    }
    for p in squad_info
]
candidates = [
    {
        "id": p["id"],
        "name": p["name"],
        "position": POSITIONS[p["position"]],
        "predicted_points": predicted.get(p["id"], {}).get("predicted_points", 0),
        "price": p["market_price"],  # lo que cuesta ficharlo
        "club_id": p["teamID"],
        "free_agent": p["free_agent"],
    }
    for p in candidate_info
]

cash = league_info["user"]["balance"]
print(f"Caja actual: {cash:,}\n")

baseline_formation, baseline = best_lineup(squad)
print(f"Sin fichar nada, tu mejor once ({baseline_formation}) suma {baseline['total_points']:.2f} puntos previstos.\n")

formation, result = best_transfers(squad, candidates, cash)

if not result["sell"] and not result["buy"]:
    print("Ningún movimiento mejora tu once ahora mismo -- no se recomienda nada.")
else:
    gain = result["total_points"] - baseline["total_points"]
    print(f"Con fichajes, mejor once ({formation}) suma {result['total_points']:.2f} puntos previstos (+{gain:.2f})")
    print(f"Caja tras los movimientos: {result['cash_after']:,}\n")
    for p in result["sell"]:
        print(f"  VENDER  {p['name']:<20} ({p['position']}, {p['predicted_points']} pts) por {p['price']:,}")
    for p in result["buy"]:
        origen = "libre" if p["free_agent"] else "de otro mánager"
        print(f"  FICHAR  {p['name']:<20} ({p['position']}, {p['predicted_points']} pts) por {p['price']:,} -- {origen}")
    print("\nOnce resultante:")
    for p in result["starting_xi"]:
        print(f"  {p['position']}  {p['name']:<20} ({p['predicted_points']} pts)")
