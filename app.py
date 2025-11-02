# app.py
import json
import datetime
from collections import defaultdict

import streamlit as st
from uuid import uuid4  # IDs uniques
from models import Person, Depense

# Charts
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Gestion personnes & dépenses", layout="wide")

STORAGE_FILE = "storage.json"

# ------------------ Helpers ------------------
def delete_by_id(items: list, item_id: str):
    return [x for x in items if x.get("id") != item_id]

def safe_sum(values):
    return sum(v for v in values if isinstance(v, (int, float)))

def to_date(obj):
    """Accepte date ou str ISO ('YYYY-MM-DD') -> datetime.date"""
    if isinstance(obj, datetime.date):
        return obj
    if isinstance(obj, str) and obj:
        try:
            return datetime.date.fromisoformat(obj)
        except ValueError:
            pass
    return None

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

        # Répartition alcool pondérée (🍷)
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

        # Répartition viande pondérée (🍖)
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

def filter_depenses_by_date(depenses, start_date, end_date):
    """Filtre d par date_depense dans [start_date, end_date] (bornes incluses)"""
    if not start_date and not end_date:
        return depenses
    out = []
    for d in depenses:
        dd = to_date(d.get("date_depense"))
        if not dd:
            continue
        if start_date and dd < start_date:
            continue
        if end_date and dd > end_date:
            continue
        out.append(d)
    return out

