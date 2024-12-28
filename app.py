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

                  #st.subheader("Merchant Map") #commented out
                  #min_lat = df_mapped['latitude'].min() #commented out
                  #max_lat = df_mapped['latitude'].max() #commented out
                  #min_lng = df_mapped['longitude'].min() #commented out
                  #max_lng = df_mapped['longitude'].max() #commented out

                  ## Define the boundary polygon for the mapping #commented out
                  #coords = [[min_lng,min_lat],[min_lng,max_lat],[max_lng,max_lat],[max_lng,min_lat],[min_lng,min_lat]] #commented out
                  #boundary_polygon = Polygon(coords) #commented out
                 
                  ## Create the folium map #commented out
                  #m = folium.Map(location=[df_mapped['latitude'].mean(), df_mapped['longitude'].mean()], zoom_start=10) #commented out
                  #for _, row in df_mapped.iterrows(): #commented out
                  #    folium.Marker([row['latitude'], row['longitude']], popup=row[address_column]).add_to(m) #commented out
                  
                  # Use folium.folium_static #commented out
                  #st_folium = folium.folium_static(m) #commented out
                  #st.components.v1.html(st_folium._repr_html_(), height=450, width = 800) #commented out
                
                  # Create a heatmap #commented out
                  #st.subheader("Merchant Density") #commented out
                  #heatmap = create_heatmap(df_mapped) #commented out
                  #st_folium_heat = folium.folium_static(heatmap) #commented out
                  #st.components.v1.html(st_folium_heat._repr_html_(), height=450, width = 800) #commented out
                  
                  # Plot unplotted areas #commented out
                  #st.subheader("Unplotted area") #commented out
                  #unplotted_fig = plot_unplotted_areas(df_mapped, boundary_polygon, min_lat, max_lat, min_lng, max_lng) #commented out
                  #st.pyplot(unplotted_fig) #commented out
        
        except Exception as e:
            st.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
