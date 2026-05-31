# Device Profiles

sjagent uses the same Gitee codebase on every device. Smaller devices, such as
an Orange Pi desktop robot, should not fork or delete features. They should keep
pulling the same code and use environment variables to decide what runs locally.

## Common Profiles

Full server:

```env
SJAGENT_DEVICE_PROFILE=full
SJAGENT_LITE_MODE=0
SJAGENT_ENABLE_BAG_UPLOAD=1
BAG_UPLOAD_WORKERS=3
```

Orange Pi desktop robot:

```env
SJAGENT_DEVICE_PROFILE=orangepi_desktop
SJAGENT_LITE_MODE=1
SJAGENT_ENABLE_BAG_UPLOAD=0
BAG_UPLOAD_WORKERS=1
```

`orangepi_desktop` still pulls bag template code from Gitee, including future
templates such as wide bag designs. With `SJAGENT_ENABLE_BAG_UPLOAD=0`, that code
is not imported as a workflow and local uploads will not run the renderer.

## Feature Switches

- `SJAGENT_ENABLE_BAG_UPLOAD`: enables the bag upload workflow and renderer.
- `BAG_UPLOAD_WORKERS`: caps concurrent bag rendering workers.

Explicit `SJAGENT_ENABLE_*` values override lite profile defaults.
