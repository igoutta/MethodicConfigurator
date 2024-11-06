#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import JSONDecodeError
from json import load as json_load
from logging import error as logging_error

# from sys import exit as sys_exit
# from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from os import path as os_path
from typing import Tuple

from MethodicConfigurator import _
from MethodicConfigurator.annotate_params import Par


class ConfigurationSteps:
    """
    A class to manage configuration steps for the ArduPilot methodic configurator.

    This class provides methods for reading and validating configuration steps, including forced and derived parameters.
    It is designed to simplify the interaction with configuration steps for managing ArduPilot configuration files.

    Attributes:
        configuration_steps_filename (str): The name of the file containing documentation for the configuration files.
        configuration_steps (dict): A dictionary containing the configuration steps.
    """

    def __init__(self, _vehicle_dir: str, vehicle_type: str):
        self.configuration_steps_filename = "configuration_steps_" + vehicle_type + ".json"
        self.configuration_steps = {}
        self.forced_parameters = {}
        self.derived_parameters = {}
        self.log_loaded_file = False

    def re_init(self, vehicle_dir: str, vehicle_type: str):
        if vehicle_type == "":
            return
        self.configuration_steps_filename = "configuration_steps_" + vehicle_type + ".json"
        # Define a list of directories to search for the configuration_steps_filename file
        search_directories = [vehicle_dir, os_path.dirname(os_path.abspath(__file__))]
        file_found = False
        for i, directory in enumerate(search_directories):
            try:
                with open(os_path.join(directory, self.configuration_steps_filename), encoding="utf-8") as file:
                    self.configuration_steps = json_load(file)
                    file_found = True
                    if self.log_loaded_file:
                        if i == 0:
                            logging_warning(
                                _("Configuration steps '%s' loaded from %s (overwriting default configuration steps)."),
                                self.configuration_steps_filename,
                                directory,
                            )
                        if i == 1:
                            logging_info(
                                _("Configuration steps '%s' loaded from %s."), self.configuration_steps_filename, directory
                            )
                    break
            except FileNotFoundError:
                pass
            except JSONDecodeError as e:
                logging_error(_("Error in file '%s': %s"), self.configuration_steps_filename, e)
                break
        if file_found:
            for filename, file_info in self.configuration_steps.items():
                self.__validate_parameters_in_configuration_steps(filename, file_info, "forced")
                self.__validate_parameters_in_configuration_steps(filename, file_info, "derived")
        else:
            logging_warning(_("No configuration steps documentation and no forced and derived parameters will be available."))
        self.log_loaded_file = True

    def __validate_parameters_in_configuration_steps(self, filename: str, file_info: dict, parameter_type: str) -> None:
        """
        Validates the parameters in the configuration steps.

        This method checks if the parameters in the configuration steps are correctly formatted.
        If a parameter is missing the 'New Value' or 'Change Reason' attribute, an error message is logged.
        """
        if parameter_type + "_parameters" in file_info:
            if not isinstance(file_info[parameter_type + "_parameters"], dict):
                logging_error(
                    _("Error in file '%s': '%s' %s parameter is not a dictionary"),
                    self.configuration_steps_filename,
                    filename,
                    parameter_type,
                )
                return
            for parameter, parameter_info in file_info[parameter_type + "_parameters"].items():
                if "New Value" not in parameter_info:
                    logging_error(
                        _("Error in file '%s': '%s' %s parameter '%s' 'New Value' attribute not found."),
                        self.configuration_steps_filename,
                        filename,
                        parameter_type,
                        parameter,
                    )
                if "Change Reason" not in parameter_info:
                    logging_error(
                        _("Error in file '%s': '%s' %s parameter '%s' 'Change Reason' attribute not found."),
                        self.configuration_steps_filename,
                        filename,
                        parameter_type,
                        parameter,
                    )

    def compute_parameters(self, filename: str, file_info: dict, parameter_type: str, variables: dict) -> str:
        """
        Computes the forced or derived parameters for a given configuration file.

        If the parameter is forced, it is added to the forced_parameters dictionary.
        If the parameter is derived, it is added to the derived_parameters dictionary.
        """
        if parameter_type + "_parameters" not in file_info or not variables:
            return ""
        destination = self.forced_parameters if parameter_type == "forced" else self.derived_parameters
        for parameter, parameter_info in file_info[parameter_type + "_parameters"].items():
            try:
                if ("fc_parameters" in str(parameter_info["New Value"])) and (
                    "fc_parameters" not in variables or variables["fc_parameters"] == {}
                ):
                    error_msg = _(
                        "In file '{self.configuration_steps_filename}': '{filename}' {parameter_type} "
                        "parameter '{parameter}' could not be computed: 'fc_parameters' not found, is an FC connected?"
                    )
                    error_msg = error_msg.format(**locals())
                    if parameter_type == "forced":
                        logging_error(error_msg)
                        return error_msg
                    logging_warning(error_msg)
                    continue
                result = eval(str(parameter_info["New Value"]), {}, variables)  # noqa S307 pylint: disable=eval-used

                # convert (combobox) string text to (parameter value) string int or float
                if isinstance(result, str) and parameter in variables["doc_dict"]:
                    values = variables["doc_dict"][parameter]["values"]
                    if values:
                        result = next(key for key, value in values.items() if value == result)
                    else:
                        bitmasks = variables["doc_dict"][parameter]["Bitmask"]
                        if bitmasks:
                            result = 2 ** next(key for key, bitmask in bitmasks.items() if bitmask == result)

                if filename not in destination:
                    destination[filename] = {}
                destination[filename][parameter] = Par(float(result), parameter_info["Change Reason"])
            except (SyntaxError, NameError, KeyError, StopIteration) as _e:
                error_msg = _(
                    "In file '{self.configuration_steps_filename}': '{filename}' {parameter_type} "
                    "parameter '{parameter}' could not be computed: {_e}"
                )
                error_msg = error_msg.format(**locals())
                if parameter_type == "forced":
                    logging_error(error_msg)
                    return error_msg
                logging_warning(error_msg)
        return ""

    def auto_changed_by(self, selected_file: str):
        if selected_file in self.configuration_steps:
            return self.configuration_steps[selected_file].get("auto_changed_by", "")
        return ""

    def jump_possible(self, selected_file: str):
        if selected_file in self.configuration_steps:
            return self.configuration_steps[selected_file].get("jump_possible", {})
        return {}

    def get_documentation_text_and_url(self, selected_file: str, prefix_key: str) -> Tuple[str, str]:
        documentation = self.configuration_steps.get(selected_file, {}) if self.configuration_steps else None
        if documentation is None:
            text = _(
                "File '{self.configuration_steps_filename}' not found. "
                "No intermediate parameter configuration steps available"
            )
            text = text.format(**locals())
            url = None
        else:
            text = _("No documentation available for {selected_file} in the {self.configuration_steps_filename} file")
            text = documentation.get(prefix_key + "_text", text.format(**locals()))
            url = documentation.get(prefix_key + "_url", None)
        return text, url
