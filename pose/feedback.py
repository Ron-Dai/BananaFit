def get_feedback(exercise_name, angles):
    """Return list of coaching cues for the given exercise and joint angles."""
    if not angles:
        return ['No pose detected']

    messages = []

    if exercise_name == 'squat':
        avg_knee = (angles.get('left_knee', 180) + angles.get('right_knee', 180)) / 2
        avg_hip = (angles.get('left_hip', 180) + angles.get('right_hip', 180)) / 2
        if avg_knee > 160:
            messages.append('Bend your knees — go lower')
        elif avg_knee < 60:
            messages.append('Too deep — watch your knees')
        if avg_hip > 130:
            messages.append('Hinge at the hips and keep chest up')

    elif exercise_name == 'bicep_curl':
        for side, key in [('Left', 'left_elbow'), ('Right', 'right_elbow')]:
            angle = angles.get(key, 180)
            if angle > 150:
                messages.append(f'{side}: Keep tension — don\'t fully lock out')
            elif angle < 30:
                messages.append(f'{side}: Fully extend at the bottom')

    elif exercise_name == 'pushup':
        avg_elbow = (angles.get('left_elbow', 180) + angles.get('right_elbow', 180)) / 2
        if avg_elbow > 160:
            messages.append('Lower your chest to the ground')
        elif avg_elbow < 70:
            messages.append('Good depth — now push back up!')

    if not messages:
        messages.append('Good form — keep it up!')

    return messages
