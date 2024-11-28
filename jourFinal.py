import streamlit as st
import pandas as pd
import json
from datetime import datetime
from geopy.distance import geodesic
import folium
from streamlit_folium import st_folium
import plotly.express as px
from scipy.spatial import Delaunay
import numpy as np
from tqdm import tqdm
import time

# Configuration de la page
st.set_page_config(page_title="Dashboard - Stations Service", layout="wide")

# Charger les données
@st.cache_data
def load_data():
    progress_bar = st.progress(0)
    status_text = st.empty()

    data_files = [
        ("Carrefour", "./data/carrefour_data.csv"),
        ("Autres enseignes", "./data/other_enseigne_data.csv"),
        ("Concurrents", "./data/concurrentes_par_station.json")
    ]

    data = {}
    for i, (name, path) in enumerate(tqdm(data_files, desc="Chargement des données", unit="fichier")):
        status_text.text(f"Chargement des données {name}...")
        if name == "Concurrents":
            with open(path) as f:
                data[name] = json.load(f)
        else:
            data[name] = pd.read_csv(path)
        time.sleep(0.5)  # Simule le temps de chargement
        progress_bar.progress((i + 1) / len(data_files))

    status_text.text("Chargement terminé ✅")
    time.sleep(0.5)

    progress_bar.empty()
    status_text.empty()

    return data["Carrefour"], data["Autres enseignes"], data["Concurrents"]

carrefour_data, other_data, competitors = load_data()

# Configuration des colonnes nécessaires
carrefour_data['Date'] = pd.to_datetime(carrefour_data['Date'], errors='coerce')
other_data['Date'] = pd.to_datetime(other_data['Date'], errors='coerce')

# Inclure les 6 carburants
carburants = ['Gazole', 'SP95', 'SP98', 'E10', 'E85', 'GPLc']

# Convertir les colonnes carburants en numérique
for df in [carrefour_data, other_data]:
    df[carburants] = df[carburants].apply(pd.to_numeric, errors='coerce')

# Fusionner les données
carrefour_data['Enseignes'] = 'Carrefour'
combined_data = pd.concat([carrefour_data, other_data], ignore_index=True)

# Liste des enseignes
enseigne_list = combined_data['Enseignes'].unique()

# Barre de navigation

pages = ["Étape A : KPI", "Étape B : Analyse des stations Carrefour"]
selected_page = st.sidebar.radio("Navigation", pages)

