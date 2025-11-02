# models.py
from dataclasses import dataclass
import datetime

@dataclass
class Person:
    nom: str
    alcool_boolean: bool
    alcool_classification: int
    nourriture_boolean: bool
    nourriture_classification: int
    date_arrive: datetime.date
    date_depart: datetime.date

@dataclass
class Depense:
    nom: str
    prix_depense: float
    alcool_boolean: bool
    alcool_prix: float
    nourriture_boolean: bool
    nourriture_prix: float
    date_depense: datetime.date
    payeur_nom: str = ""   # 👈 nouveau champ optionnel
