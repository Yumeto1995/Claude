import pygame

from engine import Engine
from graphics import Renderer

MAP_WIDTH = 80
MAP_HEIGHT = 50
VIEW_W = 24  # 画面に映すタイル数（横）
VIEW_H = 17  # 画面に映すタイル数（縦）


def main():
    pygame.init()
    engine = Engine(MAP_WIDTH, MAP_HEIGHT)
    renderer = Renderer(VIEW_W, VIEW_H)
    clock = pygame.time.Clock()

    try:
        while True:
            renderer.render(engine)
            engine.handle_events(pygame.event.get())
            clock.tick(30)  # 最大30fps（ターン制なので入力時のみ進む）
    except SystemExit:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
