import pygame

import colors
import display_settings as ds
import savegame
from actions import ReturnToTitle
from engine import Engine
from graphics import Renderer
from input_handlers import held_movement_action

MAP_WIDTH = 80
MAP_HEIGHT = 50
MOVE_COOLDOWN_MS = 120  # 押しっぱなし時の移動間隔（小さいほど速い）


def build_renderer(index: int) -> Renderer:
    """解像度番号から Renderer を作る（横タイル数・縦タイル数・パネル高を導出）。"""
    w, h = ds.RESOLUTIONS[index]
    view_w, view_h, panel = ds.layout_for(w, h)
    return Renderer(view_w, view_h, panel)

_UP = (pygame.K_UP, pygame.K_w, pygame.K_k)
_DOWN = (pygame.K_DOWN, pygame.K_s, pygame.K_j)
_ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)


def run_title(renderer: Renderer, clock) -> str:
    """タイトル画面。'new' / 'load' / 'settings' / 'quit' を返す。"""
    cursor = 0
    while True:
        # 毎回セーブの有無を見て「つづきから」を出し分け
        options = ["新規ゲーム"]
        if savegame.has_save():
            options.append("つづきから")
        options += ["画面設定", "全画面切替", "終了"]
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
                if sel == "画面設定":
                    return "settings"
                if sel == "全画面切替":
                    pygame.display.toggle_fullscreen()
                if sel == "終了":
                    return "quit"
        clock.tick(30)


def run_settings(renderer: Renderer, clock) -> Renderer:
    """解像度を選ぶ。変更したら新しい Renderer を作って返す（保存もする）。"""
    idx = ds.load_index()
    cursor = idx
    while True:
        options = []
        for i, (w, h) in enumerate(ds.RESOLUTIONS):
            mark = "● " if i == idx else "   "
            options.append(f"{mark}{ds.label(w, h)}")
        cur_w, cur_h = ds.RESOLUTIONS[idx]
        note = f"現在の解像度：{ds.label(cur_w, cur_h)}（タイル64pxで等倍表示）"
        renderer.render_settings(options, cursor, note)

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
                if cursor != idx:           # 選択を適用＝表示を作り直す
                    idx = cursor
                    ds.save_index(idx)
                    renderer = build_renderer(idx)
            elif ev.key == pygame.K_ESCAPE:
                return renderer
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
    renderer = build_renderer(ds.load_index())  # 前回選んだ解像度で起動
    clock = pygame.time.Clock()
    try:
        while True:
            choice = run_title(renderer, clock)
            if choice == "quit":
                break
            if choice == "settings":
                renderer = run_settings(renderer, clock)  # 解像度変更を反映
                continue
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
