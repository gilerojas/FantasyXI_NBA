"""
Funciones para manejar el schedule de la NBA.
"""

import json
from pathlib import Path
import pandas as pd
from datetime import date

CACHE_DIR = Path("data/processed/misc")
SCHEDULE_CACHE = CACHE_DIR / "scheduleLeagueV2.json"


def build_schedule_df_from_cache() -> pd.DataFrame:
    """Construye DataFrame del schedule desde el cache."""
    if not SCHEDULE_CACHE.exists():
        raise FileNotFoundError(f"Schedule cache no encontrado: {SCHEDULE_CACHE}")
    
    with open(SCHEDULE_CACHE) as f:
        data = json.load(f)
    
    # Parsear juegos del JSON
    games = data.get("leagueSchedule", {}).get("gameDates", [])
    rows = []
    for game_date in games:
        for game in game_date.get("games", []):
            rows.append({
                "GAME_ID": game["gameId"],
                "GAME_DATE": game_date["gameDate"],
            })
    
    return pd.DataFrame(rows)


def get_game_ids_for_date(day: date, sched_df: pd.DataFrame) -> list:
    """Obtiene game IDs para una fecha específica."""
    day_str = day.isoformat()
    return sched_df[sched_df["GAME_DATE"] == day_str]["GAME_ID"].tolist()