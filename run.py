"""
Run hive w/ inputs defined in config.py
"""
import subprocess
import os
import sys
import random
import shutil
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pickle
import glob
import time
import yaml

import config as cfg

from hive import preprocess as pp
from hive import tripenergy as nrg
from hive import charging as chrg
from hive import utils
from hive import reporting
from hive.initialize import initialize_stations, initialize_fleet
from hive.vehicle import Vehicle
from hive.dispatcher import Dispatcher
from hive.constraints import ENV_PARAMS


seed = 123
random.seed(seed)
np.random.seed(seed)
THIS_DIR = os.path.dirname(os.path.realpath(__file__))
LIB_PATH = os.path.join(THIS_DIR, cfg.IN_PATH, 'library')
SCENARIO_PATH = os.path.join(THIS_DIR, cfg.IN_PATH, 'scenarios')
STATIC_PATH = os.path.join(LIB_PATH, '.static')

OUT_PATH = os.path.join(THIS_DIR, cfg.OUT_PATH)

FLEET_STATE_IDX ={
    'x': 0,
    'y': 1,
    'active': 2,
    'available': 3,
    'soc': 4,
    'idle_min': 5,
    'KWH__MI': 6,
    'BATTERY_CAPACITY_KWH': 7,
    'avail_seats': 8,
}

def load_scenarios():

    scenarios = {}

    def name(path):
        return os.path.splitext(os.path.basename(path))[0]

    charge_file = os.path.join(STATIC_PATH, 'raw_leaf_curves.csv')
    whmi_lookup_file = os.path.join(STATIC_PATH, 'wh_mi_lookup.csv')
    charge_df = pd.read_csv(charge_file)
    whmi_df = pd.read_csv(whmi_lookup_file)

    all_scenarios = glob.glob(os.path.join(SCENARIO_PATH, '*.yaml'))
    scenario_files = [file for file in all_scenarios if name(file) in cfg.SCENARIOS]

    for scenario_file in scenario_files:
        scenario_name = name(scenario_file)
        with open(scenario_file, 'r') as f:
            yaml_data = yaml.safe_load(f)

            data = {}

            filepaths = yaml_data['filepaths']
            data['requests'] = pp.load_requests(filepaths['requests_file_path'])
            data['main'] = yaml_data['parameters']
            #TODO: Rewrite so as to not need dataframe for stations and bases
            network_dtype = {
                            'longitude': "float64",
                            'latitude': "float64",
                            'plugs': "int64",
                            'plug_power_kw': "float64",
                            }
            data['stations'] = pd.DataFrame(yaml_data['stations']).astype(dtype=network_dtype)
            data['bases'] = pd.DataFrame(yaml_data['bases']).astype(dtype=network_dtype)

            vehicle_dtype = {
                            'BATTERY_CAPACITY_KWH': 'float64',
                            'PASSENGERS': 'int64',
                            'EFFICIENCY_WHMI': 'float64',
                            'MAX_KW_ACCEPTANCE': 'float64',
                            'NUM_VEHICLES': 'int64',
                            }
            data['vehicles'] = pd.DataFrame(yaml_data['vehicles']).astype(dtype=vehicle_dtype)

            data['charge_curves'] = charge_df
            data['whmi_lookup'] = whmi_df

            scenarios[scenario_name] = data

    return scenarios


