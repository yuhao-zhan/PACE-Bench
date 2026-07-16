import sys

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from pace_bench.renderer import Renderer

from Box2D.b2 import dynamicBody, staticBody, circleShape

import pygame

class ClassifyBallsRenderer(Renderer):
    def render(self, sandbox, agent_components, camera_offset_x):
        self.set_camera_offset(camera_offset_x)
        self.clear((250, 250, 250))
        for body in sandbox.world.bodies:
            if body.type == staticBody:
                is_conveyor = (hasattr(sandbox, 'conveyor') and body == sandbox.conveyor)
                if is_conveyor:
                    self.draw_body(body,
                                 dynamic_color=(100, 150, 240),
                                 static_color=(120, 120, 120),
                                 outline_color=(80, 80, 80),
                                 outline_width=3)
                else:
                    self.draw_body(body,
                                 dynamic_color=(100, 150, 240),
                                 static_color=(100, 100, 100),
                                 outline_color=(60, 60, 60),
                                 outline_width=3)
        if hasattr(sandbox, 'red_basket'):
            red_basket = sandbox.red_basket
            basket_x = red_basket['x'] - red_basket['width']/2
            basket_y = red_basket['y'] - red_basket['height']/2
            screen_x = int(basket_x * self.simulator.ppm - camera_offset_x)
            screen_y = int(self.simulator.screen_height - (basket_y + red_basket['height']) * self.simulator.ppm)
            screen_w = int(red_basket['width'] * self.simulator.ppm)
            screen_h = int(red_basket['height'] * self.simulator.ppm)
            red_rect = pygame.Rect(screen_x, screen_y, screen_w, screen_h)
            pygame.draw.rect(self.simulator.screen, (255, 180, 180), red_rect)
            pygame.draw.rect(self.simulator.screen, (220, 0, 0), red_rect, 5)
        if hasattr(sandbox, 'blue_basket'):
            blue_basket = sandbox.blue_basket
            basket_x = blue_basket['x'] - blue_basket['width']/2
            basket_y = blue_basket['y'] - blue_basket['height']/2
            screen_x = int(basket_x * self.simulator.ppm - camera_offset_x)
            screen_y = int(self.simulator.screen_height - (basket_y + blue_basket['height']) * self.simulator.ppm)
            screen_w = int(blue_basket['width'] * self.simulator.ppm)
            screen_h = int(blue_basket['height'] * self.simulator.ppm)
            blue_rect = pygame.Rect(screen_x, screen_y, screen_w, screen_h)
            pygame.draw.rect(self.simulator.screen, (180, 180, 255), blue_rect)
            pygame.draw.rect(self.simulator.screen, (0, 0, 220), blue_rect, 5)
        for body in sandbox.bodies:
            if body.type == dynamicBody:
                is_ball = False
                ball_color = None
                if hasattr(sandbox, 'balls'):
                    for ball_data in sandbox.balls:
                        if ball_data['body'] == body:
                            is_ball = True
                            ball_color = ball_data['color']
                            break
                if not is_ball:
                    self.draw_body(body,
                                 dynamic_color=(80, 80, 80),
                                 static_color=(150, 100, 50),
                                 outline_color=(40, 40, 40),
                                 outline_width=4)
        if hasattr(sandbox, 'balls'):
            for ball_data in sandbox.balls:
                ball = ball_data['body']
                if ball_data['color'] == 'red':
                    self.draw_circle(ball.position.x, ball.position.y,
                                   sandbox.ball_radius,
                                   (255, 0, 0),
                                   (200, 0, 0),
                                   2)
                else:
                    self.draw_circle(ball.position.x, ball.position.y,
                                   sandbox.ball_radius,
                                   (0, 0, 255),
                                   (0, 0, 200),
                                   2)
        if hasattr(sandbox, 'sensors'):
            for sensor in sandbox.sensors:
                sensor_pos = self.world_to_screen(sensor['origin'][0], sensor['origin'][1])
                sensor_radius = int(sensor['length'] * self.simulator.ppm)
                pygame.draw.circle(self.simulator.screen, (0, 255, 0), sensor_pos, sensor_radius, 3)
                pygame.draw.circle(self.simulator.screen, (0, 220, 0), sensor_pos, 8)
                pygame.draw.circle(self.simulator.screen, (0, 150, 0), sensor_pos, 8, 2)
                end_x = sensor['origin'][0] + sensor['direction'][0] * sensor['length']
                end_y = sensor['origin'][1] + sensor['direction'][1] * sensor['length']
                end_pos = self.world_to_screen(end_x, end_y)
                pygame.draw.line(self.simulator.screen, (0, 200, 0), sensor_pos, end_pos, 2)
        if hasattr(sandbox, 'build_zone'):
            zone = sandbox.build_zone
            zone_x1 = zone['min_x']
            zone_y1 = zone['min_y']
            zone_x2 = zone['max_x']
            zone_y2 = zone['max_y']
            self.draw_line(zone_x1, zone_y1, zone_x2, zone_y1, (200, 200, 0), 1)
            self.draw_line(zone_x1, zone_y2, zone_x2, zone_y2, (200, 200, 0), 1)
            self.draw_line(zone_x1, zone_y1, zone_x1, zone_y2, (200, 200, 0), 1)
            self.draw_line(zone_x2, zone_y1, zone_x2, zone_y2, (200, 200, 0), 1)
