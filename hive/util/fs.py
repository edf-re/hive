import os
from typing import Optional
from pathlib import Path
from hive.config.global_config import GlobalConfig
import pkg_resources
import yaml


def global_hive_config_search() -> GlobalConfig:
    """
    searches for the global hive config, and if found, loads it. if not, loads the default from hive.resources
    :return: global hive config
    """
    # this searches up the path to the root of the file system
    def _backprop_search(search_path: Path) -> Optional[Path]:
        search_file = search_path.joinpath(".hive.yaml")
        if search_file.is_file():
            return search_file
        else:
            updated_search_path = search_path.parent
            if updated_search_path == search_path:
                return None
            else:
                return _backprop_search(updated_search_path)

    # load the default file to be merged with any found files
    default_global_config_file_path = pkg_resources.resource_filename("hive.resources.defaults", ".hive.yaml")
    with Path(default_global_config_file_path).open() as df:
        default = yaml.safe_load(df)

    file_found_in_backprop = _backprop_search(Path.cwd())
    file_at_home_directory = Path.home().joinpath(".hive.yaml")
    file_found_at_home_directory = file_at_home_directory.is_file()
    file_found = file_found_in_backprop if file_found_in_backprop else file_at_home_directory if file_found_at_home_directory else None
    if file_found:
        with file_found.open() as f:
            global_hive_config = yaml.safe_load(f)
            default.update(global_hive_config)
            return GlobalConfig.from_dict(default, str(file_found))
    else:
        return GlobalConfig.from_dict(default, default_global_config_file_path)


def construct_asset_path(file: str, scenario_directory: str, default_directory_name: str, resources_subdirectory: str) -> str:
    """
    constructs the path to a scenario asset relative to a scenario directory. attempts to load at both
    the user-provided relative path, and if that fails, attempts to load at the default directory; finally, checks
    the resources directory for a fallback.

    for example, with file "leaf.yaml", scenario_directory "/home/jimbob/hive/denver" and default_directory "powertrain",
    this will test "/home/jimbob/hive/denver/leaf.yaml" then "/home/jimbob/hive/denver/vehicles/leaf.yaml" and finally
    "hive/resources/powertrain/leaf.yaml" and return the first path where the file is found to exist.

    :param file: file we are seaching for
    :param scenario_directory: the scenario directory
    :param default_directory_name: the directory name where assets of this type are typically saved
    :param resources_subdirectory: the subdirectory of resources where we also expect this could be saved
    :return: the path string if the file exists, otherwise None
    :raises: FileNotFoundError if asset is not found
    """
    try:
        result = construct_scenario_asset_path(file, scenario_directory, default_directory_name)
        return result
    except FileNotFoundError:
        # try the resources directory fallback
        fallback = pkg_resources.resource_filename(f"hive.resources.{resources_subdirectory}", file)
        if Path(fallback).is_file():
            return fallback
        else:
            raise FileNotFoundError(file)


def construct_scenario_asset_path(file: str, scenario_directory: str, default_directory_name: str) -> str:
    """
    constructs the path to a scenario asset relative to a scenario directory. attempts to load at both
    the user-provided relative path, and if that fails, attempts to load at the default directory.

    for example, with file "vehicles.csv", scenario_directory "/home/jimbob/hive/denver" and default_directory "vehicles",
    this will test "/home/jimbob/hive/denver/vehicles.csv" then "/home/jimbob/hive/denver/vehicles/vehicles.csv" and return
    the first path where the file is found to exist.

    :param file: file we are searching for
    :param scenario_directory: the directory where the scenario file was found
    :param default_directory_name: the default directory name for the type of asset we are checking for
    :return: the path string if the file exists, otherwise None
    :raises: FileNotFoundError if asset is not found
    """
    file_at_scenario_directory = Path(scenario_directory).joinpath(file)
    file_at_default_directory = Path(scenario_directory).joinpath(default_directory_name).joinpath(file)
    if file_at_scenario_directory.is_file():
        return str(file_at_scenario_directory)
    elif file_at_default_directory.is_file():
        return str(file_at_default_directory)
    else:
        raise FileNotFoundError(f"cannot find file {file} in directory {scenario_directory}")


def check_built_in_scenarios(user_provided_scenario: str) -> Path:
    """
    allows users to declare built-in scenario filenames without absolute/relative paths or
    expects the user has provided a valid relative/absolute to another file

    :param user_provided_scenario: the scenario requested
    :return: the absolute path of this scenario if it exists
    :raises: FileNotFoundError
    """
    absolute_path = Path(user_provided_scenario)
    relative_path = Path.cwd().joinpath(user_provided_scenario)
    den_path = Path(pkg_resources.resource_filename("hive.resources.scenarios.denver_downtown", user_provided_scenario))
    nyc_path = Path(pkg_resources.resource_filename("hive.resources.scenarios.manhattan", user_provided_scenario))

    if absolute_path.is_file():
        return absolute_path
    elif relative_path.is_file():
        return relative_path
    elif den_path.is_file():
        return den_path
    elif nyc_path.is_file():
        return nyc_path
    else:
        raise FileNotFoundError(user_provided_scenario)


def search_for_file(file: str, scenario_directory: str, data_directory: Optional[str] = None) -> Optional[str]:
    """
    returns a URI to a file, attempting to find the file at
    1. the scenario directory, where the path is relative to the user-defined data directory
    2. the scenario directory, where the path is absolute
    3. the scenario directory, where the path is relative to the current working directory
    4. the hive.resources package as a fallback
    :param file: the filename we are looking for
    :param scenario_directory: the input directory set in the scenario config
    :param data_directory: the user's global data directory location, or None if not defined
    :return: the complete URI to the file if it was found, otherwise None
    """

    file_at_data_dir_plus_input_dir = os.path.normpath(os.path.join(data_directory, scenario_directory, file)) if data_directory else None
    file_at_input_dir = os.path.normpath(os.path.join(scenario_directory, file))
    file_at_cwd_plus_input_dir = os.path.normpath(os.path.join(os.getcwd(), scenario_directory, file))
    file_at_resources_dir = pkg_resources.resource_filename("hive.resources", file)

    if file_at_data_dir_plus_input_dir and os.path.isfile(file_at_data_dir_plus_input_dir):
        return file_at_data_dir_plus_input_dir
    elif os.path.isfile(file_at_input_dir):
        return file_at_input_dir
    elif os.path.isfile(file_at_cwd_plus_input_dir):
        return file_at_cwd_plus_input_dir
    elif os.path.isfile(file_at_resources_dir):
        return file_at_resources_dir
    else:
        return None
