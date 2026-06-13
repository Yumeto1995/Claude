import pygame

import colors
import savegame
from actions import ReturnToTitle
from engine import Engine
from graphics import Renderer
from input_handlers import held_movement_action

MAP_WIDTH = 80
MAP_HEIGHT = 50
VIEW_W = 16  # 画面に映すタイル数（横。TILE_SIZE=64 で 16×64=1024px）
VIEW_H = 10  # 画面に映すタイル数（縦。10×64=640px ＋下部パネル）
MOVE_COOLDOWN_MS = 120  # 押しっぱなし時の移動間隔（小さいほど速い）

_UP = (pygame.K_UP, pygame.K_w, pygame.K_k)
_DOWN = (pygame.K_DOWN, pygame.K_s, pygame.K_j)
_ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)


def run_title(renderer: Renderer, clock) -> str:
    """タイトル画面。'new' / 'load' / 'quit' を返す。"""
    cursor = 0
    while True:
        # 毎回セーブの有無を見て「つづきから」を出し分け
        options = ["新規ゲーム"]
        if savegame.has_save():
            options.append("つづきから")
        options += ["全画面切替", "終了"]
        cursor %= len(options)

        renderer.render_title(options, cursor)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                raise SystemExit()
            if ev.type != pygame.KEYDOWN:
                continue
            if ev.key in _UP:
                cursor = (cursor - 1) % len(options)
            elif ev.key in _DOWN:
                cursor = (cursor + 1) % len(options)
            elif ev.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif ev.key in _ENTER:
                sel = options[cursor]
                if sel == "新規ゲーム":
                    return "new"
                if sel == "つづきから":
                    return "load"
                if sel == "全画面切替":
                    pygame.display.toggle_fullscreen()
                if sel == "終了":
                    return "quit"
        clock.tick(30)


def _autosave(engine: Engine) -> None:
    if not engine.game_over:
        savegame.save_game(engine)


def run_game(renderer: Renderer, clock, engine: Engine) -> None:
    """ゲーム本編ループ。ESC でタイトルへ戻る（自動セーブ）。"""
    last_move = 0
    try:
        while True:
            renderer.render(engine)
            events = pygame.event.get()

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

            engine.handle_events(events)

            now = pygame.time.get_ticks()
            if now - last_move >= MOVE_COOLDOWN_MS:
                action = held_movement_action(engine)
                if action is not None:
                    engine.perform_player_action(action)
                    last_move = now

            clock.tick(60)
    except ReturnToTitle:
        _autosave(engine)  # タイトルへ戻る前に自動セーブ
    except SystemExit:
        _autosave(engine)  # ウィンドウを閉じる前にも保存
        raise


def main():
    pygame.init()
    renderer = Renderer(VIEW_W, VIEW_H)
    clock = pygame.time.Clock()
    try:
        while True:
            choice = run_title(renderer, clock)
            if choice == "quit":
                break
            if choice == "load":
                try:
                    engine = savegame.load_game()
                except Exception:
                    engine = Engine(MAP_WIDTH, MAP_HEIGHT)
            else:
                engine = Engine(MAP_WIDTH, MAP_HEIGHT)
            run_game(renderer, clock, engine)
    except SystemExit:
        pass
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
