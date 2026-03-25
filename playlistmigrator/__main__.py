import sys
from . import cli
import inspect

def list_commands(module):
    # include only functions defined in e.g. 'cli' module
    commands = [name for name, obj in inspect.getmembers(module) if inspect.isfunction(obj)]
    # filter out internal helpers like parse_arguments
    commands = [c for c in commands if not c.startswith('_')]
    return commands

def main():
    available_commands = list_commands(cli)

    # Some basic name fixups since the commands are hypenated in standard cli usage:
    # "load-csv" -> "load_csv"
    if len(sys.argv) > 1:
        sys.argv[1] = sys.argv[1].replace('-', '_')

    if len(sys.argv) < 2:
        print(f"usage: playlistmigrator [COMMAND] <ARGUMENTS>")
        print("Available commands:", ", ".join(c.replace('_', '-') for c in available_commands))
        print("       For example, try 'playlistmigrator list-playlists'")
        sys.exit(1)

    cmd_name = sys.argv[1]

    if cmd_name not in available_commands:
        print(f"ERROR: Unknown command '{cmd_name.replace('_', '-')}'")
        print("Available commands: ", ", ".join(c.replace('_', '-') for c in available_commands))
        sys.exit(1)

    fn = getattr(cli, cmd_name)
    sys.argv = sys.argv[1:]
    fn()

if __name__ == '__main__':
    main()
