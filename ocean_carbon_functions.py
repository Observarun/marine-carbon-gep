import os
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
from shapely.validation import make_valid


def calculate_eez_areas(eez_gpkg_path, output_eez_csv_path):
    """
    Load EEZ marine correspondence file and calculate area for each country.
    """
    if os.path.exists(output_eez_csv_path):
        df_eez_areas = pd.read_csv(output_eez_csv_path)
        return df_eez_areas
    
    # Load the marine EEZ correspondence file
    print(f"Loading EEZ data from {eez_gpkg_path}")
    gdf = gpd.read_file(eez_gpkg_path)
    print(f"Loaded {len(gdf)} records")
    
    # Validate required columns
    required_cols = ['iso3_r250_id', 'iso3_r250_label', 'iso3_r250_name', 'geometry']
    missing = [col for col in required_cols if col not in gdf.columns]
    if missing:
        raise ValueError(f"GeoPackage missing columns: {missing}")
    
    # Keep only true marine EEZ polygons: name ends with 'Marine EEZ'
    if 'eemarine_r566_name' in gdf.columns:
        gdf = gdf[gdf['eemarine_r566_name'].str.contains('Marine EEZ', na=False)].copy()
        print(f"Kept only 'Marine EEZ' geometries. Remaining: {len(gdf)}")
    else:
        raise ValueError("eemarine_r566_name column not found; cannot select only 'Marine EEZ' geometries.")
    
    # Filter out records with missing country codes (assumed high seas)
    # before_filter = len(gdf)
    # gdf = gdf[gdf['iso3_r250_id'].notna() & (gdf['iso3_r250_id'] != '')].copy()
    # print(f"Filtered out {before_filter - len(gdf)} high seas records. Remaining: {len(gdf)}")
    
    # Fix invalid geometries with make_valid() - more robust than buffer(0)
    if (~gdf.geometry.is_valid).any():
        print(f"Found {(~gdf.geometry.is_valid).sum()} invalid geometries. Fixing...")
        gdf['geometry'] = gdf.geometry.make_valid()
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()
        print(f"Geometries after validation: {len(gdf)}")
    
    # Reproject to Mollweide (equal-area) for area calculation
    mollweide_wkt = (
        'PROJCS["World_Mollweide",'
        'GEOGCS["GCS_WGS_1984",'
        'DATUM["WGS_1984",'
        'SPHEROID["WGS_84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],'
        'UNIT["Degree",0.017453292519943295]],'
        'PROJECTION["Mollweide"],'
        'PARAMETER["False_Easting",0],'
        'PARAMETER["False_Northing",0],'
        'PARAMETER["Central_Meridian",0],'
        'UNIT["Meter",1]]'
    )
    
    try:
        gdf_proj = gdf.to_crs(mollweide_wkt)
        print("Reprojected to Mollweide for area calculation.")
    except Exception:
        try:
            gdf_proj = gdf.to_crs("EPSG:3857")
            print("Reprojected to Web Mercator (fallback).")
        except Exception:
            gdf_proj = gdf
            print("Using original CRS (no reprojection).")
    
    # Fix geometries again after reprojection (reprojection can introduce errors)
    if (~gdf_proj.geometry.is_valid).any():
        print(f"Found {(~gdf_proj.geometry.is_valid).sum()} invalid geometries after reprojection. Fixing...")
        gdf_proj['geometry'] = gdf_proj.geometry.make_valid()
        gdf_proj = gdf_proj[gdf_proj.geometry.is_valid & ~gdf_proj.geometry.is_empty].copy()
    
    # Simplify complex geometries to avoid topology errors during dissolve
    # 100m tolerance is negligible for EEZ-scale analysis
    # NOT REQUIRED!!!
    #print("Simplifying geometries...")
    #gdf_proj['geometry'] = gdf_proj.geometry.simplify(tolerance=100, preserve_topology=True)
    
    # Keep only needed columns for dissolve
    df_eez = gdf_proj[['iso3_r250_id', 'iso3_r250_label', 'iso3_r250_name', 'geometry']].copy()
    
    # Dissolve polygons by country (ISO3) to avoid double-counting overlaps
    print("Dissolving polygons by country...")
    try:
        gdf_dissolved = df_eez.dissolve(
            by='iso3_r250_id',
            as_index=False,
            aggfunc={
                'iso3_r250_label': 'first',
                'iso3_r250_name': 'first'
            }
        )
        print(f"Dissolved to {len(gdf_dissolved)} unique countries")
    except Exception as e:
        print(f"Error during dissolve: {e}")
        print("Attempting alternative approach: groupby + unary_union")
        # Fallback: manual dissolve using groupby + unary_union
        from shapely.ops import unary_union
        
        dissolved_list = []
        for iso3, group in df_eez.groupby('iso3_r250_id'):
            dissolved_geom = unary_union(group.geometry.tolist())
            dissolved_list.append({
                'iso3_r250_id': iso3,
                'iso3_r250_label': group['iso3_r250_label'].iloc[0],
                'iso3_r250_name': group['iso3_r250_name'].iloc[0],
                'geometry': dissolved_geom
            })
        gdf_dissolved = gpd.GeoDataFrame(dissolved_list, crs=gdf_proj.crs)
        print(f"Manual dissolve completed: {len(gdf_dissolved)} countries")
    
    # Calculate area for each dissolved geometry
    gdf_dissolved['eez_area_m2'] = gdf_dissolved.geometry.area
    gdf_dissolved['eez_area_km2'] = gdf_dissolved['eez_area_m2'] / 1e6
    
    # Compute global EEZ total and proportions
    total_eez_area_km2 = gdf_dissolved['eez_area_km2'].sum()
    print(f"\nTotal global EEZ area: {total_eez_area_km2:,.0f} km²")
    
    gdf_dissolved['proportion_of_global_eez'] = (
        gdf_dissolved['eez_area_km2'] / total_eez_area_km2
    )
    
    # Prepare output DataFrame
    df_eez_areas = gdf_dissolved[[
        'iso3_r250_id',
        'iso3_r250_label',
        'iso3_r250_name',
        'eez_area_km2',
        'proportion_of_global_eez'
    ]].copy()
     
    # Sort by EEZ area (largest first)
    df_eez_areas = df_eez_areas.sort_values(
        'eez_area_km2', ascending=False
    ).reset_index(drop=True)
    
    # Display top 10
    # print("\nTop 10 countries by EEZ area:")
    # print(df_eez_areas[['iso3_code', 'country_name', 'eez_area_km2']].head(10).to_string(index=False))
    
    # Save to CSV
    df_eez_areas.to_csv(output_eez_csv_path, index=False)
    print(f"\nEEZ areas saved to: {output_eez_csv_path}")
    
    return df_eez_areas


