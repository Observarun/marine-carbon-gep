# Marine Carbon Valuation Workflow


# Imports

import os
import hazelbean as hb
import ocean_carbon_tasks


# Build Task Tree

def build_task_tree(p):
    """
    This function sets up the tasks to calculate ocean area, EEZ areas, and allocate ocean carbon value.
    """
    
    # Total ocean area (EEZ + high seas)
    p.task_ocean_area = p.add_task(ocean_carbon_tasks.task_calculate_ocean_area)

    # EEZ areas by country
    p.task_eez_areas = p.add_task(ocean_carbon_tasks.task_calculate_eez_areas)

    # Allocate value
    p.task_allocate_value = p.add_task(ocean_carbon_tasks.task_allocate_marine_carbon_value)


if __name__ == '__main__':
    
    # Create the project flow object
    p = hb.ProjectFlow()
    
    # Set directories
    p.user_dir = os.path.expanduser('~')
    p.extra_dirs = ['Files', 'global_invest', 'projects']
    p.project_name = 'ocean_carbon_' + hb.pretty_time()
    p.project_dir = os.path.join(p.user_dir, os.sep.join(p.extra_dirs), p.project_name)
    p.set_project_dir(p.project_dir)
    
    # Set base data directory
    p.base_data_dir = os.path.join(p.user_dir, 'Files', 'base_data')
    
    # Set model paths for global processing
    p.aoi = 'global'
    p.total_ocean_carbon_pg = 5000.0  # Petagrams of Carbon
    p.rental_price_2019_per_tc_per_year = 13.19  # 2019 USD per tonne C per year
    p.total_ocean_carbon_tonnes = p.total_ocean_carbon_pg * 1e9  # comment this line if already have tonnes C
    p.eez_correspondence_gpkg = p.get_path(
        os.path.join(p.base_data_dir, "cartographic\\ee\\eemarine_r566_correspondence.gpkg")
    )
    
    # Build the task tree and execute it
    build_task_tree(p)
    p.fail_fast = True
    p.verbosity = True
    p.debug = True
    p.execute()