A Python API to Minecraft that works with the [FruitJuice](https://github.com/jdeast/FruitJuice) Bukkit plugin to enable a python and/or scratch programming interface.

See [FruitJuice/README_server_setup.md](https://github.com/jdeast/FruitJuice/blob/master/README_server_setup.md) for instructions to set up your own python/scratch server that works on java or bedrock.

## Running the examples

Every example connects to `localhost:4711` by default, which is right when the
Minecraft server is on the same machine as your code.

To point somewhere else, either pass it:

```
python examples/rainbow.py --host mc.example.org
python examples/rainbow.py --host mc.example.org --port 4712 --player steve
```

or set it once for the whole session:

| variable | what it sets | default |
|---|---|---|
| `PYNCRAFT_HOST` | server address (`PYNCRAFT_ADDRESS` also works) | `localhost` |
| `PYNCRAFT_PORT` | the FruitJuice port | `4711` |
| `PYNCRAFT_PLAYER` | which player to control, when several are online | first to connect |

```
export PYNCRAFT_HOST=mc.example.org      # macOS, Linux
set PYNCRAFT_HOST=mc.example.org         # Windows
```

A command-line flag always beats the environment. The examples that need a 3D
model download it on first run and check it afterwards, so nothing else needs
fetching by hand.
