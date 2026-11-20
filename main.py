import os
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import (
    Color, Rectangle, Ellipse, Line, RoundedRectangle
)


class MarioGame(Widget):
    WORLD = 3000
    PLAYER_W = 38
    NORMAL_H = 70

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs)

        self.store = store
        self.best_score = store.get("record")["score"] if store.exists("record") else 0
        self.level_records = (
            dict(store.get("level_records").get("levels", {}))
            if store.exists("level_records") else {}
        )
        self.level = 1
        self.unlocked_level = (
            int(store.get("progress").get("unlocked", 1))
            if store.exists("progress") else 1
        )
        self.unlocked_level = max(1, min(100, self.unlocked_level))

        self.gravity = -1450
        self.speed = 320
        self.jump_power = 640

        self.left_pressed = False
        self.right_pressed = False

        self.reset_game()
        Clock.schedule_interval(self.update, 1 / 60)

    def reset_game(self):
        self.x_player = 90
        self.y_player = 75
        self.vy = 0
        self.grounded = True

        self.camera = 0
        self.score = 0
        self.lives = 3

        self.big = False
        self.star_time = 0
        self.invincible_time = 0

        self.finished = False
        self.game_over = False
        self.result_saved = False

        self.coins = [
            [340, 205], [390, 205], [570, 305],
            [900, 215], [1120, 325], [1500, 225],
            [1750, 325], [2150, 215], [2400, 315],
            [2700, 120]
        ]

        self.platforms = [
            (0, 0, 650, 75),
            (760, 0, 520, 75),
            (1380, 0, 510, 75),
            (1990, 0, 1010, 75),

            (300, 160, 140, 25),
            (520, 260, 150, 25),
            (850, 170, 150, 25),
            (1080, 280, 150, 25),
            (1450, 180, 150, 25),
            (1700, 280, 150, 25),
            (2100, 170, 150, 25),
            (2350, 270, 150, 25),
        ]

        self.blocks = [
            [350, 240, "coin", False],
            [550, 340, "mushroom", False],
            [920, 250, "coin", False],
            [1150, 360, "star", False],
            [1520, 260, "mushroom", False],
            [1780, 360, "coin", False],
            [2170, 250, "star", False],
            [2420, 350, "mushroom", False],
        ]

        self.items = []

        enemy_spots = [1000, 1650, 2250, 430, 850, 1450, 2050, 2600, 2780]
        enemy_count = min(3 + (self.level - 1) // 12, len(enemy_spots))
        self.enemies = []

        for index, enemy_x in enumerate(enemy_spots[:enemy_count]):
            patrol_left = max(80, enemy_x - 85)
            patrol_right = min(self.WORLD - 80, enemy_x + 85)
            direction = 1 if index % 2 == 0 else -1
            self.enemies.append([
                enemy_x, 75, direction, True, patrol_left, patrol_right
            ])

        level_rng = random.Random(self.level)

        for _ in range(min(2 + self.level // 10, 10)):
            coin_x = level_rng.randint(250, 2750)
            coin_y = level_rng.choice([125, 180, 220, 270, 310])
            self.coins.append([coin_x, coin_y])

        self.mushroom = []

    def add_score(self, amount):
        self.score += amount

        if self.score > self.best_score:
            self.best_score = self.score
            self.store.put("record", score=self.best_score)

    def stars_for_score(self, score):
        """Convert a completed level score into zero to three stars."""
        if score >= 3000:
            return 3
        if score >= 1500:
            return 2
        if score >= 500:
            return 1
        return 0

    def get_level_record(self, level):
        return self.level_records.get(str(int(level)), {})

    def save_level_result(self):
        """Save a level result only when its score beats the previous best."""
        key = str(self.level)
        previous = self.level_records.get(key)
        if previous is None or self.score > int(previous.get("score", -1)):
            self.level_records[key] = {
                "score": int(self.score),
                "stars": self.stars_for_score(self.score)
            }
            self.store.put("level_records", levels=self.level_records)
        return self.level_records.get(key, {})

    def restart(self):
        self.reset_game()

    def load_level(self, level):
        self.level = max(1, min(100, int(level)))
        self.reset_game()

    def jump(self):
        if self.grounded and not self.finished and not self.game_over:
            self.vy = self.jump_power
            self.grounded = False

    def player_height(self):
        return 95 if self.big else self.NORMAL_H

    def lose_life(self):
        if self.invincible_time > 0:
            return

        self.lives -= 1
        self.invincible_time = 1.5

        if self.lives <= 0:
            self.game_over = True
            self.finished = True
        else:
            self.x_player = max(80, self.x_player - 180)
            self.y_player = 75
            self.vy = 0
            self.grounded = True
            self.big = False

    def hit_block(self, block):
        if block[3]:
            return

        block[3] = True

        if block[2] == "coin":
            self.add_score(100)
            self.coins.append([block[0] + 12, block[1] + 55])

        elif block[2] == "mushroom":
            self.items.append([
                block[0] + 5,
                block[1] + 45,
                "mushroom"
            ])

        elif block[2] == "star":
            self.items.append([
                block[0] + 5,
                block[1] + 45,
                "star"
            ])

    def update(self, dt):
        if self.width <= 0 or self.height <= 0:
            return

        dt = min(dt, 0.033)

        if not self.finished:
            self.invincible_time = max(0, self.invincible_time - dt)
            self.star_time = max(0, self.star_time - dt)

            old_y = self.y_player
            old_top = old_y + self.player_height()

            if self.left_pressed:
                self.x_player -= self.speed * dt

            if self.right_pressed:
                self.x_player += self.speed * dt

            self.x_player = max(
                0, min(self.WORLD - self.PLAYER_W, self.x_player)
            )

            self.vy += self.gravity * dt
            self.y_player += self.vy * dt

            self.grounded = False
            height = self.player_height()

            for px, py, pw, ph in self.platforms:
                if (
                    self.x_player + self.PLAYER_W > px
                    and self.x_player < px + pw
                    and self.vy <= 0
                    and old_y >= py + ph - 5
                    and self.y_player <= py + ph
                ):
                    self.y_player = py + ph
                    self.vy = 0
                    self.grounded = True

            new_top = self.y_player + height

            if self.vy > 0:
                for block in self.blocks:
                    bx, by, kind, used = block

                    if (
                        not used
                        and self.x_player + self.PLAYER_W > bx
                        and self.x_player < bx + 42
                        and old_top <= by + 42
                        and new_top >= by
                    ):
                        self.y_player = by - height
                        self.vy = -80
                        self.hit_block(block)
                        break

            for enemy in self.enemies:
                ex, ey, direction, alive, patrol_left, patrol_right = enemy

                if not alive:
                    continue

                enemy_speed = 95 + min(self.level - 1, 40) * 2
                enemy[0] += direction * enemy_speed * dt

                if enemy[0] > patrol_right or enemy[0] < patrol_left:
                    enemy[2] *= -1

                horizontal = (
                    self.x_player + self.PLAYER_W > ex
                    and self.x_player < ex + 40
                )

                vertical = (
                    self.y_player < ey + 38
                    and self.y_player + height > ey
                )

                if horizontal and vertical:
                    if self.star_time > 0:
                        enemy[3] = False
                        self.add_score(200)

                    elif self.vy < 0 and old_y >= ey + 25:
                        enemy[3] = False
                        self.vy = 360
                        self.add_score(200)

                    else:
                        self.lose_life()

            remaining_items = []

            for item in self.items:
                ix, iy, kind = item

                if kind == "mushroom":
                    item[0] += 75 * dt

                close_x = abs(self.x_player + 19 - ix) < 35
                close_y = abs(self.y_player + height / 2 - iy) < 45

                if close_x and close_y:
                    if kind == "mushroom":
                        self.big = True
                        self.add_score(500)
                    else:
                        self.star_time = 8
                        self.add_score(1000)
                else:
                    remaining_items.append(item)

            self.items = remaining_items

            remaining_coins = []

            for coin in self.coins:
                cx, cy = coin

                if (
                    abs(self.x_player + 19 - cx) < 30
                    and abs(self.y_player + height / 2 - cy) < 40
                ):
                    self.add_score(100)
                else:
                    remaining_coins.append(coin)

            self.coins = remaining_coins

            if self.y_player < -150:
                self.lose_life()

            if self.x_player > 2880:
                self.finished = True

            self.camera = max(
                0,
                min(self.WORLD - self.width,
                    self.x_player - self.width * 0.38)
            )

        self.draw_game()

    def draw_game(self):
        self.canvas.clear()

        cam = self.camera
        w = self.width

        with self.canvas:
            Color(0.35, 0.72, 0.98, 1)
            Rectangle(pos=self.pos, size=self.size)

            for cx, cy in [(180, 430), (700, 500), (1300, 420),
                           (1900, 490), (2450, 430)]:
                sx = self.x + cx - cam * 0.35

                Color(1, 1, 1, 0.95)
                Ellipse(pos=(sx, self.y + cy), size=(75, 35))
                Ellipse(pos=(sx + 25, self.y + cy + 12), size=(55, 42))
                Ellipse(pos=(sx + 50, self.y + cy), size=(60, 30))

            Color(0.2, 0.68, 0.28, 1)

            for hx in range(0, self.WORLD, 350):
                Ellipse(
                    pos=(self.x + hx - cam * 0.65, self.y + 35),
                    size=(250, 150)
                )

            for px, py, pw, ph in self.platforms:
                sx = self.x + px - cam
                sy = self.y + py

                if sx + pw < self.x or sx > self.x + w:
                    continue

                Color(0.62, 0.30, 0.12, 1)
                Rectangle(pos=(sx, sy), size=(pw, ph))

                Color(0.18, 0.72, 0.18, 1)
                Rectangle(pos=(sx, sy + ph - 10), size=(pw, 10))

                Color(0.35, 0.15, 0.06, 1)
                for bx in range(int(sx), int(sx + pw), 45):
                    Line(points=[bx, sy + 3, bx, sy + ph - 10], width=1)

            for pipe_x in [650, 1285, 1895, 2540]:
                sx = self.x + pipe_x - cam

                if -100 < sx - self.x < w + 100:
                    Color(0.04, 0.48, 0.12, 1)
                    Rectangle(pos=(sx, self.y + 75), size=(65, 100))

                    Color(0.12, 0.75, 0.2, 1)
                    Rectangle(pos=(sx - 8, self.y + 160), size=(81, 20))

                    Color(0.02, 0.32, 0.07, 1)
                    Line(rectangle=(sx, self.y + 75, 65, 100), width=2)

            for bx, by, kind, used in self.blocks:
                sx = self.x + bx - cam
                sy = self.y + by

                if sx < self.x - 60 or sx > self.x + w + 60:
                    continue

                if used:
                    Color(0.48, 0.28, 0.12, 1)
                else:
                    Color(1, 0.62, 0.08, 1)

                Rectangle(pos=(sx, sy), size=(42, 42))

                Color(0.95, 0.85, 0.35, 1)
                Line(rectangle=(sx, sy, 42, 42), width=2)

                if not used:
                    Color(1, 1, 1, 1)
                    Line(points=[
                        sx + 13, sy + 27,
                        sx + 16, sy + 32,
                        sx + 25, sy + 32,
                        sx + 29, sy + 27,
                        sx + 25, sy + 22,
                        sx + 21, sy + 18,
                        sx + 21, sy + 13
                    ], width=2.5)
                    Ellipse(pos=(sx + 19, sy + 5), size=(5, 5))

            for cx, cy in self.coins:
                sx = self.x + cx - cam
                sy = self.y + cy

                Color(1, 0.78, 0.05, 1)
                Ellipse(pos=(sx, sy), size=(24, 32))

                Color(1, 0.95, 0.55, 1)
                Ellipse(pos=(sx + 7, sy + 5), size=(7, 22))

            for ix, iy, kind in self.items:
                sx = self.x + ix - cam
                sy = self.y + iy

                if kind == "mushroom":
                    Color(0.95, 0.15, 0.12, 1)
                    Ellipse(pos=(sx, sy + 10), size=(38, 27))
                    Color(1, 1, 1, 1)
                    Ellipse(pos=(sx + 8, sy + 22), size=(8, 8))
                    Ellipse(pos=(sx + 23, sy + 22), size=(8, 8))
                    Color(1, 0.85, 0.65, 1)
                    Rectangle(pos=(sx + 8, sy), size=(22, 15))
                else:
                    Color(1, 0.85, 0.05, 1)
                    Ellipse(pos=(sx, sy), size=(38, 38))
                    Color(1, 1, 1, 1)
                    Line(points=[
                        sx + 19, sy + 32,
                        sx + 24, sy + 22,
                        sx + 35, sy + 20,
                        sx + 27, sy + 13,
                        sx + 29, sy + 3,
                        sx + 19, sy + 9,
                        sx + 9, sy + 3,
                        sx + 11, sy + 13,
                        sx + 3, sy + 20,
                        sx + 14, sy + 22,
                        sx + 19, sy + 32
                    ], width=2)

            for ex, ey, direction, alive, patrol_left, patrol_right in self.enemies:
                if not alive:
                    continue

                sx = self.x + ex - cam
                sy = self.y + ey

                Color(0.55, 0.18, 0.12, 1)
                Ellipse(pos=(sx, sy), size=(40, 35))

                Color(1, 1, 1, 1)
                Ellipse(pos=(sx + 7, sy + 18), size=(9, 10))
                Ellipse(pos=(sx + 24, sy + 18), size=(9, 10))

                Color(0, 0, 0, 1)
                Ellipse(pos=(sx + 10, sy + 21), size=(4, 5))
                Ellipse(pos=(sx + 27, sy + 21), size=(4, 5))

            px = self.x + self.x_player - cam
            py = self.y + self.y_player
            ph = self.player_height()

            if self.star_time > 0:
                Color(1, 0.9, 0.1, 0.45)
                Ellipse(pos=(px - 12, py - 8), size=(65, ph + 25))

            Color(0.25, 0.09, 0.04, 1)
            RoundedRectangle(pos=(px - 3, py), size=(19, 11), radius=[4])
            RoundedRectangle(pos=(px + 21, py), size=(19, 11), radius=[4])

            Color(0.05, 0.25, 0.85, 1)
            Rectangle(pos=(px + 4, py + 10), size=(31, ph * 0.30))

            Color(0.9, 0.12, 0.08, 1)
            Rectangle(pos=(px + 2, py + ph * 0.38), size=(35, ph * 0.27))

            Color(1, 0.72, 0.48, 1)
            Ellipse(pos=(px + 5, py + ph * 0.65), size=(30, 28))

            Color(0.22, 0.10, 0.04, 1)
            Rectangle(pos=(px + 5, py + ph * 0.65 + 21), size=(30, 7))

            Color(0.12, 0.35, 0.85, 1)
            RoundedRectangle(
                pos=(px + 1, py + ph * 0.65 + 23),
                size=(37, 10),
                radius=[4]
            )

            Color(1, 1, 1, 1)
            Ellipse(pos=(px + 23, py + ph * 0.65 + 8), size=(6, 9))

            Color(0.05, 0.05, 0.05, 1)
            Ellipse(pos=(px + 26, py + ph * 0.65 + 10), size=(3, 5))

            gx = self.x + 2920 - cam
            Color(0.25, 0.2, 0.15, 1)
            Rectangle(pos=(gx, self.y + 75), size=(6, 220))

            Color(1, 0.85, 0.1, 1)
            Rectangle(pos=(gx + 6, self.y + 255), size=(55, 30))


class SuperMarioApp(App):
    def build(self):
        root = FloatLayout()

        score_path = os.path.join(self.user_data_dir, "scores.json")
        self.store = JsonStore(score_path)

        self.game = MarioGame(
            self.store,
            size_hint=(1, 1)
        )
        root.add_widget(self.game)

        def make_button(text, x, width, color):
            btn = Button(
                text=text,
                font_size=dp(27),
                size_hint=(width, 0.14),
                pos_hint={"x": x, "y": 0.03},
                background_normal="",
                background_color=color
            )
            return btn

        left = make_button(
            "◀", 0.02, 0.15, (0.05, 0.15, 0.4, 0.85)
        )
        left.bind(
            on_press=lambda *_: setattr(self.game, "left_pressed", True)
        )
        left.bind(
            on_release=lambda *_: setattr(self.game, "left_pressed", False)
        )
        root.add_widget(left)

        right = make_button(
            "▶", 0.19, 0.15, (0.05, 0.15, 0.4, 0.85)
        )
        right.bind(
            on_press=lambda *_: setattr(self.game, "right_pressed", True)
        )
        right.bind(
            on_release=lambda *_: setattr(self.game, "right_pressed", False)
        )
        root.add_widget(right)

        jump = make_button(
            "Jump", 0.78, 0.19, (0.1, 0.55, 0.2, 0.9)
        )
        jump.bind(on_press=lambda *_: self.game.jump())
        root.add_widget(jump)

        self.info = Label(
            text="",
            font_size=dp(17),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.62, 0.09),
            pos_hint={"x": 0.19, "top": 0.89}
        )
        root.add_widget(self.info)

        self.message = Label(
            text="",
            font_size=dp(25),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(0.6, 0.14),
            pos_hint={"center_x": 0.5, "center_y": 0.56}
        )
        root.add_widget(self.message)

        restart = Button(
            text="Restart",
            font_size=dp(15),
            size_hint=(0.17, 0.08),
            pos_hint={"right": 0.98, "top": 0.98},
            background_normal="",
            background_color=(0.1, 0.2, 0.5, 0.85)
        )
        restart.bind(on_press=lambda *_: self.restart_game())
        root.add_widget(restart)

        self.level_label = Label(
            text="LEVEL 1 / 100",
            font_size=dp(16),
            bold=True,
            color=(1, 1, 1, 0.8),
            size_hint=(0.24, 0.07),
            pos_hint={"center_x": 0.5, "top": 0.98}
        )
        root.add_widget(self.level_label)

        self.level_stars_label = Label(
            text="STARS: ☆☆☆",
            font_size=dp(14),
            bold=True,
            color=(1, 0.9, 0.25, 1),
            size_hint=(0.42, 0.05),
            pos_hint={"center_x": 0.5, "top": 0.91}
        )
        root.add_widget(self.level_stars_label)

        self.previous_level_button = Button(
            text="◀",
            font_size=dp(19),
            size_hint=(0.07, 0.065),
            pos_hint={"right": 0.36, "top": 0.98},
            background_normal="",
            background_color=(0.08, 0.12, 0.25, 0.32),
            color=(1, 1, 1, 0.55)
        )
        self.previous_level_button.bind(
            on_press=lambda *_: self.change_level(-1)
        )
        root.add_widget(self.previous_level_button)

        self.next_level_button = Button(
            text="▶",
            font_size=dp(19),
            size_hint=(0.07, 0.065),
            pos_hint={"x": 0.57, "top": 0.98},
            background_normal="",
            background_color=(0.08, 0.12, 0.25, 0.32),
            color=(1, 1, 1, 0.55)
        )
        self.next_level_button.bind(
            on_press=lambda *_: self.change_level(1)
        )
        root.add_widget(self.next_level_button)

        Clock.schedule_interval(self.update_ui, 0.1)
        return root

    def restart_game(self):
        self.game.restart()
        self.message.text = ""

    def change_level(self, direction):
        target = self.game.level + direction
        if 1 <= target <= self.game.unlocked_level:
            self.game.load_level(target)
            self.message.text = ""

    def update_ui(self, dt):
        g = self.game

        self.info.text = (
            f"Score: {g.score}     "
            f"Best: {g.best_score}     "
            f"Lives: {g.lives}"
        )
        self.level_label.text = f"LEVEL {g.level} / 100"

        level_record = g.get_level_record(g.level)
        saved_stars = max(0, min(3, int(level_record.get("stars", 0))))
        saved_score = int(level_record.get("score", 0))
        star_display = "★" * saved_stars + "☆" * (3 - saved_stars)
        self.level_stars_label.text = f"STARS: {star_display}   BEST: {saved_score}"

        previous_available = g.level > 1
        next_available = g.level < g.unlocked_level

        self.previous_level_button.disabled = not previous_available
        self.previous_level_button.opacity = 1 if previous_available else 0.45

        self.next_level_button.disabled = not next_available
        self.next_level_button.opacity = 1 if next_available else 0.45

        if g.finished:
            if g.game_over:
                self.message.text = "GAME OVER"
            else:
                if not g.result_saved:
                    g.save_level_result()
                    g.result_saved = True

                if g.level < 100:
                    self.message.text = "LEVEL COMPLETE!"

                    if g.unlocked_level < g.level + 1:
                        g.unlocked_level = g.level + 1
                        self.store.put("progress", unlocked=g.unlocked_level)
                else:
                    self.message.text = "YOU WIN! ALL 100 LEVELS COMPLETE!"

    def on_stop(self):
        self.store.put("record", score=self.game.best_score)


if __name__ == "__main__":
    SuperMarioApp().run()
