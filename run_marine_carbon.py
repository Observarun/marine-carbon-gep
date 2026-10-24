# Marine Carbon Valuation Workflow


# Imports

import os
import hazelbean as hb
import marine_carbon_tasks


# Build Task Tree

def build_task_tree(p):
    """
    This function sets up the tasks to calculate ocean area, EEZ areas, and allocate marine carbon value.
    """

    # Total ocean area (EEZ + high seas)
    p.task_ocean_area = p.add_task(marine_carbon_tasks.task_calculate_ocean_area)

    # EEZ areas by country
    p.task_eez_areas = p.add_task(marine_carbon_tasks.task_calculate_eez_areas)

    # Allocate value (countries + high seas)
    p.task_allocate_value = p.add_task(marine_carbon_tasks.task_allocate_marine_carbon_value)


if __name__ == '__main__':

    # Create the project flow object
    p = hb.ProjectFlow()

    # Set directories
    p.user_dir = os.path.expanduser('~')
    p.extra_dirs = ['Files', 'global_invest', 'projects']
    p.project_name = 'marine_carbon_' + hb.pretty_time()
    p.project_dir = os.path.join(p.user_dir, os.sep.join(p.extra_dirs), p.project_name)
    p.set_project_dir(p.project_dir)

    # Set base data directory
    p.base_data_dir = os.path.join(p.user_dir, 'Files', 'base_data')

    # Set model paths for global processing
    p.aoi = 'global'

    # Marine carbon pools: stock (Pg C) and rental price (2019 USD per tonne C per year).
    # SC-CO2 rental price for organic and inorganic carbon, SC-CH4 rental price for methane hydrates.
    sc_co2_rental_price = 13.19
    sc_ch4_rental_price = 49.25
    p.marine_carbon_pools = {
        'DIC': {'stock_pg_c': 38000.0, 'rental_price_2019_per_tc_per_year': sc_co2_rental_price},
        'DOC_and_biota': {'stock_pg_c': 703.0, 'rental_price_2019_per_tc_per_year': sc_co2_rental_price},  # 700 DOC + 3 biota
        'sediment_carbon': {'stock_pg_c': 2303.0, 'rental_price_2019_per_tc_per_year': sc_co2_rental_price},  # top 1 m
        'methane_hydrates': {'stock_pg_c': 1780.0, 'rental_price_2019_per_tc_per_year': sc_ch4_rental_price},  # marine + subsea permafrost
    }
    p.eez_correspondence_gpkg = p.get_path(
        os.path.join(p.base_data_dir, 'cartographic', 'ee', 'eemarine_r566_correspondence.gpkg')
    )

    # Build the task tree and execute it
    build_task_tree(p)
    p.fail_fast = True
    p.verbosity = True
    p.debug = True
    p.execute()