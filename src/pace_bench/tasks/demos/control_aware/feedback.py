from typing import Dict, Any, List

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    metric_parts = []
    if 'distance_traveled' in metrics:
        metric_parts.append(f"**Distance traveled**: {metrics['distance_traveled']:.2f}m")
        metric_parts.append(f"**Current position**: x={metrics.get('current_x', 0):.2f}m")
        if 'target_x' in metrics:
            metric_parts.append(f"**Target position**: x={metrics['target_x']:.2f}m")
        if 'progress' in metrics:
            metric_parts.append(f"**Progress**: {metrics['progress']:.1f}%")
        if 'max_distance' in metrics:
            metric_parts.append(f"**Maximum distance reached**: {metrics['max_distance']:.2f}m")
        if 'current_zone' in metrics:
            metric_parts.append(f"\n**Speed Zone Information**:")
            metric_parts.append(f"- Current zone: {metrics['current_zone']}")
            if 'speed_limit' in metrics:
                metric_parts.append(f"- Speed limit: {metrics['speed_limit']:.2f} m/s")
            if 'velocity_x' in metrics:
                metric_parts.append(f"- Current speed: {metrics['velocity_x']:.2f} m/s")
            if 'speed_violated' in metrics and metrics['speed_violated']:
                metric_parts.append(f"- ⚠️ **SPEED LIMIT VIOLATED**")
            if 'speed_violation_count' in metrics:
                metric_parts.append(f"- Total speed violations: {metrics['speed_violation_count']}")
    return metric_parts
