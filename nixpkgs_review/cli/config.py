import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any, Literal

import tomllib  # type: ignore

from ..utils import nix_nom_tool, BUILD_GRAPH_TYPE


def regex_type(s: str) -> Pattern[str]:
    try:
        return re.compile(s)
    except re.error as e:
        raise argparse.ArgumentTypeError(f"'{s}' is not a valid regex: {e}")


def get_config_home() -> Path:
    raw_config_home = os.environ.get("XDG_CONFIG_HOME", None)
    if raw_config_home is None:
        config_home = Path.home().joinpath(".config")
    else:
        config_home = Path(raw_config_home)

    return config_home


def _check_type(option_name: str, value: Any, expected_type: type) -> None:
    if not isinstance(value, expected_type):
        raise ValueError(
            f"Incorrect value for option '{option_name}'."
            f"Expected '{expected_type}' but got '{type(value)}'."
        )


# Unfortunately, we cannot 'dynamically' set the allowed values in `Literal`
EVAL_VALUES: tuple[str, ...] = ("ofborg", "local")
EVAL_TYPE = Literal["ofborg", "local"]

CHECKOUT_VALUES: tuple[str, ...] = ("merge", "commit")
CHECKOUT_TYPE = Literal["merge", "commit"]


@dataclass
class PrConfig:
    eval: EVAL_TYPE = "ofborg"
    checkout: CHECKOUT_TYPE = "merge"
    post_result: bool = False

    def update_from_dict(self, config_dict: dict[str, Any]) -> None:
        self.eval = config_dict.get("eval", self.eval)
        assert self.eval in EVAL_VALUES

        self.checkout = config_dict.get("checkout", self.checkout)
        assert self.checkout in CHECKOUT_VALUES

        self.post_result = config_dict.get("post_result", self.post_result)
        _check_type("pr.post_result", self.post_result, bool)


@dataclass
class RevConfig:
    branch: str = "master"

    def update_from_dict(self, config_dict: dict[str, Any]) -> None:
        self.branch = config_dict.get("branch", self.branch)
        _check_type("rev.branch", self.branch, str)


@dataclass
class WipConfig:
    branch: str = "master"
    staged: bool = False

    def update_from_dict(self, config_dict: dict[str, Any]) -> None:
        self.branch = config_dict.get("branch", self.branch)
        _check_type("wip.branch", self.branch, str)

        self.staged = config_dict.get("staged", self.branch)
        _check_type("wip.staged", self.staged, bool)


ALLOW_VALUES: tuple[str, ...] = ("aliases", "ifd", "url-literals")
ALLOW_TYPE = list[Literal["aliases", "ifd", "url-literals"]]
BUILD_GRAPH_VALUES: tuple[str, ...] = ("nix", "nom")


@dataclass
class Config:
    allow: ALLOW_TYPE = []
    build_args: str = ""
    no_shell: bool = False
    remote: str = "https://github.com/NixOS/nixpkgs"
    run: str = ""
    sandbox: bool = False
    skipped_packages: list[str] = []
    skipped_package_regexes: list[Pattern[str]] = []
    systems: str | list[str] = "current"
    build_graph: BUILD_GRAPH_TYPE = nix_nom_tool()
    print_result: bool = False
    extra_nixpkgs_config: str = "{ }"
    num_parallel_evals: int = 1

    rev_config: RevConfig = RevConfig()
    pr_config: PrConfig = PrConfig()
    wip_config: WipConfig = WipConfig()

    def update_from_dict(self, config_dict: dict[str, Any]) -> None:
        self.allow = config_dict.get("allow", self.allow)
        _check_type("allow", self.allow, list)
        assert all(v in ALLOW_VALUES for v in self.allow)

        self.build_args = config_dict.get("build_args", self.build_args)
        _check_type("build_args", self.build_args, str)

        self.no_shell = config_dict.get("no_shell", self.no_shell)
        _check_type("no_shell", self.no_shell, bool)

        self.remote = config_dict.get("remote", self.remote)
        _check_type("remote", self.remote, str)

        self.run = config_dict.get("run", self.run)
        _check_type("run", self.run, str)

        self.sandbox = config_dict.get("sandbox", self.sandbox)
        _check_type("sandbox", self.sandbox, bool)

        self.skipped_packages = config_dict.get(
            "skipped_packages", self.skipped_packages
        )
        _check_type("skipped_packages", self.skipped_packages, list)

        skipped_package_regexes: list[str] = config_dict.get(
            "skipped_package_regexes", self.skipped_package_regexes
        )
        _check_type("skipped_package_regexes", skipped_package_regexes, list)
        self.skipped_package_regexes = [
            regex_type(regex) for regex in skipped_package_regexes
        ]

        self.systems = config_dict.get("systems", self.systems)
        assert isinstance(self.systems, str) or isinstance(self.systems, list)
        if isinstance(self.systems, list):
            assert all(isinstance(system, str) for system in self.systems)

        self.build_graph = config_dict.get("build_graph", self.build_graph)
        _check_type("build_graph", self.build_graph, str)
        assert self.build_graph in BUILD_GRAPH_VALUES

        self.print_result = config_dict.get("print_result", self.print_result)
        _check_type("print_result", self.print_result, bool)

        self.extra_nixpkgs_config = config_dict.get(
            "extra_nixpkgs_config", self.extra_nixpkgs_config
        )
        _check_type("extra_nixpkgs_config", self.extra_nixpkgs_config, str)

        self.num_parallel_evals = config_dict.get(
            "num_parallel_evals", self.num_parallel_evals
        )
        _check_type("num_parallel_evals", self.num_parallel_evals, int)
        assert self.num_parallel_evals > 0

        # Sub-commands specific options

        self.rev_config.update_from_dict(
            config_dict=config_dict.get("rev", {}),
        )

        self.wip_config.update_from_dict(
            config_dict=config_dict.get("wip", {}),
        )

        self.pr_config.update_from_dict(
            config_dict=config_dict.get("pr", {}),
        )

    def update_from_args(args: argparse.Namespace) -> None:
        self.update_from_dict(config_dict={})

    def read_config(self) -> None:
        config_path: Path = get_config_home() / "nixpkgs-review" / "config.toml"
        if not config_path.exists():
            return

        with open(config_path, "rb") as f:
            file_config: dict[str, Any] = tomllib.load(f)
            self.update_from_dict(config_dict=file_config)
