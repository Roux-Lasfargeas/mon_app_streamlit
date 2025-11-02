import json
import datetime
import streamlit as st
from models import Person, Depense

st.set_page_config(page_title="Gestion personnes & dépenses", layout="wide")

# --- Stockage simple (JSON local) ---
def load_state():
    try:
        with open("storage.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("people", []), data.get("depenses", [])
    except FileNotFoundError:
        return [], []

def save_state(people, depenses):
    with open("storage.json", "w", encoding="utf-8") as f:
        json.dump({"people": people, "depenses": depenses}, f, ensure_ascii=False, indent=2, default=str)

people, depenses = load_state()

# --- Sidebar navigation ---
page = st.sidebar.radio("Navigation", ["Personnes", "Dépenses", "Synthèse"])

# --- Personnes ---
if page == "Personnes":
    st.header("Personnes")
    with st.form("add_person"):
        nom = st.text_input("Nom")
        alcool_boolean = st.checkbox("Alcool ?")
        alcool_classification = st.number_input("Classification alcool (int)", step=1, format="%d")
        nourriture_boolean = st.checkbox("Nourriture ?")
        nourriture_classification = st.number_input("Classification nourriture (int)", step=1, format="%d")
        date_arrive = st.date_input("Date d'arrivée", datetime.date.today())
        date_depart = st.date_input("Date de départ", datetime.date.today())
        submitted = st.form_submit_button("Ajouter")
        if submitted:
            p = Person(nom, alcool_boolean, int(alcool_classification),
                       nourriture_boolean, int(nourriture_classification),
                       date_arrive, date_depart)
            people.append(p.__dict__)
            save_state(people, depenses)
            st.success(f"Ajouté : {nom}")

    st.subheader("Liste")
    st.dataframe(people, use_container_width=True)

# --- Dépenses ---
elif page == "Dépenses":
    st.header("Dépenses")
    with st.form("add_depense"):
        nom = st.text_input("Nom de la dépense")
        prix_depense = st.number_input("Prix total", min_value=0.0, step=1.0)
        alcool_boolean = st.checkbox("Contient de l'alcool ?")
        alcool_prix = st.number_input("Prix alcool", min_value=0.0, step=1.0)
        nourriture_boolean = st.checkbox("Contient de la nourriture ?")
        nourriture_prix = st.number_input("Prix nourriture", min_value=0.0, step=1.0)
        date_debut = st.date_input("Date début", datetime.date.today())
        date_fin = st.date_input("Date fin", datetime.date.today())
        submitted = st.form_submit_button("Ajouter")
        if submitted:
            d = Depense(nom, prix_depense, alcool_boolean, alcool_prix,
                        nourriture_boolean, nourriture_prix, date_debut, date_fin)
            depenses.append(d.__dict__)
            save_state(people, depenses)
            st.success(f"Dépense ajoutée : {nom}")

    st.subheader("Liste")
    st.dataframe(depenses, use_container_width=True)

# --- Synthèse ---
else:
    st.header("Synthèse")
    total = sum(x.get("prix_depense", 0.0) for x in depenses)
    total_alcool = sum(x.get("alcool_prix", 0.0) for x in depenses if x.get("alcool_boolean"))
    total_nourriture = sum(x.get("nourriture_prix", 0.0) for x in depenses if x.get("nourriture_boolean"))
    st.metric("Total dépenses", f"{total:.2f} €")
    st.metric("Total alcool", f"{total_alcool:.2f} €")
    st.metric("Total nourriture", f"{total_nourriture:.2f} €")
    st.write("Filtre par période (optionnel) à ajouter si besoin.")

    st.download_button("Exporter JSON", json.dumps({"people": people, "depenses": depenses}, ensure_ascii=False, indent=2), file_name="export.json")
