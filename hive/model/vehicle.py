from __future__ import annotations

import copy
from typing import NamedTuple, Tuple, Dict, Optional


from hive.util.typealiases import *
from hive.model.battery import Battery
from hive.model.charger import Charger
from hive.model.engine import Engine
from hive.model.passenger import Passenger

from hive.roadnetwork.position import Position
from hive.model.charger import Charger
from hive.model.vehiclestate import VehicleState, VehicleStateCategory
from hive.roadnetwork.position import Position
from hive.roadnetwork.route import Route
from hive.util.exception import *
from hive.util.typealiases import *


class Vehicle(NamedTuple):
    # fixed vehicle attributes
    id: VehicleId
    engine: EngineId
    battery: Battery
    position: Position
    geoid: GeoId
    soc_upper_limit: Percentage = 1.0
    soc_lower_limit: Percentage = 0.0
    route: Route = Route.empty()
    vehicle_state: VehicleState = VehicleState.IDLE
    # frozenmap implementation does not yet exist
    # https://www.python.org/dev/peps/pep-0603/
    passengers: Dict[PassengerId, Passenger] = {}
    # todo: p_locations: Dict[GeoId, PassengerId] = {}
    distance_traveled: float = 0.0

    def has_passengers(self) -> bool:
        return len(self.passengers) > 0

    def has_route(self) -> bool:
        return bool(self.route.has_route())

    def plugged_in(self) -> bool:
        return self.plugged_in_charger is not None

    def add_passengers(self, new_passengers: Tuple[Passenger, ...]) -> Vehicle:
        """
        loads some passengers onto this vehicle
        :param self:
        :param new_passengers: the set of passengers we want to add
        :return: the updated vehicle
        """
        updated_passengers = copy.copy(self.passengers)
        for passenger in new_passengers:
            passenger_with_vehicle_id = passenger.add_vehicle_id(self.id)
            updated_passengers[passenger.id] = passenger_with_vehicle_id
        return self._replace(passengers=updated_passengers)

    def __repr__(self) -> str:
        return f"Vehicle({self.id},{self.vehicle_state},{self.battery})"

    def _move(self) -> Vehicle:
        # take one route step
        # todo: need to update the GeoId here; i think this means the RoadNetwork
        #  needs to be in scope (a parameter of step/_move)
        this_route_step, updated_route = self.route.step_route()
        this_fuel_usage = self.engine.route_step_fuel_cost(this_route_step)
        updated_battery = self.battery.use_fuel(this_fuel_usage)
        return self._replace(
            position=this_route_step.position,
            battery=updated_battery,
            route=updated_route,
            distance_traveled=self.distance_traveled + this_route_step.distance
        )

    def step(self) -> Vehicle:
        """
        when an agent stays in the same vehicle state for two subsequent time steps,
        we perform their action in the transition.

        this may be charging, or, following a route.
        also may make a default state transition to IDLE if it is legal.
        :return:
        """
        step_type = VehicleStateCategory.from_vehicle_state(self.vehicle_state)

        if step_type == VehicleStateCategory.DO_NOTHING:
            return self  # NOOP

        elif step_type == VehicleStateCategory.CHARGE:
            # perform a CHARGE step
            if self.plugged_in_charger is None:
                raise StateOfChargeError(f"{self} cannot charge without a plugged-in charger")
            elif self.battery.soc() >= self.soc_upper_limit:
                # fall into IDLE state
                return self.transition(VehicleState.IDLE)
            else:
                # take one charging step
                return self._replace(
                    battery=self.battery.charge(self.plugged_in_charger)
                )

        elif step_type == VehicleStateCategory.MOVE:
            # perform a MOVE step
            if self.route.is_empty():
                if self.has_passengers():
                    raise RouteStepError(f"{self} no default behavior with empty route and on-board passengers")
                else:
                    return self.transition(VehicleState.IDLE)
            else:
                return self._move()

        else:
            raise NotImplementedError(f"Step function failed for undefined vehicle state category {step_type}")

    def battery_swap(self, battery: Battery) -> Vehicle:
        return self._replace(battery=battery)

    """
    TRANSITION FUNCTIONS
    --------------------
    """

    def can_transition(self, vehicle_state: VehicleState) -> bool:
        if not VehicleState.is_valid(vehicle_state):
            raise TypeError("Invalid vehicle state type.")
        elif self.vehicle_state == vehicle_state:
            return True
        elif VehicleState.is_valid_transition(self.vehicle_state, vehicle_state):
            return True
        else:
            return False

    def transition(self, vehicle_state: VehicleState) -> Optional[Vehicle]:
        if self.vehicle_state == vehicle_state:
            return self
        elif self.can_transition(vehicle_state):
            return self._replace(vehicle_state=vehicle_state)
        else:
            return None
