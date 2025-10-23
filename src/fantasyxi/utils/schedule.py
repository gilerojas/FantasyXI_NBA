"""
Funciones para obtener el schedule de la NBA sin cache.
"""

from datetime import date
from time import sleep
from nba_api.stats.endpoints import scoreboardv2


def get_game_ids_for_date(day: date, timeout: int = 60, max_retries: int = 3) -> list:
    """
    Obtiene los game IDs para una fecha específica usando NBA API.
    
    Args:
        day: Fecha en formato date
        timeout: Timeout en segundos (default: 60)
        max_retries: Número máximo de reintentos (default: 3)
        
    Returns:
        Lista de game IDs
    """
    day_str = day.strftime("%m/%d/%Y")  # Formato: MM/DD/YYYY
    
    for attempt in range(max_retries):
        try:
            print(f"🔍 Intento {attempt + 1}/{max_retries} - Obteniendo juegos para {day}...")
            
            scoreboard = scoreboardv2.ScoreboardV2(
                game_date=day_str,
                timeout=timeout
            )
            games_df = scoreboard.game_header.get_data_frame()
            
            if games_df.empty:
                print(f"⚠️ No hay juegos registrados para {day}")
                return []
            
            game_ids = games_df["GAME_ID"].astype(str).tolist()
            print(f"✅ Encontrados {len(game_ids)} juegos para {day}")
            return game_ids
            
        except Exception as e:
            print(f"❌ Intento {attempt + 1} falló: {e}")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                print(f"⏳ Esperando {wait_time}s antes de reintentar...")
                sleep(wait_time)
            else:
                print(f"❌ Error final obteniendo juegos para {day}: {e}")
                return []
    
    return []