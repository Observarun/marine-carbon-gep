import os
import ocean_carbon_functions


def task_calculate_eez_areas(p):
    """
    Task to load EEZ data and calculate total area by country.
    """
    
    p.eez_areas_csv = os.path.join(p.project_dir, "eez_areas_by_country.csv")
    
    p.df_eez_areas = ocean_carbon_functions.calculate_eez_areas(
        p.eez_correspondence_gpkg,
        p.eez_areas_csv
    )
    
    print("EEZ areas calculated:", p.eez_areas_csv)


def task_calculate_ocean_area(p):
    """
    Task to calculate the total ocean area (EEZ + high seas) for each country
    from marine correspondence file (eemarine_r566_correspondence.gpkg).
    """

    p.ocean_area = os.path.join(p.project_dir, "total_ocean_area.csv")

    p.ocean_area = ocean_carbon_functions.calculate_ocean_area(
        p.eez_correspondence_gpkg,
        p.ocean_area
    )
    
    print("Total ocean area (sq km):", p.ocean_area)


def task_allocate_marine_carbon_value(p):
    """
    Task to allocate total marine carbon value to countries proportional to EEZ area.
    """

    #Output path
    p.marine_carbon_value_csv = os.path.join(p.project_dir, "marine_carbon_value_by_country_2019.csv")

    #Allocate marine carbon value
    ocean_carbon_functions.allocate_marine_carbon_value(
        df_eez_areas=p.df_eez_areas,
        total_ocean_area_km2=p.ocean_area,
        total_ocean_carbon_tonnes=p.total_ocean_carbon_tonnes,
        rental_price_2019_per_tc_per_year=p.rental_price_2019_per_tc_per_year,
        output_csv_path=p.marine_carbon_value_csv
    )
    
    #print("Marine carbon value allocated:", p.marine_carbon_value_csv)