if selected_page == "Étape A : KPI":
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'>📊 Étape A : KPI - Analyse des Prix Moyens par Enseigne</h1>", unsafe_allow_html=True)

    # Filtres pour Étape A
    selected_enseigne_A = st.sidebar.selectbox("📍 Sélectionnez une enseigne :", enseigne_list)
    selected_date_A = st.sidebar.date_input("📅 Sélectionnez une date :", datetime.now())

    # Filtrer les données par enseigne et date
    filtered_data_A = combined_data[
        (combined_data['Enseignes'] == selected_enseigne_A) &
        (combined_data['Date'] == pd.to_datetime(selected_date_A))
    ]

    if not filtered_data_A.empty:
        # Calculer les prix moyens par produit
        avg_prices_A = filtered_data_A[carburants].mean().reset_index()
        avg_prices_A.columns = ['Produit', 'Prix Moyen']

        st.markdown(f"<h2 style='text-align: center;'>Prix moyens pour l'enseigne {selected_enseigne_A} à la date {selected_date_A}</h2>", unsafe_allow_html=True)

        # Affichage sous forme de cartes fixes
        css_style = """
        <style>
            .fixed-card {
                background-color: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
                width: 150px; 
                height: 200px; 
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                animation: fadeIn 1.5s;
            }
            @keyframes fadeIn {
                from {
                    opacity: 0;
                }
                to {
                    opacity: 1;
                }
            }
            .fixed-card h3 {
                margin: 0;
                font-size: 16px;
                color: #333;
            }
            .fixed-card h1 {
                margin: 0;
                color: #007BFF;
                font-size: 24px;
                font-weight: bold;
            }
        </style>
        """
        st.markdown(css_style, unsafe_allow_html=True)

        cols = st.columns(len(avg_prices_A))
        for i, (produit, prix) in enumerate(zip(avg_prices_A['Produit'], avg_prices_A['Prix Moyen'])):
            with cols[i]:
                st.markdown(
                    f"""
                    <div class="fixed-card">
                        <h3>{produit}</h3>
                        <h1>{prix:.2f} €</h1>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Graphique des prix moyens
        fig = px.bar(avg_prices_A, x='Produit', y='Prix Moyen',
                     title=f"Prix Moyens des Carburants ({selected_enseigne_A}) à la date {selected_date_A}",
                     text='Prix Moyen')
        fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig.update_layout(xaxis_title="Produits", yaxis_title="Prix Moyen (€)", title_font_size=16)
        st.plotly_chart(fig)
    else:
        st.warning(f"Aucune donnée disponible pour l'enseigne {selected_enseigne_A} à la date {selected_date_A}.")


elif selected_page == "Étape B : Analyse des stations Carrefour":
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'>📍 Étape B : Analyse des Stations Carrefour</h1>", unsafe_allow_html=True)

    station_list = carrefour_data['ID'].unique()
    selected_station_id = st.sidebar.selectbox("📍 Sélectionnez une station Carrefour :", station_list)

    station_data = carrefour_data[carrefour_data['ID'] == selected_station_id].iloc[0]
    station_location = (station_data['Latitude'], station_data['Longitude'])

    st.subheader("🗺️ Carte des Stations Concurrentes")
    competitors_within_10km = []
    for comp_id in competitors.get(str(selected_station_id), []):
        competitor = other_data[other_data['ID'] == comp_id]
        if not competitor.empty:
            comp_location = (competitor.iloc[0]['Latitude'], competitor.iloc[0]['Longitude'])
            distance = geodesic(station_location, comp_location).km
            if distance <= 10:
                competitors_within_10km.append(competitor.iloc[0])

    competitor_df = pd.DataFrame(competitors_within_10km)

    m = folium.Map(location=station_location, zoom_start=12)

    folium.Marker(location=station_location,
                  popup=f"Carrefour Station ({station_data['Ville']})",
                  icon=folium.Icon(color="green", icon="info-sign")).add_to(m)

    for _, row in competitor_df.iterrows():
        folium.Marker(location=(row['Latitude'], row['Longitude']),
                      popup=f"{row['Enseignes']} ({row['Ville']})",
                      icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

    folium.Circle(
        location=station_location,
        radius=10000,
        color="blue",
        fill=True,
        fill_color="blue",
        fill_opacity=0.2,
        popup=f"Rayon de 10 km autour de Carrefour ({station_data['Ville']})",
    ).add_to(m)

    coordinates = [(station_location[0], station_location[1])]
    for _, row in competitor_df.iterrows():
        coordinates.append((row['Latitude'], row['Longitude']))

    if len(coordinates) >= 3:
        points = np.array(coordinates)
        delaunay = Delaunay(points)
        for simplex in delaunay.simplices:
            triangle = [coordinates[i] for i in simplex]
            folium.Polygon(
                locations=triangle,
                color="purple",
                fill=True,
                fill_opacity=0.2,
                popup="Triangle Delaunay",
            ).add_to(m)

    st_folium(m, width=1200)

    # Tableau comparatif
    st.subheader("📋 Tableau de Comparaison des Prix")
    if not competitor_df.empty:
        carrefour_prices = pd.DataFrame({
            'Enseigne': ['Carrefour'],
            'Adresse': [station_data['Adresse']],
            **{fuel: [station_data[fuel]] for fuel in carburants}
        })

        competitor_prices = competitor_df[['Enseignes', 'Adresse'] + carburants].copy()
        competitor_prices.rename(columns={'Enseignes': 'Enseigne'}, inplace=True)

        full_table = pd.concat([carrefour_prices, competitor_prices], ignore_index=True)
        full_table.sort_values(by='Gazole', inplace=True)

        def highlight_carrefour(row):
            if row['Enseigne'] == 'Carrefour':
                return ['background-color: lightgreen'] * len(row)
            return [''] * len(row)

        st.dataframe(full_table.style.apply(highlight_carrefour, axis=1))
    else:
        st.write("Aucune station concurrente trouvée dans un rayon de 10 km.")


    # Courbes des prix
    st.subheader("📈 Courbes d'Évolution des Prix")
    date_range = st.sidebar.date_input(
        "📅 Sélectionnez une plage de dates :",
        [datetime.now() - pd.Timedelta(days=30), datetime.now()]
    )
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

    # Filtrer les données de la station Carrefour
    carrefour_trend = carrefour_data[
        (carrefour_data['ID'] == selected_station_id) &
        (carrefour_data['Date'].between(start_date, end_date))
    ].copy()

    # Filtrer les données des concurrents dans un rayon de 10 km
    competitor_ids = competitor_df['ID'].unique()
    competitor_trend = other_data[
        (other_data['ID'].isin(competitor_ids)) &
        (other_data['Date'].between(start_date, end_date))
    ].copy()

    # Ajouter une colonne pour identifier les stations
    carrefour_trend['Source'] = 'Carrefour'
    competitor_trend['Source'] = competitor_trend['Enseignes'] + " (" + competitor_trend['ID'].astype(str) + ")"

    # Combiner les données
    trend_data = pd.concat([carrefour_trend, competitor_trend], ignore_index=True)

    # Graphiques pour chaque type de carburant
    if not trend_data.empty:
        for carburant in carburants:
            fig = px.line(
                trend_data,
                x='Date',
                y=carburant,
                color='Source',
                title=f"Évolution du prix : {carburant}",
                labels={'Source': 'Station', 'Date': 'Date', carburant: 'Prix (€)'}
            )
            fig.update_traces(mode='lines+markers')
            fig.update_layout(title_font_size=16, xaxis_title="Date", yaxis_title="Prix (€)")
            st.plotly_chart(fig)
    else:
        st.write("Aucune donnée disponible pour la plage de dates sélectionnée.")



    # SECTION 4 : Comparaison avec le fichier "comparaison_prix_carrefour.csv"
    st.subheader("📂 Comparaison des Concurrents par Station Carrefour")

    comparaison_data = pd.read_csv("./data/comparaison_prix_carrefour.csv")

    carrefour_ids = comparaison_data['Carrefour_ID'].unique()
    selected_carrefour_id = st.selectbox("📍 Sélectionnez un Carrefour_ID :", carrefour_ids)

    filtered_comparaison = comparaison_data[comparaison_data['Carrefour_ID'] == selected_carrefour_id]

    if not filtered_comparaison.empty:
        st.dataframe(filtered_comparaison)

        fig = px.bar(
            filtered_comparaison,
            x='Produit',
            y=['Concurrentes_Inf', 'Concurrentes_Sup', 'Concurrentes_Egaux'],
            barmode='group',
            title=f"Comparaison des Concurrents pour Carrefour_ID : {selected_carrefour_id}",
            labels={'value': 'Nombre de stations', 'variable': 'Type de concurrents'}
        )
        fig.update_layout(
            xaxis_title="Produit",
            yaxis_title="Nombre de stations",
            title_font_size=16,
            legend_title_text="Type de Concurrents"
        )
        st.plotly_chart(fig)
    else:
        st.warning(f"Aucune donnée disponible pour le Carrefour_ID : {selected_carrefour_id}")

    


# Logo et légende
st.sidebar.image(
    "https://my.ecole-hexagone.com/logo-small.svg",
    use_container_width=True,  # Remplace use_column_width par use_container_width
)
st.sidebar.markdown("### Exaucé kenny Tshibuabua - Master 2 IA")
st.sidebar.markdown("Tableau de bord pour l'analyse des prix des stations service avec des visualisations interactives.")
