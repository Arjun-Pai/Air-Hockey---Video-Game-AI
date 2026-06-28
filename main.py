import asyncio
import sys
sys.path.insert(0, '.')
import pygame
import warnings
warnings.simplefilter('ignore')

pygame.init()

_orig_set_mode = pygame.display.set_mode
def _windowed_set_mode(size, flags=0, *args, **kwargs):
    flags = flags & ~pygame.FULLSCREEN & ~pygame.NOFRAME
    return _orig_set_mode(size, flags, *args, **kwargs)
pygame.display.set_mode = _windowed_set_mode

import Constants

info    = pygame.display.Info()
HUD_H   = 90
HINT_H  = 30
PADDING = 30

max_field_w = info.current_w - PADDING * 2
max_field_h = info.current_h - HUD_H - HINT_H - 60

scale = min(max_field_w / Constants.FIELD_WIDTH,
            max_field_h / Constants.FIELD_HEIGHT,
            1.2)

FPW = round(Constants.FIELD_WIDTH  * scale)
FPH = round(Constants.FIELD_HEIGHT * scale)
W   = FPW + PADDING * 2
H   = FPH + HUD_H + HINT_H

Constants.UNITS_TO_PIXELS_SCALE  = scale
Constants.FIELD_PIXEL_WIDTH      = FPW
Constants.FIELD_PIXEL_HEIGHT     = FPH
Constants.WIDTH                  = W
Constants.HEIGHT                 = H
Constants.RIGHT_BORDER_FROM_EDGE = PADDING
Constants.TOP_BORDER_FROM_EDGE   = HUD_H
Constants.X_OFF                  = PADDING + FPW // 2 - 500
Constants.Y_OFF                  = HUD_H   + FPH // 2
Constants.STRIKER_RADIUS         = round(Constants.STRIKER_RADIUS * 0.65)
Constants.PUCK_RADIUS            = round(Constants.PUCK_RADIUS    * 0.45)

from Graphics.Graphics import AHGraphics
from Game.Game import Game
from Constants import MAX_SPEED

WHITE  = (255, 255, 255)
CYAN   = (0,   210, 255)
ORANGE = (255, 140, 0)
GREEN  = (0,   210, 80)
RED    = (255, 60,  60)
GREY_L = (180, 180, 180)
GREY_D = (55,  55,  70)
DARK   = (10,  10,  20)

DIFFICULTIES = {
    "Easy":          0.40,
    "Medium":        0.80,
    "Hard":          1.20,
    "Stupidly Hard": 50.0,
}
DIFF_COLORS = {
    "Easy": GREEN, "Medium": ORANGE, "Hard": RED, "Stupidly Hard": WHITE
}
PUCK_DAMP = {"Easy": 0.990, "Medium": 0.995, "Hard": 0.999, "Stupidly Hard": 0.999}
PUCK_FRIC = {"Easy": 80,    "Medium": 45,    "Hard": 20,    "Stupidly Hard": 5}
WIN_SCORE = 7


def draw_centered(surface, text, font, color, cx, cy):
    s = font.render(text, True, color)
    surface.blit(s, s.get_rect(center=(cx, cy)))


def cap_ai_speed(game, frac):
    s   = game.simulation.strikers[0]
    spd = s.velocity.magnitude()
    lim = MAX_SPEED * frac
    if spd > lim > 0:
        r = lim / spd
        s.velocity.x *= r
        s.velocity.y *= r


