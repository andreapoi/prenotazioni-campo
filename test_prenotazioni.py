import streamlit as st
import pandas as pd
import numpy as np
import string
import random
from datetime import datetime, timedelta

# URL del file CSV iniziale ospitato su GitHub
GITHUB_CSV_URL = 'https://github.com/andreapoi/prenotazioni-campo/blob/main/initial_data.csv'

# Funzione per caricare il file CSV iniziale da GitHub
@st.cache(allow_output_mutation=True)
def load_initial_data():
    return pd.read_csv(GITHUB_CSV_URL, header=[0, 1])  # Carica con colonne multi-livello

# Funzione per generare gli intervalli orari
def generate_time_intervals(start_time='08:00', end_time='22:00', interval_minutes=90):
    intervals = []
    start = datetime.strptime(start_time, '%H:%M')
    end = datetime.strptime(end_time, '%H:%M')
    
    while start + timedelta(minutes=interval_minutes) <= end + timedelta(minutes=interval_minutes):
        next_time = start + timedelta(minutes=interval_minutes)
        intervals.append(f"{start.strftime('%H:%M')} - {next_time.strftime('%H:%M')}")
        start += timedelta(minutes=30)  # Sposta l'inizio dell'intervallo di 30 minuti per creare intervalli sovrapposti

    return intervals

# Funzione per controllare la sovrapposizione delle prenotazioni
def is_overlapping(existing_interval, new_interval):
    # Converti gli intervalli di tempo in oggetti datetime
    existing_start, existing_end = [datetime.strptime(t.strip(), '%H:%M') for t in existing_interval.split('-')]
    new_start, new_end = [datetime.strptime(t.strip(), '%H:%M') for t in new_interval.split('-')]
    
    # Verifica se c'è sovrapposizione
    return not (new_end <= existing_start or new_start >= existing_end)

# Funzione per inizializzare un DataFrame se non è già caricato
def initialize_dataframe():
    # Carica i dati iniziali da GitHub
    try:
        df = load_initial_data()
    except:
        df = pd.DataFrame()  # Se il caricamento fallisce, crea un nuovo DataFrame
    
    # Crea la struttura corretta se il caricamento fallisce o se è il primo avvio
    if df.empty or ('orario di gioco', '') not in df.columns:
        base_column = ('orario di gioco', '')
        date_columns = [(day, field) for day in [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)] for field in ['Campo 1', 'Campo 2']]
        columns = [base_column] + date_columns

        # Genera gli intervalli orari
        time_intervals = generate_time_intervals()

        # Crea il DataFrame iniziale con colonne multi-livello
        df = pd.DataFrame(columns=pd.MultiIndex.from_tuples(columns))
        df[('orario di gioco', '')] = time_intervals  # Popola con gli intervalli orari

    return df

# Funzione per bloccare gli intervalli di tempo predefiniti
def block_predefined_slots(df):
    # Regole di blocco: (Giorno, Ora di inizio, Ora di fine, Campo)
    blocking_rules = [
        ('Monday', '15:00', '16:00', 'Campo 1'),
        ('Monday', '19:30', '21:00', 'Campo 1'),
        ('Tuesday', '15:00', '21:00', 'Campo 1'),
        ('Tuesday', '20:00', '21:00', 'Campo 2'),
        ('Thursday', '15:00', '21:00', 'Campo 1'),
        ('Thursday', '19:00', '21:00', 'Campo 2')
    ]
    
    for day_name, start_time, end_time, field in blocking_rules:
        # Converti day_name in una data
        for i in range(14):
            current_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            current_day_name = (datetime.now() + timedelta(days=i)).strftime('%A')
            if current_day_name == day_name:
                # Trova l'indice degli intervalli di tempo bloccati
                for idx, interval in enumerate(df[('orario di gioco', '')]):
                    if is_overlapping(interval, f"{start_time} - {end_time}"):
                        df.at[idx, (current_date, field)] = 'NOT AVAILABLE'
    return df

# Funzione per generare un codice alfanumerico di lunghezza fissa
def generate_fixed_code(length=5):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Funzione per salvare il DataFrame aggiornato nel CSV
def save_to_csv(df):
    # Salva il DataFrame aggiornato in un file CSV
    df.to_csv('updated_data.csv', index=False)

# Inizializza il DataFrame nello stato della sessione
if 'df' not in st.session_state:
    st.session_state.df = initialize_dataframe()
    st.session_state.df = block_predefined_slots(st.session_state.df)  # Applica i blocchi predefiniti

# Inizializza la memoria per i codici di prenotazione
if 'reservation_codes' not in st.session_state:
    st.session_state.reservation_codes = {}

