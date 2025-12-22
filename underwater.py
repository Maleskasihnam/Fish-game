from math import *
from pygame import *
from random import *

init()

back = (30, 185, 227)
win_width = 900
win_height = 700
window = display.set_mode((win_width, win_height))


class GameSprite(sprite.Sprite):
    def __init__(self, player_image, x_co, y_co, player_speed, width, height):
        super().__init__()
        self.image = transform.scale(image.load(player_image), (width, height))
        self.speed = player_speed
        self.rect = self.image.get_rect()
        self.hitbox = self.rect.inflate(-int(width * 0.6), -int(height * 0.6))
        self.rect.x = x_co
        self.rect.y = y_co

    def update_hitbox(self):
        self.hitbox.center = self.rect.center

    def reset(self):
        window.blit(self.image, (self.rect.x, self.rect.y))

class Player(GameSprite):
    def upd(self):
        keys = key.get_pressed()
        if (keys[K_w] or keys[K_UP]) and self.rect.y > 50:
            self.rect.y -= self.speed
        if (keys[K_s] or keys[K_DOWN]) and self.rect.y < 650:
            self.rect.y += self.speed
        if (keys[K_a] or keys[K_LEFT]) and self.rect.x > 50:
            self.rect.x -= self.speed
        if (keys[K_d] or keys[K_RIGHT]) and self.rect.x < 800:
            self.rect.x += self.speed


class Obstacle(GameSprite):
    def __init__(self, player_image, speed, width, height):
        origin = randint(1, 3)

        if origin == 1:  # FROM TOP
            angle = randint(30, 150)
            x = randint(0, win_width - width)
            y = -height

        elif origin == 2:  # FROM RIGHT
            angle = randint(150, 180)
            x = win_width - 10
            y = randint(0, win_height - height)

        else:  # FROM LEFT
            angle = randint(0, 30)
            x = -width
            y = randint(0, win_height - height)

        rad = radians(angle)
        super().__init__(player_image, x, y, speed, width, height)

        # FLOAT position (THIS IS THE KEY)
        self.fx = float(self.rect.x)
        self.fy = float(self.rect.y)

        self.vx = speed * cos(rad)
        self.vy = speed * sin(rad)

    def update(self):
        self.fx += self.vx
        self.fy += self.vy

        self.rect.x = int(self.fx)
        self.rect.y = int(self.fy)

        if (self.rect.top > win_height or self.rect.right < 0
            or self.rect.left > win_width or self.rect.bottom < 0):
            self.kill()

background = transform.scale(image.load("bg.jpg"), (win_width, win_height))
bullets = sprite.Group()
turtle = Player("turtle.png", 450, 200, 5, 50, 50)
START_TIME = time.get_ticks()
SPAWN_INTERVAL = 1000  # 1 second
last_spawn_time = START_TIME
GAME_DURATION = 60000  # 60 seconds
game = True
clock = time.Clock()
FPS = 60
spawn_timer = 0
spawn_delay = 30

while game:
    current_time = time.get_ticks()

    for e in event.get():
        if e.type == QUIT:
            game = False

    window.blit(background, (0, 0))

    # ---- SPAWNING LOGIC ----
    if current_time - START_TIME < GAME_DURATION:
        if current_time - last_spawn_time >= SPAWN_INTERVAL:
            last_spawn_time = current_time

            # 3 obs1
            for _ in range(3):
                bullets.add(Obstacle("obs1.png", 1, 100, 100))

            # 5 obs2
            for _ in range(5):
                bullets.add(Obstacle("obs2.png", 3, 50, 100))

            # 7 obs3
            for _ in range(7):
                bullets.add(Obstacle("obs3.png", 4, 45, 45))

    if current_time >= GAME_DURATION:
        game = False

    # ---- UPDATE & DRAW ----
    turtle.upd()
    turtle.update_hitbox()
    bullets.update()
    for o in bullets:
        o.update_hitbox()
        if turtle.hitbox.colliderect(o.hitbox):
            game = False

    bullets.draw(window)
    turtle.reset()

    display.update()
    clock.tick(FPS)
