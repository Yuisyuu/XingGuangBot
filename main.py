import botpy
import tomlkit

from bot.client import Client

with open("config.toml", "r", encoding="utf-8") as f:
    config = tomlkit.load(f)

if __name__ == "__main__":
    intents = botpy.Intents(public_messages=True)
    client = Client(intents=intents)
    client.run(appid=config["appid"], secret=config["secret"])
