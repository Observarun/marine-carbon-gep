import os
import pandas as pd
import geopandas as gpd

# Equal-area projection (World Mollweide) used for all area calculations
MOLLWEIDE_CRS = "ESRI:54009"


def calculate_eez_areas(eez_gpkg_path, output_eez_csv_path):
    """
    Load EEZ marine correspondence file and calculate EEZ area for each country.
    """
    if os.path.exists(output_eez_csv_path):
        return pd.read_csv(output_eez_csv_path)

    print(f"Loading EEZ data from {eez_gpkg_path}")
    gdf = gpd.read_file(eez_gpkg_path)
    print(f"Loaded {len(gdf)} records")

    # Validate required columns
    required_cols = ['iso3_r250_id', 'iso3_r250_label', 'iso3_r250_name', 'eemarine_r566_name', 'geometry']
    missing = [col for col in required_cols if col not in gdf.columns]
    if missing:
        raise ValueError(f"GeoPackage missing columns: {missing}")

    # Keep only true marine EEZ polygons
    gdf = gdf[gdf['eemarine_r566_name'].str.contains('Marine EEZ', na=False)].copy()
    print(f"Kept only 'Marine EEZ' geometries. Remaining: {len(gdf)}")

    # Reproject to an equal-area CRS, then fix invalid geometries
    gdf = gdf.to_crs(MOLLWEIDE_CRS)
    gdf['geometry'] = gdf.geometry.make_valid()

    # Dissolve polygons by country (ISO3) to avoid double-counting overlaps.
    # dropna=False keeps any EEZ polygon without a country code as its own row
    # instead of silently dropping it.
    gdf = gdf[['iso3_r250_id', 'iso3_r250_label', 'iso3_r250_name', 'geometry']]
    gdf_dissolved = gdf.dissolve(
        by='iso3_r250_id',
        as_index=False,
        dropna=False,
        aggfunc={
            'iso3_r250_label': 'first',
            'iso3_r250_name': 'first'
        }
    )
    print(f"Dissolved to {len(gdf_dissolved)} unique countries")

    # The source stores country codes as floats (10.0, 840.0); keep them as integers
    gdf_dissolved['iso3_r250_id'] = gdf_dissolved['iso3_r250_id'].astype('Int64')

    # Calculate area and share of global EEZ for each country
    gdf_dissolved['eez_area_km2'] = gdf_dissolved.geometry.area / 1e6
    total_eez_area_km2 = gdf_dissolved['eez_area_km2'].sum()
    print(f"Total global EEZ area: {total_eez_area_km2:,.0f} km²")

    gdf_dissolved['proportion_of_global_eez'] = (
        gdf_dissolved['eez_area_km2'] / total_eez_area_km2
    )

    # Prepare output table, sorted by EEZ area (largest first)
    df_eez_areas = gdf_dissolved[[
        'iso3_r250_id',
        'iso3_r250_label',
        'iso3_r250_name',
        'eez_area_km2',
        'proportion_of_global_eez'
    ]].sort_values('eez_area_km2', ascending=False).reset_index(drop=True)

    df_eez_areas.to_csv(output_eez_csv_path, index=False)
    print(f"EEZ areas saved to: {output_eez_csv_path}")

    return df_eez_areas


