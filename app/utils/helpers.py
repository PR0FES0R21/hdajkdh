# ===========================================================================
# File: app/utils/helpers.py (MODIFIKASI: Fungsi generate_sci_fi_username lebih variatif)
# ===========================================================================
# (Sama seperti versi sebelumnya)
import random
import string
from typing import List, Optional
from datetime import datetime, timezone

SCI_FI_MAIN_WORDS: List[str] = [
    "Nova", "Orion", "Cygnus", "Vega", "Sirius", "Rigel", "Alpha", "Zeta", "Krypton", 
    "Xylar", "Zorg", "Krell", "Cyber", "Robo", "Mecha", "Droid", "Plasma", "Quantum",
    "Void", "Echo", "Helio", "Luna", "Terra", "Mars", "Jupiter", "Saturn", "Titan", 
    "Europa", "Ganymede", "Callisto", "Io", "Pluto", "Charon", "Xenon", "Argon", 
    "Kryptos", "Stardust", "Comet", "Meteor", "Pulsar", "Quasar", "Nebulae", 
    "Celestia", "Solara", "Lunaris", "Terran", "Galaxion", "Vortex", "Apex",
    "Zenith", "Flux", "Matrix", "Cipher", "Vector", "Relic", "Oracle", "Aegis",
    "Nomad", "Rogue", "Specter", "Wraith", "Phantom", "Reaper", "Guardian"
]

def generate_random_numeric_suffix(min_digits: int = 1, max_digits: int = 3) -> str:
    if min_digits > max_digits:
        min_digits = max(1, max_digits)
    max_digits = max(min_digits, max_digits)
    max_digits = max(1, max_digits)

    length = random.randint(min_digits, max_digits)
    return "".join(random.choices(string.digits, k=length))

def generate_sci_fi_username() -> str:
    word = random.choice(SCI_FI_MAIN_WORDS)
    word_trimmed = word[:15] if len(word) > 15 else word
    numeric_suffix = generate_random_numeric_suffix(1, 3)
    use_underscore = random.choice([True, False])
    
    if use_underscore:
        return f"{word_trimmed}_{numeric_suffix}"
    else:
        return f"{word_trimmed}{numeric_suffix}"

def generate_unique_referral_code(prefix: str = "CGR", length: int = 6) -> str:
    characters = string.ascii_uppercase + string.digits
    random_part = "".join(random.choices(characters, k=length))
    return f"{prefix}{random_part}"

def generate_stardate() -> str:
    now_utc = datetime.now(timezone.utc)
    year = now_utc.year
    day_of_year = now_utc.timetuple().tm_yday
    hours = now_utc.strftime("%H")
    minutes = now_utc.strftime("%M")
    return f"{year}.{day_of_year}.{hours}{minutes}"