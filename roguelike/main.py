import tcod

from engine import Engine

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50


def main():
    engine = Engine(width=SCREEN_WIDTH, height=SCREEN_HEIGHT)

    with tcod.context.new(
        columns=SCREEN_WIDTH,
        rows=SCREEN_HEIGHT,
        title="Roguelike",
    ) as context:
        console = tcod.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="F")

        while True:
            engine.render(console, context)
            engine.handle_events(tcod.event.wait())


if __name__ == "__main__":
    main()
