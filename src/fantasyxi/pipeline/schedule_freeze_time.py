"""
Detecta el primer juego del día y programa el freeze time.
Se ejecuta diariamente a las 9:00 AM RD.
"""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard

TZ_RD = ZoneInfo("America/Santo_Domingo")
TZ_UTC = ZoneInfo("UTC")

FREEZE_PATH = Path("data/processed/freeze_time.json")
FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_first_game_today():
    """
    Obtiene el primer juego del día usando NBA Live API.
    Retorna datetime UTC del primer tipoff.
    """
    sb = live_scoreboard.ScoreBoard()
    data = sb.get_dict().get("scoreboard", {})
    games = data.get("games", [])
    
    tips = []
    for g in games:
        gt_utc = g.get("gameTimeUTC")
        if gt_utc and gt_utc.endswith("Z"):
            tip_utc = datetime.fromisoformat(gt_utc.replace("Z", "+00:00"))
            tips.append(tip_utc)
    
    return min(tips) if tips else None


def main():
    first_tip = get_first_game_today()
    
    if not first_tip:
        print("⚠️ No hay juegos hoy. Saltando freeze.")
        FREEZE_PATH.write_text(json.dumps({
            "date": datetime.now(TZ_RD).date().isoformat(),
            "freeze_time": None,
            "processed": True
        }, indent=2))
        return
    
    # Freeze 4 minutos después del primer juego
    freeze_time = first_tip + timedelta(minutes=4)
    
    payload = {
        "date": first_tip.astimezone(TZ_RD).date().isoformat(),
        "freeze_time": freeze_time.isoformat(),
        "first_game_utc": first_tip.isoformat(),
        "processed": False
    }
    
    FREEZE_PATH.write_text(json.dumps(payload, indent=2))
    print(f"✅ Freeze programado: {freeze_time.astimezone(TZ_RD)}")


if __name__ == "__main__":
    main()