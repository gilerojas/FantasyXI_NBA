"""
Congela rosters de la liga cuando se alcanza el freeze time.
Se ejecuta cada 30 min desde las 11:00 AM hasta las 7:30 PM RD.
"""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from espn_api.basketball import League

# ✅ Imports corregidos (fantasyxi, no fantasyx_nba)
from fantasyxi.utils.mapping import extract_league_players, map_nba_ids

TZ_RD = ZoneInfo("America/Santo_Domingo")
TZ_UTC = ZoneInfo("UTC")

FREEZE_PATH = Path("data/processed/freeze_time.json")
ROSTER_DIR = Path("data/processed/daily_rosters_excels")
ROSTER_DIR.mkdir(parents=True, exist_ok=True)


def load_freeze_data():
    return json.loads(FREEZE_PATH.read_text())


def save_frozen_roster(df: pd.DataFrame, freeze_date: str):
    """Guarda el roster congelado como Excel."""
    output = ROSTER_DIR / f"roster_{freeze_date}.xlsx"
    df.to_excel(output, index=False)
    print(f"📋 Roster congelado guardado: {output}")


def main():
    freeze_data = load_freeze_data()
    
    # Si ya se procesó, salir
    if freeze_data.get("processed"):
        print("✅ Freeze ya procesado hoy. Saliendo.")
        return
    
    # Verificar si es hora de congelar
    freeze_time = datetime.fromisoformat(freeze_data["freeze_time"])
    now = datetime.now(TZ_UTC)
    
    if now < freeze_time:
        print(f"⏳ Esperando freeze time: {freeze_time.astimezone(TZ_RD)}")
        return
    
    # Cargar liga ESPN
    league = League(
        league_id=int(os.getenv("ESPN_LEAGUE_ID")),
        year=2025,
        espn_s2=os.getenv("ESPN_S2"),
        swid=os.getenv("ESPN_SWID")
    )
    
    # Extraer y mapear jugadores
    roster = extract_league_players(league)
    roster = map_nba_ids(roster)
    
    # Guardar roster congelado
    freeze_date = freeze_data["date"]
    save_frozen_roster(roster, freeze_date)
    
    # Marcar como procesado
    freeze_data["processed"] = True
    FREEZE_PATH.write_text(json.dumps(freeze_data, indent=2))
    print("✅ Rosters congelados exitosamente.")


if __name__ == "__main__":
    main()