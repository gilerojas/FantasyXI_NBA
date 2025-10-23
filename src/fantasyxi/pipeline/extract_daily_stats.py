"""
Extrae stats de jugadores para la fecha del freeze (día anterior).
Se ejecuta a las 6:00 AM RD del día siguiente.
"""

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd

# ✅ Imports corregidos
from fantasyxi.stats.boxscore import daily_stats_from_game_ids

TZ_RD = ZoneInfo("America/Santo_Domingo")
FREEZE_PATH = Path("data/processed/freeze_time.json")
ROSTER_DIR = Path("data/processed/daily_rosters_excels")
STATS_DIR = Path("data/processed/daily_stats")
STATS_DIR.mkdir(parents=True, exist_ok=True)


def load_frozen_roster(freeze_date: str) -> pd.DataFrame:
    """Carga el roster congelado del día anterior."""
    roster_file = ROSTER_DIR / f"roster_{freeze_date}.xlsx"
    if not roster_file.exists():
        raise FileNotFoundError(f"No se encontró roster: {roster_file}")
    return pd.read_excel(roster_file)


def main():
    # Leer freeze data (incluye game_ids pre-cacheados)
    freeze_data = json.loads(FREEZE_PATH.read_text())
    freeze_date = date.fromisoformat(freeze_data["date"])
    game_ids = freeze_data.get("game_ids", [])
    
    print(f"📅 Extrayendo stats para: {freeze_date}")
    
    if not game_ids:
        print("⚠️ No hay game IDs cacheados. El día no tuvo juegos.")
        return
    
    print(f"🎮 Game IDs cacheados: {len(game_ids)} juegos")
    
    # Cargar roster congelado
    roster = load_frozen_roster(freeze_data["date"])
    player_ids = roster["nba_player_id"].dropna()
    
    print(f"👥 Filtrando {len(player_ids)} jugadores rostered")
    
    # Extraer stats usando game IDs pre-cacheados (SIN llamar a ScoreboardV2)
    stats = daily_stats_from_game_ids(
        game_ids=game_ids,
        filter_ids=player_ids,
        timeout=60
    )
    
    if stats.empty:
        print(f"⚠️ No hay stats disponibles para {freeze_date}")
        return
    
    # Guardar stats
    month_dir = STATS_DIR / freeze_date.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    output = month_dir / f"stats_{freeze_date}.csv"
    stats.to_csv(output, index=False)
    
    print(f"📊 Stats extraídas: {len(stats)} registros → {output}")
    print(f"✅ Proceso completado exitosamente")


if __name__ == "__main__":
    main()