async def difficulty_menu(screen, clock):
    fw, fh = screen.get_size()
    font_t = pygame.font.SysFont("Arial", 56, bold=True)
    font_b = pygame.font.SysFont("Arial", 30, bold=True)
    font_s = pygame.font.SysFont("Arial", 22)

    bw, bh = 190, 54
    gap    = 18
    names  = list(DIFFICULTIES.keys())
    total  = len(names) * bw + (len(names) - 1) * gap
    bx0    = (fw - total) // 2
    by     = fh // 2 + 10

    buttons = {name: pygame.Rect(bx0 + i*(bw+gap), by, bw, bh)
               for i, name in enumerate(names)}

    chosen = None
    while chosen is None:
        clock.tick(60)
        screen.fill(DARK)
        draw_centered(screen, "AIR  HOCKEY", font_t, CYAN,   fw//2, fh//2 - 90)
        draw_centered(screen, "Select difficulty", font_s, GREY_L, fw//2, fh//2 - 30)

        mx, my = pygame.mouse.get_pos()
        for name, rect in buttons.items():
            col   = DIFF_COLORS[name]
            hover = rect.collidepoint(mx, my)
            surf  = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            surf.fill((*col, 190 if hover else 55))
            screen.blit(surf, rect)
            pygame.draw.rect(screen, col, rect, 2, border_radius=8)
            draw_centered(screen, name, font_b, WHITE, rect.centerx, rect.centery)

        draw_centered(screen, "Move cursor = move paddle  |  R = menu  |  ESC = quit",
                      font_s, (90, 90, 110), fw//2, fh - 18)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for name, rect in buttons.items():
                    if rect.collidepoint(mx, my):
                        chosen = name

        pygame.display.flip()
        await asyncio.sleep(0)

    return chosen


async def main():
    clock    = pygame.time.Clock()
    graphics = AHGraphics('Air Hockey', W, H)
    screen   = pygame.display.get_surface()

    font_big = pygame.font.SysFont("Arial", 64, bold=True)
    font_med = pygame.font.SysFont("Arial", 40, bold=True)
    font_sm  = pygame.font.SysFont("Arial", 22)
    font_sub = pygame.font.SysFont("Arial", 28)
    font_hud = pygame.font.SysFont("Arial", 28, bold=True)

    def new_game():
        return Game("vsAI", 0)

    def reset():
        return new_game(), 0, 0, 0, 0, "playing"

    diff_name = await difficulty_menu(screen, clock)
    diff_frac = DIFFICULTIES[diff_name]
    diff_col  = DIFF_COLORS[diff_name]
    Constants.VELOCITY_DAMP = PUCK_DAMP[diff_name]
    Constants.FRICTION_MAG  = PUCK_FRIC[diff_name]

    game, player_score, ai_score, prev_you, prev_ai, state = reset()
    goal_timer = 0
    GOAL_MS    = 1400

    running = True
    while running:
        clock.tick(120)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_r:
                    diff_name = await difficulty_menu(screen, clock)
                    diff_frac = DIFFICULTIES[diff_name]
                    diff_col  = DIFF_COLORS[diff_name]
                    Constants.VELOCITY_DAMP = PUCK_DAMP[diff_name]
                    Constants.FRICTION_MAG  = PUCK_FRIC[diff_name]
                    game, player_score, ai_score, prev_you, prev_ai, state = reset()

        mouse = pygame.mouse.get_pos()
        game.leftMouseDown   = True
        game.middleMouseDown = False
        game.rightMouseDown  = False
        game.mousePosition   = mouse
        game.stepTime        = 1 / 120
        game.gameSpeed       = 1

        if state == "playing":
            game.update()
            cap_ai_speed(game, diff_frac)

            you_goals = game.players[1].goals
            ai_goals  = game.players[0].goals

            if you_goals > prev_you:
                prev_you      = you_goals
                player_score += 1
                goal_timer    = pygame.time.get_ticks()
                state         = "goal_you"
            elif ai_goals > prev_ai:
                prev_ai   = ai_goals
                ai_score += 1
                goal_timer = pygame.time.get_ticks()
                state      = "goal_ai"

            if player_score >= WIN_SCORE or ai_score >= WIN_SCORE:
                state = "done"

        elif state in ("goal_you", "goal_ai"):
            if pygame.time.get_ticks() - goal_timer > GOAL_MS:
                state = "playing"

        graphics.drawBackgrond()
        graphics.drawField()
        graphics.drawPuck(game.simulation.puck.position)
        for striker in game.simulation.strikers:
            graphics.drawStriker(striker.position, GREY_L)

        hud = pygame.Surface((W, HUD_H), pygame.SRCALPHA)
        hud.fill((0, 0, 0, 160))
        screen.blit(hud, (0, 0))

        badge = font_sm.render(diff_name, True, diff_col)
        screen.blit(badge, (W - badge.get_width() - 10, 8))

        draw_centered(screen, f"YOU  {player_score} — {ai_score}  AI", font_hud, WHITE, W//2, 22)

        dot_r  = 6
        dot_sp = dot_r * 2 + 6

        ox = W//2 - WIN_SCORE * dot_sp - 10
        for i in range(WIN_SCORE):
            col = CYAN if i < player_score else GREY_D
            pygame.draw.circle(screen, col, (ox + i*dot_sp + dot_r, 50), dot_r)

        ox2 = W//2 + 10
        for i in range(WIN_SCORE):
            col = ORANGE if i < ai_score else GREY_D
            pygame.draw.circle(screen, col, (ox2 + i*dot_sp + dot_r, 50), dot_r)

        hint = font_sm.render("Move cursor = move paddle  |  R = menu  |  ESC = quit",
                              True, (90, 90, 110))
        screen.blit(hint, hint.get_rect(center=(W//2, H - HINT_H//2)))

        if state == "goal_you":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 140))
            screen.blit(ov, (0, 0))
            draw_centered(screen, "GOAL!", font_big, GREEN, W//2, H//2 - 30)
            draw_centered(screen, f"You {player_score}  —  {ai_score} AI", font_sub, WHITE, W//2, H//2 + 40)

        if state == "goal_ai":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 140))
            screen.blit(ov, (0, 0))
            draw_centered(screen, "AI SCORED", font_big, RED, W//2, H//2 - 30)
            draw_centered(screen, f"You {player_score}  —  {ai_score} AI", font_sub, WHITE, W//2, H//2 + 40)

        if state == "done":
            won = player_score >= WIN_SCORE
            ov  = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 190))
            screen.blit(ov, (0, 0))
            draw_centered(screen, "YOU WIN!" if won else "AI WINS",
                          font_big, GREEN if won else RED, W//2, H//2 - 60)
            draw_centered(screen, f"You {player_score}  —  {ai_score} AI",
                          font_med, WHITE, W//2, H//2 + 5)
            draw_centered(screen, "Press R to play again",
                          font_sub, GREY_L, W//2, H//2 + 60)

        pygame.display.flip()
        await asyncio.sleep(0)   # this line is what makes it work in the browser

    pygame.quit()


asyncio.run(main())