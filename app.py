import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import folium
import time
import re
from fuzzywuzzy import process, fuzz
from folium.plugins import HeatMap
from shapely.geometry import Polygon

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

def geocode_address(address, city, geolocator, state=None, postal_code=None, max_retries=3):
    """Geocodes an address with retry logic."""
    full_address = f"{address}, {city}"
    if state:
        full_address += f", {state}"
    if postal_code:
      full_address += f", {postal_code}"
    full_address = clean_address(full_address)

    for retry in range(max_retries):
      try:
        location = geolocator.geocode(full_address, timeout=10)
        if location:
          return location.latitude, location.longitude
      except (GeocoderTimedOut, GeocoderServiceError) as e:
          print(f"Geocoding error for address '{full_address}': {e}. Retrying ({retry + 1}/{max_retries}) after a delay.")
          time.sleep(5)
    print(f"Failed to geocode address: {full_address}")
    return None, None


def create_heatmap(df):
    """
    Generates a heatmap
    """
    heat_data = df[['latitude', 'longitude']].dropna().values.tolist()
    m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=10, tiles="cartodbdarkmatter")
    HeatMap(heat_data).add_to(m)
    return m

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
                    lat, lng = geocode_address(address, city, geolocator, state, postal_code)
                    geocoded_results.append((lat, lng))

                  df['latitude'], df['longitude'] = zip(*geocoded_results)

                # Handle un-geocoded locations
                df_unmapped = df[df['latitude'].isna()]
                if not df_unmapped.empty:
                   st.error("The following addresses could not be geocoded and will not be displayed on the map:")
                   st.dataframe(df_unmapped)

                # Filter for successfully geocoded locations
                df_mapped = df.dropna(subset=['latitude', 'longitude'])
                if df_mapped.empty:
                  st.warning("No addresses could be geocoded. Please check address data")
                else:
                  st.success("Geocoding complete!")
                  st.write("Data with Coordinates:")
                  st.dataframe(df.head())

                  st.subheader("Merchant Map")

                  # Create the base map
                  m = folium.Map(location=[df_mapped['latitude'].mean(), df_mapped['longitude'].mean()], zoom_start=10)

                  # Plot points as markers
                  for _, row in df_mapped.iterrows():
                      folium.Marker([row['latitude'], row['longitude']], popup=row[address_column]).add_to(m)
                  
                  # Display the map
                  st_folium = folium.folium_static(m)
                  st.components.v1.html(st_folium._repr_html_(), height=450, width = 800)
                
                  # Create a heatmap
                  st.subheader("Merchant Density")
                  heatmap = create_heatmap(df_mapped)
                  st_folium_heat = folium.folium_static(heatmap)
                  st.components.v1.html(st_folium_heat._repr_html_(), height=450, width = 800)

        except Exception as e:
            st.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
