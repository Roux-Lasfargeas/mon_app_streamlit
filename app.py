# app.py
import json
import datetime
import streamlit as st
from uuid import uuid4  # ← IDs uniques
from models import Person, Depense

st.set_page_config(page_title="Gestion personnes & dépenses", layout="wide")

STORAGE_FILE = "storage.json"

# --- Helpers ---
def delete_by_id(items: list, item_id: str):
    return [x for x in items if x.get("id") != item_id]

# --- Stockage simple (JSON local) ---
def load_state():
    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            people_raw = data.get("people", [])
            depenses_raw = data.get("depenses", [])

            # Ajoute un id si manquant (anciens enregistrements)
            people = []
            for p in people_raw:
                if "id" not in p:
                    p["id"] = str(uuid4())
                people.append(p)

            # Migration douce : si anciens champs date_debut/date_fin, on fabrique date_depense
            depenses = []
            for d in depenses_raw:
                if "date_depense" not in d:
                    if "date_debut" in d and d["date_debut"]:
                        d["date_depense"] = d["date_debut"]
                    elif "date_fin" in d and d["date_fin"]:
                        d["date_depense"] = d["date_fin"]
                    else:
                        d["date_depense"] = str(datetime.date.today())
                # Nettoyage éventuel des anciens champs
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

people, depenses = load_state()

# --- Sidebar navigation ---
page = st.sidebar.radio("Navigation", ["Personnes", "Dépenses", "Synthèse"])

# --- Personnes ---
if page == "Personnes":
    st.header("Personnes")
    with st.form("add_person"):
        nom = st.text_input("Nom")

        # Libellés mis à jour
        alcool_boolean = st.checkbox("Bois-tu de l'alcool ?")
        alcool_classification = st.number_input(
            "Par rapport aux autres personnes renseignées sur ce groupe, note sur une échelle de 1 à 10 ta consommation d'alcool",
            min_value=1, max_value=10, step=1, value=5, format="%d"
        )

        nourriture_boolean = st.checkbox("Manges-tu de la viande ?")
        nourriture_classification = st.number_input(
            "Par rapport aux autres personnes renseignées sur ce groupe, note sur une échelle de 1 à 10 ta consommation de nourriture espèce de gros mangeur",
            min_value=1, max_value=10, step=1, value=5, format="%d"
        )

        date_arrive = st.date_input("Date d'arrivée", datetime.date.today())
        date_depart = st.date_input("Date de départ", datetime.date.today())

        submitted = st.form_submit_button("Ajouter")
        if submitted:
            p = Person(
                nom,
                alcool_boolean,
                int(alcool_classification),
                nourriture_boolean,
                int(nourriture_classification),
                date_arrive,
                date_depart
            )
            person_dict = p.__dict__
            person_dict["id"] = str(uuid4())  # ← ID unique
            people.append(person_dict)
            save_state(people, depenses)
            st.success(f"Ajouté : {nom}")
            st.rerun()

    st.subheader("Liste")
    if not people:
        st.info("Aucune personne enregistrée.")
    else:
        # Affichage en lignes avec bouton "Supprimer"
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

        # (Optionnel) Vue tabulaire rapide
        with st.expander("Voir le tableau brut"):
            st.dataframe(people, use_container_width=True)

        # (Optionnel) Tout supprimer
        if st.button("🗑️ Supprimer TOUTES les personnes"):
            people = []
            save_state(people, depenses)
            st.warning("Toutes les personnes ont été supprimées.")
            st.rerun()

# --- Dépenses ---
elif page == "Dépenses":
    st.header("Dépenses")
    with st.form("add_depense"):
        nom = st.text_input("Nom de la dépense")
        prix_depense = st.number_input("Prix total", min_value=0.0, step=1.0)

        # Libellés modifiés
        alcool_boolean = st.checkbox("Est ce que cette dépense contient de l'alcool ?")
        alcool_prix = st.number_input("Prix concernant l'achat d'alcool", min_value=0.0, step=1.0)

        nourriture_boolean = st.checkbox("Est ce que cette dépense contient l'achat de viande ?")
        nourriture_prix = st.number_input("Prix concernant l'achat de viande", min_value=0.0, step=1.0)

        # Une seule date
        date_depense = st.date_input("Date de la dépense", datetime.date.today())

        submitted = st.form_submit_button("Ajouter")
        if submitted:
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
            depense_dict["id"] = str(uuid4())  # ← ID unique
            depenses.append(depense_dict)
            save_state(people, depenses)
            st.success(f"Dépense ajoutée : {nom}")
            st.rerun()

    st.subheader("Liste")
    if not depenses:
        st.info("Aucune dépense enregistrée.")
    else:
        for d in depenses:
            cols = st.columns([5, 3, 3, 2, 2])
            cols[0].markdown(f"**{d.get('nom','(sans nom)')}** — {d.get('date_depense')}")
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

        if st.button("🗑️ Supprimer TOUTES les dépenses"):
            depenses = []
            save_state(people, depenses)
            st.warning("Toutes les dépenses ont été supprimées.")
            st.rerun()

# --- Synthèse ---
else:
    st.header("Synthèse")
    total = sum(x.get("prix_depense", 0.0) for x in depenses)
    total_alcool = sum(x.get("alcool_prix", 0.0) for x in depenses if x.get("alcool_boolean"))
    total_nourriture = sum(x.get("nourriture_prix", 0.0) for x in depenses if x.get("nourriture_boolean"))
    st.metric("Total dépenses", f"{total:.2f} €")
    st.metric("Total alcool", f"{total_alcool:.2f} €")
    st.metric("Total viande", f"{total_nourriture:.2f} €")
    st.write("Filtre par période (optionnel) à ajouter si besoin.")

    st.download_button(
        "Exporter JSON",
        json.dumps({"people": people, "depenses": depenses}, ensure_ascii=False, indent=2),
        file_name="export.json"
    )