def calculate_ocean_area(eez_gpkg_path, output_ocean_area_csv_path):
    """
    Calculate total ocean area (EEZ + high seas) from eemarine_r566_correspondence.gpkg.
    """
    # If already computed, just read and return
    if os.path.exists(output_ocean_area_csv_path):
        df = pd.read_csv(output_ocean_area_csv_path)
        return float(df.loc[0, "total_ocean_area_km2"])

    print(f"Loading marine correspondence data from {eez_gpkg_path}")
    gdf = gpd.read_file(eez_gpkg_path)
    print(f"Loaded {len(gdf)} records")

    if "eemarine_r566_name" not in gdf.columns:
        raise ValueError("eemarine_r566_name column not found; cannot select marine geometries.")

    # Select ALL marine/ocean polygons: names that contain 'Marine EEZ'
    # OR 'Nearest Open Ocean'. This gives EEZ + associated open-ocean tiles.
    marine_mask = (
        gdf["eemarine_r566_name"].str.contains("Marine EEZ", na=False) |
        gdf["eemarine_r566_name"].str.contains("Nearest Open Ocean", na=False)
    )
    gdf_marine = gdf[marine_mask].copy()
    print(f"Selected {len(gdf_marine)} marine polygons (EEZ + open ocean).")

    # Basic geometry fix in original CRS
    if (~gdf_marine.geometry.is_valid).any():
        print(f"Found {(~gdf_marine.geometry.is_valid).sum()} invalid geometries. Fixing...")
        gdf_marine['geometry'] = gdf_marine.geometry.make_valid()
        gdf_marine = gdf_marine[gdf_marine.geometry.is_valid & ~gdf_marine.geometry.is_empty].copy()
        print(f"Geometries after validation: {len(gdf_marine)}")

    # Reproject to equal-area CRS (Mollweide)
    mollweide_wkt = (
        'PROJCS["World_Mollweide",'
        'GEOGCS["GCS_WGS_1984",'
        'DATUM["WGS_1984",'
        'SPHEROID["WGS_84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],'
        'UNIT["Degree",0.017453292519943295]],'
        'PROJECTION["Mollweide"],'
        'PARAMETER["False_Easting",0],'
        'PARAMETER["False_Northing",0],'
        'PARAMETER["Central_Meridian",0],'
        'UNIT["Meter",1]]'
    )

    try:
        gdf_proj = gdf_marine.to_crs(mollweide_wkt)
        print("Reprojected to Mollweide for area calculation.")
    except Exception:
        try:
            gdf_proj = gdf_marine.to_crs("EPSG:3857")
            print("Reprojected to Web Mercator (fallback).")
        except Exception:
            gdf_proj = gdf_marine
            print("Using original CRS (no reprojection).")

    # Fix geometries again after reprojection
    if (~gdf_proj.geometry.is_valid).any():
        print(f"Found {(~gdf_proj.geometry.is_valid).sum()} invalid geometries after reprojection. Fixing...")
        gdf_proj["geometry"] = gdf_proj.geometry.make_valid()
        gdf_proj = gdf_proj[gdf_proj.geometry.is_valid & ~gdf_proj.geometry.is_empty].copy()

    # No dissolve here: we just sum polygon areas.
    gdf_proj["area_m2"] = gdf_proj.geometry.area
    gdf_proj["area_km2"] = gdf_proj["area_m2"] / 1e6

    total_ocean_area_km2 = float(gdf_proj["area_km2"].sum())
    print(f"Total ocean area (EEZ + open ocean): {total_ocean_area_km2:,.0f} km²")

    # Save to CSV
    pd.DataFrame(
        [{"total_ocean_area_km2": total_ocean_area_km2}]
    ).to_csv(output_ocean_area_csv_path, index=False)
    print(f"Total ocean area saved to: {output_ocean_area_csv_path}")

    return total_ocean_area_km2


