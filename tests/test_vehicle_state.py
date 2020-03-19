from unittest import TestCase

from hive.model.vehicle.vehicle_state.charging_base import ChargingBase
from hive.model.vehicle.vehicle_state.charging_station import ChargingStation
from hive.model.vehicle.vehicle_state.dispatch_base import DispatchBase
from hive.model.vehicle.vehicle_state.dispatch_station import DispatchStation
from hive.model.vehicle.vehicle_state.dispatch_trip import DispatchTrip
from tests.mock_lobster import *


class TestVehicleState(TestCase):

    ####################################################################################################################
    ### ChargingStation ################################################################################################
    ####################################################################################################################

    def test_charging_station_enter(self):
        vehicle = mock_vehicle()
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()

        state = ChargingStation(vehicle.id, station.id, charger)
        error, updated_sim = state.enter(sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        updated_station = updated_sim.stations.get(station.id)
        available_chargers = updated_station.available_chargers.get(charger)
        self.assertIsInstance(updated_vehicle.vehicle_state, ChargingStation, "should be in a charging state")
        self.assertEquals(available_chargers, 0, "should have claimed the only DCFC charger")

    def test_charging_station_exit(self):
        vehicle = mock_vehicle()
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()

        state = ChargingStation(vehicle.id, station.id, charger)
        enter_error, updated_sim = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        # begin test
        error, updated_sim = state.exit(updated_sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        updated_station = updated_sim.stations.get(station.id)
        available_chargers = updated_station.available_chargers.get(charger)
        self.assertIsInstance(updated_vehicle.vehicle_state, ChargingStation, "should still be in a charging state")
        self.assertEquals(available_chargers, 1, "should have returned the only DCFC charger")

    def test_charging_station_update(self):
        vehicle = mock_vehicle()
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()

        state = ChargingStation(vehicle.id, station.id, charger)
        enter_error, sim_with_charging_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_charging_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        self.assertAlmostEqual(
            first=updated_vehicle.energy_source.energy_kwh,
            second=vehicle.energy_source.energy_kwh + 0.83,
            places=2,
            msg="should have charged for 60 seconds")

    def test_charging_station_update_terminal(self):
        vehicle = mock_vehicle(soc=0.99)
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()

        state = ChargingStation(vehicle.id, station.id, charger)
        enter_error, sim_with_charging_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_charging_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        updated_station = sim_updated.stations.get(station.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, Idle, "vehicle should be in idle state")
        self.assertEquals(updated_station.available_chargers.get(charger), 1, "should have returned the charger")

    ####################################################################################################################
    ### ChargingBase ###################################################################################################
    ####################################################################################################################

    def test_charging_base_enter(self):
        vehicle = mock_vehicle()
        station = mock_station()
        base = mock_base(station_id=DefaultIds.mock_station_id())
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,),
            bases=(base,)
        )
        env = mock_env()

        state = ChargingBase(vehicle.id, base.id, charger)
        error, updated_sim = state.enter(sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        updated_station = updated_sim.stations.get(station.id)
        available_chargers = updated_station.available_chargers.get(charger)
        self.assertIsInstance(updated_vehicle.vehicle_state, ChargingBase, "should be in a charging state")
        self.assertEquals(available_chargers, 0, "should have claimed the only DCFC charger")

    def test_charging_base_exit(self):
        vehicle = mock_vehicle()
        station = mock_station()
        base = mock_base(station_id=DefaultIds.mock_station_id())
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,),
            bases=(base,)
        )
        env = mock_env()

        state = ChargingBase(vehicle.id, base.id, charger)
        enter_error, updated_sim = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        # begin test
        error, updated_sim = state.exit(updated_sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        updated_station = updated_sim.stations.get(station.id)
        available_chargers = updated_station.available_chargers.get(charger)
        self.assertIsInstance(updated_vehicle.vehicle_state, ChargingBase, "should still be in a charging state")
        self.assertEquals(available_chargers, 1, "should have returned the only DCFC charger")

    def test_charging_base_update(self):
        vehicle = mock_vehicle()
        station = mock_station()
        base = mock_base(station_id=DefaultIds.mock_station_id())
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,),
            bases=(base,)
        )
        env = mock_env()

        state = ChargingBase(vehicle.id, base.id, charger)
        enter_error, sim_with_charging_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_charging_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        self.assertAlmostEqual(
            first=updated_vehicle.energy_source.energy_kwh,
            second=vehicle.energy_source.energy_kwh + 0.83,
            places=2,
            msg="should have charged for 60 seconds")

    def test_charging_base_update_terminal(self):
        vehicle = mock_vehicle()
        station = mock_station()
        base = mock_base(station_id=DefaultIds.mock_station_id())
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,),
            bases=(base,)
        )
        env = mock_env()

        state = ChargingBase(vehicle.id, base.id, charger)
        enter_error, sim_with_charging_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_charging_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        updated_base = sim_updated.bases.get(base.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, ReserveBase, "vehicle should be in ReserveBase state")
        self.assertEquals(updated_base.available_stalls, 0, "should have taken the only available stall")

    ####################################################################################################################
    ### DispatchBase ###################################################################################################
    ####################################################################################################################

    def test_dispatch_base_enter(self):
        vehicle = mock_vehicle()
        base = mock_base()
        sim = mock_sim(
            vehicles=(vehicle,),
            bases=(base,)
        )
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, base.geoid)

        state = DispatchBase(vehicle.id, base.id, route)
        error, updated_sim = state.enter(sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, DispatchBase, "should be in a dispatch to base state")
        self.assertEquals(len(updated_vehicle.vehicle_state.route), 1, "should have a route")

    def test_dispatch_base_exit(self):
        vehicle = mock_vehicle()
        base = mock_base()
        sim = mock_sim(
            vehicles=(vehicle,),
            bases=(base,)
        )
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, base.geoid)

        state = DispatchBase(vehicle.id, base.id, route)
        enter_error, entered_sim = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        # begin test
        error, exited_sim = state.exit(entered_sim, env)

        self.assertIsNone(error, "should have no errors")
        self.assertEquals(entered_sim, exited_sim, "should see no change due to exit")

    def test_dispatch_base_update(self):
        near = h3.geo_to_h3(39.7539, -104.974, 15)
        omf_brewing = h3.geo_to_h3(39.7608873, -104.9845391, 15)
        vehicle = mock_vehicle_from_geoid(geoid=near)
        base = mock_base_from_geoid(geoid=omf_brewing)
        sim = mock_sim(
            vehicles=(vehicle,),
            bases=(base,)
        )
        env = mock_env()
        route = mock_route_from_geoids(near, omf_brewing)

        state = DispatchBase(vehicle.id, base.id, route)
        enter_error, sim_with_dispatched_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_dispatched_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        self.assertNotEqual(vehicle.geoid, updated_vehicle.geoid, "should have moved")
        self.assertIsInstance(updated_vehicle.vehicle_state, DispatchBase, "should still be in a dispatch to base state")
        self.assertLess(updated_vehicle.energy_source.soc, vehicle.energy_source.soc, "should have less energy")

    def test_dispatch_base_update_terminal(self):
        vehicle = mock_vehicle()
        base = mock_base()
        sim = mock_sim(
            vehicles=(vehicle,),
            bases=(base,)
        )
        env = mock_env()
        route = ()  # empty route should trigger a default transition

        state = DispatchBase(vehicle.id, base.id, route)
        enter_error, sim_with_dispatch_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_dispatch_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        updated_base = sim_updated.bases.get(base.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, ReserveBase, "vehicle should be in ReserveBase state")
        self.assertEquals(updated_base.available_stalls, 0, "should have taken the only available stall")

    ####################################################################################################################
    ### DispatchBase ###################################################################################################
    ####################################################################################################################

    def test_dispatch_station_enter(self):
        vehicle = mock_vehicle()
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, station.geoid)

        state = DispatchStation(vehicle.id, station.id, route, charger)
        error, updated_sim = state.enter(sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, DispatchStation, "should be in a dispatch to station state")
        self.assertEquals(len(updated_vehicle.vehicle_state.route), 1, "should have a route")

    def test_dispatch_station_exit(self):
        vehicle = mock_vehicle()
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, station.geoid)

        state = DispatchStation(vehicle.id, station.id, route, charger)
        enter_error, entered_sim = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        # begin test
        error, exited_sim = state.exit(entered_sim, env)

        self.assertIsNone(error, "should have no errors")
        self.assertEquals(entered_sim, exited_sim, "should see no change due to exit")

    def test_dispatch_station_update(self):
        near = h3.geo_to_h3(39.7539, -104.974, 15)
        omf_brewing = h3.geo_to_h3(39.7608873, -104.9845391, 15)
        vehicle = mock_vehicle_from_geoid(geoid=near)
        station = mock_station_from_geoid(geoid=omf_brewing)
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()
        route = mock_route_from_geoids(near, omf_brewing)

        state = DispatchStation(vehicle.id, station.id, route, charger)
        enter_error, sim_with_dispatched_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_dispatched_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        self.assertNotEqual(vehicle.geoid, updated_vehicle.geoid, "should have moved")
        self.assertIsInstance(updated_vehicle.vehicle_state, DispatchStation, "should still be in a dispatch to station state")
        self.assertLess(updated_vehicle.energy_source.soc, vehicle.energy_source.soc, "should have less energy")

    def test_dispatch_station_update_terminal(self):
        initial_soc = 0.1
        vehicle = mock_vehicle(soc=initial_soc)
        station = mock_station()
        charger = Charger.DCFC
        sim = mock_sim(
            vehicles=(vehicle,),
            stations=(station,)
        )
        env = mock_env()
        route = ()  # empty route should trigger a default transition

        state = DispatchStation(vehicle.id, station.id, route, charger)
        enter_error, sim_with_dispatch_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_dispatch_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        updated_station = sim_updated.stations.get(station.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, ChargingStation, "vehicle should be in ChargingStation state")
        self.assertEquals(updated_station.available_chargers.get(charger), 0, "should have taken the only available charger")
        self.assertGreater(updated_vehicle.energy_source.soc, initial_soc, "should have charged for one time step")

    ####################################################################################################################
    ### DispatchTrip ###################################################################################################
    ####################################################################################################################

    def test_dispatch_trip_enter(self):
        vehicle = mock_vehicle()
        request = mock_request()
        sim = mock_sim(vehicles=(vehicle,)).add_request(request)
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, request.geoid)

        state = DispatchTrip(vehicle.id, request.id, route)
        error, updated_sim = state.enter(sim, env)

        self.assertIsNone(error, "should have no errors")

        updated_vehicle = updated_sim.vehicles.get(vehicle.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, DispatchTrip, "should be in a dispatch to request state")
        self.assertEquals(len(updated_vehicle.vehicle_state.route), 1, "should have a route")

    def test_dispatch_trip_exit(self):
        vehicle = mock_vehicle()
        request = mock_request()
        sim = mock_sim(vehicles=(vehicle,)).add_request(request)
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, request.geoid)

        state = DispatchTrip(vehicle.id, request.id, route)
        enter_error, entered_sim = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        # begin test
        error, exited_sim = state.exit(entered_sim, env)

        self.assertIsNone(error, "should have no errors")
        self.assertEquals(entered_sim, exited_sim, "should see no change due to exit")

    def test_dispatch_trip_update(self):
        near = h3.geo_to_h3(39.7539, -104.974, 15)
        omf_brewing = h3.geo_to_h3(39.7608873, -104.9845391, 15)
        vehicle = mock_vehicle()
        request = mock_request()
        sim = mock_sim(vehicles=(vehicle,)).add_request(request)
        env = mock_env()
        route = mock_route_from_geoids(near, omf_brewing)

        state = DispatchTrip(vehicle.id, request.id, route)
        enter_error, sim_with_dispatched_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_dispatched_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        self.assertNotEqual(vehicle.geoid, updated_vehicle.geoid, "should have moved")
        self.assertIsInstance(updated_vehicle.vehicle_state, DispatchTrip, "should still be in a dispatch to request state")
        self.assertLess(updated_vehicle.energy_source.soc, vehicle.energy_source.soc, "should have less energy")

    def test_dispatch_trip_update_terminal(self):
        initial_soc = 0.1
        vehicle = mock_vehicle()
        request = mock_request()
        sim = mock_sim(vehicles=(vehicle,)).add_request(request)
        env = mock_env()
        route = mock_route_from_geoids(vehicle.geoid, request.geoid)  # vehicle is at the request

        state = DispatchTrip(vehicle.id, request.id, route)
        enter_error, sim_with_dispatch_vehicle = state.enter(sim, env)
        self.assertIsNone(enter_error, "test precondition (enter works correctly) not met")

        update_error, sim_updated = state.update(sim_with_dispatch_vehicle, env)
        self.assertIsNone(update_error, "should have no error from update call")

        updated_vehicle = sim_updated.vehicles.get(vehicle.id)
        updated_request = sim_updated.requests.get(request.id)
        self.assertIsInstance(updated_vehicle.vehicle_state, ServicingTrip, "vehicle should be in ServicingTrip state")
        self.assertEquals(updated_vehicle.passengers)
        self.assertIsNone(updated_request, "request should no longer exist as it has been picked up")
        self.assertGreater(updated_vehicle.energy_source.soc, initial_soc, "should have charged for one time step")
