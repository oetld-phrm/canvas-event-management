"""Run with python -m canvas_events {export,import,update,delete}."""
import argparse
from importlib import import_module
from .common import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command, module_name, description in (
        ('export', 'export', 'Export course calendar events'),
        ('import', 'create', 'Create new calendar events from CSV'),
        ('update', 'update', 'Modify existing calendar events'),
        ('delete', 'delete', 'Delete all calendar events for selected courses'),
    ):
        module = import_module(f'.{module_name}', __package__)
        subparser = commands.add_parser(command, help=description, description=description)
        module.configure_parser(subparser)
        subparser.set_defaults(handler=module.main)
    args = parser.parse_args()
    return run(lambda: args.handler(args))


if __name__ == '__main__':
    raise SystemExit(main())
