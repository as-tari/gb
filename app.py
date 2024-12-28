import streamlit as st
import pandas as pd
import plotly.express as px
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable
import time
from functools import lru_cache
import re

def normalize_address(address):
    if not isinstance(address, str):
        return ""  # or handle non-string input differently
    address = address.lower()
    address = re.sub(r'[^\w\s\.,-]', '', address)  # Remove most punctuation but keep ,.-
    address = re.sub(r'\s+', ' ', address).strip()  # Reduce multiple spaces to single
    # Expand common abbreviations (this is not exhaustive and can be expanded)
    address = address.replace('jln', 'jalan').replace('jl', 'jalan')
    address = address.replace('kp ', 'kampung ').replace('kg ', 'kampung ')
    address = address.replace('perum ', 'perumahan ')
    address = address.replace('komp ', 'komplek ')
    address = address.replace('rt ', 'rukun tetangga ')
    address = address.replace('rw ', 'rukun warga ')

    return address

# Initialize the geolocator
geolocator = Nominatim(user_agent="geoapiExercises")

# Caching for geocoding results
@lru_cache(maxsize=512)
def geocode_address(address, retries=3):
    if not isinstance(address, str):
      return None, None
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else (None, None)
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as e:
      if retries > 0:
        time.sleep(1) # Wait for one second before retrying
        return geocode_address(address, retries-1)
      else:
         print(f"Geocoding failed for {address} after {retries} retries: {e}")
         return None, None


# Streamlit app title
st.title("Interactive Map-Based Data Visualization")

# File uploader for CSV or Excel files
uploaded_file = st.file_uploader("Upload your CSV or Excel file", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # Load the data
    if uploaded_file.name.endswith('.csv'):
        # Use semicolon as delimiter for the specific CSV file you provided
        data = pd.read_csv(uploaded_file, delimiter=';')
    else:
        data = pd.read_excel(uploaded_file)

    # Display the full data
    st.write("Full Data:")
    st.write(data)
    
    # Check if 'Address' column exists
    if 'Address' not in data.columns:
        st.error("The uploaded file must contain an 'Address' column.")
    else:
        # Verify that the address column exists and contains strings
        address_column = 'Address'  # We are hardcoding this as per the data you gave

        data[address_column] = data[address_column].astype(str)
        #Check for empty or whitespace-only addresses:
        invalid_addresses = data[data[address_column].str.strip() == ""]

        if not invalid_addresses.empty:
          st.error("Some addresses in the data are empty or contain only whitespace. Please provide valid addresses")
          st.write("The following rows have invalid address:")
          st.write(invalid_addresses)
        else:
          # Allow the user to select which map style to use
            map_style = st.selectbox("Select map style:",
                   ['carto-positron','open-street-map','carto-darkmatter','stamen-terrain','white-bg']
                  )
            if st.button("Generate Map"):

                # Geocode addresses with progress bar
                st.write("Geocoding addresses...")
                progress_bar = st.progress(0)
                total_addresses = len(data)

                # Create a new column to indicate geocoding failure
                data['GeocodingFailed'] = False
                for index, row in data.iterrows():
                    normalized_address = normalize_address(row[address_column])
                    coords = geocode_address(normalized_address)
                    if coords == (None, None):
                       data.loc[index,'GeocodingFailed'] = True
                       data.loc[index,'Latitude'] = None
                       data.loc[index,'Longitude'] = None
                    else:
                        data.loc[index,'Latitude'] = coords[0]
                        data.loc[index,'Longitude'] = coords[1]

                    progress_bar.progress((index + 1) / total_addresses)
                # Display the map, or a loading message
                with st.spinner("Generating map..."):
                  # Create a map visualization
                   fig = px.scatter_mapbox(data, lat='Latitude', lon='Longitude', hover_name=address_column,
                          color='GeocodingFailed', color_discrete_sequence=['blue','red'],
                           mapbox_style=map_style, zoom=10, title="Customer Locations")

                  # Update the hover template to not show the 'GeocodingFailed' boolean
                   fig.update_traces(hovertemplate="%{hovertext}")
                   st.plotly_chart(fig)


            # Identify and display unplotted areas
            unplotted = data[data['Latitude'].isnull() | data['Longitude'].isnull()]
            if not unplotted.empty:
                st.write(f"Unplotted Areas: {len(unplotted)} address(es) could not be geocoded.")
                #Allow user to specify which other columns should be shown:
                columns_to_show = st.multiselect("Select columns to show for unplotted areas",data.columns, default = [address_column])
                st.write(unplotted[columns_to_show])
            else:
                st.success("All addresses were successfully geocoded!")
            st.write("Geocoding Complete")
