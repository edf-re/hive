from __future__ import annotations

import logging
from typing import NamedTuple, Tuple, Optional, TYPE_CHECKING

import immutables

from hive.model.roadnetwork.route import Route, route_cooresponds_with_entities
from hive.model.vehicle.trip_phase import TripPhase
from hive.runner.environment import Environment
from hive.state.simulation_state import simulation_state_ops
from hive.state.simulation_state.simulation_state_ops import modify_request
from hive.state.vehicle_state import vehicle_state_ops
from hive.state.vehicle_state.idle import Idle
from hive.state.vehicle_state.servicing_pooling_trip import ServicingPoolingTrip
from hive.state.vehicle_state.servicing_trip import ServicingTrip
from hive.state.vehicle_state.vehicle_state import VehicleState
from hive.state.vehicle_state.vehicle_state_type import VehicleStateType
from hive.util.exception import SimulationStateError
from hive.util.typealiases import RequestId, VehicleId

if TYPE_CHECKING:
    from hive.state.simulation_state.simulation_state import SimulationState

log = logging.getLogger(__name__)


class DispatchTrip(NamedTuple, VehicleState):
    vehicle_id: VehicleId
    request_id: RequestId
    route: Route

    @property
    def vehicle_state_type(cls) -> VehicleStateType:
        return VehicleStateType.DISPATCH_TRIP

    def update(self, sim: SimulationState,
               env: Environment) -> Tuple[Optional[Exception], Optional[SimulationState]]:
        return VehicleState.default_update(sim, env, self)

    def enter(self, sim: SimulationState,
              env: Environment) -> Tuple[Optional[Exception], Optional[SimulationState]]:
        """
        checks that the request exists and if so, updates the request to know that this vehicle is on it's way

        :param sim: the sim state
        :param env: the sim environment
        :return: an exception, or a sim state, or (None, None) if the request isn't there anymore
        """
        vehicle = sim.vehicles.get(self.vehicle_id)
        request = sim.requests.get(self.request_id)
        is_valid = route_cooresponds_with_entities(
            self.route, vehicle.position, request.origin_position) if vehicle and request else False
        context = f"vehicle {self.vehicle_id} entering dispatch trip for request {self.request_id}"
        if not vehicle:
            return SimulationStateError(f"vehicle not found; context: {context}"), None
        elif not request:
            # not an error - may have been picked up. fail silently
            return None, None
        elif not request.membership.grant_access_to_membership(vehicle.membership):
            msg = f"vehicle {vehicle.id} doesn't have access to request {request.id}"
            return SimulationStateError(msg), None
        elif not is_valid:
            return None, None
        else:
            updated_request = request.assign_dispatched_vehicle(self.vehicle_id, sim.sim_time)
            error, updated_sim = simulation_state_ops.modify_request(sim, updated_request)
            if error:
                response = SimulationStateError(
                    f"failure during DispatchTrip.enter for vehicle {self.vehicle_id}")
                response.__cause__ = error
                return response, None
            else:
                result = VehicleState.apply_new_vehicle_state(updated_sim, self.vehicle_id, self)
                return result

    def exit(self, next_state: VehicleState, sim: SimulationState,
             env: Environment) -> Tuple[Optional[Exception], Optional[SimulationState]]:
        """
        release the vehicle from the request it was dispatched to

        :param sim: the simulation state
        :param env: the simulation environment
        :return: an error, or, the updated simulation state, where the request is no longer awaiting this vehicle
        """
        request = sim.requests.get(self.request_id)
        if request is None:
            # request doesn't exist, doesn't need to be updated
            return None, sim
        else:
            updated_request = request.unassign_dispatched_vehicle()
            # todo: possibly log this event here
            result = modify_request(sim, updated_request)
            return result

    def _has_reached_terminal_state_condition(self, sim: SimulationState, env: Environment) -> bool:
        """
        this terminates when we reach a base

        :param sim: the sim state
        :param env: the sim environment
        :return: True if we have reached the base
        """
        return len(self.route) == 0

    def _default_terminal_state(
            self, sim: SimulationState,
            env: Environment) -> Tuple[Optional[Exception], Optional[VehicleState]]:
        """
        give the default state to transition to after having met a terminal condition

        :param sim: the simulation state
        :param env: the simulation environment
        :return: an exception due to failure or the next_state after finishing a task
        """
        vehicle = sim.vehicles.get(self.vehicle_id)
        request = sim.requests.get(self.request_id)
        if request and request.geoid != vehicle.geoid:
            locations = f"{request.geoid} != {vehicle.geoid}"
            message = f"vehicle {self.vehicle_id} ended dispatch trip to request {self.request_id} but locations do not match: {locations}. sim_time: {sim.sim_time}"
            return SimulationStateError(message), None
        elif not request:
            # request already got picked up or was cancelled; go an Idle state
            next_state = Idle(self.vehicle_id)
            return None, next_state
        else:
            # request exists: pick up the trip and enter a ServicingTrip state
            route = sim.road_network.route(request.origin_position, request.destination_position)
            # apply next state
            # generate the data to describe the trip for this request
            # where the pickup phase is currently happening + doesn't need to be added to the trip plan
            trip_plan: Tuple[Tuple[RequestId, TripPhase], ...] = ((request.id, TripPhase.DROPOFF), )
            departure_time = sim.sim_time

            # create the state (pooling, or, standard servicing trip, depending on the sitch)
            pooling_trip = vehicle.driver_state.allows_pooling and request.allows_pooling
            next_state = ServicingPoolingTrip(
                vehicle_id=vehicle.id,
                trip_plan=trip_plan,
                boarded_requests=immutables.Map({request.id: request}),
                departure_times=immutables.Map({request.id, departure_time}),
                routes=(route, ),
                num_passengers=len(request.passengers)) if pooling_trip else ServicingTrip(
                    vehicle_id=vehicle.id,
                    request=request,
                    departure_time=departure_time,
                    route=route)
            return None, next_state

    def _perform_update(self, sim: SimulationState,
                        env: Environment) -> Tuple[Optional[Exception], Optional[SimulationState]]:
        """
        take a step along the route to the request

        :param sim: the simulation state
        :param env: the simulation environment
        :return: the sim state with vehicle moved
        """
        move_error, move_sim = vehicle_state_ops.move(sim, env, self.vehicle_id)

        if move_error:
            response = SimulationStateError(
                f"failure during DispatchTrip._perform_update for vehicle {self.vehicle_id}")
            response.__cause__ = move_error
            return response, None
        else:
            return None, move_sim