def calculate_ocean_area(eez_gpkg_path, output_ocean_area_csv_path):
    """
    Calculate total ocean area (EEZ + high seas) from eemarine_r566_correspondence.gpkg.
    """
    if os.path.exists(output_ocean_area_csv_path):
        df = pd.read_csv(output_ocean_area_csv_path)
        return float(df.loc[0, "total_ocean_area_km2"])

    print(f"Loading marine correspondence data from {eez_gpkg_path}")
    gdf = gpd.read_file(eez_gpkg_path)
    print(f"Loaded {len(gdf)} records")

    if "eemarine_r566_name" not in gdf.columns:
        raise ValueError("eemarine_r566_name column not found; cannot select marine geometries.")

    # Select ALL ocean polygons: EEZs plus the open-ocean (high seas) polygons
    ocean_mask = gdf["eemarine_r566_name"].str.contains("Marine EEZ|Nearest Open Ocean", na=False)
    gdf = gdf[ocean_mask].copy()
    print(f"Selected {len(gdf)} ocean polygons (EEZ + open ocean).")

    # Reproject to an equal-area CRS, then fix invalid geometries
    gdf = gdf.to_crs(MOLLWEIDE_CRS)
    gdf['geometry'] = gdf.geometry.make_valid()

    # No dissolve here: we just sum polygon areas.
    total_ocean_area_km2 = float(gdf.geometry.area.sum() / 1e6)
    print(f"Total ocean area (EEZ + open ocean): {total_ocean_area_km2:,.0f} km²")

    pd.DataFrame(
        [{"total_ocean_area_km2": total_ocean_area_km2}]
    ).to_csv(output_ocean_area_csv_path, index=False)
    print(f"Total ocean area saved to: {output_ocean_area_csv_path}")

    return total_ocean_area_km2


def allocate_marine_carbon_value(
        df_eez_areas,
        total_ocean_area_km2,
        marine_carbon_pools,
        output_csv_path
    ):
    """
    Allocate marine carbon value proportional to area: each country gets the
    share corresponding to its EEZ, and the high seas (international waters,
    i.e. all ocean outside EEZs) are reported as their own category.

    marine_carbon_pools maps pool name -> {'stock_pg_c': ..., 'rental_price_2019_per_tc_per_year': ...}.
    Each pool is valued with its own rental price; pool values are reported
    separately and summed into allocated_value_usd.
    """
    df_alloc = df_eez_areas[[
        'iso3_r250_id',
        'iso3_r250_label',
        'iso3_r250_name',
        'eez_area_km2'
    ]].rename(columns={'eez_area_km2': 'area_km2'})

    # High seas = total ocean area minus the sum of all EEZ areas
    high_seas_area_km2 = total_ocean_area_km2 - df_alloc['area_km2'].sum()
    if high_seas_area_km2 < 0:
        raise ValueError(
            f"EEZ areas ({df_alloc['area_km2'].sum():,.0f} km²) exceed total ocean area "
            f"({total_ocean_area_km2:,.0f} km²); check the polygon selection."
        )

    # Numeric id 999 (ISO 3166-1 user-assigned range) keeps the id column integer;
    # the label 'ABNJ' identifies the row.
    df_high_seas = pd.DataFrame([{
        'iso3_r250_id': 999,
        'iso3_r250_label': 'ABNJ',
        'iso3_r250_name': 'High Seas (Areas Beyond National Jurisdiction)',
        'area_km2': high_seas_area_km2
    }])
    df_alloc = pd.concat([df_alloc, df_high_seas], ignore_index=True)

    # Share of total ocean area (countries' EEZs + high seas sum to 1)
    df_alloc['share_of_total_ocean_area'] = df_alloc['area_km2'] / total_ocean_area_km2

    # Value each pool (Pg C -> tonnes C, times its own rental price), then allocate by area share
    pool_value_cols = []
    for pool_name, pool in marine_carbon_pools.items():
        pool_value_usd = pool['stock_pg_c'] * 1e9 * pool['rental_price_2019_per_tc_per_year']
        col = f'allocated_value_{pool_name}_usd'
        df_alloc[col] = pool_value_usd * df_alloc['share_of_total_ocean_area']
        pool_value_cols.append(col)
    df_alloc['allocated_value_usd'] = df_alloc[pool_value_cols].sum(axis=1)

    # Sort by allocated value and save
    df_output = df_alloc.sort_values(
        'allocated_value_usd', ascending=False
    ).reset_index(drop=True)

    df_output.to_csv(output_csv_path, index=False)

    return df_output