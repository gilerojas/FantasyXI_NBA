"""
Detecta el primer juego del día y programa el freeze time.
Se ejecuta diariamente a las 9:00 AM RD.
"""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
from time import sleep
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
from nba_api.stats.endpoints import scoreboardv2

TZ_RD = ZoneInfo("America/Santo_Domingo")
TZ_UTC = ZoneInfo("UTC")

FREEZE_PATH = Path("data/processed/freeze_time.json")
FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_first_game_and_all_game_ids():
    """
    Obtiene el primer juego del día y TODOS los game IDs.
    Retorna: (primer_tip_utc, lista_game_ids)
    """
    try:
        # Intentar Live API primero
        sb = live_scoreboard.ScoreBoard()
        data = sb.get_dict().get("scoreboard", {})
        games = data.get("games", [])
        
        tips = []
        game_ids = []
        
        for g in games:
            game_ids.append(g.get("gameId"))
            gt_utc = g.get("gameTimeUTC")
            if gt_utc and gt_utc.endswith("Z"):
                tip_utc = datetime.fromisoformat(gt_utc.replace("Z", "+00:00"))
                tips.append(tip_utc)
        
        if tips and game_ids:
            return min(tips), game_ids
    
    except Exception as e:
        print(f"⚠️ Live API falló: {e}, intentando Stats API...")
    
    # Fallback: Stats API
    try:
        today = datetime.now(TZ_RD).date()
        day_str = today.strftime("%m/%d/%Y")
        
        for attempt in range(3):
            try:
                scoreboard = scoreboardv2.ScoreboardV2(game_date=day_str, timeout=60)
                games_df = scoreboard.game_header.get_data_frame()
                
                if not games_df.empty:
                    game_ids = games_df["GAME_ID"].astype(str).tolist()
                    # Asumir primera hora típica de juegos NBA (7 PM ET = 23:00 UTC)
                    first_tip = datetime.combine(today, datetime.min.time()).replace(
                        hour=23, minute=0, tzinfo=TZ_UTC
                    )
                    return first_tip, game_ids
            except Exception as e:
                print(f"❌ Intento {attempt + 1} falló: {e}")
                if attempt < 2:
                    sleep(5)
    
    except Exception as e:
        print(f"❌ Stats API falló: {e}")
    
    return None, []


def main():
    first_tip, game_ids = get_first_game_and_all_game_ids()
    
    if not first_tip or not game_ids:
        print("⚠️ No hay juegos hoy. Saltando freeze.")
        FREEZE_PATH.write_text(json.dumps({
            "date": datetime.now(TZ_RD).date().isoformat(),
            "freeze_time": None,
            "game_ids": [],
            "processed": True
        }, indent=2))
        return
    
    # Freeze 4 minutos después del primer juego
    freeze_time = first_tip + timedelta(minutes=4)
    
    payload = {
        "date": first_tip.astimezone(TZ_RD).date().isoformat(),
        "freeze_time": freeze_time.isoformat(),
        "first_game_utc": first_tip.isoformat(),
        "game_ids": game_ids,  # ✅ GUARDAR GAME IDs
        "processed": False
    }
    
    FREEZE_PATH.write_text(json.dumps(payload, indent=2))
    print(f"✅ Freeze programado: {freeze_time.astimezone(TZ_RD)}")
    print(f"📋 Game IDs cacheados: {len(game_ids)} juegos")


if __name__ == "__main__":
    main()