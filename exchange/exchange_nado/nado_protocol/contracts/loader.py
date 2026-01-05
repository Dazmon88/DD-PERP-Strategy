import json
from pathlib import Path
from nado_protocol.contracts.types import (
    NadoAbiName,
    NadoDeployment,
    NadoNetwork,
)
from nado_protocol.utils.model import ensure_data_type, parse_enum_value


def load_abi(abi_name: NadoAbiName) -> list[dict]:
    """
    Load the Application Binary Interface (ABI) for a given contract.

    Args:
        abi_name (NadoAbiName): The name of the contract for which the ABI is loaded.

    Returns:
        list[dict]: A list of dictionaries representing the ABI of the contract.
    """
    file_path = Path(__file__).parent / "abis" / f"{parse_enum_value(abi_name)}.json"
    return ensure_data_type(_load_json(file_path), list)


def load_deployment(network: NadoNetwork) -> NadoDeployment:
    """
    Load the deployment data for a given network.

    Args:
        network (NadoNetwork): The network for which the deployment data is loaded.

    Returns:
        NadoDeployment: An instance of NadoDeployment containing the loaded deployment data.
    """
    file_path = (
        Path(__file__).parent
        / "deployments"
        / f"deployment.{parse_enum_value(network)}.json"
    )
    return NadoDeployment(**_load_json(file_path))


def _load_json(file_path: Path) -> dict:
    """
    Load a JSON file.

    Args:
        file_path (Path): The path to the JSON file.

    Returns:
        dict: The content of the JSON file as a dictionary.
    """
    with open(file_path, "r") as f:
        data = json.load(f)
    return data
