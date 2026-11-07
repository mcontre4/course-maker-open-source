import json
from dataclasses import asdict, replace

from app.courses.application.generate_storyboard import artifact_hash


def legacy_speech(lesson, artifacts):
    """Store a complete, internally consistent pre-fix speech cache."""
    alignment = lesson.alignment
    aligned_scenes = []
    for scene, aligned in zip(lesson.storyboard.scenes, alignment.scenes, strict=True):
        legacy_hash = artifact_hash(
            {
                "scene_id": scene.scene_id,
                "text": scene.narration_text,
                "cues": [(c.id, c.anchor_text) for c in scene.cues],
                "settings": asdict(alignment.settings),
                "version": "speech-v1",
            }
        )
        older = replace(aligned, input_hash=legacy_hash)
        aligned_scenes.append(older)
        for key in tuple(artifacts.scenes):
            if aligned.input_hash in key:
                del artifacts.scenes[key]
                artifacts.scenes[key.replace(aligned.input_hash, legacy_hash)] = older
    alignment = replace(alignment, scenes=tuple(aligned_scenes))
    artifacts.objects[alignment.alignment_key] = json.dumps(asdict(alignment)).encode()
    return replace(lesson, alignment=alignment)
