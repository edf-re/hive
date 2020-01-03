from csv import DictReader
from unittest import TestCase, skip

from typing import Optional

from h3 import h3

from hive.model.energy.charger import Charger
from hive.model.energy.energysource import EnergySource
from hive.model.energy.powertrain import Powertrain
from hive.model.energy.powercurve import Powercurve
from hive.model.request import Request
from hive.model.roadnetwork.property_link import PropertyLink
from hive.model.roadnetwork.roadnetwork import RoadNetwork
from hive.model.roadnetwork.haversine_roadnetwork import HaversineRoadNetwork
from hive.model.vehicle import Vehicle
from hive.model.vehiclestate import VehicleState
from hive.model.roadnetwork.routetraversal import Route
from hive.model.roadnetwork.link import Link
from hive.util.typealiases import *
from hive.util.units import unit, kwh, s
from hive.model.energy.energytype import EnergyType


class TestVehicle(TestCase):
    def test_has_passengers(self):
        self.assertEqual(TestVehicle.mock_vehicle().has_passengers(), False, "should have no passengers")
        updated_vehicle = TestVehicle.mock_vehicle().add_passengers(TestVehicle.mock_request().passengers)
        self.assertEqual(updated_vehicle.has_passengers(), True, "should have passengers")

    def test_has_route(self):
        self.assertEqual(TestVehicle.mock_vehicle().has_route(), False, "should have no route")
        updated_vehicle = TestVehicle.mock_vehicle()._replace(route=TestVehicle.mock_route())
        self.assertEqual(updated_vehicle.has_route(), True, "should have a route")

    def test_add_passengers(self):
        no_pass_veh = TestVehicle.mock_vehicle()
        mock_request = TestVehicle.mock_request()

        self.assertEqual(no_pass_veh.has_passengers(), False)
        with_pass_veh = no_pass_veh.add_passengers(mock_request.passengers)
        self.assertEqual(len(with_pass_veh.passengers), len(mock_request.passengers))

    @skip("test not yet implemented")
    def test_battery_swap(self):
        self.fail()

    def test_transition_idle(self):
        non_idling_vehicle = TestVehicle.mock_vehicle()._replace(route=TestVehicle.mock_route(),
                                                                 vehicle_state=VehicleState.REPOSITIONING)
        transitioned = non_idling_vehicle.transition(VehicleState.IDLE)
        self.assertEqual(transitioned.vehicle_state, VehicleState.IDLE, "should have transitioned into an idle state")

    def test_transition_repositioning(self):
        idle_vehicle = TestVehicle.mock_vehicle()
        self.assertNotEqual(idle_vehicle.vehicle_state, VehicleState.REPOSITIONING,
                            "test vehicle should not begin in repositioning state")

        transitioned = idle_vehicle.transition(VehicleState.REPOSITIONING)
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_dispatch_trip(self):
        """
        given a Vehicle in an IDLE state,
        - assign it to a DISPATCH_TRIP state via Vehicle.transition_dispatch_trip
          - confirm the vehicle state is correctly updated
        """
        idle_vehicle = TestVehicle.mock_vehicle()

        # check on transition function result
        transitioned = idle_vehicle.transition(VehicleState.DISPATCH_TRIP)
        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_servicing_trip(self):
        idle_vehicle = TestVehicle.mock_vehicle()

        transitioned = idle_vehicle.transition(VehicleState.SERVICING_TRIP)

        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_dispatch_station(self):
        idle_vehicle = TestVehicle.mock_vehicle()

        transitioned = idle_vehicle.transition(VehicleState.DISPATCH_TRIP)
        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_charging_station(self):
        idle_vehicle = TestVehicle.mock_vehicle()

        transitioned = idle_vehicle.transition(VehicleState.CHARGING_STATION)
        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_dispatch_base(self):
        idle_vehicle = TestVehicle.mock_vehicle()

        transitioned = idle_vehicle.transition(VehicleState.DISPATCH_BASE)
        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_charging_base(self):
        idle_vehicle = TestVehicle.mock_vehicle()

        transitioned = idle_vehicle.transition(VehicleState.CHARGING_BASE)
        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_transition_reserve_base(self):
        idle_vehicle = TestVehicle.mock_vehicle()

        transitioned = idle_vehicle.transition(VehicleState.RESERVE_BASE)
        self.assertIsInstance(transitioned, Vehicle, "result should be a Vehicle, not an Exception")
        self.assertEqual(transitioned.geoid, idle_vehicle.geoid,
                         "vehicle position should not be changed")

    def test_can_transition_good(self):
        idle_veh = TestVehicle.mock_vehicle()
        veh_serving_trip = idle_veh.transition(VehicleState.IDLE)

        veh_can_trans = veh_serving_trip.can_transition(VehicleState.DISPATCH_TRIP)

        self.assertEqual(veh_can_trans, True)

    def test_can_transition_bad(self):
        mock_request = TestVehicle.mock_request()
        idle_veh = TestVehicle.mock_vehicle()
        veh_serving_trip = idle_veh.transition(VehicleState.SERVICING_TRIP)
        veh_w_pass = veh_serving_trip.add_passengers(mock_request.passengers)

        veh_can_trans = veh_w_pass.can_transition(VehicleState.IDLE)

        self.assertEqual(veh_can_trans, False)

    def test_move(self):
        # approx 8.5 km distance.
        somewhere = h3.geo_to_h3(39.75, -105.1, 15)
        somewhere_else = h3.geo_to_h3(39.75, -105, 15)

        vehicle = TestVehicle.mock_vehicle(geoid=somewhere).transition(VehicleState.REPOSITIONING)
        power_train = TestVehicle.mock_powertrain()
        road_network = TestVehicle.mock_network()

        start = road_network.property_link_from_geoid(somewhere)
        end = road_network.property_link_from_geoid(somewhere_else)

        route = road_network.route(start, end)

        vehicle_w_route = vehicle.assign_route(route)

        moved_vehicle = vehicle_w_route.move(road_network=road_network,
                                             power_train=power_train,
                                             time_step=400 * unit.seconds)
        m2 = moved_vehicle.move(road_network=road_network,
                                power_train=power_train,
                                time_step=400 * unit.seconds)
        # vehicle should have arrived after second move.
        m3 = m2.move(road_network=road_network,
                     power_train=power_train,
                     time_step=10 * unit.seconds)

        self.assertLess(moved_vehicle.energy_source.soc, 1)
        self.assertNotEqual(somewhere, moved_vehicle.geoid)
        self.assertNotEqual(somewhere, moved_vehicle.property_link.link.start)

        self.assertNotEqual(moved_vehicle.geoid, m2.geoid)
        self.assertNotEqual(moved_vehicle.property_link.link.start, m2.property_link.link.start)

        self.assertEqual(m3.vehicle_state, VehicleState.IDLE, 'Vehicle should have finished route')
        self.assertGreater(m3.distance_traveled, 8.5 * unit.kilometer, 'Vehicle should have traveled around 8km')

    def test_charge(self):
        vehicle = TestVehicle.mock_vehicle().transition(VehicleState.CHARGING_STATION).plug_in_to('s1', Charger.DCFC)
        power_curve = TestVehicle.mock_powercurve()
        time_step_size_secs = 1.0 * unit.seconds

        result = vehicle.charge(power_curve, time_step_size_secs)
        self.assertEqual(result.energy_source.energy,
                         vehicle.energy_source.energy + 0.1 * unit.kilowatthour,
                         "should have charged")

    def test_charge_when_full(self):
        vehicle = TestVehicle.mock_vehicle().transition(VehicleState.CHARGING_STATION).plug_in_to('s1', Charger.DCFC)
        vehicle_full = vehicle.battery_swap(TestVehicle.mock_energysource(cap=100 * unit.kilowatthour,
                                                                          soc=1.0))  # full
        power_curve = TestVehicle.mock_powercurve()
        time_step_size_secs = 1.0 * unit.seconds

        result = vehicle_full.charge(power_curve, time_step_size_secs)
        self.assertEqual(result.energy_source.energy, vehicle_full.energy_source.energy, "should have not charged")

    def test_idle(self):
        idle_vehicle = TestVehicle.mock_vehicle()
        idle_vehicle_less_energy = idle_vehicle.idle(60 * unit.seconds)  # idle for 60 seconds

        self.assertLess(idle_vehicle_less_energy.energy_source.soc, idle_vehicle.energy_source.soc,
                        "Idle vehicles should have consumed energy.")
        self.assertEqual(idle_vehicle_less_energy.idle_time_s, 60 * unit.seconds, "Should have recorded idle time.")

    def test_idle_reset(self):
        idle_vehicle = TestVehicle.mock_vehicle().idle(60 * unit.seconds)

        dispatch_vehicle = idle_vehicle.transition(VehicleState.DISPATCH_TRIP)

        self.assertEqual(dispatch_vehicle.idle_time_s, 0 * unit.seconds, "Should have reset idle time.")

    def test_from_row(self):
        source = """vehicle_id,lat,lon,powertrain_id,powercurve_id,capacity,ideal_energy_limit,max_charge_acceptance,initial_soc
                    v1,37,122,leaf,leaf,50.0,40,50,1.0"""

        row = next(DictReader(source.split()))
        road_network = HaversineRoadNetwork()
        expected_geoid = h3.geo_to_h3(37, 122, road_network.sim_h3_resolution)

        vehicle = Vehicle.from_row(row, road_network)

        self.assertEqual(vehicle.id, "v1")
        self.assertEqual(vehicle.geoid, expected_geoid)
        self.assertEqual(vehicle.powercurve_id, 'leaf')
        self.assertEqual(vehicle.powertrain_id, 'leaf')
        self.assertEqual(vehicle.energy_source.powercurve_id, 'leaf')
        self.assertEqual(vehicle.energy_source.ideal_energy_limit, 40.0 * unit.kilowatthours)
        self.assertEqual(vehicle.energy_source.energy, 50.0 * unit.kilowatthours)
        self.assertEqual(vehicle.energy_source.capacity, 50.0 * unit.kilowatthours)
        self.assertEqual(vehicle.energy_source.energy_type, EnergyType.ELECTRIC)
        self.assertEqual(vehicle.energy_source.max_charge_acceptance_kw, 50.0 * unit.kilowatt)
        self.assertEqual(len(vehicle.passengers), 0)
        self.assertEqual(vehicle.property_link.start, expected_geoid)
        self.assertEqual(vehicle.vehicle_state, VehicleState.IDLE)
        self.assertEqual(vehicle.distance_traveled, 0)
        self.assertEqual(vehicle.idle_time_s, 0)
        self.assertEqual(vehicle.route, ())
        self.assertEqual(vehicle.station, None)
        self.assertEqual(vehicle.station_intent, None)
        self.assertEqual(vehicle.plugged_in_charger, None)
        self.assertEqual(vehicle.charger_intent, None)

    def test_from_row_bad_powertrain_id(self):
        source = """vehicle_id,lat,lon,powertrain_id,powercurve_id,capacity,ideal_energy_limit,max_charge_acceptance,initial_soc
                    v1,37,122,beef!@#$,leaf,50.0,40,50,1.0"""

        row = next(DictReader(source.split()))
        road_network = HaversineRoadNetwork()

        with self.assertRaises(IOError):
            Vehicle.from_row(row, road_network)

    def test_from_row_bad_powercurve_id(self):
        source = """vehicle_id,lat,lon,powertrain_id,powercurve_id,capacity,ideal_energy_limit,max_charge_acceptance,initial_soc
                    v1,37,122,leaf,asdjfkl;asdfjkl;,50.0,40,50,1.0"""

        row = next(DictReader(source.split()))
        road_network = HaversineRoadNetwork()

        with self.assertRaises(IOError):
            Vehicle.from_row(row, road_network)

    @classmethod
    def mock_powertrain(cls) -> Powertrain:
        return VehicleTestAssests.MockPowertrain()

    @classmethod
    def mock_powercurve(cls) -> Powercurve:
        return VehicleTestAssests.MockPowercurve()

    @classmethod
    def mock_network(cls) -> HaversineRoadNetwork:
        return HaversineRoadNetwork()

    @classmethod
    def mock_energysource(cls,
                          cap=100 * unit.kilowatthour,
                          soc=0.25,
                          ideal_energy_limit=50.0 * unit.kilowatthour) -> EnergySource:
        """
        invariant: test_charge depends on having some amount of battery to fill
        """
        return EnergySource.build(
            powercurve_id=TestVehicle.mock_powercurve().get_id(),
            energy_type=EnergyType.ELECTRIC,
            capacity=cap,
            ideal_energy_limit=ideal_energy_limit,
            soc=soc)

    @classmethod
    def mock_vehicle(cls, geoid=h3.geo_to_h3(39.75, -105.1, 15)) -> Vehicle:
        mock_powertrain = TestVehicle.mock_powertrain()
        mock_powercurve = TestVehicle.mock_powercurve()
        mock_energy_source = TestVehicle.mock_energysource()
        mock_network = TestVehicle.mock_network()
        mock_property_link = mock_network.property_link_from_geoid(geoid)
        mock_veh = Vehicle(id="v1",
                           powertrain_id=mock_powertrain.get_id(),
                           powercurve_id=mock_powercurve.get_id(),
                           energy_source=mock_energy_source,
                           property_link=mock_property_link
                           )
        return mock_veh

    @classmethod
    def mock_request(cls) -> Request:
        return Request.build("test_request",
                             origin=h3.geo_to_h3(0, 0, 11),
                             destination=h3.geo_to_h3(10, 10, 11),
                             departure_time=0,
                             cancel_time=10,
                             passengers=2)

    @classmethod
    def mock_route(cls) -> Route:
        property_links = VehicleTestAssests.property_links

        return property_links["1"], property_links["2"], property_links["3"], property_links["4"]


