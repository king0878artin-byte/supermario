
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Ellipse

Window.clearcolor = (0.35, 0.72, 1, 1)


class Game(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.world_width = 2800
        self.player_x = 80
        self.player_y = 70
        self.player_w = 36
        self.player_h = 52

        self.vy = 0
        self.speed = 260
        self.gravity = 1050
        self.jump_power = 520
        self.grounded = True

        self.left = False
        self.right = False
        self.camera = 0

        self.score = 0
        self.lives = 3
        self.finished = False
        self.message = "به خط پایان برس!"

        self.platforms = [
            (0, 0, 700, 70),
            (780, 0, 500, 70),
            (1380, 0, 500, 70),
            (1980, 0, 820, 70),
            (350, 145, 130, 22),
            (570, 220, 130, 22),
            (900, 150, 150, 22),
            (1150, 235, 140, 22),
            (1500, 160, 150, 22),
            (1750, 240, 150, 22),
            (2150, 170, 150, 22),
        ]

        self.initial_coins = [
            [390, 185], [610, 260], [950, 195],
            [1200, 275], [1550, 205], [1800, 280],
            [2200, 215], [2400, 110]
        ]

        self.coins = [c[:] for c in self.initial_coins]

        self.enemy_x = 850
        self.enemy_dir = 1
        self.enemy_alive = True

        self.bind(pos=self.draw, size=self.draw)
        Clock.schedule_interval(self.update, 1 / 60)

    def move_left(self, value):
        self.left = value

    def move_right(self, value):
        self.right = value

    def jump(self):
        if self.grounded and not self.finished:
            self.vy = self.jump_power
            self.grounded = False

    def update_score(self):
        if hasattr(self, "score_callback"):
            self.score_callback(self.score, self.lives)

    def end_game(self, message):
        self.finished = True
        self.message = message

        if hasattr(self, "end_callback"):
            self.end_callback(message)

    def lose_life(self):
        self.lives -= 1

        if self.lives <= 0:
            self.end_game("بازی تمام شد!")
        else:
            self.player_x = max(80, self.player_x - 150)
            self.player_y = 70
            self.vy = 0
            self.grounded = True

        self.update_score()

    def restart(self):
        self.player_x = 80
        self.player_y = 70
        self.vy = 0
        self.camera = 0

        self.score = 0
        self.lives = 3
        self.finished = False
        self.enemy_alive = True
        self.enemy_x = 850
        self.enemy_dir = 1

        self.coins = [c[:] for c in self.initial_coins]

        self.grounded = True
        self.left = False
        self.right = False
        self.message = "به خط پایان برس!"

        self.update_score()

        if hasattr(self, "end_callback"):
            self.end_callback(self.message)

        self.draw()

    def update(self, dt):
        if self.finished or self.width <= 0:
            return

        dt = min(dt, 0.04)

        if self.left:
            self.player_x -= self.speed * dt

        if self.right:
            self.player_x += self.speed * dt

        self.player_x = max(
            0,
            min(self.player_x, self.world_width - self.player_w)
        )

        old_y = self.player_y

        self.vy -= self.gravity * dt
        self.player_y += self.vy * dt
        self.grounded = False

        # برخورد با سکو هنگام پایین آمدن
        if self.vy <= 0:
            for px, py, pw, ph in self.platforms:
                horizontal = (
                    self.player_x + self.player_w > px
                    and self.player_x < px + pw
                )

                crossed = (
                    old_y >= py + ph
                    and self.player_y <= py + ph
                )

                if horizontal and crossed:
                    self.player_y = py + ph
                    self.vy = 0
                    self.grounded = True
                    break

        # سقوط
        if self.player_y < -100:
            self.lose_life()
            self.draw()
            return

        # جمع‌آوری سکه
        for coin in self.coins[:]:
            cx, cy = coin

            if (
                abs(self.player_x + self.player_w / 2 - cx) < 28
                and abs(self.player_y + self.player_h / 2 - cy) < 35
            ):
                self.coins.remove(coin)
                self.score += 10
                self.update_score()

        # حرکت دشمن
        if self.enemy_alive:
            self.enemy_x += self.enemy_dir * 100 * dt

            if self.enemy_x > 1100 or self.enemy_x < 800:
                self.enemy_dir *= -1

            hit = (
                self.player_x + self.player_w > self.enemy_x
                and self.player_x < self.enemy_x + 42
                and self.player_y + self.player_h > 70
                and self.player_y < 108
            )

            if hit:
                if self.vy < 0 and old_y >= 108:
                    self.enemy_alive = False
                    self.vy = self.jump_power * 0.55
                else:
                    self.lose_life()

                    if self.finished:
                        self.draw()
                        return

        # دوربین
        target = self.player_x - self.width * .35

        self.camera = max(
            0,
            min(target, self.world_width - self.width)
        )

        # پایان مرحله
        if self.player_x >= self.world_width - 100:
            self.end_game("مرحله را بردی!")

        self.draw()

    def draw(self, *args):
        self.canvas.clear()

        if self.width <= 0 or self.height <= 0:
            return

        floor_y = self.y + dp(125)

        with self.canvas:
            # آسمان
            Color(.35, .72, 1, 1)
            Rectangle(pos=self.pos, size=self.size)

            # ابرها
            Color(1, 1, 1, 1)

            for x in (150, 550, 950, 1400, 1900, 2400):
                sx = self.x + x - self.camera * .45

                Ellipse(
                    pos=(sx, self.y + self.height * .75),
                    size=(dp(90), dp(32))
                )

            # تپه‌ها
            Color(.25, .65, .30, 1)

            for x in (250, 850, 1500, 2150):
                sx = self.x + x - self.camera * .7

                Ellipse(
                    pos=(sx, floor_y),
                    size=(dp(230), dp(150))
                )

            # سکوها
            for px, py, pw, ph in self.platforms:
                sx = self.x + px - self.camera
                sy = floor_y + dp(py)

                if sx + dp(pw) < self.x or sx > self.right:
                    continue

                Color(.48, .25, .10, 1)
                Rectangle(
                    pos=(sx, sy),
                    size=(dp(pw), dp(ph))
                )

                Color(.25, .75, .18, 1)
                Rectangle(
                    pos=(sx, sy + dp(ph) - dp(6)),
                    size=(dp(pw), dp(6))
                )

            # سکه‌ها
            for cx, cy in self.coins:
                sx = self.x + cx - self.camera
                sy = floor_y + dp(cy)

                Color(1, .78, .05, 1)
                Ellipse(
                    pos=(sx, sy),
                    size=(dp(22), dp(22))
                )

                Color(1, 1, .65, 1)
                Ellipse(
                    pos=(sx + dp(6), sy + dp(5)),
                    size=(dp(5), dp(10))
                )

            # دشمن
            if self.enemy_alive:
                ex = self.x + self.enemy_x - self.camera
                ey = floor_y + dp(70)

                Color(.65, .20, .12, 1)
                Ellipse(
                    pos=(ex, ey),
                    size=(dp(42), dp(38))
                )

                Color(1, 1, 1, 1)
                Ellipse(
                    pos=(ex + dp(9), ey + dp(20)),
                    size=(dp(8), dp(8))
                )

            # شخصیت اصلی اختصاصی
            px = self.x + self.player_x - self.camera
            py = floor_y + dp(self.player_y)

            Color(.05, .25, .9, 1)
            Rectangle(
                pos=(px, py),
                size=(dp(36), dp(52))
            )

            Color(1, .72, .48, 1)
            Rectangle(
                pos=(px + dp(7), py + dp(27)),
                size=(dp(23), dp(18))
            )

            Color(.85, .12, .10, 1)
            Rectangle(
                pos=(px - dp(3), py + dp(44)),
                size=(dp(42), dp(10))
            )

            Color(.18, .08, .04, 1)
            Rectangle(
                pos=(px, py),
                size=(dp(17), dp(7))
            )

            Rectangle(
                pos=(px + dp(20), py),
                size=(dp(17), dp(7))
            )


class SuperMarioApp(App):
    def build(self):
        root = FloatLayout()

        self.game = Game()
        root.add_widget(self.game)

        self.score_label = Label(
            text="امتیاز: 0 | جان: 3",
            size_hint=(1, None),
            height=dp(45),
            pos_hint={"top": 1},
            font_size="20sp",
            bold=True,
            color=(1, 1, 1, 1)
        )
        root.add_widget(self.score_label)

        self.message = Label(
            text="به خط پایان برس!",
            size_hint=(1, None),
            height=dp(35),
            pos_hint={"center_x": .5, "y": .13},
            font_size="16sp",
            color=(1, 1, 1, 1)
        )
        root.add_widget(self.message)

        left = Button(
            text="◀",
            size_hint=(.19, .12),
            pos_hint={"x": .02, "y": .015},
            font_size="25sp"
        )

        left.bind(
            on_press=lambda *_: self.game.move_left(True),
            on_release=lambda *_: self.game.move_left(False)
        )
        root.add_widget(left)

        right = Button(
            text="▶",
            size_hint=(.19, .12),
            pos_hint={"x": .23, "y": .015},
            font_size="25sp"
        )

        right.bind(
            on_press=lambda *_: self.game.move_right(True),
            on_release=lambda *_: self.game.move_right(False)
        )
        root.add_widget(right)

        jump = Button(
            text="پرش",
            size_hint=(.22, .12),
            pos_hint={"right": .98, "y": .015},
            font_size="20sp"
        )

        jump.bind(on_press=lambda *_: self.game.jump())
        root.add_widget(jump)

        restart = Button(
            text="شروع دوباره",
            size_hint=(.25, .07),
            pos_hint={"center_x": .5, "y": .025},
            font_size="14sp"
        )

        restart.bind(on_press=lambda *_: self.game.restart())
        root.add_widget(restart)

        self.game.score_callback = self.update_score
        self.game.end_callback = self.update_message

        return root

    def update_score(self, score, lives):
        self.score_label.text = f"امتیاز: {score} | جان: {lives}"

    def update_message(self, message):
        self.message.text = message


if __name__ == "__main__":
    SuperMarioApp().run()