def css_theme(dark: bool):
    """Applique un thème clair/sombre simple via CSS."""
    if dark:
        bg = "#0E1117"
        text = "#FAFAFA"
        card = "#1E222A"
    else:
        bg = "#FFFFFF"
        text = "#0E0E0E"
        card = "#F6F6F6"
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {bg}; color: {text}; }}
        .stMarkdown, .stMetric {{ color: {text} !important; }}
        .stDataFrame, .stExpander, .stButton>button, .stSelectbox, .stTextInput, .stNumberInput, .stDateInput {{
            background: {card} !important; color: {text} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ------------------ Chargement ------------------
people, depenses = load_state()

# ------------------ Menu + Thème ------------------
with st.sidebar:
    dark_mode = st.toggle("🌙 Thème sombre", value=False)
css_theme(dark_mode)

page = st.sidebar.radio(
    "Navigation",
    [
        "Participant (ajouter/enlever des participants)",
        "Dépenses (ajouter/enlever des participants)",
        "Synthèse",
        "📈 Résumé des dépenses",
        "🧬 Résumé des profils du groupe",
    ],
)

# ------------------ Participants ------------------
if page == "Participant (ajouter/enlever des participants)":
    st.header("👥 Participants")
    with st.form("add_person"):
        nom = st.text_input("Nom")
        if not nom.strip():
            st.caption("⚠️ Le nom ne peut pas être vide.")

        alcool_boolean = st.checkbox("Bois-tu de l'alcool ? 🍷")
        alcool_classification = st.number_input(
            "Par rapport aux autres personnes renseignées sur ce groupe, note sur une échelle de 1 à 10 ta consommation d'alcool",
            min_value=1, max_value=10, step=1, value=5
        )

        nourriture_boolean = st.checkbox("Manges-tu de la viande ? 🍖")
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
                f"🍷 Alcool: {'Oui' if p.get('alcool_boolean') else 'Non'} · "
                f"Note: {p.get('alcool_classification')}"
            )
            cols[2].markdown(
                f"🍖 Viande: {'Oui' if p.get('nourriture_boolean') else 'Non'} · "
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
    st.header("💰 Dépenses")

    if not people:
        st.warning("⚠️ Vous devez enregistrer au moins un participant avant d'ajouter une dépense.")
        st.stop()

    with st.form("add_depense"):
        nom = st.text_input("Nom de la dépense")
        prix_depense = st.number_input("Prix total (€)", min_value=0.0, step=1.0)

        alcool_boolean = st.checkbox("Est ce que cette dépense contient de l'alcool ? 🍷")
        alcool_prix = st.number_input("Prix concernant l'achat d'alcool (€)", min_value=0.0, step=1.0)

        nourriture_boolean = st.checkbox("Est ce que cette dépense contient l'achat de viande ? 🍖")
        nourriture_prix = st.number_input("Prix concernant l'achat de viande (€)", min_value=0.0, step=1.0)

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
            cols[1].markdown(f"💰 Total: {d.get('prix_depense',0.0):.2f} €")
            cols[2].markdown(
                f"🍷 Alcool: {'Oui' if d.get('alcool_boolean') else 'Non'} "
                f"({d.get('alcool_prix',0.0):.2f} €) · "
                f"🍖 Viande: {'Oui' if d.get('nourriture_boolean') else 'Non'} "
                f"({d.get('nourriture_prix',0.0):.2f} €)"
            )
            if cols[4].button("Supprimer", key=f"del_depense_{d['id']}"):
                depenses = delete_by_id(depenses, d["id"])
                save_state(people, depenses)
                st.success(f"Dépense supprimée : {d.get('nom')}")
                st.rerun()

        with st.expander("Voir le tableau brut"):
            st.dataframe(depenses, use_container_width=True)

# ------------------ Synthèse (totaux + équilibre SEULS) ------------------
elif page == "Synthèse":
    st.header("📊 Synthèse")

    # Totaux globaux (pas de filtres ici)
    total = sum(x.get("prix_depense", 0.0) for x in depenses)
    total_alcool = sum(x.get("alcool_prix", 0.0) for x in depenses if x.get("alcool_boolean"))
    total_viande = sum(x.get("nourriture_prix", 0.0) for x in depenses if x.get("nourriture_boolean"))

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total dépenses", f"{total:.2f} €")
    c2.metric("🍷 Total alcool", f"{total_alcool:.2f} €")
    c3.metric("🍖 Total viande", f"{total_viande:.2f} €")

    # Équilibre pondéré (sur toutes les dépenses)
    st.subheader("⚖️ Équilibre des dépenses (pondéré)")
    if not people:
        st.info("Aucun participant pour calculer l'équilibre.")
    else:
        dues = compute_weighted_shares(people, depenses)
        if not dues:
            st.info("Aucune dépense enregistrée.")
        else:
            df_dues = pd.DataFrame({"Participant": list(dues.keys()), "Part due (€)": list(dues.values())})
            st.dataframe(df_dues, use_container_width=True)

    # Export global
    st.download_button(
        "📥 Exporter JSON (tout)",
        json.dumps({"people": people, "depenses": depenses}, ensure_ascii=False, indent=2),
        file_name="export_total.json"
    )

# ------------------ Résumé des dépenses (FILTRES + GRAPHIQUES) ------------------
elif page == "📈 Résumé des dépenses":
    st.header("📈 Résumé des dépenses")

    # Filtres par période
    colf1, colf2 = st.columns(2)
    with colf1:
        start_date = st.date_input("📅 Date de début (filtre)", value=None)
    with colf2:
        end_date = st.date_input("📅 Date de fin (filtre)", value=None)

    depenses_filtered = filter_depenses_by_date(depenses, start_date, end_date)

    total = sum(x.get("prix_depense", 0.0) for x in depenses_filtered)
    total_alcool = sum(x.get("alcool_prix", 0.0) for x in depenses_filtered if x.get("alcool_boolean"))
    total_viande = sum(x.get("nourriture_prix", 0.0) for x in depenses_filtered if x.get("nourriture_boolean"))
    total_autres = max(total - total_alcool - total_viande, 0.0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Total dépenses", f"{total:.2f} €")
    c2.metric("🍷 Total alcool", f"{total_alcool:.2f} €")
    c3.metric("🍖 Total viande", f"{total_viande:.2f} €")
    c4.metric("🧾 Autres", f"{total_autres:.2f} €")

    st.subheader("📊 Graphiques")

    # 1) Répartition par type (camembert)
    df_types = pd.DataFrame(
        {"Type": ["🍷 Alcool", "🍖 Viande", "💰 Autres"], "Montant (€)": [total_alcool, total_viande, total_autres]}
    )
    fig_types = px.pie(df_types, names="Type", values="Montant (€)", title="Répartition par type")
    st.plotly_chart(fig_types, use_container_width=True)

    # 2) Évolution des dépenses dans le temps (ligne)
    series_by_date = defaultdict(float)
    for d in depenses_filtered:
        dd = to_date(d.get("date_depense"))
        if dd:
            series_by_date[dd] += float(d.get("prix_depense", 0.0) or 0.0)
    if series_by_date:
        df_time = pd.DataFrame({"Date": sorted(series_by_date.keys())})
        df_time["Dépenses (€)"] = df_time["Date"].map(series_by_date)
        fig_line = px.line(df_time, x="Date", y="Dépenses (€)", markers=True, title="Évolution des dépenses")
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Aucune dépense dans la période pour tracer l'évolution.")

    # 3) Part de chaque payeur (barres)
    paid_by = defaultdict(float)
    for d in depenses_filtered:
        payer = d.get("payeur_nom") or "Inconnu"
        paid_by[payer] += float(d.get("prix_depense", 0.0) or 0.0)
    if paid_by:
        df_pay = pd.DataFrame({"Payeur": list(paid_by.keys()), "Payé (€)": list(paid_by.values())})
        fig_pay = px.bar(df_pay, x="Payeur", y="Payé (€)", title="Part de chaque payeur")
        st.plotly_chart(fig_pay, use_container_width=True)
    else:
        st.info("Aucun paiement enregistré dans la période choisie.")

# ------------------ Résumé des profils du groupe ------------------
else:  # "🧬 Résumé des profils du groupe"
    st.header("🧬 Résumé des profils du groupe")

    if not people:
        st.info("Aucun participant enregistré.")
    else:
        # Listes
        non_viande = [p["nom"] for p in people if p.get("nom") and not p.get("nourriture_boolean")]
        boivent = [p["nom"] for p in people if p.get("nom") and p.get("alcool_boolean")]

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🚫 Ne mangent pas de viande")
            if non_viande:
                for n in non_viande:
                    st.write(f"• {n}")
            else:
                st.caption("Tout le monde mange de la viande.")

        with col2:
            st.subheader("🍷 Boivent de l'alcool")
            if boivent:
                for n in boivent:
                    st.write(f"• {n}")
            else:
                st.caption("Personne ne boit d'alcool.")

        # Camemberts d'intensité par personne
        st.subheader("🥧 Répartition des intensités de consommation")

        # Nourriture (pondéré par note, 0 si ne mange pas de viande)
        data_food = []
        for p in people:
            name = p.get("nom")
            if not name:
                continue
            w = p.get("nourriture_classification") if p.get("nourriture_boolean") else 0
            data_food.append({"Personne": name, "Score": int(w or 0)})
        df_food = pd.DataFrame(data_food)
        if df_food["Score"].sum() > 0:
            fig_food = px.pie(df_food, names="Personne", values="Score", title="Consommation de nourriture (scores 1–10)")
            st.plotly_chart(fig_food, use_container_width=True)
        else:
            st.caption("Pas de répartition nourriture (scores nuls ou personne ne mange de viande).")

        # Alcool (pondéré par note, 0 si ne boit pas)
        data_alc = []
        for p in people:
            name = p.get("nom")
            if not name:
                continue
            w = p.get("alcool_classification") if p.get("alcool_boolean") else 0
            data_alc.append({"Personne": name, "Score": int(w or 0)})
        df_alc = pd.DataFrame(data_alc)
        if df_alc["Score"].sum() > 0:
            fig_alc = px.pie(df_alc, names="Personne", values="Score", title="Consommation d'alcool (scores 1–10)")
            st.plotly_chart(fig_alc, use_container_width=True)
        else:
            st.caption("Pas de répartition alcool (scores nuls ou personne ne boit).")
