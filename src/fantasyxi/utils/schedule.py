"""
Funciones para obtener el schedule de la NBA sin cache.
"""

from datetime import date
from nba_api.stats.endpoints import scoreboardv2


def get_game_ids_for_date(day: date) -> list:
    """
    Obtiene los game IDs para una fecha específica usando NBA API.
    
    Args:
        day: Fecha en formato date
        
    Returns:
        Lista de game IDs
    """
    day_str = day.strftime("%m/%d/%Y")  # Formato: MM/DD/YYYY
    
    try:
        scoreboard = scoreboardv2.ScoreboardV2(game_date=day_str)
        games_df = scoreboard.game_header.get_data_frame()
        
        if games_df.empty:
            print(f"⚠️ No hay juegos registrados para {day}")
            return []
        
        game_ids = games_df["GAME_ID"].astype(str).tolist()
        print(f"✅ Encontrados {len(game_ids)} juegos para {day}")
        return game_ids
        
    except Exception as e:
        print(f"❌ Error obteniendo juegos para {day}: {e}")
        return []