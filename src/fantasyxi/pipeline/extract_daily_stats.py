"""
Extrae stats de jugadores para la fecha del freeze (día anterior).
Se ejecuta a las 6:00 AM RD del día siguiente.
"""

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd

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
    freeze_date_str = freeze_data["date"]
    freeze_date = date.fromisoformat(freeze_date_str)
    game_ids = freeze_data.get("game_ids", [])
    
    print(f"📅 Freeze date: {freeze_date}")
    
    if not game_ids:
        print("⚠️ No hay game IDs cacheados. El día no tuvo juegos.")
        return
    
    print(f"🎮 Game IDs cacheados: {len(game_ids)} juegos")
    
    # Cargar roster congelado
    roster = load_frozen_roster(freeze_date_str)
    player_ids = roster["nba_player_id"].dropna()
    
    print(f"👥 Filtrando {len(player_ids)} jugadores rostered")
    
    # Extraer stats usando game IDs pre-cacheados
    stats = daily_stats_from_game_ids(
        game_ids=game_ids,
        filter_ids=player_ids,
        timeout=60
    )
    
    if stats.empty:
        print(f"⚠️ No hay stats disponibles")
        return
    
    # ===== EXTRAER FECHA REAL DEL JUEGO =====
    if 'GAME_DATE' not in stats.columns:
        print("❌ Error: GAME_DATE no está en el DataFrame")
        return
    
    game_date_str = stats['GAME_DATE'].iloc[0]
    game_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
    
    print(f"📅 Fecha real de los juegos: {game_date}")
    
    # ===== AGREGAR EQUIPO FANTASY =====
    roster_mapping = roster[['nba_player_id', 'team_abbrev', 'player_name']].copy()
    roster_mapping.columns = ['nba_player_id', 'FANTASY_TEAM', 'PLAYER_NAME_ROSTER']
    
    # Merge stats con roster (usando nba_player_id como clave)
    stats = stats.merge(
        roster_mapping[['nba_player_id', 'FANTASY_TEAM']],
        on='nba_player_id',
        how='left'
    )
    
    # Verificar que todos tienen equipo asignado
    missing_team = stats['FANTASY_TEAM'].isna().sum()
    if missing_team > 0:
        print(f"⚠️ {missing_team} jugadores sin equipo fantasy asignado")
    
    # Reordenar columnas: FANTASY_TEAM al inicio
    cols = stats.columns.tolist()
    if 'FANTASY_TEAM' in cols:
        cols.remove('FANTASY_TEAM')
        cols = ['FANTASY_TEAM'] + cols
        stats = stats[cols]
    
    # ===== GUARDAR CON FECHA CORRECTA =====
    month_dir = STATS_DIR / game_date.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    output = month_dir / f"stats_{game_date}.csv"
    stats.to_csv(output, index=False)
    
    print(f"📊 Stats extraídas: {len(stats)} registros → {output}")
    print(f"✅ Proceso completado exitosamente")


if __name__ == "__main__":
    main()