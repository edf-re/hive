from unittest import TestCase

from hive.dispatcher.greedy_dispatcher import GreedyDispatcher
from hive.state.update import CancelRequests, StepSimulation
from tests.mock_lobster import *


class TestLocalSimulationRunner(TestCase):

    def test_run(self):
        runner = mock_runner(mock_config(end_time=20, timestep_duration_seconds=1))
        req = mock_request(
            request_id='1',
            o_lat=-37.001,
            o_lon=122,
            d_lat=-37.1,
            d_lon=122,
            departure_time=0,
            cancel_time=3600,
            passengers=2
        )
        initial_sim = mock_sim(
            vehicles=(mock_vehicle(lat=-37, lon=122, capacity_kwh=100, ideal_energy_limit_kwh=None),),
            stations=(mock_station(lat=-36.999, lon=122),),
            bases=(mock_base(stall_count=5, lat=-37, lon=121.999),),
        ).add_request(req)

        result = runner.run(
            initial_simulation_state=initial_sim,
            update_functions=(CancelRequests(), StepSimulation(GreedyDispatcher())),
            reporter=mock_reporter()
        )

        at_destination = result.s.at_geoid(req.destination)
        self.assertIn(DefaultIds.mock_vehicle_id(), at_destination['vehicles'],
                      "vehicle should have driven request to destination")

        self.assertAlmostEqual(11.1, result.s.vehicles[DefaultIds.mock_vehicle_id()].distance_traveled_km, places=1)

