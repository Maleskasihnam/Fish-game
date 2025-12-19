from pygame import *
from random import *

back = (30, 185, 227)
win_width = 900
win_height = 700
window = display.set_mode((win_width,win_height))

class GameSprite(sprite.Sprite):
    def __init__(self,player_icon,x_co,y_co,player_speed,width,height):
        super().__init__()
        self.icon = transform.scale(image.load(player_icon), (width,height))
        self.speed = player_speed
        self.rect = self.icon.get_rect()
        self.rect.x = x_co
        self.rect.y = y_co

    def reset(self):
        window.blit(self.icon, (self.rect.x,self.rect.y))

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
    def move_y(self):
        self.rect.y = 700
        if self.rect.y <= 700:
            self.rect.y -= self.speed
        if self.rect.y <= 0:
            self.kill()

    def move_xright(self):
        self.rect.x = 0
        if self.rect.x >= 0:
            self.rect.x += self.speed
        if self.rect.x >= 700:
            self.kill()
    
    def move_xleft(self):
        self.rect.x = 900
        if self.rect.x <= 900:
            self.rect.x -= self.speed
        if self.rect.x <= 0:
            self.kill()

    def decide(self):
        decision = randint(1,3)
        if decision == 1:
            self.move_y()
        elif decision == 2:
            self.move_xright()
        elif decision == 3:
            self.move_xleft()

background = transform.scale(image.load("bg.jpg"),(win_width,win_height))
obstacles1 = sprite.Group()
obstacles2 = sprite.Group()
obstacles3 = sprite.Group()
for i in range(180):
    obs1 = Obstacle("obs1.png",randint(1,900),randint(1,700),3,25,25)
    obstacles1.add(obs1)
for j in range(300):
    obs2 = Obstacle("obs2.png",randint(1,900), randint(1,700),5,10,20)
    obstacles2.add(obs2)
for k in range(420):
    obs3 = Obstacle("obs3.png",randint(1,900),randint(1,700),7,10,10)
    obstacles3.add(obs3)

fish = Player("fish.png",450,200,5,50,50)

game = True
finish = False
clock = time.Clock()
FPS = 60

while game:
    for e in event.get():
        if e.type == QUIT:
            game = False

    if finish != True:
        window.blit(background,(0,0))
        #obstacles1.draw(window)
        #obstacles2.draw(window)
        #obstacles3.draw(window)
        fish.reset()
        fish.upd()
        #obstacles1.decide()
        #obstacles2.decide()
        #obstacles3.decide()

    display.update()
    clock.tick(FPS)
