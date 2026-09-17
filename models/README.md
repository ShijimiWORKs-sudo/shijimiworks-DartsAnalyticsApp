# models/

Pose estimation (Phase 5) uses MediaPipe's Tasks API (`PoseLandmarker`),
which needs a `.task` model file on disk — it is not bundled in the
`mediapipe` pip package for the installed version (0.10.32; only the new
Tasks API is exposed, not the older `mediapipe.solutions` API that used to
ship a model inline).

This is a **one-time local setup step**, not a runtime network dependency:
download the model once, then all pose analysis runs fully offline
(consistent with docs §25 原則ローカル処理).

## Setup

```bash
curl -L -o models/pose_landmarker_lite.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task
```

`pose_landmarker_lite.task` (~5.8MB) is the lite/fastest variant — good
enough for the joint-angle features Phase 5 computes. `pose_landmarker_full`
or `pose_landmarker_heavy` (same host, different path segment) trade speed
for accuracy if that's ever needed later.

The `.task` file itself is **not committed to git** (binary model weights;
see `.gitignore`) — every clone needs to run the command above once.
`dartsanalytics.pose.landmarker.PoseModelNotFoundError` is raised with this
same instruction if the file is missing when pose analysis runs.
