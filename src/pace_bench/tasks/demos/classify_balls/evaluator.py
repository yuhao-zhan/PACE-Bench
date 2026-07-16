import math

from pace_bench.primitives import compute_constraint_penalty

class Evaluator:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.red_balls_correct = 0
        self.blue_balls_correct = 0
        self.red_balls_wrong = 0
        self.blue_balls_wrong = 0
        self.total_balls = 0
    def check_ball_in_basket(self, ball_data):
        ball = ball_data['body']
        ball_x = ball.position.x
        ball_y = ball.position.y
        color = ball_data['color']
        if color == 'red':
            red_basket = self.sandbox.red_basket
            if (red_basket['x'] - red_basket['width']/2 <= ball_x <= red_basket['x'] + red_basket['width']/2 and
                red_basket['y'] - red_basket['height']/2 <= ball_y <= red_basket['y'] + red_basket['height']/2):
                if not ball_data['classified']:
                    self.red_balls_correct += 1
                    ball_data['classified'] = True
                    ball_data['in_basket'] = True
                return True
            blue_basket = self.sandbox.blue_basket
            if (blue_basket['x'] - blue_basket['width']/2 <= ball_x <= blue_basket['x'] + blue_basket['width']/2 and
                blue_basket['y'] - blue_basket['height']/2 <= ball_y <= blue_basket['y'] + blue_basket['height']/2):
                if not ball_data['classified']:
                    self.red_balls_wrong += 1
                    ball_data['classified'] = True
                    ball_data['in_basket'] = True
                return True
        else:
            blue_basket = self.sandbox.blue_basket
            if (blue_basket['x'] - blue_basket['width']/2 <= ball_x <= blue_basket['x'] + blue_basket['width']/2 and
                blue_basket['y'] - blue_basket['height']/2 <= ball_y <= blue_basket['y'] + blue_basket['height']/2):
                if not ball_data['classified']:
                    self.blue_balls_correct += 1
                    ball_data['classified'] = True
                    ball_data['in_basket'] = True
                return True
            red_basket = self.sandbox.red_basket
            if (red_basket['x'] - red_basket['width']/2 <= ball_x <= red_basket['x'] + red_basket['width']/2 and
                red_basket['y'] - red_basket['height']/2 <= ball_y <= red_basket['y'] + red_basket['height']/2):
                if not ball_data['classified']:
                    self.blue_balls_wrong += 1
                    ball_data['classified'] = True
                    ball_data['in_basket'] = True
                return True
        return False
    def compute_score_with_penalty(self, score: float, metrics: dict) -> float:
        if score > 0:
            return score
        constraint_info = self.get_constraint_info()
        penalty = compute_constraint_penalty("classify_balls", score, metrics, constraint_info)
        return penalty
    def get_constraint_info(self):
        return {
            'red_basket': self.sandbox.red_basket,
            'blue_basket': self.sandbox.blue_basket,
            'build_zone': self.sandbox.build_zone,
        }
    def evaluate(self, step_count, max_steps):
        for ball_data in self.sandbox.balls:
            if not ball_data['in_basket']:
                self.check_ball_in_basket(ball_data)
        total_red = sum(1 for b in self.sandbox.balls if b['color'] == 'red')
        total_blue = sum(1 for b in self.sandbox.balls if b['color'] == 'blue')
        self.total_balls = len(self.sandbox.balls)
        correct = self.red_balls_correct + self.blue_balls_correct
        wrong = self.red_balls_wrong + self.blue_balls_wrong
        total_classified = correct + wrong
        if total_classified > 0:
            accuracy = correct / total_classified * 100.0
        else:
            accuracy = 0.0
        all_spawned = self.sandbox.balls_spawned >= self.sandbox.balls_to_spawn
        all_classified = total_classified >= self.total_balls and self.total_balls > 0
        success = (all_classified and
                  self.red_balls_correct == total_red and
                  self.blue_balls_correct == total_blue and
                  self.red_balls_wrong == 0 and
                  self.blue_balls_wrong == 0)
        if success:
            score = 100.0
        elif total_classified > 0:
            score = accuracy
        else:
            score = 0.0
        should_stop = (all_classified and all_spawned) or (step_count >= max_steps)
        metrics = {
            'total_balls': self.total_balls,
            'total_red': total_red,
            'total_blue': total_blue,
            'red_balls_correct': self.red_balls_correct,
            'blue_balls_correct': self.blue_balls_correct,
            'red_balls_wrong': self.red_balls_wrong,
            'blue_balls_wrong': self.blue_balls_wrong,
            'accuracy': accuracy,
            'success': success,
            'all_spawned': all_spawned,
            'all_classified': all_classified
        }
        return should_stop, score, metrics
    def get_task_description(self):
        return {
            'task': 'Classify red and blue balls',
            'description': 'Design a device connected to conveyor end to put red balls into red bin, blue balls into blue bin',
            'requirements': {
                'sensor': 'Need raycast sensor to detect ball color',
                'actuator': 'Need piston or motor to control diversion device',
                'logic': 'Can use logic gates and delay to build control logic',
                'red_basket': f"Red balls should enter red bin (x={self.sandbox.red_basket['x']:.1f}, range {self.sandbox.red_basket['x'] - self.sandbox.red_basket['width']/2:.1f}-{self.sandbox.red_basket['x'] + self.sandbox.red_basket['width']/2:.1f}) - wider and closer for easier classification",
                'blue_basket': f"Blue balls should enter blue bin (x={self.sandbox.blue_basket['x']:.1f}, range {self.sandbox.blue_basket['x'] - self.sandbox.blue_basket['width']/2:.1f}-{self.sandbox.blue_basket['x'] + self.sandbox.blue_basket['width']/2:.1f}) - wider for easier classification",
                'build_zone': f"Agent can only build in build area ({self.sandbox.build_zone['min_x']}, {self.sandbox.build_zone['min_y']}) to ({self.sandbox.build_zone['max_x']}, {self.sandbox.build_zone['max_y']})"
            },
            'success_criteria': {
                'primary': 'All red balls enter red bin, all blue balls enter blue bin',
                'secondary': 'No balls enter wrong bin',
                'accuracy': 'Classification accuracy 100%'
            },
            'evaluation': {
                'score_range': '0-100',
                'success_score': 100,
                'partial_score': 'Based on classification accuracy',
                'failure_score': 0
            }
        }
