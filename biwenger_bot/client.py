import requests

AUTH_URL = "https://biwenger.as.com/api/v2/auth/login"
BASE_URL = "https://biwenger.as.com/api/v2"


class BiwengerClient:
    def __init__(self, token=None, league_id=None, team_id=None, version=None):
        self.token = token
        self.league_id = league_id
        self.team_id = team_id
        self.version = version

    def login(self, email, password):
        response = requests.post(
            AUTH_URL,
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        self.token = data.get("token")
        return data

    def _headers(self):
        headers = {"Authorization": f"Bearer {self.token}", "X-Lang": "es"}
        if self.league_id:
            headers["X-League"] = str(self.league_id)
        if self.team_id:
            headers["X-User"] = str(self.team_id)
        if self.version:
            headers["X-Version"] = str(self.version)
        return headers

    def _request(self, method, path, params=None, json_body=None):
        response = requests.request(
            method, f"{BASE_URL}{path}", headers=self._headers(), params=params, json=json_body
        )
        response.raise_for_status()
        return response.json()

    def _get(self, path, params=None):
        return self._request("GET", path, params=params)

    def account(self):
        return self._get("/account")

    def team(self, team_id=None):
        team_id = team_id or self.team_id
        return self._get(
            f"/user/{team_id}",
            params={
                "fields": "*,account(id),players(id,name,position,price,owner),lineups(round,points,count,position),"
                "league(id,name,competition,mode,scoreID),market,seasons,offers,lastPositions"
            },
        )

    def league(self):
        return self._get("/league", params={"include": "all", "fields": "*,standings,group,settings(description)"})

    def board(self, offset=0, limit=500):
        return self._get(f"/league/{self.league_id}/board", params={"offset": offset, "limit": limit})

    def market(self):
        return self._get("/market")

    def market_evolution(self):
        response = requests.get(
            "https://cf.biwenger.com/api/v2/competitions/la-liga/market",
            params={"interval": "day", "includeValues": "true"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        return response.json()

    def competition_players(self):
        """All La Liga players (id, name, team, position, price, ...) in a single call."""
        response = requests.get(
            "https://cf.biwenger.com/api/v2/competitions/la-liga/data",
            params={"score": 5, "lang": "es"},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        return response.json()["data"]["players"]

    def send_to_market(self, price):
        return self._request("POST", "/market", json_body={"type": "team", "price": price})

    def place_offer(self, player_id, amount, to=None, offer_type="team"):
        return self._request(
            "POST",
            "/offers",
            json_body={"amount": amount, "requestedPlayers": [player_id], "to": to, "type": offer_type},
        )

    def respond_to_offer(self, offer_id, accept=True):
        return self._request(
            "PUT", f"/offers/{offer_id}", json_body={"status": "accepted" if accept else "rejected"}
        )

    def set_lineup(self, formation, player_ids):
        return self._request(
            "PUT", "/user", params={"fields": "*"}, json_body={"lineup": {"type": formation, "playersID": player_ids}}
        )
