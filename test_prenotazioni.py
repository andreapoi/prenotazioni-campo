import streamlit as st
import pandas as pd
import numpy as np
import string
import random
from datetime import datetime, timedelta

# URL of the initial CSV file hosted on GitHub
GITHUB_CSV_URL = 'https://raw.githubusercontent.com/<your-username>/<your-repo-name>/main/initial_data.csv'

# Function to load the initial CSV file from GitHub
@st.cache(allow_output_mutation=True)
def load_initial_data():
    return pd.read_csv(GITHUB_CSV_URL, header=[0, 1])  # Load with multi-level columns

# Function to generate time intervals
def generate_time_intervals(start_time='08:00', end_time='22:00', interval_minutes=90):
    intervals = []
    start = datetime.strptime(start_time, '%H:%M')
    end = datetime.strptime(end_time, '%H:%M')
    
    while start + timedelta(minutes=interval_minutes) <= end + timedelta(minutes=interval_minutes):
        next_time = start + timedelta(minutes=interval_minutes)
        intervals.append(f"{start.strftime('%H:%M')} - {next_time.strftime('%H:%M')}")
        start += timedelta(minutes=30)  # Move the start time by 30 minutes to create overlapping intervals

    return intervals

# Function to check for overlapping reservations
def is_overlapping(existing_interval, new_interval):
    # Convert time intervals to datetime objects
    existing_start, existing_end = [datetime.strptime(t.strip(), '%H:%M') for t in existing_interval.split('-')]
    new_start, new_end = [datetime.strptime(t.strip(), '%H:%M') for t in new_interval.split('-')]
    
    # Check for overlap
    return not (new_end <= existing_start or new_start >= existing_end)

# Function to initialize a DataFrame if it is not already loaded
def initialize_dataframe():
    # Load initial data from GitHub
    try:
        df = load_initial_data()
    except:
        df = pd.DataFrame()  # If loading fails, create a new DataFrame
    
    # Create the correct structure if loading fails or if it's the first run
    if df.empty or ('orario di gioco', '') not in df.columns:
        base_column = ('orario di gioco', '')
        date_columns = [(day, field) for day in [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)] for field in ['Campo 1', 'Campo 2']]
        columns = [base_column] + date_columns

        # Generate the time intervals
        time_intervals = generate_time_intervals()

        # Create the initial DataFrame with multi-level columns
        df = pd.DataFrame(columns=pd.MultiIndex.from_tuples(columns))
        df[('orario di gioco', '')] = time_intervals  # Populate with time intervals

    return df

# Function to block predefined time slots
def block_predefined_slots(df):
    # Blocking rules: (Day, Start time, End time, Field)
    blocking_rules = [
        ('Monday', '15:00', '16:00', 'Campo 1'),
        ('Monday', '19:30', '21:00', 'Campo 1'),
        ('Tuesday', '15:00', '21:00', 'Campo 1'),
        ('Tuesday', '20:00', '21:00', 'Campo 2'),
        ('Thursday', '15:00', '21:00', 'Campo 1'),
        ('Thursday', '19:00', '21:00', 'Campo 2')
    ]
    
    for day_name, start_time, end_time, field in blocking_rules:
        # Convert day_name to a date
        for i in range(14):
            current_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
            current_day_name = (datetime.now() + timedelta(days=i)).strftime('%A')
            if current_day_name == day_name:
                # Find the index of the blocked time intervals
                for idx, interval in enumerate(df[('orario di gioco', '')]):
                    if is_overlapping(interval, f"{start_time} - {end_time}"):
                        df.at[idx, (current_date, field)] = 'NOT AVAILABLE'
    return df

# Function to generate a fixed-length alphanumeric code
def generate_fixed_code(length=5):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Function to save the updated DataFrame to CSV
def save_to_csv(df):
    # Save the updated DataFrame to a CSV file
    df.to_csv('updated_data.csv', index=False)

# Initialize the DataFrame in session state
if 'df' not in st.session_state:
    st.session_state.df = initialize_dataframe()
    st.session_state.df = block_predefined_slots(st.session_state.df)  # Apply predefined blocks