# Funzione per aggiungere una prenotazione a un campo specifico
def add_reservation():
    st.write("### Aggiungi una Prenotazione")

    # Menu a tendina per selezionare il giorno
    days = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]
    selected_day = st.selectbox('Seleziona il Giorno per la Prenotazione', options=days)

    # Menu a tendina per selezionare tra "Campo 1" e "Campo 2"
    selected_field = st.selectbox('Seleziona il Campo per la Prenotazione', options=['Campo 1', 'Campo 2'])

    # Combina il giorno e il campo per la selezione della colonna nel DataFrame
    selected_day_field = (selected_day, selected_field)

    # Menu a tendina per selezionare il periodo di tempo disponibile
    available_periods = st.session_state.df[st.session_state.df[selected_day_field].isna()][('orario di gioco', '')]
    selected_period = st.selectbox('Seleziona il Periodo di Tempo per la Prenotazione', options=available_periods)

    # Bottone per aggiungere la prenotazione
    if st.button('Aggiungi Prenotazione'):
        # Verifica se il periodo di tempo selezionato non è disponibile
        if selected_period in st.session_state.df[st.session_state.df[selected_day_field] == 'NOT AVAILABLE'][('orario di gioco', '')].values:
            st.error("Il periodo di tempo selezionato non è disponibile per la prenotazione. Si prega di scegliere un altro.")
            return

        # Verifica la sovrapposizione delle prenotazioni
        for existing_period in st.session_state.df[selected_day_field].dropna():
            if 'BLOCKED' not in existing_period and is_overlapping(existing_period, selected_period):
                st.error("Il periodo di tempo selezionato si sovrappone a una prenotazione esistente. Si prega di scegliere un altro.")
                return

        # Trova l'indice del periodo selezionato
        row_index = st.session_state.df[st.session_state.df[('orario di gioco', '')] == selected_period].index[0]

        # Aggiungi la prenotazione
        if pd.isna(st.session_state.df.at[row_index, selected_day_field]):
            st.session_state.df.at[row_index, selected_day_field] = 'RESERVED'
            st.success(f"Prenotazione aggiunta con successo per {selected_field} il {selected_day} alle {selected_period}.")
            save_to_csv(st.session_state.df)  # Salva il DataFrame aggiornato nel CSV
        else:
            st.error("Il periodo di tempo selezionato è già occupato. Si prega di scegliere un altro.")

# Funzione per eliminare un blocco utilizzando un codice casuale
def delete_block():
    st.write("### Elimina una Prenotazione")

    # Input per il codice del blocco da eliminare
    block_code = st.text_input('Inserisci il Codice del Blocco (5 cifre) per Rimuoverlo')

    # Bottone per eliminare il blocco utilizzando il codice del blocco
    if st.button('Elimina Prenotazione'):
        if block_code in st.session_state.reservation_codes:
            selected_day_field, row_index = st.session_state.reservation_codes[block_code]

            # Rimuovi il blocco impostando le celle a NaN
            st.session_state.df.at[row_index, selected_day_field] = pd.NA
            
            # Rimuovi il codice di prenotazione dalla memoria interna
            del st.session_state.reservation_codes[block_code]
            
            st.success("Prenotazione rimossa con successo!")
            save_to_csv(st.session_state.df)  # Salva il DataFrame aggiornato nel CSV
        else:
            st.error("Codice del blocco non valido. Riprova.")

# Funzione per visualizzare i DataFrame per Campo 1 e Campo 2
def display_dataframes():
    # DataFrame separati per Campo 1 e Campo 2
    campo1_df = st.session_state.df.xs('Campo 1', level=1, axis=1)
    campo2_df = st.session_state.df.xs('Campo 2', level=1, axis=1)

    # Funzione per colorare le celle
    def color_cells(val):
        if pd.isna(val):
            return 'background-color: white;'  # Celle libere e vuote
        elif 'NOT AVAILABLE' in str(val):
            return 'background-color: red;'  # Slot non disponibili
        elif 'BLOCKED' in str(val):
            return 'background-color: orange;'  # Bloccato da codice specifico
        else:
            return 'background-color: yellow;'  # Prenotato con una normale prenotazione

    # Visualizza il DataFrame di Campo 1 con le fasce orarie come indice
    st.write('### Prenotazioni per Campo 1')
    st.dataframe(campo1_df.set_index(st.session_state.df[('orario di gioco', '')]).style.applymap(color_cells))

    # Visualizza il DataFrame di Campo 2 con le fasce orarie come indice
    st.write('### Prenotazioni per Campo 2')
    st.dataframe(campo2_df.set_index(st.session_state.df[('orario di gioco', '')]).style.applymap(color_cells))

# Visualizza i DataFrame all'avvio dell'app
display_dataframes()

# Inputs per le prenotazioni e bottone
add_reservation()

# Inputs per la cancellazione delle prenotazioni e bottone
delete_block()
