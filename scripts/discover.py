import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from biwenger_bot.client import BiwengerClient

load_dotenv()

email = os.environ["BIWENGER_EMAIL"]
password = os.environ["BIWENGER_PASSWORD"]

client = BiwengerClient()
client.login(email, password)

account = client.account()["data"]
league = account["leagues"][0]

client.league_id = league["id"]
client.team_id = league["user"]["id"]
client.version = account["version"]

print(f"Liga: {league['name']} (id={league['id']})")
print(f"Equipo: {league['user']['name']} (id={league['user']['id']}, balance={league['user']['balance']})")
print()

team = client.team()["data"]
all_players = client.competition_players()

print(f"Plantilla ({len(team['players'])} jugadores):")
for player in team["players"]:
    info = all_players.get(str(player["id"])) or all_players.get(player["id"])
    name = info["name"] if info else f"?(id={player['id']})"
    price = info["price"] if info else None
    print(f"  - {name:<25} precio={price} owner={player.get('owner')}")
