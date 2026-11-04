import httpx
import os
import re
from .domain import ALLOWED_GROUPS, normalize_unit


class Monday:
    def __init__(self, token, board_id, version):
        self.token, self.board_id, self.version = token, board_id, version

    async def query(self, query, variables=None):
        if not self.token:
            raise ValueError("MONDAY_TOKEN sozlanmagan")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post("https://api.monday.com/v2", headers={
                "Authorization": self.token, "API-Version": self.version},
                json={"query": query, "variables": variables or {}})
            response.raise_for_status()
            data = response.json()
            if data.get("errors"):
                raise ValueError("Monday API: " + "; ".join(e["message"] for e in data["errors"]))
            return data["data"]

    async def find_board(self):
        if self.board_id:
            return self.board_id
        matches = []
        page = 1
        while True:
            data = await self.query('query($page:Int!){boards(limit:100,page:$page){id name}}', {"page": page})
            boards = data["boards"]
            matches.extend(b["id"] for b in boards if b["name"] == "TRUCK FILES")
            if len(boards) < 100:
                break
            page += 1
        if len(matches) != 1:
            raise ValueError("TRUCK FILES topilmadi yoki bir nechta. MONDAY_BOARD_ID kiriting.")
        self.board_id = matches[0]
        return self.board_id

    async def trucks(self):
        board_id = await self.find_board()
        data = await self.query('query($ids:[ID!]!){boards(ids:$ids){name columns{id title} groups{id title}}}', {"ids": [board_id]})
        if not data["boards"] or re.sub(r'^[^A-Za-z]+', '', data["boards"][0]["name"]).strip() != "TRUCK FILES":
            raise ValueError("Tanlangan doska TRUCK FILES emas")
        board = data["boards"][0]
        columns = {}
        for title in ("Unit", "VIN", "Status"):
            if title == "Unit" and os.getenv("MONDAY_UNIT_SOURCE") == "item_name":
                columns[title] = "__item_name__"
                continue
            matches = [c["id"] for c in board["columns"] if c["title"].strip() == title]
            if len(matches) != 1:
                raise ValueError(f"Monday: {title} ustuni yo'q yoki takrorlangan")
            columns[title] = matches[0]
        allowed = set(os.getenv("MONDAY_GROUP_TITLES", "").split("|")) if os.getenv("MONDAY_GROUP_TITLES") else ALLOWED_GROUPS
        groups = [g for g in board["groups"] if g["title"] in allowed]
        if len(allowed) != 3 or {g["title"] for g in groups} != allowed:
            raise ValueError("Monday: uchta talab qilingan guruh to'liq topilmadi")
        trucks = []
        for group in groups:
            cursor = None
            while True:
                data = await self.query('''query($ids:[ID!]!,$groups:[String!]!,$cursor:String){
                  boards(ids:$ids){groups(ids:$groups){items_page(limit:100,cursor:$cursor){
                    cursor items{id name column_values{id text}}}}}}''',
                  {"ids": [board_id], "groups": [group["id"]], "cursor": cursor})
                page = data["boards"][0]["groups"][0]["items_page"]
                for item in page["items"]:
                    values = {c["id"]: (c["text"] or "").strip() for c in item["column_values"]}
                    if columns["Unit"] == "__item_name__":
                        # This board stores e.g. '133 - LOCAL' in the item name.
                        match = re.match(r'^\s*([A-Za-z0-9]+)\b', item.get("name", ""))
                        values["__item_name__"] = match[1] if match else ""
                    trucks.append({"unit": normalize_unit(values.get(columns["Unit"], "")),
                        "vin": values.get(columns["VIN"], "").upper(),
                        "status": values.get(columns["Status"], ""), "group": group["title"]})
                cursor = page["cursor"]
                if not cursor:
                    break
        return trucks
