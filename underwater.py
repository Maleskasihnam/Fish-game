from pygame import *
from random import *

back = (30, 185, 227)
win_width = 900
win_height = 700
window = display.set_mode((win_width,win_height))
window.fill(back)

class GameSprite(sprite.Sprite):
    def __init__(self,player_icon,x_co,y_co,player_speed,width,height):
        super().__init__()
        self.icon = transform.scale(image.load(player_icon), (width,height))
        self.speed = player_speed
        self.rect = self.icon.get_rect
        self.rect.x = x_co
        self.rect.y = y_co

    def reset(self):
        window.blit(self.icon, (self.rect.x,self.rect.y))

class Player(GameSprite):
    def upd(self):
        keys = key.get_pressed()
        if keys[K_w] or keys[K_UP] and self.rect.y < 900:
            self.rect.y += self.speed
        if keys[K_s] or keys[K_DOWN] and self.rect.y > 0:
            self.rect.y -= self.speed
        if keys[K_a] or keys[K_LEFT] and self.rect.x > 0:
            self.rect.x -= self.speed
        if keys[K_d] or keys[K_RIGHT] and self.rect.x < 700:
            self.rect.x += self.speed

class Obstacle(GameSprite):
    def move_y(self):
        if self.rect.y <= 900:
            self.rect.y -= self.speed
        if self.rect.y <= 0:
            self.kill()

    def move_xright(self):
        if self.rect.x >= 0:
            self.rect.x += self.speed
        if self.rect.x >= 700:
            self.kill()
    
    def move_xleft(self):
        if self.rect.x <= 700:
            self.rect.x -= self.speed
        if self.rect.x <= 0:
            self.kill()

obs1 = Obstacle()
obs2 = Obstacle()
obs3 = Obstacle()
fish = Player()

game = True
finish = False
clock = time.Clock()
FPS = 60

while game:
    for e in event.get():
        if e == QUIT:
            game = False

    if finish != True:
        window.fill(back)