class VehicleTestAssests:
    class MockPowertrain(Powertrain):
        def get_id(self) -> PowertrainId:
            return "mock_powertrain"

        def get_energy_type(self) -> EnergyType:
            return EnergyType.ELECTRIC

        def energy_cost(self, route: Route) -> kwh:
            return 0.01 * unit.kilowatthour

    class MockPowercurve(Powercurve):

        def get_id(self) -> PowercurveId:
            return "mock_powercurve"

        def get_energy_type(self) -> EnergyType:
            return EnergyType.ELECTRIC

        def refuel(self, energy_source: 'EnergySource', charger: 'Charger', duration_seconds: s = 1 * unit.seconds,
                   step_size_seconds: s = 1 * unit.seconds) -> 'EnergySource':
            return energy_source.load_energy(0.1 * unit.kilowatthours)

    sim_h3_resolution = 15

    links = {
        "1": Link("1",
                  h3.geo_to_h3(0, 0, sim_h3_resolution),
                  h3.geo_to_h3(0, 5, sim_h3_resolution)),
        "2": Link("2",
                  h3.geo_to_h3(0, 5, sim_h3_resolution),
                  h3.geo_to_h3(5, 5, sim_h3_resolution)),
        "3": Link("3",
                  h3.geo_to_h3(5, 5, sim_h3_resolution),
                  h3.geo_to_h3(5, 10, sim_h3_resolution)),
        "4": Link("4",
                  h3.geo_to_h3(5, 10, sim_h3_resolution),
                  h3.geo_to_h3(10, 10, sim_h3_resolution)),
    }

    kmph = (unit.kilometers / unit.hour)
    property_links = {
        "1": PropertyLink.build(links["1"], 40 * kmph),
        "2": PropertyLink.build(links["2"], 40 * kmph),
        "3": PropertyLink.build(links["3"], 40 * kmph),
        "4": PropertyLink.build(links["4"], 40 * kmph)
    }
