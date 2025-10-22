"""
Funciones para mapear jugadores de ESPN a NBA API.
"""

import json
import pandas as pd
import unicodedata
from pathlib import Path
from thefuzz import process
from nba_api.stats.static import players as nba_players_static

NBA_ID_CACHE_PATH = Path("data/processed/mappings/nba_id_cache.json")
NBA_ID_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def normalize_name(name):
    """Normaliza nombres removiendo acentos."""
    return unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')


def _load_cache(path=NBA_ID_CACHE_PATH):
    return {k: str(v) for k, v in json.loads(path.read_text()).items()} if path.exists() else {}


def _save_cache(cache, path=NBA_ID_CACHE_PATH):
    path.write_text(json.dumps({k: str(v) for k, v in cache.items()}, ensure_ascii=False, indent=2))


def build_nba_name_index():
    plist = nba_players_static.get_players()
    by_name = {normalize_name(p["full_name"]): str(p["id"]) for p in plist}
    name_list = list(by_name.keys())
    return by_name, name_list


def fuzzy_resolve(name, name_list, threshold=90):
    normalized_name = normalize_name(name)
    match, score = process.extractOne(normalized_name, name_list)
    return match if score >= threshold else None


def _get(o, k, default=None):
    return getattr(o, k, default)


def extract_league_players(league) -> pd.DataFrame:
    """Extrae jugadores rostered de la liga ESPN."""
    rows = []
    for t in league.teams:
        owners_data = _get(t, "owners", [])
        
        if isinstance(owners_data, list) and owners_data and isinstance(owners_data[0], dict):
            owners = ", ".join(owner.get('name', 'Unknown') for owner in owners_data)
        else:
            owners = ", ".join(owners_data) if isinstance(owners_data, list) else owners_data

        for p in t.roster:
            rows.append({
                "team_id": _get(t, "team_id"),
                "team_abbrev": _get(t, "team_abbrev"),
                "team_name": _get(t, "team_name"),
                "player_id": _get(p, "playerId"),
                "player_name": _get(p, "name"),
                "pro_team": _get(p, "proTeam"),
                "lineup_slot": _get(p, "position"),
            })
            
    df = pd.DataFrame(rows).drop_duplicates(subset=["player_id"]).reset_index(drop=True)
    return df


def map_nba_ids(league_players: pd.DataFrame) -> pd.DataFrame:
    """Mapea ESPN player IDs a NBA API IDs usando cache + fuzzy matching."""
    cache = _load_cache()
    by_name, name_list = build_nba_name_index()
    out = league_players.copy()

    def resolve_id(row):
        key = f'{row["player_name"]}|{row.get("pro_team","")}'
        if key in cache:
            return cache[key]

        pid = by_name.get(row["player_name"])
        if pid:
            cache[key] = pid
            return pid

        match = fuzzy_resolve(row["player_name"], name_list, threshold=90)
        if match:
            pid = by_name[match]
            cache[key] = pid
            return pid

        return None

    out["nba_player_id"] = out.apply(resolve_id, axis=1).astype(str)
    _save_cache(cache)
    return out