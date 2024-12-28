import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import folium
from folium.plugins import HeatMap
import time
import numpy as np
from scipy.spatial import Delaunay
import geopandas
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, Point
import matplotlib
from matplotlib.cm import get_cmap
import streamlit.components as components
import re

def clean_address(address):
    """Cleans up the address string by removing unnecessary punctuations and spaces."""
    address = re.sub(r'[^\w\s,]', '', address)  # Remove all punctuation except commas
    address = ' '.join(address.split())  # Remove extra whitespace
    return address

def geocode_address(address, city, geolocator, state=None, postal_code=None, max_retries=3):
    """Geocodes an address with retry logic and optional city, state, and postal code."""

    for retry in range(max_retries):
      try:
        full_address = f"{address}, {city}"
        if state:
           full_address = f"{full_address}, {state}"
        if postal_code:
          full_address = f"{full_address}, {postal_code}"
        full_address = clean_address(full_address)
        location = geolocator.geocode(full_address, timeout=10)

        if location:
            return location.latitude, location.longitude
        else:
          # Try without the street name
            full_address = f"{city}"
            if state:
               full_address = f"{full_address}, {state}"
            if postal_code:
                full_address = f"{full_address}, {postal_code}"
            full_address = clean_address(full_address)
            location = geolocator.geocode(full_address, timeout=10)
            if location:
              return location.latitude, location.longitude

      except (GeocoderTimedOut, GeocoderServiceError) as e:
          print(f"Geocoding error for address '{full_address}': {e}. Retrying ({retry + 1}/{max_retries}) after a delay.")
          time.sleep(5)
          continue
      except Exception as e:
          print(f"Geocoding error for address '{full_address}': {e}. Skipping address.")
          break
    
    print(f"Failed to geocode address: {address}, {city}")
    return None, None
    
def create_voronoi_polygons(points):
  """
    Generates voronoi polygons for given points.
  """

  points = np.array(points)
  tri = Delaunay(points)
  polygons = []
  
  for simplex in tri.simplices:
    polygon_points = []
    for vertex_idx in simplex:
      vertex = tri.points[vertex_idx]
      polygon_points.append(vertex)

    polygon = Polygon(polygon_points)
    polygons.append(polygon)

  # Convert the polygons to GeoDataFrame
  gdf = geopandas.GeoDataFrame(geometry=polygons)
  
  return gdf

def create_heatmap(df):
    """
    Generates a heatmap
    """
    heat_data = df[['latitude', 'longitude']].dropna().values.tolist()
    m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=10, tiles="cartodbdarkmatter")
    HeatMap(heat_data).add_to(m)
    return m

def plot_unplotted_areas(df, boundary_polygon, min_lat, max_lat, min_lng, max_lng):
    """
    Plots unplotted area
    """
    # Create a grid of points within the bounding box of the mapped data
    lat_range = np.linspace(min_lat, max_lat, num=50)
    lng_range = np.linspace(min_lng, max_lng, num=50)
    grid_points = np.array(np.meshgrid(lat_range, lng_range)).T.reshape(-1, 2)
    grid_gdf = geopandas.GeoDataFrame(geometry=[Point(xy) for xy in grid_points])
    
    # Filter points to be only those inside the boundary
    grid_gdf['within'] = grid_gdf.geometry.apply(lambda p: boundary_polygon.contains(p))
    grid_gdf = grid_gdf[grid_gdf['within']==True]
    
    # Get the points
    mapped_points = df[['latitude', 'longitude']].dropna().values.tolist()
    
    # Create voronoi polygons
    voronoi_gdf = create_voronoi_polygons(mapped_points)
    
    # Create a spatial join between the grid and the voronoi polygons. 
    grid_gdf = geopandas.sjoin(grid_gdf, voronoi_gdf, how='left', predicate='intersects')

    # Create the matplotlib plot
    fig, ax = plt.subplots(1,1, figsize=(8, 6))
    cmap = get_cmap('RdYlGn_r')
    norm = matplotlib.colors.Normalize(vmin=0, vmax=1)

    # Loop through grid points and color them
    for idx, row in grid_gdf.iterrows():
        if pd.isna(row['index_right']):
          point_color = [1,1,1]
        else:
          point_color = [0.2, 0.7, 0.2]
        
        ax.plot(row.geometry.x, row.geometry.y, marker='o', markersize=5, color=point_color, alpha=0.75)

    # Add a label to the color bar
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Unplotted Area")
    ax.grid(True, alpha=0.4)
    return fig

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
                  for index, row in df.iterrows():
                    state = row[state_column] if state_column != 'None' else None
                    postal_code = row[postal_code_column] if postal_code_column != 'None' else None
                    lat, lng = geocode_address(row[address_column], row[city_column], geolocator, state, postal_code)
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

                  min_lat = df_mapped['latitude'].min()
                  max_lat = df_mapped['latitude'].max()
                  min_lng = df_mapped['longitude'].min()
                  max_lng = df_mapped['longitude'].max()

                  # Define the boundary polygon for the mapping
                  coords = [[min_lng,min_lat],[min_lng,max_lat],[max_lng,max_lat],[max_lng,min_lat],[min_lng,min_lat]]
                  boundary_polygon = Polygon(coords)
                 
                  # Create the folium map
                  m = folium.Map(location=[df_mapped['latitude'].mean(), df_mapped['longitude'].mean()], zoom_start=10)
                  for _, row in df_mapped.iterrows():
                      folium.Marker([row['latitude'], row['longitude']], popup=row[address_column]).add_to(m)
                  
                  components.html(m._repr_html_(), height=450, width = 800)
                
                  # Create a heatmap
                  st.subheader("Merchant Density")
                  heatmap = create_heatmap(df_mapped)
                  components.html(heatmap._repr_html_(), height=450, width = 800)
                  
                  # Plot unplotted areas
                  st.subheader("Unplotted area")
                  unplotted_fig = plot_unplotted_areas(df_mapped, boundary_polygon, min_lat, max_lat, min_lng, max_lng)
                  st.pyplot(unplotted_fig)
        
        except Exception as e:
            st.error(f"Error processing file: {e}")

if __name__ == "__main__":
    main()
