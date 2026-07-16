from typing import Dict, Any, List

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    metric_parts = []
    if 'accuracy' in metrics:
        metric_parts.append(f"**Classification accuracy**: {metrics['accuracy']:.1f}%")
        metric_parts.append(f"**Total balls**: {metrics.get('total_balls', 0)}")
        if 'red_balls_correct' in metrics:
            metric_parts.append(f"**Red balls correct**: {metrics['red_balls_correct']}/{metrics.get('total_red', 0)}")
            metric_parts.append(f"**Blue balls correct**: {metrics['blue_balls_correct']}/{metrics.get('total_blue', 0)}")
        if 'red_balls_wrong' in metrics:
            if metrics['red_balls_wrong'] > 0:
                metric_parts.append(f"**Red balls wrong**: {metrics['red_balls_wrong']}")
            if metrics['blue_balls_wrong'] > 0:
                metric_parts.append(f"**Blue balls wrong**: {metrics['blue_balls_wrong']}")
        metric_parts.append("\n**Physical State Information**:")
        if 'balls_on_conveyor' in metrics:
            metric_parts.append(f"- Balls on conveyor: {metrics['balls_on_conveyor']}")
        if 'balls_in_red_basket' in metrics:
            metric_parts.append(f"- Balls in red basket: {metrics['balls_in_red_basket']}")
        if 'balls_in_blue_basket' in metrics:
            metric_parts.append(f"- Balls in blue basket: {metrics['balls_in_blue_basket']}")
    excluded_keys = ['accuracy', 'total_balls', 'red_balls_correct', 'blue_balls_correct',
                    'red_balls_wrong', 'blue_balls_wrong', 'balls_on_conveyor',
                    'balls_in_red_basket', 'balls_in_blue_basket', 'success', 'failed', 'failure_reason']
    other_metrics = {k: v for k, v in metrics.items() if k not in excluded_keys}
    if other_metrics:
        metric_parts.append("\n**Additional Metrics**:")
        for key, value in other_metrics.items():
            if isinstance(value, (int, float)):
                metric_parts.append(f"- {key}: {value:.3f}" if isinstance(value, float) else f"- {key}: {value}")
            else:
                metric_parts.append(f"- {key}: {value}")
    return metric_parts
