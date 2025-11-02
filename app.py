# app.py
import json
import datetime
import streamlit as st
from uuid import uuid4  # IDs uniques
from models import Person, Depense

st.set_page_config(page_title="Gestion personnes & dépenses", layout="wide")

STORAGE_FILE = "storage.json"

# ------------------ Helpers ------------------
def delete_by_id(items: list, item_id: str):
    return [x for x in items if x.get("id") != item_id]

def safe_sum(values):
    return sum(v for v in values if isinstance(v, (int, float)))

def load_state():
    """Charge le storage.json, migre les anciens schémas (id manquant, dates anciennes)"""
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            people_raw = data.get("people", [])
            depenses_raw = data.get("depenses", [])

            # Migrate people: add id if missing
            people = []
            for p in people_raw:
                if "id" not in p:
                    p["id"] = str(uuid4())
                people.append(p)

            # Migrate depenses: ensure date_depense, drop old dates, add id if missing
            depenses = []
            for d in depenses_raw:
                if "date_depense" not in d:
                    if "date_debut" in d and d["date_debut"]:
                        d["date_depense"] = d["date_debut"]
                    elif "date_fin" in d and d["date_fin"]:
                        d["date_depense"] = d["date_fin"]
                    else:
                        d["date_depense"] = str(datetime.date.today())
                d.pop("date_debut", None)
                d.pop("date_fin", None)
                if "id" not in d:
                    d["id"] = str(uuid4())
                depenses.append(d)

            return people, depenses
    except FileNotFoundError:
        return [], []

def save_state(people, depenses):
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump({"people": people, "depenses": depenses}, f, ensure_ascii=False, indent=2, default=str)

def compute_weighted_shares(people, depenses):
    """Calcule les parts dues par personne selon pondération"""
    if not people:
        return {}

    dues = {p["nom"]: 0.0 for p in people if p.get("nom")}
    for d in depenses:
        total = float(d.get("prix_depense", 0.0) or 0.0)
        alcool_part = float(d.get("alcool_prix", 0.0) or 0.0) if d.get("alcool_boolean") else 0.0
        viande_part = float(d.get("nourriture_prix", 0.0) or 0.0) if d.get("nourriture_boolean") else 0.0
        base_part = total - alcool_part - viande_part
        if base_part < 0:
            base_part = 0.0

        nb_all = max(len(dues), 1)
        base_share = base_part / nb_all
        for name in dues:
            dues[name] += base_share

        # Répartition alcool pondérée
        drinkers = [p for p in people if p.get("alcool_boolean")]
        w_sum_a = safe_sum([(p.get("alcool_classification") or 0) for p in drinkers])
        if alcool_part > 0:
            if drinkers and w_sum_a > 0:
                for p in drinkers:
                    w = p.get("alcool_classification") or 0
                    dues[p["nom"]] += alcool_part * (w / w_sum_a)
            else:
                for n in dues:
                    dues[n] += alcool_part / nb_all

        # Répartition viande pondérée
        eaters = [p for p in people if p.get("nourriture_boolean")]
        w_sum_f = safe_sum([(p.get("nourriture_classification") or 0) for p in eaters])
        if viande_part > 0:
            if eaters and w_sum_f > 0:
                for p in eaters:
                    w = p.get("nourriture_classification") or 0
                    dues[p["nom"]] += viande_part * (w / w_sum_f)
            else:
                for n in dues:
                    dues[n] += viande_part / nb_all

    return {k: round(v, 2) for k, v in dues.items()}

# ------------------ Chargement ------------------
people, depenses = load_state()

# ------------------ Menu ------------------
page = st.sidebar.radio(
    "Navigation",
    [
        "Participant (ajouter/enlever des participants)",
        "Dépenses (ajouter/enlever des participants)",
        "Synthèse",
    ],
)

# ------------------ Participants ------------------
if page == "Participant (ajouter/enlever des participants)":
    st.header("Participants")
    with st.form("add_person"):
        nom = st.text_input("Nom")
        if not nom.strip():
            st.caption("⚠️ Le nom ne peut pas être vide.")

        alcool_boolean = st.checkbox("Bois-tu de l'alcool ?")
        alcool_classification = st.number_input(
            "Par rapport aux autres personnes renseignées sur ce groupe, note sur une échelle de 1 à 10 ta consommation d'alcool",
            min_value=1, max_value=10, step=1, value=5
        )

        nourriture_boolean = st.checkbox("Manges-tu de la viande ?")
        nourriture_classification = st.number_input(
            "Par rapport aux autres personnes renseignées sur ce groupe, note sur une échelle de 1 à 10 ta consommation de nourriture espèce de gros mangeur",
            min_value=1, max_value=10, step=1, value=5
        )

        date_arrive = st.date_input("Date d'arrivée", datetime.date.today())
        date_depart = st.date_input("Date de départ", datetime.date.today())

        submitted = st.form_submit_button("Ajouter")
        if submitted:
            if not nom.strip():
                st.error("Merci de renseigner un nom avant d'ajouter.")
            else:
                p = Person(
                    nom.strip(),
                    alcool_boolean,
                    int(alcool_classification),
                    nourriture_boolean,
                    int(nourriture_classification),
                    date_arrive,
                    date_depart
                )
                person_dict = p.__dict__
                person_dict["id"] = str(uuid4())
                people.append(person_dict)
                save_state(people, depenses)
                st.success(f"Ajouté : {nom}")
                st.rerun()

    st.subheader("Liste des participants")
    if not people:
        st.info("Aucun participant enregistré.")
    else:
        for p in people:
            cols = st.columns([5, 3, 2, 2])
            cols[0].markdown(f"**{p.get('nom','(sans nom)')}**")
            cols[1].markdown(
                f"Alcool: {'Oui' if p.get('alcool_boolean') else 'Non'} · "
                f"Note: {p.get('alcool_classification')}"
            )
            cols[2].markdown(
                f"Viande: {'Oui' if p.get('nourriture_boolean') else 'Non'} · "
                f"Note: {p.get('nourriture_classification')}"
            )
            if cols[3].button("Supprimer", key=f"del_person_{p['id']}"):
                people = delete_by_id(people, p["id"])
                save_state(people, depenses)
                st.success(f"Supprimé : {p.get('nom')}")
                st.rerun()

        with st.expander("Voir le tableau brut"):
            st.dataframe(people, use_container_width=True)