# Initialize reservation codes storage
if 'reservation_codes' not in st.session_state:
    st.session_state.reservation_codes = {}

# Function to add a reservation to a specific field
def add_reservation():
    st.write("### Add a Reservation")

    # Drop-down to select the day
    days = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]
    selected_day = st.selectbox('Select Day for Reservation', options=days)

    # Drop-down to select between "Campo 1" and "Campo 2"
    selected_field = st.selectbox('Select Field for Reservation', options=['Campo 1', 'Campo 2'])

    # Combine the day and field for DataFrame column selection
    selected_day_field = (selected_day, selected_field)

    # Drop-down to select the available time period
    available_periods = st.session_state.df[st.session_state.df[selected_day_field].isna()][('orario di gioco', '')]
    selected_period = st.selectbox('Select Time Period for Reservation', options=available_periods)

    # Button to add the reservation
    if st.button('Add Reservation'):
        # Check if the selected time period is not available
        if selected_period in st.session_state.df[st.session_state.df[selected_day_field] == 'NOT AVAILABLE'][('orario di gioco', '')].values:
            st.error("Selected time period is not available for reservation. Please choose another one.")
            return

        # Check for overlapping reservations
        for existing_period in st.session_state.df[selected_day_field].dropna():
            if 'BLOCKED' not in existing_period and is_overlapping(existing_period, selected_period):
                st.error("Selected time period overlaps with an existing reservation. Please choose another one.")
                return

        # Find the index of the selected period
        row_index = st.session_state.df[st.session_state.df[('orario di gioco', '')] == selected_period].index[0]

        # Add the reservation
        if pd.isna(st.session_state.df.at[row_index, selected_day_field]):
            st.session_state.df.at[row_index, selected_day_field] = 'RESERVED'
            st.success(f"Reservation added successfully for {selected_field} on {selected_day} at {selected_period}.")
            save_to_csv(st.session_state.df)  # Save the updated DataFrame to CSV
        else:
            st.error("Selected time period is already occupied. Please choose another one.")

# Function to delete a block using a random code
def delete_block():
    st.write("### Delete a Block")

    # Input for the random block code to delete
    block_code = st.text_input('Enter the 5-digit Block Code to Remove')

    # Button to delete the block using the block code
    if st.button('Delete Block'):
        if block_code in st.session_state.reservation_codes:
            selected_day_field, row_index = st.session_state.reservation_codes[block_code]

            # Remove the block by setting cells to NaN
            st.session_state.df.at[row_index, selected_day_field] = pd.NA
            
            # Remove the reservation code from internal storage
            del st.session_state.reservation_codes[block_code]
            
            st.success("Block removed successfully!")
            save_to_csv(st.session_state.df)  # Save the updated DataFrame to CSV
        else:
            st.error("Invalid block code. Please try again.")

# Function to display the DataFrames for Campo 1 and Campo 2
def display_dataframes():
    # Separate DataFrames for Campo 1 and Campo 2
    campo1_df = st.session_state.df.xs('Campo 1', level=1, axis=1)
    campo2_df = st.session_state.df.xs('Campo 2', level=1, axis=1)

    # Function to color-code the cells
    def color_cells(val):
        if pd.isna(val):
            return 'background-color: green;'  # Free cells
        elif 'NOT AVAILABLE' in str(val):
            return 'background-color: red;'  # Predefined unavailable slots
        elif 'BLOCKED' in str(val):
            return 'background-color: orange;'  # Blocked by specific code
        else:
            return 'background-color: yellow;'  # Reserved by a normal submission

    # Display Campo 1 DataFrame with time intervals as index
    st.write('### Reservations for Campo 1')
    st.dataframe(campo1_df.set_index(st.session_state.df[('orario di gioco', '')]).style.applymap(color_cells))

    # Display Campo 2 DataFrame with time intervals as index
    st.write('### Reservations for Campo 2')
    st.dataframe(campo2_df.set_index(st.session_state.df[('orario di gioco', '')]).style.applymap(color_cells))

# Display the DataFrames on app startup
display_dataframes()

# Reservation inputs and button
add_reservation()

# Deletion input and button
delete_block()
