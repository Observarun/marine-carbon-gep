import os
import marine_carbon_functions


def task_calculate_eez_areas(p):
    """
    Task to load EEZ data and calculate total EEZ area by country.
    """

    p.eez_areas_csv = os.path.join(p.project_dir, "eez_areas_by_country.csv")

    p.df_eez_areas = marine_carbon_functions.calculate_eez_areas(
        p.eez_correspondence_gpkg,
        p.eez_areas_csv
    )

    print("EEZ areas calculated:", p.eez_areas_csv)


def task_calculate_ocean_area(p):
    """
    Task to calculate the global total ocean area (EEZ + high seas)
    from the marine correspondence file (eemarine_r566_correspondence.gpkg).
    """

    p.ocean_area_csv = os.path.join(p.project_dir, "total_ocean_area.csv")

    p.total_ocean_area_km2 = marine_carbon_functions.calculate_ocean_area(
        p.eez_correspondence_gpkg,
        p.ocean_area_csv
    )

    print("Total ocean area (sq km):", p.total_ocean_area_km2)


def task_allocate_marine_carbon_value(p):
    """
    Task to allocate total marine carbon value to countries (proportional to EEZ area)
    and to the high seas (international waters).
    """

    p.marine_carbon_value_csv = os.path.join(p.project_dir, "marine_carbon_value_by_country_2019.csv")

    marine_carbon_functions.allocate_marine_carbon_value(
        df_eez_areas=p.df_eez_areas,
        total_ocean_area_km2=p.total_ocean_area_km2,
        marine_carbon_pools=p.marine_carbon_pools,
        output_csv_path=p.marine_carbon_value_csv
    )

    print("Marine carbon value allocated:", p.marine_carbon_value_csv)