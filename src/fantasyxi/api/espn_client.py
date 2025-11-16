"""
ESPN Fantasy Basketball API Client
===================================
Handles authentication and connection to ESPN Fantasy Basketball league.
"""

from espn_api.basketball import League
from dotenv import load_dotenv
import os

load_dotenv()


def connect_to_league():
    """
    Connect to ESPN Fantasy Basketball League.
    
    Returns:
        League: Authenticated ESPN League object
        
    Requires .env file with:
        ESPN_LEAGUE_ID
        ESPN_S2
        ESPN_SWID
        LEAGUE_YEAR (optional, defaults to 2026pi)
    """
    league_id = os.getenv("ESPN_LEAGUE_ID")
    espn_s2 = os.getenv("ESPN_S2")
    swid = os.getenv("ESPN_SWID")
    year = int(os.getenv("LEAGUE_YEAR", 2025))

    league = League(
        league_id=league_id,
        year=year,
        espn_s2=espn_s2,
        swid=swid
    )
    
    print(f"✅ Connected to league: {league.settings.name} ({year})")
    return league