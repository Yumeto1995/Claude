import pygame

import colors
import savegame
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
            events = pygame.event.get()

            # システムキー（全画面・セーブ・ロード）
            for ev in events:
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                    elif ev.key == pygame.K_F5:
                        savegame.save_game(engine)
                        engine.message_log.add_message("セーブした。", colors.WELCOME)
                    elif ev.key == pygame.K_F9 and savegame.has_save():
                        engine = savegame.load_game()
                        engine.message_log.add_message("ロードした。", colors.WELCOME)

            # ゲーム操作（足踏み・モード切替・攻撃・終了・拠点操作など）
            engine.handle_events(events)

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