def run_simulation(data, sim_name, infile=None):
    if infile is not None:
        with open(infile, 'rb') as f:
            data = pickle.load(f)

    if cfg.VERBOSE: print("", "#"*30, "Preparing {}".format(sim_name), "#"*30, "", sep="\n")

    if cfg.VERBOSE: print("Reading input files..", "", sep="\n")
    inputs = data['main']

    if cfg.VERBOSE: print("Building scenario output directory..", "", sep="\n")
    output_file_paths = utils.build_output_dir(sim_name, OUT_PATH)

    vehicle_summary_file = os.path.join(output_file_paths['summary_path'], 'vehicle_summary.csv')
    fleet_summary_file = os.path.join(output_file_paths['summary_path'], 'fleet_summary.txt')
    station_summary_file = os.path.join(output_file_paths['summary_path'], 'station_summary.csv')

    #Load requests
    if cfg.VERBOSE: print("Processing requests..")
    reqs_df = data['requests']
    if cfg.VERBOSE: print("{} requests loaded".format(len(reqs_df)))

    #Filter requests where distance < min_miles
    reqs_df = pp.filter_short_distance_trips(reqs_df, min_miles=0.05)
    if cfg.VERBOSE: print("filtered requests violating min distance req, {} remain".format(len(reqs_df)))
    #
    #Filter requests where total time < min_time_s
    reqs_df = pp.filter_short_time_trips(reqs_df, min_time_s=1)
    if cfg.VERBOSE: print("filtered requests violating min time req, {} remain".format(len(reqs_df)))
    #

    sim_clock = utils.Clock(timestep_s = cfg.SIMULATION_PERIOD_SECONDS)

    #Calculate network scaling factor & average dispatch speed
    RN_SCALING_FACTOR = pp.calculate_road_vmt_scaling_factor(reqs_df)
    DISPATCH_MPH = pp.calculate_average_driving_speed(reqs_df)

    #TODO: Pool requests - from hive.pool, module for various pooling types - o/d, dynamic, n/a
    #TODO: reqs_df.to_csv(cfg.OUT_PATH + sim_name + 'requests/' + requests_filename, index=False)

    #Load charging network
    if cfg.VERBOSE: print("Loading charge network..")
    stations = initialize_stations(data['stations'], sim_clock)
    bases = initialize_stations(data['bases'], sim_clock)
    if cfg.VERBOSE: print("loaded {0} stations & {1} bases".format(len(stations), len(bases)), "", sep="\n")


    #Initialize vehicle fleet
    if cfg.VERBOSE: print("Initializing vehicle fleet..", "", sep="\n")
    env_params = {
        'MAX_DISPATCH_MILES': float(inputs['MAX_DISPATCH_MILES']),
        'MIN_ALLOWED_SOC': float(inputs['MIN_ALLOWED_SOC']),
        'RN_SCALING_FACTOR': RN_SCALING_FACTOR,
        'DISPATCH_MPH': DISPATCH_MPH,
        'LOWER_SOC_THRESH_STATION': float(inputs['LOWER_SOC_THRESH_STATION']),
        'UPPER_SOC_THRESH_STATION': float(inputs['UPPER_SOC_THRESH_STATION']),
        'MAX_ALLOWABLE_IDLE_MINUTES': float(inputs['MAX_ALLOWABLE_IDLE_MINUTES']),
    }

    for param, val in env_params.items():
        utils.assert_constraint(param, val, ENV_PARAMS, context="Environment Parameters")

    env_params['FLEET_STATE_IDX'] = FLEET_STATE_IDX

    vehicle_types = [veh for veh in data['vehicles'].itertuples()]
    fleet, fleet_state = initialize_fleet(vehicle_types = vehicle_types,
                             bases = bases,
                             charge_curve = data['charge_curves'],
                             whmi_lookup = data['whmi_lookup'],
                             start_time = reqs_df.pickup_time.iloc[0],
                             env_params = env_params,
                             clock = sim_clock)
    if cfg.VERBOSE: print("{} vehicles initialized".format(len(fleet)), "", sep="\n")

    if cfg.VERBOSE: print("#"*30, "Simulating {}".format(sim_name), "#"*30, "", sep="\n")

    dispatcher = Dispatcher(fleet = fleet,
                            fleet_state = fleet_state,
                            stations = stations,
                            bases = bases,
                            env_params = env_params,
                            clock = sim_clock)

    sim_start_time = reqs_df.pickup_time.min()
    sim_end_time = reqs_df.dropoff_time.max()
    sim_time_steps = pd.date_range(sim_start_time, sim_end_time, freq='{}S'.format(cfg.SIMULATION_PERIOD_SECONDS))

    total_iterations = len(sim_time_steps)
    i = 0


    for timestep in sim_time_steps:
        i+=1
        if i%100 == 0:
            print("{} of {} iterations completed.".format(i, total_iterations))
        requests = reqs_df[(timestep <= reqs_df.pickup_time) \
            & (reqs_df.pickup_time < (timestep + timedelta(seconds=cfg.SIMULATION_PERIOD_SECONDS)))]
        dispatcher.process_requests(requests)

        for veh in fleet:
            veh.step()

        for station in stations:
            station.step()

        for base in bases:
            base.step()

        next(sim_clock)

    if cfg.VERBOSE: print("Generating logs and summary statistics..")

    reporting.generate_logs(fleet, output_file_paths['vehicle_path'], 'vehicle')
    reporting.generate_logs(stations, output_file_paths['station_path'], 'station')
    reporting.generate_logs(bases, output_file_paths['base_path'], 'base')
    reporting.generate_logs([dispatcher], output_file_paths['dispatcher_path'], 'dispatcher')

    reporting.summarize_fleet_stats(output_file_paths['vehicle_path'], output_file_paths['summary_path'])

if __name__ == "__main__":
    #TODO: Fix cached functionality. Current functionality does not cache runs.
    # def clean_scenarios_folder():
    #     files = glob.glob(os.path.join(SCENARIO_PATH, '*'))
    #     print(files)
    #     for f in files:
    #         os.remove(f)
    #
    # if not os.path.isdir(SCENARIO_PATH):
    #     print('creating scenarios folder for input files..')
    #     os.makedirs(SCENARIO_PATH)
    #
    # if not os.listdir(SCENARIO_PATH):
    #     subprocess.run('doit build_input_files', shell=True)
    #
    # if '--cached' in sys.argv:
    #     subprocess.run('doit run_simulation', shell=True)
    # else:
    #     clean_scenarios_folder()
    #     subprocess.run('doit forget', shell=True)
    #     subprocess.run('doit build_input_files', shell=True)
    #     subprocess.run('doit run_simulation', shell=True)
    if not os.path.isdir(OUT_PATH):
        print('Building base output directory..')
        os.makedirs(cfg.OUT_PATH)

    assert len(cfg.SCENARIOS) == len(set(cfg.SCENARIOS)), 'Scenario names must be unique.'

    scenarios = load_scenarios()

    for scenario_name, data in scenarios.items():
        run_simulation(data, scenario_name)
