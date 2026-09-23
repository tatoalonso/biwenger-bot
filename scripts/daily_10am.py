"""Cron de las 10:00 (tras el cierre del mercado de las 7:00). Ver el
diseño completo en biwenger-bot.md, sección "Flujo del cron".

1. Login (prima de racha)
2. Guardar snapshot de caja de rivales -> data/rival_cash.jsonl
3. Guardar resoluciones de mercado -> data/bid_history.jsonl (siempre,
   el histórico de precios caduca en ~1 año)
4. Traer la plantilla actual (ya refleja lo resuelto esta madrugada)
5. Recalcular la alineación óptima con la plantilla actualizada
6. Evaluar fichajes contra el mercado nuevo ya abierto
7. "Enviar" la recomendación (de momento por consola -- el bot de
   Telegram todavía no existe) + log en data/recommendations.jsonl
"""

import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, REPO_ROOT)

from biwenger_bot.bidding import record_market_resolutions
from biwenger_bot.client import BiwengerClient
from biwenger_bot.lineup import POSITIONS, best_lineup
from biwenger_bot.money import record_snapshot
from biwenger_bot.predict import predict_points
from biwenger_bot.transfers import best_transfers

RECOMMENDATIONS_PATH = os.path.join(REPO_ROOT, "data", "recommendations.jsonl")


def notify(text):
    """Placeholder hasta que exista el bot de Telegram -- de momento, consola."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def format_message(lineup_formation, lineup_result, transfer_formation, transfer_result, rival_cash):
    lines = [f"📋 Recomendaciones — {datetime.now().strftime('%Y-%m-%d')}", ""]

    lines.append(f"⚽ Alineación ({lineup_formation}, {lineup_result['total_points']:.1f} pts previstos):")
    for p in lineup_result["starters"]:
        marca = " (C)" if lineup_result["captain"] and p["id"] == lineup_result["captain"]["id"] else ""
        lines.append(f"  {p['position']}  {p['name']}{marca}")
    lines.append("Reservas: " + ", ".join(p["name"] if p else "-" for p in lineup_result["reserves"]))

    lines.append("")
    if not transfer_result["sell"] and not transfer_result["buy"]:
        lines.append("💰 Fichajes: nada que mejore el once hoy.")
    else:
        gain = transfer_result["total_points"] - lineup_result["total_points"]
        lines.append(f"💰 Fichajes ({transfer_formation}, {gain:+.1f} pts, caja tras mover: {transfer_result['cash_after']:,}):")
        for p in transfer_result["sell"]:
            lines.append(f"  VENDER {p['name']} por {p['price']:,}")
        for p in transfer_result["buy"]:
            origen = "libre" if p.get("free_agent") else "de otro mánager"
            lines.append(f"  FICHAR {p['name']} por {p['price']:,} ({origen})")

    lines.append("")
    lines.append("💸 Caja estimada de rivales:")
    for row in sorted(rival_cash, key=lambda r: -r["cash"])[:5]:
        lines.append(f"  {row['team_name']}: {row['cash']:,}")

    return "\n".join(lines)


load_dotenv()

client = BiwengerClient()
client.login(os.environ["BIWENGER_EMAIL"], os.environ["BIWENGER_PASSWORD"])
account = client.account()["data"]
league_info = account["leagues"][0]
client.league_id = league_info["id"]
client.team_id = league_info["user"]["id"]
client.version = account["version"]

board = client.full_board()

print("Guardando snapshot de caja de rivales...")
rival_cash = record_snapshot(client, board, client.league()["data"])

print("Guardando resoluciones de mercado...")
record_market_resolutions(client, board)

print("Trayendo plantilla actual...")
team = client.team()["data"]
market = client.market()["data"]
all_players = client.competition_players()

squad_info = [all_players.get(str(p["id"])) or all_players.get(p["id"]) for p in team["players"]]
squad_info = [p for p in squad_info if p]
squad_ids = {p["id"] for p in squad_info}

candidate_info = []
for s in market["sales"]:
    info = all_players.get(str(s["player"]["id"])) or all_players.get(s["player"]["id"])
    if info and info["id"] not in squad_ids:
        candidate_info.append({**info, "market_price": s["price"], "free_agent": s["user"] is None})

print(f"Pidiendo predicción de puntos al LLM para {len(squad_info) + len(candidate_info)} jugadores...")
predicted, cost_usd = predict_points(squad_info + candidate_info, repo_root=REPO_ROOT)
print(f"(coste estimado: ${cost_usd:.4f})")


def to_player(info, price, free_agent=None):
    entry = {
        "id": info["id"],
        "name": info["name"],
        "position": POSITIONS[info["position"]],
        "predicted_points": predicted.get(info["id"], {}).get("predicted_points", 0),
        "price": price,
        "club_id": info["teamID"],
    }
    if free_agent is not None:
        entry["free_agent"] = free_agent
    return entry


squad = [to_player(p, p["price"]) for p in squad_info]
candidates = [to_player(p, p["market_price"], p["free_agent"]) for p in candidate_info]

print("Recalculando la alineación óptima con la plantilla actual...")
lineup_formation, lineup_result = best_lineup(squad)

print("Evaluando fichajes contra el mercado nuevo...")
cash = league_info["user"]["balance"]
transfer_formation, transfer_result = best_transfers(squad, candidates, cash)

message = format_message(lineup_formation, lineup_result, transfer_formation, transfer_result, rival_cash)
notify(message)

os.makedirs(os.path.dirname(RECOMMENDATIONS_PATH), exist_ok=True)
with open(RECOMMENDATIONS_PATH, "a") as f:
    f.write(
        json.dumps(
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "lineup": {
                    "formation": lineup_formation,
                    "captain_id": lineup_result["captain"]["id"] if lineup_result["captain"] else None,
                    "starter_ids": [p["id"] for p in lineup_result["starters"]],
                    "reserve_ids": [p["id"] if p else None for p in lineup_result["reserves"]],
                    "total_points": lineup_result["total_points"],
                },
                "transfers": {
                    "formation": transfer_formation,
                    "sell_ids": [p["id"] for p in transfer_result["sell"]],
                    "buy_ids": [p["id"] for p in transfer_result["buy"]],
                    "total_points": transfer_result["total_points"],
                    "cash_after": transfer_result["cash_after"],
                },
                "executed": False,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
