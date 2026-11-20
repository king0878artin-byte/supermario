import os
import random
import math
import struct
import wave

from kivy.core.audio import SoundLoader

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.storage.jsonstore import JsonStore
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
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
        self.paused = False
        self.anim_time = 0.0
        self.pipe_cooldown = 0.0
        self.sound_callback = None

        self.coins = [
            [340, 205], [390, 205], [570, 305],
            [900, 215], [1120, 325], [1500, 225],
            [1750, 325], [2150, 215], [2400, 315],
            [2700, 120]
        ]

        self.platforms = [
            (0, 0, 650, 75), (760, 0, 520, 75),
            (1380, 0, 510, 75), (1990, 0, 1010, 75)
        ]
        layouts = [
            [(300,160,140,25),(520,260,150,25),(850,170,150,25),(1080,280,150,25),(1450,180,150,25),(1700,280,150,25),(2100,170,150,25),(2350,270,150,25)],
            [(230,190,120,25),(420,300,130,25),(700,210,150,25),(930,330,130,25),(1190,190,140,25),(1510,300,140,25),(1800,200,150,25),(2150,310,140,25),(2450,190,130,25)],
            [(260,270,150,25),(510,170,130,25),(780,300,150,25),(1050,190,130,25),(1320,310,150,25),(1600,190,140,25),(1880,300,140,25),(2180,180,150,25),(2460,300,140,25)],
            [(320,210,180,25),(620,330,110,25),(860,160,180,25),(1160,280,110,25),(1420,210,180,25),(1740,330,110,25),(1980,160,180,25),(2300,280,110,25),(2570,190,130,25)]
        ]
        self.platforms.extend(layouts[(self.level - 1) % len(layouts)])
        self.theme = (self.level - 1) % 4
        self.pipes = [
            [650, 75, 65, 100], [1285, 75, 65, 100],
            [1895, 75, 65, 100], [2540, 75, 65, 100]
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

        turtle_spots = [720, 1380, 1980, 2500]
        self.turtles = []
        for index, tx in enumerate(turtle_spots[:min(1 + self.level // 8, 4)]):
            self.turtles.append([tx, 75, 1 if index % 2 == 0 else -1, True, tx - 90, tx + 90, False])

        self.boss = None
        if self.level % 10 == 0:
            self.boss = {"x": 2700, "y": 75, "direction": -1, "hp": 3, "alive": True}

    def play_sound(self, name):
        if self.sound_callback:
            self.sound_callback(name)

    def enter_pipe(self):
        if self.finished or self.paused or self.pipe_cooldown > 0 or not self.grounded:
            return
        center = self.x_player + self.PLAYER_W / 2
        for index, pipe in enumerate(self.pipes):
            px, py, pw, ph = pipe
            if px - 28 <= center <= px + pw + 28 and abs(self.y_player - py) < 18:
                destination = self.pipes[(index + 1) % len(self.pipes)][0] + 85
                self.x_player = min(self.WORLD - 100, destination)
                self.y_player = 75
                self.vy = 0
                self.camera = max(0, min(self.WORLD - self.width, self.x_player - self.width * 0.38))
                self.pipe_cooldown = 1.0
                self.play_sound("pipe")
                return

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
            self.play_sound("jump")

    def player_height(self):
        return 95 if self.big else self.NORMAL_H

    def lose_life(self):
        if self.invincible_time > 0:
            return

        self.lives -= 1
        self.invincible_time = 1.5
        self.play_sound("hurt")

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

        if not self.finished and not self.paused:
            self.anim_time += dt
            self.pipe_cooldown = max(0.0, self.pipe_cooldown - dt)
            self.invincible_time = max(0, self.invincible_time - dt)
            self.star_time = max(0, self.star_time - dt)

            old_y = self.y_player
            old_x = self.x_player
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

            # Solid pipe bodies and walkable pipe rims.
            for pipe in self.pipes:
                px, py, pw, ph = pipe
                horizontal_overlap = self.x_player + self.PLAYER_W > px and self.x_player < px + pw
                if horizontal_overlap and self.vy <= 0 and old_y >= py + ph - 8 and self.y_player <= py + ph:
                    self.y_player = py + ph
                    self.vy = 0
                    self.grounded = True
                elif horizontal_overlap and self.y_player < py + ph and self.y_player + height > py:
                    if old_x + self.PLAYER_W <= px:
                        self.x_player = px - self.PLAYER_W
                    elif old_x >= px + pw:
                        self.x_player = px + pw

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
                        self.play_sound("stomp")

                    elif self.vy < 0 and old_y >= ey + 25:
                        enemy[3] = False
                        self.vy = 360
                        self.add_score(200)
                        self.play_sound("stomp")

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
                    self.play_sound("coin")
                else:
                    remaining_coins.append(coin)

            self.coins = remaining_coins

            if self.y_player < -150:
                self.lose_life()

            # Turtle patrols and shell stomps.
            for turtle in self.turtles:
                tx, ty, direction, alive, left_edge, right_edge, shelled = turtle
                if not alive:
                    continue
                turtle[0] += direction * (65 if shelled else 82 + min(self.level, 30)) * dt
                if turtle[0] < left_edge or turtle[0] > right_edge:
                    turtle[2] *= -1
                overlap_x = self.x_player + self.PLAYER_W > turtle[0] and self.x_player < turtle[0] + 46
                overlap_y = self.y_player < ty + 42 and self.y_player + height > ty
                if overlap_x and overlap_y:
                    if self.star_time > 0:
                        turtle[3] = False
                        self.add_score(350)
                    elif self.vy < 0 and old_y >= ty + 25:
                        if not shelled:
                            turtle[6] = True
                            self.vy = 390
                            self.add_score(250)
                            self.play_sound("stomp")
                        else:
                            turtle[3] = False
                            self.add_score(400)
                    else:
                        self.lose_life()

            if self.boss and self.boss["alive"]:
                boss = self.boss
                boss["x"] += boss["direction"] * (55 + self.level) * dt
                if boss["x"] < 2550 or boss["x"] > 2800:
                    boss["direction"] *= -1
                boss_overlap = (self.x_player + self.PLAYER_W > boss["x"] and self.x_player < boss["x"] + 76 and self.y_player < boss["y"] + 72 and self.y_player + height > boss["y"])
                if boss_overlap:
                    if self.vy < 0 and old_y >= boss["y"] + 48:
                        boss["hp"] -= 1
                        self.vy = 470
                        self.add_score(500)
                        self.play_sound("boss")
                        if boss["hp"] <= 0:
                            boss["alive"] = False
                            self.add_score(1500)
                    elif self.star_time > 0:
                        boss["hp"] -= 1
                        if boss["hp"] <= 0:
                            boss["alive"] = False
                        self.add_score(250)
                    else:
                        self.lose_life()

            if self.x_player > 2880 and not (self.boss and self.boss["alive"]):
                self.finished = True
                self.play_sound("win")

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

        sky_colors = [
            (0.35, 0.72, 0.98), (0.95, 0.48, 0.30),
            (0.08, 0.12, 0.28), (0.58, 0.82, 0.94)
        ]
        hill_colors = [
            (0.20, 0.68, 0.28), (0.42, 0.28, 0.25),
            (0.10, 0.22, 0.30), (0.68, 0.82, 0.76)
        ]
        with self.canvas:
            Color(*sky_colors[self.theme], 1)
            Rectangle(pos=self.pos, size=self.size)

            for cx, cy in [(180, 430), (700, 500), (1300, 420),
                           (1900, 490), (2450, 430)]:
                sx = self.x + cx - cam * 0.35

                Color(1, 1, 1, 0.95)
                Ellipse(pos=(sx, self.y + cy), size=(75, 35))
                Ellipse(pos=(sx + 25, self.y + cy + 12), size=(55, 42))
                Ellipse(pos=(sx + 50, self.y + cy), size=(60, 30))

            Color(*hill_colors[self.theme], 1)

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

            for pipe_x, pipe_y, pipe_w, pipe_h in self.pipes:
                sx = self.x + pipe_x - cam
                if -100 < sx - self.x < w + 100:
                    Color(0.04, 0.48, 0.12, 1)
                    Rectangle(pos=(sx, self.y + pipe_y), size=(pipe_w, pipe_h))
                    Color(0.12, 0.75, 0.2, 1)
                    Rectangle(pos=(sx - 8, self.y + pipe_y + pipe_h - 15), size=(pipe_w + 16, 20))
                    Color(0.02, 0.32, 0.07, 1)
                    Line(rectangle=(sx, self.y + pipe_y, pipe_w, pipe_h), width=2)

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

            for tx, ty, direction, alive, left_edge, right_edge, shelled in self.turtles:
                if alive:
                    sx = self.x + tx - cam
                    sy = self.y + ty
                    Color(0.12, 0.48, 0.20, 1)
                    Ellipse(pos=(sx, sy + 5), size=(46, 34))
                    Color(0.10, 0.28, 0.12, 1)
                    Ellipse(pos=(sx + 5, sy + 2), size=(36, 27))
                    Color(0.9, 0.78, 0.48, 1)
                    Ellipse(pos=(sx + (31 if direction > 0 else -3), sy + 13), size=(18, 17))
                    Color(1, 1, 1, 1)
                    Ellipse(pos=(sx + (40 if direction > 0 else 1), sy + 22), size=(5, 6))
                    Color(0.05, 0.05, 0.05, 1)
                    Ellipse(pos=(sx + (42 if direction > 0 else 2), sy + 24), size=(2, 3))
                    if shelled:
                        Color(0.95, 0.8, 0.2, 1)
                        Line(ellipse=(sx + 7, sy + 7, 31, 26), width=1.5)

            if self.boss and self.boss["alive"]:
                bx = self.x + self.boss["x"] - cam
                by = self.y + self.boss["y"]
                Color(0.55, 0.12, 0.08, 1)
                Ellipse(pos=(bx, by), size=(76, 66))
                Color(0.18, 0.34, 0.12, 1)
                Ellipse(pos=(bx + 10, by + 25), size=(56, 37))
                Color(0.95, 0.72, 0.25, 1)
                Ellipse(pos=(bx + 52, by + 32), size=(23, 20))
                Color(1, 1, 1, 1)
                Ellipse(pos=(bx + 58, by + 44), size=(7, 8))
                Color(0.05, 0.05, 0.05, 1)
                Ellipse(pos=(bx + 61, by + 47), size=(3, 4))
                Color(1, 0.2, 0.12, 1)
                for spike_x in (bx + 16, bx + 34, bx + 50):
                    Line(points=[spike_x, by + 57, spike_x + 8, by + 77, spike_x + 15, by + 57], width=2)
                Color(1, 1, 1, 1)
                Line(points=[bx + 5, by + 82, bx + 76, by + 82], width=3)
                Color(0.9, 0.1, 0.08, 1)
                Rectangle(pos=(bx + 5, by + 82), size=(71 * self.boss["hp"] / 3, 5))

            px = self.x + self.x_player - cam
            py = self.y + self.y_player
            ph = self.player_height()
            walking = self.left_pressed or self.right_pressed
            step = math.sin(self.anim_time * 16) * 5 if walking and self.grounded else 0

            if self.star_time > 0:
                Color(1, 0.9, 0.1, 0.45)
                Ellipse(pos=(px - 12, py - 8), size=(65, ph + 25))

            Color(0.25, 0.09, 0.04, 1)
            RoundedRectangle(pos=(px - 3, py + max(0, step)), size=(19, 11), radius=[4])
            RoundedRectangle(pos=(px + 21, py + max(0, -step)), size=(19, 11), radius=[4])

            Color(0.05, 0.25, 0.85, 1)
            Rectangle(pos=(px + 4, py + 10), size=(31, ph * 0.30))

            Color(0.9, 0.12, 0.08, 1)
            Rectangle(pos=(px + 2, py + ph * 0.38), size=(35, ph * 0.27))

            Color(1, 0.72, 0.48, 1)
            Ellipse(pos=(px + 5, py + ph * 0.65), size=(30, 28))

            Color(0.22, 0.10, 0.04, 1)
            Rectangle(pos=(px + 5, py + ph * 0.65 + 21), size=(30, 7))
            Color(0.95, 0.12, 0.08, 1)
            Ellipse(pos=(px + 1, py + ph * 0.65 + 22), size=(38, 18))

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
        score_path = os.path.join(self.user_data_dir, "scores.json")
        self.store = JsonStore(score_path)
        self.sound_enabled = True
        self.sounds = {}
        self.music = None
        self.prepare_audio()

        root = FloatLayout()
        self.game = MarioGame(self.store, size_hint=(1, 1))
        self.game.sound_callback = self.play_sound
        root.add_widget(self.game)

        def make_button(text, x, width, color, y=0.03):
            return Button(
                text=text, font_size=dp(22),
                size_hint=(width, 0.13), pos_hint={"x": x, "y": y},
                background_normal="", background_color=color,
                color=(1, 1, 1, 1), bold=True
            )

        left = make_button("◀", 0.02, 0.15, (0.05, 0.15, 0.4, 0.88))
        left.bind(on_press=lambda *_: setattr(self.game, "left_pressed", True))
        left.bind(on_release=lambda *_: setattr(self.game, "left_pressed", False))
        root.add_widget(left)

        right = make_button("▶", 0.19, 0.15, (0.05, 0.15, 0.4, 0.88))
        right.bind(on_press=lambda *_: setattr(self.game, "right_pressed", True))
        right.bind(on_release=lambda *_: setattr(self.game, "right_pressed", False))
        root.add_widget(right)

        jump = make_button("JUMP", 0.78, 0.19, (0.1, 0.55, 0.2, 0.92))
        jump.bind(on_press=lambda *_: self.game.jump())
        root.add_widget(jump)

        pipe = make_button("DOWN / PIPE", 0.58, 0.18, (0.05, 0.42, 0.42, 0.92), y=0.03)
        pipe.font_size = dp(14)
        pipe.bind(on_press=lambda *_: self.game.enter_pipe())
        root.add_widget(pipe)

        self.info = Label(
            text="", font_size=dp(17), bold=True, color=(1, 1, 1, 1),
            size_hint=(0.62, 0.09), pos_hint={"x": 0.19, "top": 0.89}
        )
        root.add_widget(self.info)

        self.message = Label(
            text="", font_size=dp(25), bold=True, color=(1, 1, 1, 1),
            size_hint=(0.6, 0.14), pos_hint={"center_x": 0.5, "center_y": 0.56}
        )
        root.add_widget(self.message)

        restart = Button(
            text="Restart", font_size=dp(14), size_hint=(0.13, 0.07),
            pos_hint={"right": 0.98, "top": 0.98},
            background_normal="", background_color=(0.1, 0.2, 0.5, 0.85)
        )
        restart.bind(on_press=lambda *_: self.restart_game())
        root.add_widget(restart)

        self.level_label = Label(
            text="LEVEL 1 / 100", font_size=dp(16), bold=True,
            color=(1, 1, 1, 0.8), size_hint=(0.24, 0.07),
            pos_hint={"center_x": 0.5, "top": 0.98}
        )
        root.add_widget(self.level_label)

        self.level_stars_label = Label(
            text="STARS: ☆☆☆", font_size=dp(14), bold=True,
            color=(1, 0.9, 0.25, 1), size_hint=(0.42, 0.05),
            pos_hint={"center_x": 0.5, "top": 0.91}
        )
        root.add_widget(self.level_stars_label)

        self.previous_level_button = Button(
            text="◀", font_size=dp(19), size_hint=(0.07, 0.065),
            pos_hint={"right": 0.36, "top": 0.98},
            background_normal="", background_color=(0.08, 0.12, 0.25, 0.32),
            color=(1, 1, 1, 0.55)
        )
        self.previous_level_button.bind(on_press=lambda *_: self.change_level(-1))
        root.add_widget(self.previous_level_button)

        self.next_level_button = Button(
            text="▶", font_size=dp(19), size_hint=(0.07, 0.065),
            pos_hint={"x": 0.57, "top": 0.98},
            background_normal="", background_color=(0.08, 0.12, 0.25, 0.32),
            color=(1, 1, 1, 0.55)
        )
        self.next_level_button.bind(on_press=lambda *_: self.change_level(1))
        root.add_widget(self.next_level_button)

        menu_button = Button(
            text="MENU", font_size=dp(13), size_hint=(0.13, 0.07),
            pos_hint={"x": 0.02, "top": 0.98},
            background_normal="", background_color=(0.08, 0.12, 0.25, 0.8)
        )
        menu_button.bind(on_press=lambda *_: self.show_main_menu())
        root.add_widget(menu_button)

        self.root_layout = root
        self.menu_panel = self.make_panel()
        root.add_widget(self.menu_panel)
        self.build_main_menu()
        self.level_panel = self.make_panel()
        root.add_widget(self.level_panel)
        self.build_level_select()
        self.show_main_menu()

        Clock.schedule_interval(self.update_ui, 0.1)
        return root

    def make_panel(self):
        panel = FloatLayout(size_hint=(1, 1))
        with panel.canvas.before:
            Color(0.025, 0.045, 0.10, 0.96)
            panel.bg_rect = Rectangle(pos=panel.pos, size=panel.size)
        panel.bind(pos=lambda obj, value: setattr(obj.bg_rect, "pos", value))
        panel.bind(size=lambda obj, value: setattr(obj.bg_rect, "size", value))
        return panel

    def build_main_menu(self):
        self.menu_panel.clear_widgets()
        title = Label(
            text="SUPER MARIO", font_size=dp(38), bold=True,
            color=(1, 0.82, 0.18, 1), size_hint=(0.8, 0.2),
            pos_hint={"center_x": 0.5, "top": 0.94}
        )
        subtitle = Label(
            text="100 LEVELS  •  3-STAR CHALLENGE",
            font_size=dp(15), color=(0.82, 0.9, 1, 1),
            size_hint=(0.8, 0.08), pos_hint={"center_x": 0.5, "top": 0.76}
        )
        self.menu_panel.add_widget(title)
        self.menu_panel.add_widget(subtitle)

        start = Button(
            text="PLAY", font_size=dp(23), bold=True,
            size_hint=(0.52, 0.13), pos_hint={"center_x": 0.5, "center_y": 0.58},
            background_normal="", background_color=(0.12, 0.58, 0.22, 1)
        )
        start.bind(on_press=lambda *_: self.start_level(self.game.level))
        self.menu_panel.add_widget(start)

        levels = Button(
            text="LEVEL SELECT", font_size=dp(19), bold=True,
            size_hint=(0.52, 0.12), pos_hint={"center_x": 0.5, "center_y": 0.42},
            background_normal="", background_color=(0.12, 0.30, 0.68, 1)
        )
        levels.bind(on_press=lambda *_: self.show_level_select())
        self.menu_panel.add_widget(levels)

        self.sound_button = Button(
            text="SOUND: ON", font_size=dp(15),
            size_hint=(0.35, 0.09), pos_hint={"center_x": 0.5, "center_y": 0.27},
            background_normal="", background_color=(0.22, 0.24, 0.32, 1)
        )
        self.sound_button.bind(on_press=lambda *_: self.toggle_sound())
        self.menu_panel.add_widget(self.sound_button)

        best = Label(
            text=f"BEST SCORE: {self.game.best_score}",
            font_size=dp(13), color=(0.8, 0.85, 0.95, 1),
            size_hint=(0.7, 0.06), pos_hint={"center_x": 0.5, "y": 0.04}
        )
        self.menu_panel.add_widget(best)

    def build_level_select(self):
        self.level_panel.clear_widgets()
        title = Label(
            text="SELECT LEVEL", font_size=dp(27), bold=True,
            color=(1, 0.85, 0.25, 1), size_hint=(0.8, 0.13),
            pos_hint={"center_x": 0.5, "top": 0.98}
        )
        self.level_panel.add_widget(title)

        back = Button(
            text="BACK", font_size=dp(15), size_hint=(0.2, 0.08),
            pos_hint={"x": 0.04, "y": 0.025},
            background_normal="", background_color=(0.25, 0.28, 0.38, 1)
        )
        back.bind(on_press=lambda *_: self.show_main_menu())
        self.level_panel.add_widget(back)

        scroll = ScrollView(
            size_hint=(0.9, 0.72), pos_hint={"center_x": 0.5, "y": 0.14},
            do_scroll_x=False
        )
        grid = GridLayout(
            cols=5, spacing=dp(7), padding=dp(7),
            size_hint_y=None
        )
        grid.bind(minimum_height=grid.setter("height"))
        self.level_buttons = []
        for level in range(1, 101):
            record = self.game.get_level_record(level)
            stars = max(0, min(3, int(record.get("stars", 0))))
            star_text = "★" * stars + "☆" * (3 - stars)
            unlocked = level <= self.game.unlocked_level
            button = Button(
                text=f"{level}\n{star_text}",
                font_size=dp(13), bold=True,
                size_hint_y=None, height=dp(62),
                disabled=not unlocked,
                opacity=1 if unlocked else 0.38,
                background_normal="",
                background_color=(0.12, 0.42, 0.25, 1) if unlocked else (0.18, 0.2, 0.25, 1)
            )
            button.bind(on_press=lambda instance, n=level: self.start_level(n))
            grid.add_widget(button)
            self.level_buttons.append(button)
        scroll.add_widget(grid)
        self.level_panel.add_widget(scroll)

    def refresh_level_grid(self):
        if not hasattr(self, "level_buttons"):
            return
        for level, button in enumerate(self.level_buttons, 1):
            record = self.game.get_level_record(level)
            stars = max(0, min(3, int(record.get("stars", 0))))
            unlocked = level <= self.game.unlocked_level
            button.text = f"{level}\n{'★' * stars}{'☆' * (3 - stars)}"
            button.disabled = not unlocked
            button.opacity = 1 if unlocked else 0.38
            button.background_color = (
                (0.12, 0.42, 0.25, 1) if unlocked
                else (0.18, 0.2, 0.25, 1)
            )

    def show_main_menu(self):
        self.game.paused = True
        self.menu_panel.opacity = 1
        self.menu_panel.disabled = False
        self.level_panel.opacity = 0
        self.level_panel.disabled = True
        self.refresh_level_grid()

    def show_level_select(self):
        self.refresh_level_grid()
        self.menu_panel.opacity = 0
        self.menu_panel.disabled = True
        self.level_panel.opacity = 1
        self.level_panel.disabled = False
        self.game.paused = True

    def start_level(self, level):
        self.game.load_level(level)
        self.game.paused = False
        self.message.text = ""
        self.menu_panel.opacity = 0
        self.menu_panel.disabled = True
        self.level_panel.opacity = 0
        self.level_panel.disabled = True

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.sound_button.text = "SOUND: ON" if self.sound_enabled else "SOUND: OFF"
        if self.music:
            if self.sound_enabled:
                self.music.play()
            else:
                self.music.stop()

    def _write_wave(self, path, notes):
        sample_rate = 22050
        frames = bytearray()
        for frequency, duration in notes:
            count = int(sample_rate * duration)
            for i in range(count):
                if frequency <= 0:
                    sample = 0
                else:
                    t = i / sample_rate
                    fade = min(1.0, i / 180, (count - i) / 250)
                    sample = int(6500 * fade * math.sin(2 * math.pi * frequency * t))
                frames.extend(struct.pack("<h", sample))
        with wave.open(path, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(frames)

    def prepare_audio(self):
        audio_dir = os.path.join(self.user_data_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        melodies = {
            "jump": [(660, 0.07), (880, 0.09)],
            "coin": [(990, 0.06), (1320, 0.12)],
            "stomp": [(180, 0.08), (110, 0.10)],
            "hurt": [(300, 0.12), (180, 0.18)],
            "pipe": [(440, 0.12), (330, 0.12), (220, 0.16)],
            "boss": [(180, 0.08), (260, 0.08), (140, 0.16)],
            "win": [(523, 0.12), (659, 0.12), (784, 0.12), (1046, 0.24)],
            "music": [
                (523, 0.16), (659, 0.16), (784, 0.16), (659, 0.16),
                (587, 0.16), (698, 0.16), (880, 0.16), (698, 0.16),
                (523, 0.16), (659, 0.16), (784, 0.16), (1046, 0.24),
                (784, 0.16), (659, 0.16), (587, 0.16), (494, 0.24)
            ]
        }
        for name, notes in melodies.items():
            path = os.path.join(audio_dir, name + ".wav")
            try:
                if not os.path.exists(path):
                    self._write_wave(path, notes)
                sound = SoundLoader.load(path)
                if sound:
                    if name == "music":
                        sound.loop = True
                        sound.volume = 0.16
                        self.music = sound
                    else:
                        sound.volume = 0.55
                        self.sounds[name] = sound
            except Exception:
                continue
        if self.music:
            self.music.play()

    def play_sound(self, name):
        if not self.sound_enabled:
            return
        sound = self.sounds.get(name)
        if sound:
            try:
                sound.stop()
                sound.play()
            except Exception:
                pass

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
            f"Score: {g.score}     Best: {g.best_score}     Lives: {g.lives}"
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
                    self.refresh_level_grid()
                if g.level < 100:
                    self.message.text = "LEVEL COMPLETE!"
                    if g.unlocked_level < g.level + 1:
                        g.unlocked_level = g.level + 1
                        self.store.put("progress", unlocked=g.unlocked_level)
                        self.refresh_level_grid()
                else:
                    self.message.text = "YOU WIN! ALL 100 LEVELS COMPLETE!"

    def on_stop(self):
        if getattr(self, "music", None):
            self.music.stop()
        if hasattr(self, "game"):
            self.store.put("record", score=self.game.best_score)


if __name__ == "__main__":
    SuperMarioApp().run()
