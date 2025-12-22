from math import *
from pygame import *
from random import *
from collections import deque

init()
font.init()
IMAGES = {
    "obs1.png": transform.scale(image.load("obs1.png"), (85, 100)),
    "obs2.png": transform.scale(image.load("obs2.png"), (125, 125)),
    "obs3.png": transform.scale(image.load("obs3.png"), (70, 80)),
    "turtle.png": transform.scale(image.load("turtle.png"), (50, 50)),
}

font_title = font.Font(None, 288)
font_explanation = font.Font(None,144)
font_subtitle = font.Font(None,108)
font_system = font.Font(None, 72)

win_width = 900
win_height = 700
window = display.set_mode((win_width, win_height))


class GameSprite(sprite.Sprite):
    def __init__(self, player_image, x_co, y_co, player_speed, width, height):
        super().__init__()
        self.image = IMAGES[player_image]
        self.speed = player_speed
        self.rect = self.image.get_rect()
        self.rect.x = x_co
        self.rect.y = y_co

    def reset(self):
        window.blit(self.image, (self.rect.x, self.rect.y))

class Player(GameSprite):
    def __init__(self,*args):
        super().__init__(*args)

        HITBOX_RADIUS = 2.5
        self.hitbox = Rect(0, 0, HITBOX_RADIUS * 2, HITBOX_RADIUS * 2)
        self.update_hitbox()

    def update_hitbox(self):
        self.hitbox.center = self.rect.center

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
turtle = Player("turtle.png", 450, 200, 2, 50, 50)
START_TIME = time.get_ticks()
SPAWN_INTERVAL = 1000  # 1 second
last_spawn_time = START_TIME
GAME_DURATION = 60000  # 60 seconds
game = True
clock = time.Clock()
FPS = 60
spawn_timer = 0
spawn_delay = 30
spawn_queue = deque()

while game:
    for e in event.get():
        if e.type == QUIT:
            game = False
    current_time = time.get_ticks()
    window.blit(background, (0, 0))

    # ---- SPAWNING LOGIC ----
    if current_time - START_TIME < GAME_DURATION:
        if current_time - last_spawn_time >= SPAWN_INTERVAL:
            last_spawn_time = current_time

            spawn_queue += [("obs1.png", 1, 85, 100)] * 1
            spawn_queue += [("obs2.png", 0.75, 125, 125)] * 1
            spawn_queue += [("obs3.png", 1.5, 70, 80)] * 1

        if spawn_queue:
            img, speed, w, h = spawn_queue.popleft()
            bullets.add(Obstacle(img, speed, w, h))
    if current_time - START_TIME >= GAME_DURATION:
        game = False

    # ---- UPDATE & DRAW ----
    turtle.upd()
    turtle.update_hitbox()
    bullets.update()
    for o in bullets:
        if turtle.hitbox.colliderect(o.rect):
            game = False

    bullets.draw(window)
    turtle.reset()
    time_left = max(0, (GAME_DURATION - (current_time - START_TIME)) // 1000)
    if time_left > 10:
        if time_left > 30:
            timer_text = font_system.render(f"Time Left: {time_left}s", True, (0, 255, 0))
            window.blit(timer_text, (550, 20))
        else:
            timer_text = font_system.render(f"Time Left: {time_left}s", True, (255, 255, 0))
            window.blit(timer_text, (550, 20))
    else:
        timer_text = font_title.render(f"{time_left}", True, (255,0,0))
        timer_text.set_alpha(128)
        timer_rect = timer_text.get_rect(center=(win_width // 2, win_height // 2))
        overlay = Surface((win_width, win_height))
        overlay.set_alpha(100)
        overlay.fill((0, 0, 0))
        window.blit(overlay, (0, 0))
        window.blit(timer_text, timer_rect)

    display.update()
    clock.tick(FPS)
