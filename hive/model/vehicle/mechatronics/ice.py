from __future__ import annotations

from typing import Dict, NamedTuple, TYPE_CHECKING, Tuple

from hive.model.energy.energytype import EnergyType
from hive.model.vehicle.mechatronics.mechatronics_interface import MechatronicsInterface
from hive.model.vehicle.mechatronics.powertrain import build_powertrain
from hive.util.typealiases import MechatronicsId
from hive.util.units import *

if TYPE_CHECKING:
    from hive.model.energy.charger import Charger
    from hive.model.vehicle.vehicle import Vehicle
    from hive.model.roadnetwork.route import Route
    from hive.model.vehicle.mechatronics.powertrain.powertrain import Powertrain


class ICE(NamedTuple, MechatronicsInterface):
    """
    Mechatronics for an internal combustion engine (ICE)
    """

    mechatronics_id: MechatronicsId
    tank_capacity_gallons: GallonGasoline
    idle_gallons_per_hour: GallonPerHour
    powertrain: Powertrain
    nominal_miles_per_gallon: MilesPerGallon

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> ICE:
        """
        build from a dictionary
        :param d: the dictionary to build from
        :return: the built Mechatronics object
        """
        tank_capacity_gallons = float(d['tank_capacity_gallons'])
        idle_gallons_per_hour = float(d['idle_gallons_per_hour'])
        nominal_miles_per_gallon = float(d['nominal_miles_per_gallon'])

        # set scale factor in config dict so the tabular powertrain can use it to scale the normalized lookup
        d['scale_factor'] = 1 / nominal_miles_per_gallon

        return ICE(
            mechatronics_id=d['mechatronics_id'],
            tank_capacity_gallons=tank_capacity_gallons,
            idle_gallons_per_hour=idle_gallons_per_hour,
            powertrain=build_powertrain(d),
            nominal_miles_per_gallon=nominal_miles_per_gallon,
        )

    def valid_charger(self, charger: Charger) -> bool:
        """
        checks to make sure charger is gasoline energy type

        :param charger: the charger to check
        :return: true/false
        """
        return charger.energy_type == EnergyType.GASOLINE

    def initial_energy(self, percent_full: Ratio) -> Dict[EnergyType, float]:
        """
        return an energy dictionary from an initial soc
        :param percent_full:
        :return:
        """
        return {EnergyType.GASOLINE: self.tank_capacity_gallons * percent_full}

    def range_remaining_km(self, vehicle: Vehicle) -> Kilometers:
        """
        how much range remains, in kilometers
        :return:
        """
        energy_gal_gas = vehicle.energy[EnergyType.GASOLINE]
        miles = energy_gal_gas * self.nominal_miles_per_gallon
        km = miles * MILE_TO_KM
        return km

    def fuel_source_soc(self, vehicle: Vehicle) -> Ratio:
        """
        what is the level of the fuel tank
        :return:
        """
        energy_gal_gas = vehicle.energy[EnergyType.GASOLINE]
        return energy_gal_gas / self.tank_capacity_gallons

    def is_empty(self, vehicle: Vehicle) -> bool:
        """
        is the vehicle empty
        :param vehicle:
        :return:
        """
        return vehicle.energy[EnergyType.GASOLINE] <= 0

    def is_full(self, vehicle: Vehicle) -> bool:
        """
        is the vehicle full
        :param vehicle:
        :return:
        """
        return vehicle.energy[EnergyType.GASOLINE] >= self.tank_capacity_gallons

    def move(self, vehicle: Vehicle, route: Route) -> Vehicle:
        """
        move over a set distance

        :param vehicle:
        :param route:
        :return:
        """
        energy_used = self.powertrain.energy_cost(route)
        energy_used_gal_gas = energy_used * get_unit_conversion(self.powertrain.energy_units, "gal_gas")

        vehicle_energy_gal_gas = vehicle.energy[EnergyType.GASOLINE]
        new_energy_gal_gas = max(0.0, vehicle_energy_gal_gas - energy_used_gal_gas)
        updated_vehicle = vehicle.modify_energy({EnergyType.GASOLINE: new_energy_gal_gas})

        return updated_vehicle

    def idle(self, vehicle: Vehicle, time_seconds: Seconds) -> Vehicle:
        """
        idle for a set amount of time

        :param vehicle:
        :param time_seconds:
        :return:
        """
        idle_energy_gal_gas = self.idle_gallons_per_hour * time_seconds * SECONDS_TO_HOURS
        vehicle_energy_gal_gas = vehicle.energy[EnergyType.GASOLINE]
        new_energy_gal_gas = max(0.0, vehicle_energy_gal_gas - idle_energy_gal_gas)
        updated_vehicle = vehicle.modify_energy({EnergyType.GASOLINE: new_energy_gal_gas})

        return updated_vehicle

    def add_energy(self, vehicle: Vehicle, charger: Charger, time_seconds: Seconds) -> Tuple[Vehicle, Seconds]:
        """
        add energy into the system. units for the charger are gallons per second

        :param vehicle:
        :param charger:
        :param time_seconds:
        :return: the updated vehicle, along with the time spent charging
        """
        start_gal_gas = vehicle.energy[EnergyType.GASOLINE]

        pump_gal_gas = start_gal_gas + charger.rate * time_seconds
        new_gal_gas = min(self.tank_capacity_gallons, pump_gal_gas)

        updated_vehicle = vehicle.modify_energy({EnergyType.GASOLINE: new_gal_gas})

        return updated_vehicle, time_seconds
