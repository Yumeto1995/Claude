import pygame

from engine import Engine
from graphics import Renderer
from input_handlers import held_movement_action

MAP_WIDTH = 80
MAP_HEIGHT = 50
VIEW_W = 24  # 画面に映すタイル数（横）
VIEW_H = 17  # 画面に映すタイル数（縦）
MOVE_COOLDOWN_MS = 120  # 押しっぱなし時の移動間隔（小さいほど速い）


def main():
    pygame.init()
    engine = Engine(MAP_WIDTH, MAP_HEIGHT)
    renderer = Renderer(VIEW_W, VIEW_H)
    clock = pygame.time.Clock()
    last_move = 0

    try:
        while True:
            renderer.render(engine)

            # 単発キー（足踏み・モード切替・攻撃・終了）
            engine.handle_events(pygame.event.get())

            # 押しっぱなしの方向キーで連続移動（クールダウンで間引き）
            now = pygame.time.get_ticks()
            if now - last_move >= MOVE_COOLDOWN_MS:
                action = held_movement_action(engine)
                if action is not None:
                    engine.perform_player_action(action)
                    last_move = now

            clock.tick(60)
    except SystemExit:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