def allocate_marine_carbon_value(
        df_eez_areas,
        total_ocean_area_km2,
        total_ocean_carbon_tonnes,
        rental_price_2019_per_tc_per_year,
        output_csv_path
    ):
    """
    Allocate total marine carbon value to countries proportional to EEZ area.
    """
    df_alloc = df_eez_areas.copy()

    # Share of total ocean area (not just EEZ)
    df_alloc["share_of_total_ocean"] = df_alloc["eez_area_km2"] / total_ocean_area_km2

    # Allocate value proportional to EEZ area share
    total_annual_value_usd = total_ocean_carbon_tonnes * rental_price_2019_per_tc_per_year
    df_alloc['allocated_value_usd'] = (
        total_annual_value_usd * df_alloc['share_of_total_ocean']
    )

    # Value per km2 of EEZ
    df_alloc['value_per_km2_eez'] = (
        df_alloc['allocated_value_usd'] / df_alloc['eez_area_km2']
    )

    # Sort by allocated value
    df_alloc = df_alloc.sort_values(
        'allocated_value_usd', ascending=False
    ).reset_index(drop=True)

    # Cumulative share
    df_alloc['cumulative_value'] = df_alloc['allocated_value_usd'].cumsum()
    df_alloc['cumulative_share'] = (
        100.0 * df_alloc['cumulative_value'] / total_annual_value_usd
    )

    # Build output table
    df_output = df_alloc[[
        'iso3_r250_id',
        'iso3_r250_label',
        'iso3_r250_name',
        'eez_area_km2',
        'proportion_of_global_eez',
        'allocated_value_usd'
    ]].copy()

    # Save to CSV
    df_output.to_csv(output_csv_path, index=False)

    return df_output