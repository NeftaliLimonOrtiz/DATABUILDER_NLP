import re

INPUT_DIR = "input"
OUTPUT_DIR = "output"

EMAIL_PAT = re.compile(r"\b[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
PHONE_PAT = re.compile(r"\b(?:\d{2}[.\s-]?){4}\d{2}\b")
DATE_PAT = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
FRENCH_DATE_PAT = re.compile(
    r"\b(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)\s+(\d{4})\b",
    re.IGNORECASE,
)

MONTHS_FR = {
    "janvier": "01",
    "février": "02",
    "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "août": "08",
    "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "décembre": "12",
    "decembre": "12",
}

LOT_PAT = re.compile(
    r"^\s*LOT\.?\s*"
    r"([0-9]+(?:\.[a-z])?(?:\s*ET\s*[0-9]+(?:\.[a-z])?)?)?"
    r"\s*(.*)$",
    re.IGNORECASE,
)

PAGE_PAT = re.compile(r"^\s*\d+\s*/\s*\d+\s*$")
DIGITS_PAT = re.compile(r"^\s*\d+\s*$")

PLACE_PATS = [
    r"\b(?:Bât(?:iment)?|bat|bât)\s*[A-Z0-9/]+(?:\s*[A-Z0-9/]+)?\b",
    r"\bCage\s+[A-Z0-9]+(?:\s+[A-Z0-9]+)?\b",
    r"\bEscalier\s+[A-Z0-9]+\b",
    r"\bFaçade\s+[A-Z0-9À-ÿ\-]+\b",
    r"\bLocal\s+[A-Z0-9À-ÿ\-]+\b",
    r"\bNiveau\s+\d+\b",
    r"\bRDC\b",
    r"\bR\+\d+\b",
    r"\bSS\d*\b",
    r"\bSous-sol\b",
    r"\bToiture\b",
]


BANNED_TASK_WORDS = {
    "planning", "calendrier", "programme", "remarques", "observations",
    "commentaires", "echantillon", "fait", "ras", "ok", "neant", "néant",
}

PLANNING_HEADERS = {
    "tâches", "taches", "début", "debut", "fin", "avancement", "retard",
    "intemp", "description", "semaine", "choix", "présenté", "presente",
    "validé", "valide", "pour le", "fait le", "accord le",
}

TASK_KEYS = {"taches", "tache", "tâches", "tâche", "description"}

SECTION_MARKERS = {
    "cage d", "cage e", "interieure", "exterieure",
    "interieure cage d", "interieure cage e",
    "menuiseries", "menuiseries pvc cage d", "menuiseries pvc cage e",
    "pvc cage d", "pvc cage e", "cage", "d", "e",
}

TASK_LIKE_PREFIXES = (
    "traitement", "pose", "approvisionnement", "appro", "reglage", "réglage",
    "montage", "mise", "peinture", "plancher", "chape", "carrelage",
    "faiences", "faïences", "doublage", "tracage", "traçage", "pieux",
    "essai", "recollement", "récollement", "prise", "fabrication", "projection",
)