# ------------------ Dépenses ------------------
elif page == "Dépenses (ajouter/enlever des participants)":
    st.header("Dépenses")

    if not people:
        st.warning("⚠️ Vous devez enregistrer au moins un participant avant d'ajouter une dépense.")
        st.stop()

    with st.form("add_depense"):
        nom = st.text_input("Nom de la dépense")
        prix_depense = st.number_input("Prix total", min_value=0.0, step=1.0)

        alcool_boolean = st.checkbox("Est ce que cette dépense contient de l'alcool ?")
        alcool_prix = st.number_input("Prix concernant l'achat d'alcool", min_value=0.0, step=1.0)

        nourriture_boolean = st.checkbox("Est ce que cette dépense contient l'achat de viande ?")
        nourriture_prix = st.number_input("Prix concernant l'achat de viande", min_value=0.0, step=1.0)

        date_depense = st.date_input("Date de la dépense", datetime.date.today())

        # --- Qui a payé ? ---
        noms_participants = [p.get("nom","").strip() for p in people if p.get("nom","").strip()]
        payeur_nom = None
        if not noms_participants:
            st.warning("⚠️ Ajoute au moins un participant avec un nom avant d’enregistrer une dépense.")
        elif len(noms_participants) == 1:
            payeur_nom = noms_participants[0]
            st.info(f"Payeur par défaut : **{payeur_nom}** (seul participant nommé).")
        else:
            payeur_nom = st.selectbox("Qui a payé ?", options=noms_participants, key="payeur_select")

        submitted = st.form_submit_button("Ajouter")
        if submitted:
            if not noms_participants:
                st.error("Impossible d'ajouter : aucun participant nommé.")
            elif payeur_nom is None:
                st.error("Merci de choisir le payeur.")
            elif alcool_prix + nourriture_prix > prix_depense:
                st.error("La somme alcool + viande dépasse le prix total.")
            else:
                d = Depense(
                    nom=nom,
                    prix_depense=prix_depense,
                    alcool_boolean=alcool_boolean,
                    alcool_prix=alcool_prix,
                    nourriture_boolean=nourriture_boolean,
                    nourriture_prix=nourriture_prix,
                    date_depense=date_depense
                )
                depense_dict = d.__dict__
                depense_dict["id"] = str(uuid4())
                depense_dict["payeur_nom"] = payeur_nom
                depenses.append(depense_dict)
                save_state(people, depenses)
                st.success(f"Dépense ajoutée : {nom}")
                st.rerun()

    st.subheader("Liste des dépenses")
    if not depenses:
        st.info("Aucune dépense enregistrée.")
    else:
        for d in depenses:
            cols = st.columns([6, 3, 3, 2, 2])
            cols[0].markdown(
                f"**{d.get('nom','(sans nom)')}** — {d.get('date_depense')}  \n"
                f"_Payée par_ **{d.get('payeur_nom','?')}**"
            )
            cols[1].markdown(f"Total: {d.get('prix_depense',0.0):.2f} €")
            cols[2].markdown(
                f"Alcool: {'Oui' if d.get('alcool_boolean') else 'Non'} "
                f"({d.get('alcool_prix',0.0):.2f} €) · "
                f"Viande: {'Oui' if d.get('nourriture_boolean') else 'Non'} "
                f"({d.get('nourriture_prix',0.0):.2f} €)"
            )
            if cols[4].button("Supprimer", key=f"del_depense_{d['id']}"):
                depenses = delete_by_id(depenses, d["id"])
                save_state(people, depenses)
                st.success(f"Dépense supprimée : {d.get('nom')}")
                st.rerun()

        with st.expander("Voir le tableau brut"):
            st.dataframe(depenses, use_container_width=True)

# ------------------ Synthèse ------------------
else:
    st.header("Synthèse")

    total = sum(x.get("prix_depense", 0.0) for x in depenses)
    total_alcool = sum(x.get("alcool_prix", 0.0) for x in depenses if x.get("alcool_boolean"))
    total_viande = sum(x.get("nourriture_prix", 0.0) for x in depenses if x.get("nourriture_boolean"))

    st.metric("Total dépenses", f"{total:.2f} €")
    st.metric("Total alcool", f"{total_alcool:.2f} €")
    st.metric("Total viande", f"{total_viande:.2f} €")

    # Équilibre des dépenses pondéré
    st.subheader("Équilibre des dépenses")
    if not people:
        st.info("Aucun participant pour calculer l'équilibre.")
    else:
        dues = compute_weighted_shares(people, depenses)
        if not dues:
            st.info("Aucune dépense enregistrée.")
        else:
            for name, amount in dues.items():
                st.write(f"• **{name}** devrait payer : **{amount:.2f} €**")

    st.download_button(
        "Exporter JSON",
        json.dumps({"people": people, "depenses": depenses}, ensure_ascii=False, indent=2),
        file_name="export.json"
    )
