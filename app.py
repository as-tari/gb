import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import re
from fuzzywuzzy import process, fuzz

def clean_address(address):
    """Cleans up the address string by removing unnecessary punctuations and spaces."""
    address = re.sub(r'[^\w\s,]', '', address)  # Remove all punctuation except commas
    address = ' '.join(address.split())  # Remove extra whitespace
    return address

def correct_typo(text, choices, threshold=70):
    """Corrects typos in a text using fuzzy matching with a set of choices."""
    if not text or not choices:
        return text

    best_match, score = process.extractOne(text, choices, scorer=fuzz.ratio)
    if score >= threshold:
        return best_match
    return text

def geocode_address(address, city, geolocator, state=None, postal_code=None, max_retries=3, all_cities = None):
    """Geocodes an address with retry logic and multiple fallback strategies."""

    strategies = [
        ("Full Address", lambda a, c, s, pc: f"{a}, {c}{f', {s}' if s else ''}{f', {pc}' if pc else ''}"),
        ("City Only", lambda a, c, s, pc: f"{c}{f', {s}' if s else ''}{f', {pc}' if pc else ''}"),
        ("City + Postal Code", lambda a, c, s, pc: f"{c}{f', {pc}' if pc else ''}" if pc else None), #Postal Code
        ("City + State", lambda a, c, s, pc: f"{c}, {s}" if s else None) #State

    ]

    for retry in range(max_retries):
        for name, strategy_func in strategies:
           try:
               full_address = strategy_func(address, city, state, postal_code)
               if not full_address:
                  continue
               
               full_address = clean_address(full_address)
               if all_cities:
                  full_address = correct_typo(full_address, all_cities)

               location = geolocator.geocode(full_address, timeout=10)
               if location:
                  print(f"Geocoded using strategy '{name}': {full_address}")
                  return location.latitude, location.longitude
           except (GeocoderTimedOut, GeocoderServiceError) as e:
               print(f"Geocoding error with strategy '{name}': {e}. Retrying ({retry + 1}/{max_retries}) after a delay.")
               time.sleep(5)
           except Exception as e:
               print(f"Geocoding error with strategy '{name}': {e}.")
               continue
    
    print(f"Failed to geocode address: {address}, {city}")
    return None, None

def main():
    st.title("Merchant Location Mapper")

    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.write("Data Preview:")
            st.dataframe(df.head())

            address_column = st.selectbox("Select Address Column", df.columns)
            city_column = st.selectbox("Select City Column", df.columns)
            
            state_column = st.selectbox("Select State Column (Optional)", ['None'] + list(df.columns))
            postal_code_column = st.selectbox("Select Postal Code Column (Optional)", ['None'] + list(df.columns))

            if st.button("Process Data & Map"):
                # Initialize geolocator
                geolocator = Nominatim(user_agent="merchant_mapper_app", timeout=10)

                with st.spinner("Geocoding addresses..."):
                  # Geocode addresses and add lat/long columns
                  geocoded_results = []
                  all_cities = df[city_column].dropna().unique().tolist() # Get all unique cities for typo checking
                  for index, row in df.iterrows():
                    city = row[city_column]
                    address = row[address_column]
                    
                    #Try to fix city typos
                    city = correct_typo(city, all_cities)
                    
                    state = row[state_column] if state_column != 'None' else None
                    postal_code = row[postal_code_column] if postal_code_column != 'None' else None
                    lat, lng = geocode_address(address, city, geolocator, state, postal_code, all_cities = all_cities)
                    geocoded_results.append((lat, lng))
                  df['latitude'], df['longitude'] = zip(*geocoded_results)
                  print(df.head()) # New line to print dataframe

                  
        
        except Exception as e:
            st.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
