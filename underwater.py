from math import *
from pygame import *
from random import *
from collections import deque

init()
font.init()
IMAGES = {
    "obs1.png": transform.scale(image.load("obs1.png"), (75, 100)),
    "obs2.png": transform.scale(image.load("obs2.png"), (125, 125)),
    "obs3.png": transform.scale(image.load("obs3.png"), (30, 80)),
    "turtle.png": transform.scale(image.load("turtle.png"), (50, 50)),
}

font_title = font.SysFont("Times New Roman", 288)
font_explanation = font.SysFont("Times New Roman",144)
font_subtitle = font.SysFont("Times New Roman",108)
font_system = font.SysFont("Times New Roman", 72)

win_width = 900
win_height = 700
window = display.set_mode((win_width, win_height))

class Text:
    def __init__(self, text_font, pos, typing_speed=40):
        self.font = text_font
        self.pos = pos
        self.typing_speed = typing_speed
        self.dialogues = []
        self.full_text = ""
        self.current_text = ""
        self.char_index = 0
        self.last_update = 0
        self.color = (255, 255, 255)
        self.alpha = 255
        self.active = False
        self.instant = False

    def choose_dialogue(self, dialogue_list):
        self.dialogues = dialogue_list
        self.full_text = choice(self.dialogues)
        self.current_text = ""
        self.char_index = 0
        self.last_update = time.get_ticks()
        self.active = True

    def update_typing(self):
        if not self.active:
            return

        now = time.get_ticks()
        delay = 1000 // self.typing_speed

        if self.char_index < len(self.full_text):
            if now - self.last_update >= delay:
                self.current_text += self.full_text[self.char_index]
                self.char_index += 1
                self.last_update = now

    def set_style(self,color=None,alpha=None):
        if color is not None:
            self.color = color
        if alpha is not None:
            self.alpha = alpha

    def update(self):
        if not self.active or self.instant:
            return
        self.update_typing()

    def draw(self, surface):
        if not self.current_text:
            return

        text_surf = self.font.render(self.current_text, True, self.color)
        text_surf.set_alpha(self.alpha)

        rect = text_surf.get_rect(center=self.pos)
        surface.blit(text_surf, rect)

    def show_instant(self, text):
        self.full_text = text
        self.current_text = text
        self.active = True
        self.instant = True

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
    def __init__(self, *args):
        super().__init__(*args)

        # 10% hitbox
        hitbox_w = self.rect.width * 0.1
        hitbox_h = self.rect.height * 0.1

        self.hitbox = Rect(0, 0, hitbox_w, hitbox_h)
        self.update_hitbox()

    def update_hitbox(self):
        self.hitbox.center = self.rect.center

    def upd(self):
        keys = key.get_pressed()

        if keys[K_LSHIFT] or keys[K_RSHIFT]:
            current_speed = self.speed / 2
        else:
            current_speed = self.speed

        if (keys[K_w] or keys[K_UP]) and self.rect.y > 50:
            self.rect.y -= current_speed
        if (keys[K_s] or keys[K_DOWN]) and self.rect.y < 650:
            self.rect.y += current_speed
        if (keys[K_a] or keys[K_LEFT]) and self.rect.x > 50:
            self.rect.x -= current_speed
        if (keys[K_d] or keys[K_RIGHT]) and self.rect.x < 800:
            self.rect.x += current_speed

        self.update_hitbox()


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

        self.rotation = choice([0, 90, -90, 180])

        if self.rotation != 0:
            self.image = transform.rotate(self.image, self.rotation)
            self.rect = self.image.get_rect(center=self.rect.center)

        self.fx = float(self.rect.x)
        self.fy = float(self.rect.y)

        self.vx = speed * cos(rad)
        self.vy = speed * sin(rad)

        hitbox_w = self.rect.width * 0.8
        hitbox_h = self.rect.height * 0.8
        self.hitbox = Rect(0, 0, hitbox_w, hitbox_h)
        self.update_hitbox()

    def update_hitbox(self):
        self.hitbox.center = self.rect.center

    def update(self):
        self.fx += self.vx
        self.fy += self.vy

        self.rect.x = int(self.fx)
        self.rect.y = int(self.fy)

        self.update_hitbox()

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

            spawn_queue += [("obs1.png", 0.9, 75, 100)] * 1
            spawn_queue += [("obs2.png", 0.9, 125, 125)] * 1
            spawn_queue += [("obs3.png", 0.9, 30, 80)] * 1

        if spawn_queue:
            img, speed, w, h = spawn_queue.popleft()
            bullets.add(Obstacle(img, speed, w, h))
    if current_time - START_TIME >= GAME_DURATION:
        game = False

    # ---- UPDATE & DRAW ----
    turtle.upd()
    turtle.update_hitbox()
    bullets.update()
    #for o in bullets:
        #if turtle.hitbox.colliderect(o.rect):
            #game = False

    bullets.draw(window)
    turtle.reset()
    time_left = max(0, (GAME_DURATION - (current_time - START_TIME)) // 1000)
    timer_text = Text(font_system, (700, 30))
    countdown_text = Text(font_title, (win_width // 2, win_height // 2))
    if time_left > 10:
        if time_left > 30:
            timer_text.set_style((0,255,0),255)
            timer_text.show_instant(f"Time left: {time_left}s")
            timer_text.draw(window)
        else:
            timer_text.set_style((255,255,0),255)
            timer_text.show_instant(f"Time left: {time_left}s")
            timer_text.draw(window)
    else:
        countdown_text.set_style((255,0,0),100)
        countdown_text.show_instant(f"{time_left}")
        countdown_text.draw(window)
        overlay = Surface((win_width, win_height),SRCALPHA)
        overlay.fill((0, 0, 0, 50))
        window.blit(overlay, (0, 0))

    display.update()
    clock.tick(FPS)
